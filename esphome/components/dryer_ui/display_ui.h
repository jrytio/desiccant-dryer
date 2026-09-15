#pragma once
// Dryer display: a pure function of UiState. No id() calls in here, so the
// same code draws the ST7789 (packages/display-st7789.yaml), the SDL window
// of the host build (packages/display-sdl.yaml) and the scenario captures
// (packages/display-scenarios.yaml). The ui_draw script in
// packages/display-draw.yaml gathers the state. Geometry and rules follow
// docs/superpowers/specs/2026-09-14-display-ui-design.md sections 2, 4, 5,
// with the cylinder colours of 2026-09-14-cylinder-state-colours-design.md
// and the palette of 2026-09-15-semantic-palette-design.md.
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>

#include "esphome/components/display/display.h"

namespace dryer_ui {

using esphome::Color;
using esphome::display::BaseFont;
using esphome::display::BaseImage;
using esphome::display::Display;
using esphome::display::TextAlign;

struct UiState {
  int active = 0;         // 0 none, 1 A, 2 B
  int standby_state = 0;  // 0 WET, 1 HEATING, 2 COOLING, 3 READY
  int fault_code = 0;     // 0 none, 1 active overtemp, 2 standby overtemp, 3 not heating
  bool enabled = true, rh_override = false, fan = false;
  bool heater_a = false, heater_b = false, valve_a = false, valve_b = false;
  float t_a = NAN, t_b = NAN, t_case = NAN, rh = NAN;
  float arm_rh = 5, swap_rh = 10;
  float service_s = 0, standby_s = 0;
  std::string status, fault_msg, ip;
  uint32_t uptime_ms = 0;
};

// Aggregate-initialised by the ui_draw script; keep the member order in step.
struct UiAssets {
  BaseFont *f_temp, *f_val, *f_cap, *f_label, *f_phase, *f_status, *f_status_b;
  BaseImage *bg, *valve_open, *valve_closed, *flow_in, *flow_out, *lit_a, *lit_b, *fan;
};

// The most recently gathered state and asset table. The ui_draw script fills
// these before drawing; the scenario build renders the same frame from them
// into its capture buffer.
inline UiState &last_state() {
  static UiState s;
  return s;
}
inline UiAssets &last_assets() {
  static UiAssets a{};
  return a;
}

// Milliseconds since the first frame. On the ESP32 millis() counts from boot,
// on the host from machine boot, so the boot-IP rule uses this relative value
// and behaves the same in both places (first frame is ~2 s after boot).
inline uint32_t uptime_since_first_frame(uint32_t now) {
  static const uint32_t first = now;
  return now - first;
}

// RGB 3-3-2 grid colours (display UI spec section 5; cylinder colours spec
// section 1).
static const Color BLACK(0, 0, 0), WHITE(255, 255, 255);
// "Semantic" palette (2026-09-15-semantic-palette-design.md): GitHub's status
// hues. GREEN success = in use, YELLOW attention = wet and the gauge's
// RISING/HIGH, ORANGE severe = heating, CYAN info = cooling, PURPLE done =
// ready, RED danger = fault.
static const Color GREEN(73, 182, 85), YELLOW(219, 182, 0), ORANGE(219, 109, 85), CYAN(73, 182, 255);
static const Color PURPLE(146, 109, 255), RED(255, 73, 85);
static const Color AMBER = YELLOW;  // gauge attention zones and the OVR badge
static const Color SHELL(73, 73, 85), DIM(146, 146, 170), STRIP_TXT(182, 182, 170);
static const Color RED_STRIP(219, 73, 85);
// Gauge zones at rest: the same three hues at roughly half brightness, so the
// bar reads as a dimmed copy of the palette rather than a different one.
static const Color DRY_DIM(36, 73, 0), AMBER_DIM(109, 109, 0), RED_DIM(109, 36, 0);

static const float HIGH_FRACTION = 1.0f / 3.0f;  // top third of the arm..swap band reads HIGH
static const uint32_t BOOT_IP_MS = 60000;        // the strip shows the IP this long after boot
static const int CX_A = 60, CX_B = 180;          // cylinder centre columns (art sits at cx + 0.5)

// What one cylinder shows, derived from UiState by pack_roles().
struct PackView {
  int cx = 0;
  float t = NAN;
  const char *phase = "";
  Color phase_color = DIM;  // also the body colour when filled
  bool filled = false;      // body painted in phase_color; false when off or starting
  bool show_timer = false;
  float timer_s = 0;
};

inline std::string fmt_timer(float seconds) {
  int m = (int) (seconds / 60.0f);
  if (m < 0) m = 0;
  char buf[16];
  if (m >= 60)
    snprintf(buf, sizeof buf, "%dh %02dm", m / 60, m % 60);
  else
    snprintf(buf, sizeof buf, "%dm", m);
  return buf;
}

inline void rounded_rect(Display &it, int x, int y, int w, int h, int r, Color c) {
  it.filled_rectangle(x + r, y, w - 2 * r, h, c);
  it.filled_rectangle(x, y + r, w, h - 2 * r, c);
  it.filled_circle(x + r, y + r, r, c);
  it.filled_circle(x + w - 1 - r, y + r, r, c);
  it.filled_circle(x + r, y + h - 1 - r, r, c);
  it.filled_circle(x + w - 1 - r, y + h - 1 - r, r, c);
}

inline void pack_roles(const UiState &s, PackView &a, PackView &b) {
  static const char *const SB_NAMES[] = {"WET", "HEATING", "COOLING", "READY"};
  static const Color SB_COLORS[] = {YELLOW, ORANGE, CYAN, PURPLE};
  a = PackView{};
  b = PackView{};
  a.cx = CX_A;
  a.t = s.t_a;
  b.cx = CX_B;
  b.t = s.t_b;
  if (!s.enabled) {
    a.phase = b.phase = "OFF";
    return;
  }
  if (s.active != 1 && s.active != 2) return;  // starting: no roles yet
  PackView &act = s.active == 1 ? a : b;
  PackView &sb = s.active == 1 ? b : a;
  act.phase = "IN USE";
  act.phase_color = GREEN;
  act.filled = true;
  act.show_timer = true;
  act.timer_s = s.service_s;
  int st = s.standby_state;
  if (st < 0 || st > 3) st = 0;
  sb.phase = SB_NAMES[st];
  sb.phase_color = SB_COLORS[st];
  sb.filled = true;
  sb.show_timer = true;
  sb.timer_s = s.standby_s;
  PackView *faulted = s.fault_code == 1 ? &act : (s.fault_code == 2 || s.fault_code == 3) ? &sb : nullptr;
  if (faulted != nullptr) {
    faulted->phase = "FAULT";
    faulted->phase_color = RED;
  }
}

// The body in its state colour: one rectangle over the cylinder interior,
// drawn before the background, which keeps its grey top cap over row 40 and
// masks everything outside the bottom cap curve down to row 156.
inline void draw_fill(Display &it, const PackView &p) {
  if (p.filled) it.filled_rectangle(p.cx - 25, 40, 51, 116, p.phase_color);
}

// The black plate, temperature, phase word and timer.
inline void draw_pack_text(Display &it, const UiAssets &a, const PackView &p) {
  rounded_rect(it, p.cx - 23, 78, 47, 52, 4, BLACK);
  if (std::isnan(p.t))
    it.print(p.cx, 100, a.f_temp, DIM, TextAlign::BASELINE_CENTER, "--°");
  else
    it.printf(p.cx, 100, a.f_temp, WHITE, TextAlign::BASELINE_CENTER, "%.0f°", p.t);
  if (p.phase[0] != '\0') it.print(p.cx, 112, a.f_phase, p.phase_color, TextAlign::BASELINE_CENTER, p.phase);
  if (p.show_timer) it.print(p.cx, 126, a.f_val, WHITE, TextAlign::BASELINE_CENTER, fmt_timer(p.timer_s).c_str());
}

// Outlet humidity: value, zone word, three-zone bar with a marker.
inline void draw_gauge(Display &it, const UiAssets &a, const UiState &s) {
  const float arm = s.arm_rh, swap = s.swap_rh, end = swap * 1.25f;
  const char *zone = "";
  Color zc = DIM;
  int z = -1;  // 0 DRY, 1 RISING/HIGH, 2 OVER
  // OVER is tested first so a misconfigured arm above swap never labels a
  // reading the controller would swap on as DRY.
  if (!std::isnan(s.rh)) {
    if (s.rh >= swap) {
      zone = "OVER";
      zc = RED;
      z = 2;
    } else if (s.rh < arm) {
      zone = "DRY";
      zc = GREEN;
      z = 0;
    } else if (s.rh < swap - (swap - arm) * HIGH_FRACTION) {
      zone = "RISING";
      zc = AMBER;
      z = 1;
    } else {
      zone = "HIGH";
      zc = AMBER;
      z = 1;
    }
  }
  if (std::isnan(s.rh))
    it.print(118, 204, a.f_val, DIM, TextAlign::BASELINE_RIGHT, "--% RH");
  else
    it.printf(118, 204, a.f_val, WHITE, TextAlign::BASELINE_RIGHT, "%.1f%% RH", s.rh);
  it.print(124, 204, a.f_phase, zc, TextAlign::BASELINE_LEFT, zone);
  const int x0 = 70, w = 100;
  int xa = x0 + (int) lroundf(w * arm / end);
  int xs = x0 + (int) lroundf(w * swap / end);
  if (xa > xs) xa = xs;  // arm above swap is a misconfiguration; keep the bar drawable
  it.filled_rectangle(x0, 208, xa - x0, 5, z == 0 ? GREEN : DRY_DIM);
  it.filled_rectangle(xa, 208, xs - xa, 5, z == 1 ? AMBER : AMBER_DIM);
  it.filled_rectangle(xs, 208, x0 + w - xs, 5, z == 2 ? RED : RED_DIM);
  if (!std::isnan(s.rh)) {
    float f = s.rh / end;
    if (f < 0) f = 0;
    if (f > 1) f = 1;
    it.filled_rectangle(x0 + (int) lroundf(w * f) - 1, 206, 2, 9, WHITE);
  }
}

// Case label and temperature, fan label and the OVR (humidity override)
// badge. The fan icon itself is an image and is drawn by draw_ui.
inline void draw_unit(Display &it, const UiAssets &a, const UiState &s) {
  it.print(6, 196, a.f_label, DIM, TextAlign::BASELINE_LEFT, "CASE");
  if (std::isnan(s.t_case))
    it.print(6, 209, a.f_val, DIM, TextAlign::BASELINE_LEFT, "--°");
  else
    it.printf(6, 209, a.f_val, WHITE, TextAlign::BASELINE_LEFT, "%.0f°", s.t_case);
  it.print(216, 211, a.f_label, DIM, TextAlign::BASELINE_CENTER, "FAN");
  if (s.rh_override) {
    rounded_rect(it, 210, 4, 22, 12, 2, AMBER);
    it.print(221, 13, a.f_phase, BLACK, TextAlign::BASELINE_CENTER, "OVR", AMBER);
  }
}

// Bottom strip: fault (red), else the IP for the first minute, else status.
inline void draw_strip(Display &it, const UiAssets &a, const UiState &s) {
  if (s.fault_code != 0) {
    it.filled_rectangle(0, 214, 240, 26, RED_STRIP);
    std::string msg = "FAULT · " + s.fault_msg;
    it.print(120, 231, a.f_status_b, BLACK, TextAlign::BASELINE_CENTER, msg.c_str(), RED_STRIP);
    return;
  }
  it.horizontal_line(0, 214, 240, SHELL);
  const bool boot = s.uptime_ms < BOOT_IP_MS && !s.ip.empty();
  it.print(120, 231, a.f_status, STRIP_TXT, TextAlign::BASELINE_CENTER, boot ? s.ip.c_str() : s.status.c_str());
}

inline void draw_ui(Display &it, const UiState &s, const UiAssets &a) {
  it.fill(BLACK);
  PackView pa, pb;
  pack_roles(s, pa, pb);
  draw_fill(it, pa);
  draw_fill(it, pb);
  it.image(0, 0, a.bg);
  // Symbols follow the real output switches, not the state machine.
  if (s.valve_a)
    it.image(55, 154, a.lit_a);
  else if (s.valve_b)
    it.image(109, 154, a.lit_b);
  it.image(CX_A - 9, 158, s.valve_a ? a.valve_open : a.valve_closed);
  it.image(CX_B - 9, 158, s.valve_b ? a.valve_open : a.valve_closed);
  // Air in at the top of a pack whose valve is open; warm air out of the top
  // of a pack whose heater is on.
  if (s.valve_a) it.image(CX_A - 8, 3, a.flow_in);
  if (s.valve_b) it.image(CX_B - 8, 3, a.flow_in);
  if (s.heater_a) it.image(CX_A - 13, 1, a.flow_out);
  if (s.heater_b) it.image(CX_B - 13, 1, a.flow_out);
  it.print(CX_A, 44, a.f_cap, WHITE, TextAlign::BASELINE_CENTER, "A", SHELL);
  it.print(CX_B, 44, a.f_cap, WHITE, TextAlign::BASELINE_CENTER, "B", SHELL);
  draw_pack_text(it, a, pa);
  draw_pack_text(it, a, pb);
  draw_gauge(it, a, s);
  draw_unit(it, a, s);
  it.image(209, 189, a.fan, s.fan ? GREEN : SHELL);
  draw_strip(it, a, s);
}

}  // namespace dryer_ui
