#include "screen_mirror.h"

#include <esp_http_server.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include <algorithm>
#include <cinttypes>
#include <cstring>

#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace esphome {
namespace screen_mirror {

static const char *const TAG = "screen_mirror";

// A redraw takes a few hundred milliseconds; one still running after this
// long means something is wrong, and the fetch gives up rather than hang.
static const uint32_t DRAW_WAIT_MS = 2000;

namespace {

// The driver keeps its frame buffer, colour mode and writer protected. A
// class derived from it may form pointers to those members and apply them to
// any driver instance. Nothing is instantiated and no header is patched.
struct Peek : public ili9xxx::ILI9XXXDisplay {
  static uint8_t *buffer(ili9xxx::ILI9XXXDisplay *d) { return d->*(&Peek::buffer_); }
  static ili9xxx::ILI9XXXColorMode mode(ili9xxx::ILI9XXXDisplay *d) { return d->*(&Peek::buffer_color_mode_); }
  static display::display_writer_t &writer(ili9xxx::ILI9XXXDisplay *d) { return d->*(&Peek::writer_); }
};

// Counts a request as streaming for as long as it is in scope, whichever way
// handleRequest() returns.
struct FetchGuard {
  explicit FetchGuard(std::atomic<int> &count) : count_(count) { count_.fetch_add(1); }
  ~FetchGuard() { count_.fetch_sub(1); }
  std::atomic<int> &count_;
};

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
  // Take over the display's writer so redraws and fetches take turns (draw_()).
  display::display_writer_t &writer = Peek::writer(this->display_);
  this->writer_ = std::move(writer);
  writer = display::display_writer_t([this](display::Display &it) { this->draw_(it); });
  this->base_->init();
  this->base_->add_handler(this);
}

// Runs on the main loop inside the display's update(). drawing_ is raised
// before fetches_ is read, and handleRequest() raises fetches_ before reading
// drawing_, so of a redraw and a fetch that start together at least one sees
// the other and the buffer is never streamed mid-redraw.
void ScreenMirror::draw_(display::Display &it) {
  this->drawing_.store(true);
  if (this->fetches_.load() > 0) {
    this->drawing_.store(false);
    this->redraw_pending_.store(true);
    return;
  }
  this->writer_(it);
  this->drawing_.store(false);
}

void ScreenMirror::loop() {
  // Run a redraw skipped during a fetch as soon as nothing is streaming.
  if (this->redraw_pending_.load() && this->fetches_.load() == 0) {
    this->redraw_pending_.store(false);
    this->display_->update();
  }
}

void ScreenMirror::dump_config() {
  ESP_LOGCONFIG(TAG, "Screen mirror:\n  Path: %s\n  Frame: %dx%d, 8-bit indexed PNG", this->path_.c_str(),
                this->display_->get_native_width(), this->display_->get_native_height());
}

bool ScreenMirror::canHandle(AsyncWebServerRequest *request) const {
  // url_to() writes the decoded URL without its ?query, so a cache-busting
  // suffix still matches. It replaces url(), which 2026.9.0 removed.
  char url_buf[AsyncWebServerRequest::URL_BUF_SIZE];
  return request->method() == HTTP_GET && request->url_to(url_buf) == this->path_;
}

void ScreenMirror::handleRequest(AsyncWebServerRequest *request) {
  httpd_req_t *req = *request;
  uint8_t *buf = Peek::buffer(this->display_);
  const bool usable = buf != nullptr && Peek::mode(this->display_) == ili9xxx::BITS_8 &&
                      this->display_->get_rotation() == display::DISPLAY_ROTATION_0_DEGREES;
  if (!usable) {
    if (buf == nullptr) {
      ESP_LOGD(TAG, "Frame buffer not allocated yet");
    } else if (!this->warned_) {
      ESP_LOGW(TAG, "Frame buffer not usable: needs color_palette 8BIT and rotation 0");
      this->warned_ = true;
    }
    httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "screen_mirror: needs an 8-bit, unrotated frame buffer");
    return;
  }

  // Let a redraw in progress finish. From here until return, draw_() skips
  // redraws and loop() runs them once the fetch is done.
  FetchGuard guard(this->fetches_);
  const uint32_t wait_start = millis();
  while (this->drawing_.load()) {
    if (millis() - wait_start > DRAW_WAIT_MS) {
      ESP_LOGW(TAG, "Display still drawing after %" PRIu32 " ms; request dropped", DRAW_WAIT_MS);
      httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "screen_mirror: display still drawing");
      return;
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }

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

  httpd_resp_set_type(req, "image/png");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  if (!send_chunk(req, head, sizeof(head)) || !send_chunk(req, PLTE.bytes, PLTE_LEN) ||
      !send_chunk(req, idat_head, sizeof(idat_head)))
    return;

  uint32_t crc = crc32_update(0xFFFFFFFFu, idat_head + 4, 4 + 2);  // "IDAT" + zlib header
  uint32_t adler_a = 1, adler_b = 0;
  uint32_t y = 0;
  uint8_t *row = this->row_.data();  // row[0] is the filter byte, always 0
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
      memcpy(row + 1, buf + static_cast<size_t>(y) * w, w);
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
