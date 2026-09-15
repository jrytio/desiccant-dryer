#include "screen_mirror.h"

#include <esp_http_server.h>

#include "esphome/core/log.h"

namespace esphome {
namespace screen_mirror {

static const char *const TAG = "screen_mirror";

namespace {

// The driver keeps its frame buffer and colour mode protected. A class
// derived from it may form pointers to those members and apply them to any
// driver instance. Nothing is instantiated and no header is patched.
struct Peek : public ili9xxx::ILI9XXXDisplay {
  static uint8_t *buffer(ili9xxx::ILI9XXXDisplay *d) { return d->*(&Peek::buffer_); }
  static ili9xxx::ILI9XXXColorMode mode(ili9xxx::ILI9XXXDisplay *d) { return d->*(&Peek::buffer_color_mode_); }
};

// BMP palette for RGB332 indices: entry i is B,G,R,0 with each channel
// stretched to 0..255. Built at compile time, lives in flash.
struct Palette {
  uint8_t bgra[256][4];
  constexpr Palette() : bgra() {
    for (int i = 0; i < 256; i++) {
      bgra[i][0] = static_cast<uint8_t>((i & 3) * 255 / 3);
      bgra[i][1] = static_cast<uint8_t>(((i >> 2) & 7) * 255 / 7);
      bgra[i][2] = static_cast<uint8_t>(((i >> 5) & 7) * 255 / 7);
      bgra[i][3] = 0;
    }
  }
};
constexpr Palette PALETTE{};

void put_u16(uint8_t *p, uint16_t v) {
  p[0] = static_cast<uint8_t>(v);
  p[1] = static_cast<uint8_t>(v >> 8);
}
void put_u32(uint8_t *p, uint32_t v) {
  p[0] = static_cast<uint8_t>(v);
  p[1] = static_cast<uint8_t>(v >> 8);
  p[2] = static_cast<uint8_t>(v >> 16);
  p[3] = static_cast<uint8_t>(v >> 24);
}

}  // namespace

void ScreenMirror::setup() {
  this->base_->init();
  this->base_->add_handler(this);
}

void ScreenMirror::dump_config() {
  ESP_LOGCONFIG(TAG, "Screen mirror:\n  Path: %s\n  Frame: %dx%d, 8-bit BMP", this->path_.c_str(),
                this->display_->get_native_width(), this->display_->get_native_height());
}

bool ScreenMirror::canHandle(AsyncWebServerRequest *request) const {
  if (request->method() != HTTP_GET)
    return false;
  std::string url = request->url();
  const auto q = url.find('?');
  if (q != std::string::npos)
    url.erase(q);
  return url == this->path_;
}

void ScreenMirror::handleRequest(AsyncWebServerRequest *request) {
  httpd_req_t *req = *request;
  uint8_t *buf = Peek::buffer(this->display_);
  const bool usable = buf != nullptr && Peek::mode(this->display_) == ili9xxx::BITS_8 &&
                      this->display_->get_rotation() == display::DISPLAY_ROTATION_0_DEGREES;
  if (!usable) {
    if (!this->warned_) {
      ESP_LOGW(TAG, "Frame buffer not usable: needs color_palette 8BIT, rotation 0 and an allocated buffer");
      this->warned_ = true;
    }
    httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "screen_mirror: needs an 8-bit, unrotated frame buffer");
    return;
  }

  const int w = this->display_->get_native_width();
  const int h = this->display_->get_native_height();
  const uint32_t stride = (static_cast<uint32_t>(w) + 3u) & ~3u;
  const uint32_t pixels = stride * static_cast<uint32_t>(h);
  const uint32_t offset = 14 + 40 + sizeof(PALETTE.bgra);
  const uint32_t file_size = offset + pixels;

  uint8_t header[54] = {};
  header[0] = 'B';
  header[1] = 'M';
  put_u32(header + 2, file_size);
  put_u32(header + 10, offset);
  put_u32(header + 14, 40);
  put_u32(header + 18, static_cast<uint32_t>(w));
  put_u32(header + 22, static_cast<uint32_t>(h));  // positive height: rows bottom-up
  put_u16(header + 26, 1);
  put_u16(header + 28, 8);
  put_u32(header + 34, pixels);
  put_u32(header + 38, 2835);
  put_u32(header + 42, 2835);
  put_u32(header + 46, 256);
  put_u32(header + 50, 256);

  httpd_resp_set_type(req, "image/bmp");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  if (httpd_resp_send_chunk(req, reinterpret_cast<const char *>(header), sizeof(header)) != ESP_OK)
    return;
  if (httpd_resp_send_chunk(req, reinterpret_cast<const char *>(PALETTE.bgra), sizeof(PALETTE.bgra)) != ESP_OK)
    return;
  static const uint8_t PAD[3] = {0, 0, 0};
  for (int y = h - 1; y >= 0; y--) {
    const char *row = reinterpret_cast<const char *>(buf + static_cast<size_t>(y) * static_cast<size_t>(w));
    if (httpd_resp_send_chunk(req, row, w) != ESP_OK)
      return;
    if (stride > static_cast<uint32_t>(w) &&
        httpd_resp_send_chunk(req, reinterpret_cast<const char *>(PAD), stride - static_cast<uint32_t>(w)) != ESP_OK)
      return;
  }
  httpd_resp_send_chunk(req, nullptr, 0);
}

}  // namespace screen_mirror
}  // namespace esphome
