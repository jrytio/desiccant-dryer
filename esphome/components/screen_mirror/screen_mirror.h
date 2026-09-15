#pragma once

#include <atomic>
#include <string>
#include <vector>

#include "esphome/core/component.h"
#include "esphome/components/display/display.h"
#include "esphome/components/ili9xxx/ili9xxx_display.h"
#include "esphome/components/web_server_base/web_server_base.h"

namespace esphome {
namespace screen_mirror {

// Answers GET <path> with the display's frame buffer as an 8-bit indexed PNG
// (stored deflate blocks, so no compressor and no frame copy). Rows are
// streamed with chunked sends; the only RAM is one scanline allocated at
// setup, and the palette and CRC table live in flash.
//
// A redraw clears the buffer and repaints it over a few hundred milliseconds,
// so a fetch that overlapped one would stream a half-drawn frame. setup()
// wraps the display's writer so the two take turns: a fetch waits for a
// redraw in progress to finish, and a redraw that falls due during a fetch
// is skipped and run from loop() once no fetch is streaming.
class ScreenMirror : public Component, public AsyncWebHandler {
 public:
  explicit ScreenMirror(web_server_base::WebServerBase *base) : base_(base) {}

  void set_display(ili9xxx::ILI9XXXDisplay *display) { this->display_ = display; }
  void set_path(const std::string &path) { this->path_ = path; }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::LATE; }

  bool canHandle(AsyncWebServerRequest *request) const override;
  void handleRequest(AsyncWebServerRequest *request) override;

 protected:
  void draw_(display::Display &it);

  web_server_base::WebServerBase *base_;
  ili9xxx::ILI9XXXDisplay *display_{nullptr};
  std::string path_;
  std::vector<uint8_t> row_;
  display::display_writer_t writer_{};       // the display's own writer, run by draw_()
  std::atomic<bool> drawing_{false};         // draw_() is running the writer (main loop)
  std::atomic<int> fetches_{0};              // requests streaming the buffer (web server task)
  std::atomic<bool> redraw_pending_{false};  // a redraw was skipped during a fetch
  bool warned_{false};
};

}  // namespace screen_mirror
}  // namespace esphome
