#pragma once
// Host-only: an in-memory Display that draw_ui() can render into, snapping
// every pixel to the ST7789's RGB 3-3-2 palette, and a PPM writer. Used by
// display-scenarios.yaml when SHOT=<path> is set, so screenshots need no
// window capture and show exactly what the real panel will.
#ifdef USE_HOST
#include <cstdint>
#include <cstdio>
#include <vector>

#include "esphome/components/display/display.h"
#include "esphome/components/display/display_color_utils.h"

namespace preview {

class CaptureDisplay : public esphome::display::Display {
 public:
  CaptureDisplay(int w, int h) : w_(w), h_(h), buf_(static_cast<size_t>(w) * h * 3, 0) {}

  esphome::display::DisplayType get_display_type() override { return esphome::display::DISPLAY_TYPE_COLOR; }
  void update() override {}

  void draw_pixel_at(int x, int y, esphome::Color color) override {
    if (x < 0 || y < 0 || x >= w_ || y >= h_) return;
    using esphome::display::ColorUtil;
    const esphome::Color q = ColorUtil::rgb332_to_color(ColorUtil::color_to_332(color));
    uint8_t *p = &buf_[(static_cast<size_t>(y) * w_ + x) * 3];
    p[0] = q.r;
    p[1] = q.g;
    p[2] = q.b;
  }

  bool save_ppm(const char *path) const {
    FILE *f = fopen(path, "wb");
    if (f == nullptr) return false;
    fprintf(f, "P6\n%d %d\n255\n", w_, h_);
    fwrite(buf_.data(), 1, buf_.size(), f);
    fclose(f);
    return true;
  }

 protected:
  int get_width_internal() override { return w_; }
  int get_height_internal() override { return h_; }

  int w_, h_;
  std::vector<uint8_t> buf_;
};

}  // namespace preview
#endif
