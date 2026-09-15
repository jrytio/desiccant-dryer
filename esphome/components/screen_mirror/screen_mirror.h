#pragma once

#include <string>
#include <vector>

#include "esphome/core/component.h"
#include "esphome/components/ili9xxx/ili9xxx_display.h"
#include "esphome/components/web_server_base/web_server_base.h"

namespace esphome {
namespace screen_mirror {

// Answers GET <path> with the display's frame buffer as an 8-bit indexed PNG
// (stored deflate blocks, so no compressor and no frame copy). Rows are
// streamed with chunked sends; the only RAM is one scanline allocated at
// setup, and the palette and CRC table live in flash.
class ScreenMirror : public Component, public AsyncWebHandler {
 public:
  explicit ScreenMirror(web_server_base::WebServerBase *base) : base_(base) {}

  void set_display(ili9xxx::ILI9XXXDisplay *display) { this->display_ = display; }
  void set_path(const std::string &path) { this->path_ = path; }

  void setup() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::LATE; }

  bool canHandle(AsyncWebServerRequest *request) const override;
  void handleRequest(AsyncWebServerRequest *request) override;

 protected:
  web_server_base::WebServerBase *base_;
  ili9xxx::ILI9XXXDisplay *display_{nullptr};
  std::string path_;
  std::vector<uint8_t> row_;
  bool warned_{false};
};

}  // namespace screen_mirror
}  // namespace esphome
