#pragma once

#include <algorithm>
#include <string>
#include <vector>

#include "esphome/core/component.h"
#include "esphome/core/color.h"
#include "esphome/components/display/display.h"
#include "esphome/components/display/display_color_utils.h"
#include "esphome/components/web_server_base/web_server_base.h"

namespace esphome {
namespace screen_mirror {

// An in-memory Display that holds only a horizontal band of the frame and
// stores each pixel as an RGB332 index, which is the panel's own 8-bit
// format. draw_ui() is called once per band; pixels outside the current
// band are discarded. Same idea as packages/preview_capture.h on the host
// build, but a band at a time so the RAM cost is a few kilobytes.
class BandDisplay : public display::Display {
 public:
  BandDisplay(int w, int h, uint8_t *band, int band_rows) : w_(w), h_(h), band_rows_(band_rows), band_(band) {}

  display::DisplayType get_display_type() override { return display::DISPLAY_TYPE_COLOR; }
  void update() override {}

  // Select the band starting at row `start`; the caller clears it first.
  void set_band_start(int start) { this->start_ = start; }

  // Display::fill() is not overridden by default, so the base class would
  // loop all get_width()xget_height() pixels through the virtual
  // draw_pixel_at() -- for the full 240x240 panel that is ~57,600 calls to
  // fill a 240x24 band, with ~87% of them clipped and discarded. Fill just
  // the band directly instead.
  void fill(Color color) override {
    std::fill(this->band_, this->band_ + static_cast<size_t>(this->band_rows_) * this->w_,
              display::ColorUtil::color_to_332(color));
  }

  void draw_pixel_at(int x, int y, Color color) override {
    if (x < 0 || x >= this->w_ || y < this->start_ || y >= this->start_ + this->band_rows_)
      return;
    this->band_[static_cast<size_t>(y - this->start_) * this->w_ + x] = display::ColorUtil::color_to_332(color);
  }

 protected:
  int get_width_internal() override { return this->w_; }
  int get_height_internal() override { return this->h_; }

  int w_, h_, band_rows_, start_{0};
  uint8_t *band_;
};

// Answers GET <path> with the current screen as an 8-bit indexed PNG
// (stored deflate blocks, so no compressor and no full frame in RAM).
//
// The frame is re-rendered on demand into BandDisplay rather than read out
// of the display driver: with a partial driver buffer there is no full
// frame to read, and reaching into driver internals tied this component to
// one driver's private members. draw_ui() is a pure function of
// dryer_ui::last_state() and last_assets(), which the ui_draw script
// refreshes on every panel redraw, so the served image is the state as of
// the last redraw.
class ScreenMirror : public Component, public AsyncWebHandler {
 public:
  explicit ScreenMirror(web_server_base::WebServerBase *base) : base_(base) {}

  void set_display(display::Display *display) { this->display_ = display; }
  void set_path(const std::string &path) { this->path_ = path; }

  void setup() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::LATE; }

  bool canHandle(AsyncWebServerRequest *request) const override;
  void handleRequest(AsyncWebServerRequest *request) override;

 protected:
  web_server_base::WebServerBase *base_;
  display::Display *display_{nullptr};
  std::string path_;
  std::vector<uint8_t> row_;   // one PNG scanline: filter byte + pixels
  std::vector<uint8_t> band_;  // BAND_ROWS scanlines of RGB332 indices
};

}  // namespace screen_mirror
}  // namespace esphome
