#include "screen_mirror.h"

#include <esp_http_server.h>

#include <algorithm>
#include <cstring>

#include "esphome/core/log.h"
#include "esphome/components/dryer_ui/display_ui.h"

namespace esphome {
namespace screen_mirror {

static const char *const TAG = "screen_mirror";

// Rows rendered per pass. 24 rows x 240 px = 5,760 bytes, and 240 divides
// evenly by 24 so no pass is short.
static const int BAND_ROWS = 24;

namespace {

// CRC-32 as used by PNG and zlib (reflected, polynomial 0xEDB88320). The
// table is built at compile time and lives in flash.
struct Crc32Table {
  uint32_t t[256];
  constexpr Crc32Table() : t() {
    for (uint32_t i = 0; i < 256; i++) {
      uint32_t c = i;
      for (int k = 0; k < 8; k++)
        c = (c & 1u) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
      t[i] = c;
    }
  }
};
constexpr Crc32Table CRC_TABLE{};

// Running CRC-32: start from 0xFFFFFFFF, feed bytes, finish with ^ 0xFFFFFFFF.
constexpr uint32_t crc32_update(uint32_t crc, const uint8_t *p, size_t n) {
  for (size_t i = 0; i < n; i++)
    crc = CRC_TABLE.t[(crc ^ p[i]) & 0xFFu] ^ (crc >> 8);
  return crc;
}

constexpr void put_be32(uint8_t *p, uint32_t v) {
  p[0] = static_cast<uint8_t>(v >> 24);
  p[1] = static_cast<uint8_t>(v >> 16);
  p[2] = static_cast<uint8_t>(v >> 8);
  p[3] = static_cast<uint8_t>(v);
}

// The PLTE chunk for RGB332 indices, complete with length, type and CRC:
// entry i is R,G,B with each channel stretched to 0..255. Built at compile
// time, lives in flash.
constexpr size_t PLTE_LEN = 4 + 4 + 768 + 4;
struct PlteChunk {
  uint8_t bytes[PLTE_LEN];
  constexpr PlteChunk() : bytes() {
    put_be32(bytes, 768);
    bytes[4] = 'P';
    bytes[5] = 'L';
    bytes[6] = 'T';
    bytes[7] = 'E';
    for (int i = 0; i < 256; i++) {
      bytes[8 + i * 3 + 0] = static_cast<uint8_t>(((i >> 5) & 7) * 255 / 7);
      bytes[8 + i * 3 + 1] = static_cast<uint8_t>(((i >> 2) & 7) * 255 / 7);
      bytes[8 + i * 3 + 2] = static_cast<uint8_t>((i & 3) * 255 / 3);
    }
    put_be32(bytes + 8 + 768, crc32_update(0xFFFFFFFFu, bytes + 4, 4 + 768) ^ 0xFFFFFFFFu);
  }
};
constexpr PlteChunk PLTE{};

const uint8_t PNG_SIGNATURE[8] = {0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A};
const uint8_t IEND_CHUNK[12] = {0, 0, 0, 0, 'I', 'E', 'N', 'D', 0xAE, 0x42, 0x60, 0x82};

bool send_chunk(httpd_req_t *req, const uint8_t *data, size_t len) {
  return httpd_resp_send_chunk(req, reinterpret_cast<const char *>(data), len) == ESP_OK;
}

}  // namespace

void ScreenMirror::setup() {
  // One PNG scanline: the filter byte (always 0, "None") followed by the row.
  this->row_.assign(static_cast<size_t>(this->display_->get_native_width()) + 1, 0);
  this->band_.assign(static_cast<size_t>(this->display_->get_native_width()) * BAND_ROWS, 0);
  this->base_->init();
  this->base_->add_handler(this);
}

void ScreenMirror::dump_config() {
  ESP_LOGCONFIG(TAG, "Screen mirror:\n  Path: %s\n  Frame: %dx%d, 8-bit indexed PNG\n  Band rows: %d",
                this->path_.c_str(), this->display_->get_native_width(), this->display_->get_native_height(),
                BAND_ROWS);
}

bool ScreenMirror::canHandle(AsyncWebServerRequest *request) const {
  // url_to() writes the decoded URL without its ?query, so a cache-busting
  // suffix still matches. It replaces url(), which 2026.9.0 removed.
  char url_buf[AsyncWebServerRequest::URL_BUF_SIZE];
  return request->method() == HTTP_GET && request->url_to(url_buf) == this->path_;
}

void ScreenMirror::handleRequest(AsyncWebServerRequest *request) {
  httpd_req_t *req = *request;

  const uint32_t w = static_cast<uint32_t>(this->display_->get_native_width());
  const uint32_t h = static_cast<uint32_t>(this->display_->get_native_height());
  const uint32_t row_len = w + 1;  // filter byte + pixels
  // Stored deflate blocks hold at most 65535 bytes; keep whole rows per block.
  uint32_t rows_per_block = 65535u / row_len;
  if (rows_per_block > h)
    rows_per_block = h;
  const uint32_t blocks = (h + rows_per_block - 1) / rows_per_block;
  const uint32_t idat_len = 2 + blocks * 5 + h * row_len + 4;  // zlib header, block headers, scanlines, Adler-32

  // Signature and IHDR chunk.
  uint8_t head[8 + 4 + 4 + 13 + 4];
  memcpy(head, PNG_SIGNATURE, 8);
  put_be32(head + 8, 13);
  memcpy(head + 12, "IHDR", 4);
  put_be32(head + 16, w);
  put_be32(head + 20, h);
  head[24] = 8;  // bit depth
  head[25] = 3;  // colour type: indexed
  head[26] = 0;  // compression method
  head[27] = 0;  // filter method
  head[28] = 0;  // no interlace
  put_be32(head + 29, crc32_update(0xFFFFFFFFu, head + 12, 4 + 13) ^ 0xFFFFFFFFu);

  // IDAT chunk header and the zlib stream header.
  uint8_t idat_head[4 + 4 + 2];
  put_be32(idat_head, idat_len);
  memcpy(idat_head + 4, "IDAT", 4);
  idat_head[8] = 0x78;  // zlib: deflate, 32 KB window
  idat_head[9] = 0x01;  // no preset dictionary, fastest level

  // Snapshot by value: ui_draw mutates the UiState singleton in place on the
  // main loop while this handler (on the httpd task) walks it across ~10
  // band renders. A by-reference binding would risk a use-after-free if any
  // of its std::string members reallocate mid-render, and would also let a
  // fetch straddle a state change and render a torn frame. Assets are left
  // by reference: they hold only pointers, which are stable once set.
  const dryer_ui::UiState state = dryer_ui::last_state();
  const dryer_ui::UiAssets &assets = dryer_ui::last_assets();

  // Guard against the boot window before the panel's first redraw: last_assets()
  // is a static UiAssets{} until then, so every pointer -- bg included, and it's
  // the first one draw_ui() dereferences -- is null. This must run before any
  // response bytes (including the PNG signature/IHDR) go out, since
  // httpd_resp_send_err() can't recall those once chunks have been sent.
  if (assets.bg == nullptr) {
    ESP_LOGD(TAG, "Refusing /%s: screen has not been drawn yet", this->path_.c_str());
    httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "screen has not been drawn yet");
    return;
  }

