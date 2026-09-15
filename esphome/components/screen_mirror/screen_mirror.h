#pragma once

#include <string>

#include "esphome/core/component.h"
#include "esphome/components/ili9xxx/ili9xxx_display.h"
#include "esphome/components/web_server_base/web_server_base.h"

namespace esphome {
namespace screen_mirror {

// Answers GET <path> with the display's frame buffer as an 8-bit BMP. The
// rows are streamed straight out of the driver's buffer with chunked sends,
// so nothing is allocated; the only copies are the 54-byte header on the
// stack and the 1 KB palette in flash.
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
  bool warned_{false};
};

}  // namespace screen_mirror
}  // namespace esphome