  httpd_resp_set_type(req, "image/png");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  if (!send_chunk(req, head, sizeof(head)) || !send_chunk(req, PLTE.bytes, PLTE_LEN) ||
      !send_chunk(req, idat_head, sizeof(idat_head)))
    return;

  // Re-render the UI into our own band buffer, a band at a time, from the
  // state the panel captured on its last redraw.
  BandDisplay band(static_cast<int>(w), static_cast<int>(h), this->band_.data(), BAND_ROWS);

  uint32_t crc = crc32_update(0xFFFFFFFFu, idat_head + 4, 4 + 2);  // "IDAT" + zlib header
  uint32_t adler_a = 1, adler_b = 0;
  uint32_t y = 0;
  uint8_t *row = this->row_.data();  // row[0] is the filter byte, always 0
  int rendered_to = -1;              // last row already rendered into band_
  for (uint32_t blk = 0; blk < blocks; blk++) {
    const uint32_t rows = std::min(rows_per_block, h - y);
    const uint16_t len = static_cast<uint16_t>(rows * row_len);
    const uint16_t nlen = static_cast<uint16_t>(~len);
    const uint8_t block_head[5] = {static_cast<uint8_t>(blk + 1 == blocks ? 1 : 0),  // BFINAL; BTYPE 00 = stored
                                   static_cast<uint8_t>(len & 0xFFu), static_cast<uint8_t>(len >> 8),
                                   static_cast<uint8_t>(nlen & 0xFFu), static_cast<uint8_t>(nlen >> 8)};
    crc = crc32_update(crc, block_head, 5);
    if (!send_chunk(req, block_head, 5))
      return;
    for (uint32_t r = 0; r < rows; r++, y++) {
      if (static_cast<int>(y) > rendered_to) {
        const int start = static_cast<int>(y) / BAND_ROWS * BAND_ROWS;
        band.set_band_start(start);
        // No explicit clear here: draw_ui() always opens with it.fill(BLACK),
        // which now goes through BandDisplay::fill() and clears exactly this
        // band directly. A second clear here would just redo that work on
        // every one of the ~10 bands per fetch -- the redundant memset this
        // component's earlier revision relied on before BandDisplay had its
        // own fill() override.
        dryer_ui::draw_ui(band, state, assets);
        rendered_to = start + BAND_ROWS - 1;
      }
      const size_t off = static_cast<size_t>(static_cast<int>(y) % BAND_ROWS) * w;
      memcpy(row + 1, this->band_.data() + off, w);
      crc = crc32_update(crc, row, row_len);
      for (uint32_t i = 0; i < row_len; i++) {
        adler_a += row[i];
        adler_b += adler_a;
      }
      adler_a %= 65521u;
      adler_b %= 65521u;
      if (!send_chunk(req, row, row_len))
        return;
    }
  }

  // Adler-32 closes the zlib stream, the CRC closes the IDAT chunk, IEND closes the file.
  uint8_t tail[4 + 4 + 12];
  put_be32(tail, (adler_b << 16) | adler_a);
  crc = crc32_update(crc, tail, 4);
  put_be32(tail + 4, crc ^ 0xFFFFFFFFu);
  memcpy(tail + 8, IEND_CHUNK, 12);
  if (!send_chunk(req, tail, sizeof(tail)))
    return;
  httpd_resp_send_chunk(req, nullptr, 0);
}

}  // namespace screen_mirror
}  // namespace esphome
