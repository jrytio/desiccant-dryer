# ST7789 mipi_spi Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the ST7789 panel to ESPHome's `mipi_spi` driver with a reduced frame buffer so the ESP32-S2 has the contiguous heap mbedTLS needs, restore the on-device `update:` entity as the single firmware update route, and keep `/screen.png` working on the test builds.

**Architecture:** `packages/display-st7789.yaml` becomes a `mipi_spi` display parameterised by two substitutions, so production runs a reduced buffer (heap for TLS) while the test builds run a full one. The `/screen.png` mirror stops reading the driver's frame buffer and instead re-renders `dryer_ui::draw_ui()` into its own band-sized scratch buffer, which makes it independent of any display driver. The `update:`/`ota: http_request` block returns to `packages/release.yaml` and the ESPHome Device Builder adoption path is deleted.

**Tech Stack:** ESPHome 2026.9.0 on ESP-IDF, C++17 external components, YAML packages, Docker for builds, `esptool` for USB flashing.

## Global Constraints

- ESPHome **2026.9.0** exactly; `packages/production.yaml` sets `min_version: 2026.9.0`. The local CLI is 2026.8.2 and is **below the floor** — every build in this plan runs in Docker.
- Docker build invocation, copied from `.github/workflows/build.yml`:
  `docker run --rm -v "$PWD:/config" -w /config -v "$PWD/.ci-cache/tools:/cache" --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 -c 'exec /entrypoint.sh compile <yaml>'`
- The `host` and `scenarios` builds additionally need, prepended inside the `-c` string:
  `apt-get update -qq && apt-get install -y -qq --no-install-recommends libsdl2-dev g++ > /dev/null &&`
- All five selectors must pass: `desiccant-dryer.yaml`, `desiccant-dryer-virtual.yaml`, `desiccant-dryer-hw-test.yaml`, `desiccant-dryer-host.yaml`, `desiccant-dryer-scenarios.yaml`.
- `esphome/secrets.yaml` is gitignored and **already holds the real dev credentials** in this worktree (copied from the main checkout, which was not modified). Do NOT overwrite it with `secrets.ci.yaml`: the CI file's SSIDs are placeholders and the board will never join WiFi. Before writing to that path for any reason, run `test -L esphome/secrets.yaml && echo SYMLINK-STOP` — if it prints `SYMLINK-STOP`, stop; writing would clobber the main checkout's credentials through the symlink.
- The ESP builds are native ESP-IDF (CMake/Ninja), **not** PlatformIO. Firmware lands at `esphome/.esphome/build/<name>/build/firmware.factory.bin` — there is no `.pioenvs` directory.
- `esptool` is on PATH as a standalone command; `python -m esptool` is not installed.
- **No real device or Home Assistant IPs in tracked files.** Write `<board>` and
  substitute the address at the shell. Find the board's address from its boot
  log, not from a hard-coded value — it changes when the unit moves between the
  home and workshop networks.
- The production build must validate with **no** `secrets.yaml` present.
- `components/dryer_ui/display_ui.h` must contain **no `id()` calls** and use only the generic `display::Display` API.
- Nothing WiFi, OTA, SPI or LEDC related may go into `base.yaml` or `display-draw.yaml` — the host build has none of those.
- Board on USB at `/dev/cu.usbserial-210`. USB flash command:
  `esptool --chip esp32s2 --port /dev/cu.usbserial-210 --baud 460800 write_flash 0x0 <firmware.factory.bin>`
- **The bench board has NO display attached.** The driver still allocates its
  buffer and still clocks pixels out over SPI, so heap figures and redraw
  timings are real and valid. What cannot be checked on this board is how the
  image *looks*: colour, banding, tearing, offset. Every such check is
  deferred, not skipped — see "Deferred: panel sign-off" below.
- Never invent a measurement. Anything not measured is marked untested.
- Commit messages end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## Deferred: panel sign-off

Acceptance criterion 4 (*"the user confirms the physical panel looks right — no
banding or tearing with a partial buffer and `auto_clear_enabled: false`"*)
**cannot be met in this plan.** The bench board has no panel attached.

What this does NOT block: buffer allocation, `Largest Free Block`, redraw and
SPI timings, control-tick behaviour, the on-device install, and `/screen.png` —
the mirror re-renders from `dryer_ui::last_state()` and never touches the panel,
so it is a full check of the *drawing*, just not of the *glass*.

What stays open: colour fidelity, banding, tearing and image offset on real
hardware. The PR must say so plainly and must not claim criterion 4 met. Carry
it as a release blocker until someone runs a build on a board with the 1.54"
panel wired per `packages/display-st7789.yaml`.

Where the plan says "ask the user to look at the physical panel", substitute:
compare `/screen.png` against the reference PNGs in `docs/display/` and record
that the glass check is outstanding.

## Design deviation from the spec — read this first

The spec (`docs/superpowers/specs/2026-09-16-mipi-spi-migration-design.md`) says the rewritten screen mirror "keeps the existing writer-hijack purely to obtain `ui_draw`". **That approach does not work and is not used in this plan.**

Reading `packages/display-draw.yaml:19` and its `ui_draw` script shows why: `display_lambda` is `id(ui_draw).execute();`, and the script's final line is

```cpp
dryer_ui::draw_ui(*id(panel), s, dryer_ui::last_assets());
```

The script **ignores the `Display &` it was handed and draws to `id(panel)` unconditionally.** Replaying that writer against a different `Display` would render to the panel anyway.

What works instead, and is simpler: the script fills the process-wide singletons `dryer_ui::last_state()` and `dryer_ui::last_assets()` before drawing, and `draw_ui(Display &, const UiState &, const UiAssets &)` is a pure function over them (`display_ui.h:243`; every `static` in that header is `const` or init-once). So the mirror calls `draw_ui()` itself against its own `Display`, using the last state the main loop captured. No driver header, no `Peek`, no script execution from the web-server task, and no access to anything protected.

This also retires the `drawing_`/`fetches_`/`redraw_pending_` interlock: it existed only because the fetch read the panel's shared frame buffer mid-redraw. With a private buffer there is nothing to interlock.

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `esphome/components/screen_mirror/screen_mirror.h` | Handler + `BandDisplay` declaration | Rewrite |
| `esphome/components/screen_mirror/screen_mirror.cpp` | PNG streaming (kept) + band rendering (new) | Rewrite |
| `esphome/components/screen_mirror/__init__.py` | Config schema; generic `Display` id | Modify |
| `esphome/packages/screen-mirror.yaml` | Wiring; unchanged keys | Unchanged |
| `esphome/packages/display-st7789.yaml` | mipi_spi driver, two substitutions | Rewrite |
| `esphome/packages/production.yaml` | Buffer substitutions; drop `dashboard_import` | Modify |
| `esphome/desiccant-dryer-virtual.yaml` | Buffer substitutions | Modify |
| `esphome/desiccant-dryer-hw-test.yaml` | Buffer substitutions | Modify |
| `esphome/packages/release.yaml` | Restore `http_request`/`ota`/`update` | Modify |
| `esphome/version.yaml` | 1.1.0 → 1.2.0 | Modify |
| `esphome/desiccant-dryer-adopt.yaml` | Device Builder entry point | **Delete** |
| `esphome/packages/ui-code-remote.yaml` | Remote component source | **Delete** |
| `esphome/packages/ota-adopted.yaml` | Adopted OTA server | **Delete** |
| `esphome/packages/api-provisioned.yaml` | Runtime API key provisioning | **Keep — not Device Builder plumbing** |
| `esphome/components/dryer_ui/display_ui.h` | Drawing | Only if Task 4 optimises |

---

### Task 1: Rewrite the screen mirror to render its own frame

Done first and **while still on `ili9xxx`**, so it is verified independently before the driver swap. The new mirror is driver-agnostic, so it compiles and runs against the current driver unchanged.

**Files:**
- Rewrite: `esphome/components/screen_mirror/screen_mirror.h`
- Rewrite: `esphome/components/screen_mirror/screen_mirror.cpp`
- Modify: `esphome/components/screen_mirror/__init__.py`
- Test: `scripts/check-screen-png.py` (create)

**Interfaces:**
- Consumes: `dryer_ui::draw_ui(display::Display &, const dryer_ui::UiState &, const dryer_ui::UiAssets &)`, `dryer_ui::last_state()`, `dryer_ui::last_assets()` — all from `esphome/components/dryer_ui/display_ui.h`.
- Produces: `screen_mirror::ScreenMirror::set_display(display::Display *)` and `set_path(const std::string &)`, called from `__init__.py`. Nothing downstream consumes these.

- [ ] **Step 1: Write the failing test — a PNG checker**

Create `scripts/check-screen-png.py`:

```python
#!/usr/bin/env python3
"""Fetch /screen.png from a board and check it is a real 240x240 frame.

Usage: scripts/check-screen-png.py <host-or-ip> [out.png]

Fails if the response is not a decodable 240x240 indexed PNG, or if the
image is a single flat colour (which is what a blank or unrendered frame
looks like and is the failure this guards against).
"""
import sys
import urllib.request
import zlib
import struct


def chunks(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    off = 8
    while off < len(data):
        (length,) = struct.unpack(">I", data[off : off + 4])
        kind = data[off + 4 : off + 8]
        body = data[off + 8 : off + 8 + length]
        yield kind, body
        off += 12 + length


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: check-screen-png.py <host> [out.png]")
    url = f"http://{sys.argv[1]}/screen.png"
    raw = urllib.request.urlopen(url, timeout=20).read()
    if len(sys.argv) > 2:
        open(sys.argv[2], "wb").write(raw)

    ihdr = idat = None
    for kind, body in chunks(raw):
        if kind == b"IHDR":
            ihdr = body
        elif kind == b"IDAT":
            idat = (idat or b"") + body
    assert ihdr is not None and idat is not None, "missing IHDR/IDAT"

    w, h, depth, color = struct.unpack(">IIBB", ihdr[:10])
    assert (w, h) == (240, 240), f"expected 240x240, got {w}x{h}"
    assert depth == 8 and color == 3, f"expected 8-bit indexed, got depth={depth} color={color}"

    pixels = zlib.decompress(idat)
    stride = w + 1
    assert len(pixels) == h * stride, f"expected {h * stride} bytes, got {len(pixels)}"
    body = bytes(b for y in range(h) for b in pixels[y * stride + 1 : (y + 1) * stride])
    distinct = len(set(body))
    assert distinct > 4, f"image is flat ({distinct} distinct colours) - nothing was drawn"

    print(f"OK {w}x{h} indexed PNG, {distinct} distinct colours, {len(raw)} bytes")


if __name__ == "__main__":
    main()
```

Then make it executable:

```bash
chmod +x scripts/check-screen-png.py
```

- [ ] **Step 2: Run it against the board to verify it fails**

The board currently runs a throwaway `mipi_spi` build, so the old `ili9xxx` mirror is not serving a valid frame.

Run: `scripts/check-screen-png.py <board>`
Expected: FAIL — a `urllib.error.HTTPError: HTTP Error 500`, a connection error, or an `AssertionError`. Record which.

- [ ] **Step 3: Rewrite the header**

Replace the entire contents of `esphome/components/screen_mirror/screen_mirror.h`:

```cpp
#pragma once

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
```

- [ ] **Step 4: Rewrite the implementation**

Replace the entire contents of `esphome/components/screen_mirror/screen_mirror.cpp`:

```cpp
#include "screen_mirror.h"

#include <esp_http_server.h>

#include <algorithm>
#include <cstring>

#include "esphome/core/log.h"
#include "dryer_ui/display_ui.h"

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

  httpd_resp_set_type(req, "image/png");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  if (!send_chunk(req, head, sizeof(head)) || !send_chunk(req, PLTE.bytes, PLTE_LEN) ||
      !send_chunk(req, idat_head, sizeof(idat_head)))
    return;

  // Re-render the UI into our own band buffer, a band at a time, from the
  // state the panel captured on its last redraw.
  BandDisplay band(static_cast<int>(w), static_cast<int>(h), this->band_.data(), BAND_ROWS);
  const dryer_ui::UiState &state = dryer_ui::last_state();
  const dryer_ui::UiAssets &assets = dryer_ui::last_assets();

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
        std::fill(this->band_.begin(), this->band_.end(), 0);
        band.set_band_start(start);
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
```

- [ ] **Step 5: Point the config schema at a generic display**

In `esphome/components/screen_mirror/__init__.py`, replace the import line

```python
from esphome.components.ili9xxx.display import ILI9XXXDisplay
```

with

```python
from esphome.components.display import Display
```

replace the schema line

```python
            cv.Required(CONF_DISPLAY_ID): cv.use_id(ILI9XXXDisplay),
```

with

```python
            cv.Required(CONF_DISPLAY_ID): cv.use_id(Display),
```

and replace the module docstring comment

```python
# Serves an ili9xxx display's 8-bit frame buffer as a PNG on the web server.
# ESP32 only: the handler streams with esp_http_server directly so the
# 58 KB image never has to sit in RAM.
```

with

```python
# Serves the current screen as an 8-bit indexed PNG on the web server. The
# frame is re-rendered on demand from dryer_ui::last_state() rather than read
# out of a display driver, so this works with any driver and with a partial
# driver frame buffer. ESP32 only: the handler streams with esp_http_server
# directly so the 58 KB image never has to sit in RAM.
```

Then add `dryer_ui` to the dependency list so its header is on the include path. Replace

```python
DEPENDENCIES = ["display"]
```

with

```python
DEPENDENCIES = ["display", "dryer_ui"]
```

- [ ] **Step 6: Compile the virtual build (still on ili9xxx)**

```bash
test -L esphome/secrets.yaml && echo SYMLINK-STOP || cp esphome/secrets.ci.yaml esphome/secrets.yaml
docker run --rm -v "$PWD:/config" -w /config -v "$PWD/.ci-cache/tools:/cache" \
  --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 \
  -c 'exec /entrypoint.sh compile esphome/desiccant-dryer-virtual.yaml'
```

Expected: `INFO Successfully compiled program.` If the compiler cannot find `dryer_ui/display_ui.h`, the `DEPENDENCIES` edit in Step 5 did not take effect — fix that rather than adding an include path.

- [ ] **Step 7: Flash the virtual build and verify the PNG**

```bash
esptool --chip esp32s2 --port /dev/cu.usbserial-210 --baud 460800 write_flash 0x0 \
  esphome/.esphome/build/desiccant-dryer-virtual/build/firmware.factory.bin
```

Then, once the board has joined WiFi:

Run: `scripts/check-screen-png.py <board> /tmp/screen-task1.png`
Expected: `OK 240x240 indexed PNG, <N> distinct colours, <M> bytes` with N well above 4.

Open `/tmp/screen-task1.png` and confirm it shows the dryer UI — two cylinders, the gauge and the status strip — not noise or a partial frame.

- [ ] **Step 8: Commit**

```bash
git add esphome/components/screen_mirror scripts/check-screen-png.py
git commit -m "Render /screen.png from draw_ui instead of the driver's buffer

The mirror reached into ILI9XXXDisplay's private members through a Peek
struct to read the frame buffer. That ties it to one driver and needs a
full frame in RAM, neither of which survives the move to mipi_spi with a
partial buffer.

draw_ui() is a pure function of dryer_ui::last_state() and last_assets(),
which the ui_draw script refreshes on every redraw, so the mirror now
re-renders the frame itself into a 24-row band buffer and streams PNG rows
as it goes. No driver header, no private access, and the interlock that
existed only to avoid reading a half-drawn shared buffer is gone.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Move the panel to mipi_spi with per-build buffer profiles

**Files:**
- Rewrite: `esphome/packages/display-st7789.yaml`
- Modify: `esphome/packages/production.yaml`
- Modify: `esphome/desiccant-dryer-virtual.yaml`
- Modify: `esphome/desiccant-dryer-hw-test.yaml`

**Interfaces:**
- Consumes: `${display_lambda}` from `packages/display-draw.yaml`; the display id `panel`, which `display-draw.yaml` and `screen-mirror.yaml` both reference.
- Produces: substitutions `display_buffer_size` and `display_update_interval`, overridable by any selector. The display keeps the id `panel`.

- [ ] **Step 1: Capture the before-config for the refactor diff**

```bash
mkdir -p /tmp/cfg
for v in desiccant-dryer desiccant-dryer-virtual desiccant-dryer-hw-test; do
  docker run --rm -v "$PWD:/config" -w /config --entrypoint bash \
    ghcr.io/esphome/esphome:2026.9.0 -c "exec /entrypoint.sh config esphome/$v.yaml" \
    > "/tmp/cfg/$v.before.yaml"
done
```

Expected: three files written, each ending with a valid config dump.

- [ ] **Step 2: Rewrite the driver package**

Replace the entire contents of `esphome/packages/display-st7789.yaml`:

```yaml
# ST7789 1.54" 240x240 display on SPI, shared by the production, virtual and
# hw-test builds. On the virtual build nothing is attached; the driver still
# runs so the frame buffer allocation on the S2 gets exercised. The drawing
# itself is ${display_lambda} from packages/display-draw.yaml.
#   GPIO36/35 SPI SCK/MOSI, GPIO5 CS, GPIO9 DC, GPIO14 RST, GPIO17 backlight
#
# mipi_spi, not ili9xxx, because ili9xxx cannot buffer less than a full frame
# (get_buffer_length_() is width * height, so 57,600 B is its floor) and that
# leaves the S2 without the ~16,749-byte contiguous block mbedTLS needs for a
# TLS record. With no such block the on-device updater can never install.
#
# The cost is that MipiSpiBuffer::update() re-runs the whole writer lambda
# once per band, so ${display_buffer_size} multiplies draw cost: 50% draws
# twice, 25% draws four times. Production trades draw time for the heap;
# the test builds keep 100% because they never self-update. Override both
# substitutions from the selector.

substitutions:
  display_buffer_size: "100%"
  display_update_interval: 5s

spi:
  clk_pin: GPIO36
  mosi_pin: GPIO35

output:
  - platform: ledc
    pin: GPIO17
    id: backlight_pwm
    frequency: 1000Hz

light:
  - platform: monochromatic
    name: "Display Backlight"
    output: backlight_pwm
    restore_mode: RESTORE_DEFAULT_ON
    default_transition_length: 0s

display:
  - platform: mipi_spi
    id: panel
    model: ST7789V
    dimensions:
      height: 240
      width: 240
      offset_height: 0     # try 80 if the image is shifted / cropped
      offset_width: 0
    cs_pin: GPIO5
    dc_pin: GPIO9
    reset_pin: GPIO14
    invert_colors: true    # most 1.54" IPS modules need this
    # RGB 3-3-2, the same grid color_palette: 8BIT used and the grid every
    # designed colour already sits on. Only valid on a single-wire SPI bus.
    color_depth: 8bit
    buffer_size: ${display_buffer_size}
    update_interval: ${display_update_interval}
    auto_clear_enabled: false   # draw_ui() fills the frame itself
    lambda: ${display_lambda}
```

- [ ] **Step 3: Give production the reduced buffer**

In `esphome/packages/production.yaml`, immediately below the `esphome: min_version:` block and above `packages:`, add:

```yaml
# The production unit installs its own firmware over HTTPS, which needs a
# ~16,749-byte contiguous block for a TLS record. Halving the frame buffer
# frees roughly 29 KB. The cost is that the writer runs twice per redraw;
# see packages/display-st7789.yaml.
substitutions:
  display_buffer_size: "50%"
  display_update_interval: 5s
```

- [ ] **Step 4: Keep a full buffer on the test builds**

In `esphome/desiccant-dryer-virtual.yaml`, extend the existing `substitutions:` block to:

```yaml
substitutions:
  name: desiccant-dryer-virtual
  friendly_name: Desiccant Dryer (Virtual)
  # No on-device updater here, so the panel keeps a full frame buffer and
  # the writer runs once per redraw.
  display_buffer_size: "100%"
  display_update_interval: 5s
```

In `esphome/desiccant-dryer-hw-test.yaml`, extend the existing `substitutions:` block to:

```yaml
substitutions:
  name: desiccant-dryer-hw-test
  friendly_name: Desiccant Dryer (HW Test)
  # No on-device updater here, so the panel keeps a full frame buffer and
  # the writer runs once per redraw.
  display_buffer_size: "100%"
  display_update_interval: 5s
```

- [ ] **Step 5: Compile all five builds**

```bash
for v in desiccant-dryer desiccant-dryer-virtual desiccant-dryer-hw-test; do
  docker run --rm -v "$PWD:/config" -w /config -v "$PWD/.ci-cache/tools:/cache" \
    --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 \
    -c "exec /entrypoint.sh compile esphome/$v.yaml" || echo "FAILED $v"
done
for v in desiccant-dryer-host desiccant-dryer-scenarios; do
  docker run --rm -v "$PWD:/config" -w /config -v "$PWD/.ci-cache/tools:/cache" \
    --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 \
    -c "apt-get update -qq && apt-get install -y -qq --no-install-recommends libsdl2-dev g++ > /dev/null && exec /entrypoint.sh compile esphome/$v.yaml" || echo "FAILED $v"
done
```

Expected: five `INFO Successfully compiled program.` and no `FAILED` lines. The `ST7789V` model declares `requires={"psram"}`; if this errors on the S2 the config-level validation was misleading and the model needs `model: CUSTOM` with explicit init — stop and report rather than guessing.

- [ ] **Step 6: Confirm the production build still needs no secrets**

```bash
mv esphome/secrets.yaml /tmp/secrets-parked.yaml
docker run --rm -v "$PWD:/config" -w /config --entrypoint bash \
  ghcr.io/esphome/esphome:2026.9.0 -c 'exec /entrypoint.sh config esphome/desiccant-dryer.yaml' > /dev/null \
  && echo "OK production validates with no secrets"
mv /tmp/secrets-parked.yaml esphome/secrets.yaml
```

Expected: `OK production validates with no secrets`.

- [ ] **Step 7: Diff the normalised config to see exactly what moved**

```bash
for v in desiccant-dryer desiccant-dryer-virtual desiccant-dryer-hw-test; do
  docker run --rm -v "$PWD:/config" -w /config --entrypoint bash \
    ghcr.io/esphome/esphome:2026.9.0 -c "exec /entrypoint.sh config esphome/$v.yaml" \
    > "/tmp/cfg/$v.after.yaml"
  echo "===== $v"
  diff <(python3 scripts/normalize-config.py < "/tmp/cfg/$v.before.yaml") \
       <(python3 scripts/normalize-config.py < "/tmp/cfg/$v.after.yaml")
done
```

Expected: differences confined to the `display:` block (platform, `color_depth`/`buffer_size` replacing `color_palette`, `update_interval`) and the new substitutions. **Anything outside the display block is a regression — investigate before continuing.**

- [ ] **Step 8: Flash hw-test and confirm the panel and the mirror**

```bash
esptool --chip esp32s2 --port /dev/cu.usbserial-210 --baud 460800 write_flash 0x0 \
  esphome/.esphome/build/desiccant-dryer-hw-test/build/firmware.factory.bin
```

Run: `scripts/check-screen-png.py <board> /tmp/screen-task2.png`
Expected: `OK 240x240 indexed PNG, ...`

Then compare `/tmp/screen-task2.png` with `/tmp/screen-task1.png` from Task 1.

**They will NOT be byte-identical, and that is expected** — Task 1's image came
from the virtual build (simulated sensors, a running uptime counter, an elapsed
service timer) and this one comes from hw-test with no probes attached. The
live values differ by design.

What must match is the *structure*: same layout, same fonts, same palette, both
cylinders drawn, gauge and status strip present, no horizontal seams at
multiples of 24 rows. A seam would mean the band stitching broke; a palette
shift would mean the RGB332 assumption is wrong. Either is a blocker.

```bash
python3 - <<'EOF'
import struct, zlib
def load(p):
    d = open(p, "rb").read(); off = 8; idat = b""; ihdr = None
    while off < len(d):
        (n,) = struct.unpack(">I", d[off:off+4]); k = d[off+4:off+8]
        if k == b"IHDR": ihdr = d[off+8:off+8+n]
        elif k == b"IDAT": idat += d[off+8:off+8+n]
        off += 12 + n
    w, h = struct.unpack(">II", ihdr[:8]); raw = zlib.decompress(idat)
    return w, h, [raw[y*(w+1)+1:(y+1)*(w+1)] for y in range(h)]
for p in ("/tmp/screen-task1.png", "/tmp/screen-task2.png"):
    w, h, rows = load(p)
    print(p, f"{w}x{h}", "palette entries used:", len({b for r in rows for b in r}))
EOF
```

Expected: both report `240x240` and a similar count of palette entries (Task 1
measured 32). A large drop means colours are being lost.
No panel is attached to this board, so the glass check (colour, banding, tearing, offset) is deferred — see "Deferred: panel sign-off". Confirm instead from the log that the driver came up and allocated its buffer:

```bash
esphome logs esphome/desiccant-dryer-hw-test.yaml --device /dev/cu.usbserial-210 2>&1 | tee /tmp/task2.log
grep -iE "mipi_spi|Buffer bytes|Buffer fraction|Buffer allocation failed|setup failed" /tmp/task2.log
```

Expected: the dump_config shows `Buffer pixels: 8 bits`, a `Buffer fraction` matching the selector, and **no** `Buffer allocation failed`.

- [ ] **Step 9: Commit**

```bash
git add esphome/packages/display-st7789.yaml esphome/packages/production.yaml \
        esphome/desiccant-dryer-virtual.yaml esphome/desiccant-dryer-hw-test.yaml
git commit -m "Move the panel from ili9xxx to mipi_spi with a per-build buffer

ili9xxx cannot buffer less than a full frame, so the S2 never had the
~16,749-byte contiguous block mbedTLS needs and the on-device updater could
check for releases but never install one.

mipi_spi takes a buffer_size fraction. Production runs 50% to free roughly
29 KB; the test builds keep 100% because they never self-update. The pin
map, SPI bus, backlight and invert_colors are unchanged, and color_depth
8bit is the same RGB 3-3-2 grid color_palette 8BIT used.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Measure the redraw, and optimise only if the measurement says to

This task is **capped by explicit user decision**: take the obvious wins, then report the honest number. Do not iterate past Step 5.

**Files:**
- Possibly modify: `esphome/packages/production.yaml` (`display_update_interval` only)
- **Not** modified: `esphome/components/dryer_ui/display_ui.h` — see Step 4

**Interfaces:**
- Consumes: nothing. This task measures and, at most, changes one substitution value.
- Produces: the redraw measurements quoted in the PR.

- [ ] **Step 1: Build a VERBOSE production image to read the band timings**

mipi_spi logs `Drawing from line %d took %dms` and `Write to display took %dms` per band, but only at VERBOSE. Temporarily append to `esphome/desiccant-dryer-hw-test.yaml`, replacing its existing `logger:` block:

```yaml
logger:
  level: VERBOSE
```

and temporarily set, in that same file's substitutions, `display_buffer_size: "50%"` so it matches production's profile.

Then compile and flash:

```bash
docker run --rm -v "$PWD:/config" -w /config -v "$PWD/.ci-cache/tools:/cache" \
  --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 \
  -c 'exec /entrypoint.sh compile esphome/desiccant-dryer-hw-test.yaml'
esptool --chip esp32s2 --port /dev/cu.usbserial-210 --baud 460800 write_flash 0x0 \
  esphome/.esphome/build/desiccant-dryer-hw-test/build/firmware.factory.bin
```

- [ ] **Step 2: Record the measurement**

```bash
esphome logs esphome/desiccant-dryer-hw-test.yaml --device /dev/cu.usbserial-210 \
  2>&1 | tee /tmp/verbose.log
```

Let it run for at least six redraws (30 s at a 5 s interval), then:

```bash
grep -E "Drawing from line|Write to display|Total update took|took a long time" /tmp/verbose.log | tail -40
```

Write the numbers into the task notes: per-band draw ms, per-band SPI write ms, total update ms, and whether any `display took a long time for an operation` warning appeared. **These are the measurements the acceptance report cites — do not round or estimate them.**

- [ ] **Step 3: Decide from the split, do not guess**

- If **total update is already under ~500 ms**: no optimisation is needed. Skip to Step 6.
- If **draw time dominates** (draw ms >> write ms): the writer is the cost, and Steps 4–5 apply.
- If **SPI write time dominates**: `draw_ui()` is not the problem and optimising it will not help. Skip to Step 6 and report that the cost is SPI bandwidth, not drawing.

- [ ] **Step 4: Record the conclusion — there is no optimisation to make**

Decided with the user before execution began: **no speculative change to
`display_ui.h`.** The only lever reachable through ESPHome's public `Display`
API is the clipping rectangle, and `MipiSpiBuffer` never sets one, so a guard
built on `get_clipping()` would be dead code. The band multiplier cannot be
removed without band-aware rendering that the `Display` API does not expose.

So the honest outcome of this task is a measurement plus a setting, not a code
change. Write into the report:

- the measured per-band draw time, per-band SPI write time and total update time
- which of the two dominates
- whether the ~500 ms target was met

- [ ] **Step 5: Bound the tick delay if the target was missed**

If the total update time from Step 2 is above ~500 ms, raise
`display_update_interval` in `esphome/packages/production.yaml` from `5s` to
`10s`, so the blocking redraw happens half as often. Record that the ~500 ms
acceptance bar was **not met**, with the measured value. Do not restate the
target as if it were met, and do not attempt further optimisation — the effort
cap is a user decision, not a suggestion.

- [ ] **Step 6: Revert the temporary VERBOSE/50% edits to hw-test**

Restore `esphome/desiccant-dryer-hw-test.yaml` to `logger: level: DEBUG` and `display_buffer_size: "100%"`.

```bash
git diff esphome/desiccant-dryer-hw-test.yaml
```

Expected: no diff against the Task 2 commit.

- [ ] **Step 7: Confirm display_ui.h was not touched**

```bash
git diff --quiet HEAD -- esphome/components/dryer_ui/display_ui.h \
  && echo "OK display_ui.h unchanged - no scenario shots needed" \
  || echo "UNEXPECTED: display_ui.h changed - run scripts/scenario-shots.sh and review docs/display/"
```

Expected: `OK display_ui.h unchanged`. The drawing code is deliberately not
modified in this task, so the rendered scenarios in `docs/display/` stay valid.

- [ ] **Step 8: Commit (skip if nothing changed)**

```bash
git add -A esphome/packages/production.yaml
git commit -m "Measure the mipi_spi redraw cost and bound the tick delay

MipiSpiBuffer::update() re-runs the writer once per band, so a 50% buffer
draws the UI twice per redraw. The multiplier cannot be removed through
ESPHome's public Display API: the only lever is the clipping rect, and
MipiSpiBuffer never sets one. So this records the measurement and lets
update_interval absorb what is left, rather than adding a guard that would
do nothing. The measured value is reported rather than the target restated.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Restore the on-device update entity

**Files:**
- Modify: `esphome/packages/release.yaml`

**Interfaces:**
- Consumes: `${version}` from `esphome/version.yaml`.
- Produces: substitution `update_manifest_url`; a Home Assistant `update` entity named `Firmware`.

- [ ] **Step 1: Confirm the manifest the device will poll actually exists**

```bash
curl -fsSL https://jrytio.github.io/desiccant-dryer/firmware/manifest.json | head -20
```

Expected: JSON containing a `version` field. If this 404s, the Pages branch has no firmware yet and the install test in Task 7 cannot pass — stop and report before writing the updater that depends on it.

- [ ] **Step 2: Add the substitution**

At the top of `esphome/packages/release.yaml`, immediately after the header comment block and before `esphome:`, add:

```yaml
# The device polls this esp-web-tools manifest on the repository's GitHub
# Pages site and reports an update to Home Assistant when the manifest's
# version differs from ${version}. Installing pulls the .ota.bin over HTTPS
# (the relative path in the manifest resolves next to it) and checks its md5.
#
# Pages, not the GitHub Release download URL: that one redirects to an
# RSA-certificate host with a ~900-byte signed URL, and the S2 has too
# little free heap for the second handshake.
substitutions:
  update_manifest_url: https://jrytio.github.io/desiccant-dryer/firmware/manifest.json
```

- [ ] **Step 3: Add the HTTP client, OTA backend and update entity**

At the end of `esphome/packages/release.yaml`, after the existing `sensor:` block, append:

```yaml
http_request:
  verify_ssl: true
  timeout: 10s
  # GitHub Pages answers directly with no redirect, so the request and
  # response headers stay short. Kept a little above the 512-byte default
  # for header headroom.
  buffer_size_rx: 1024

# The download backend for the update entity below. This is not an OTA
# *server*: nothing listens, so no LAN host can push firmware to a mains
# controller. Updates are strictly pull-based.
ota:
  - platform: http_request

update:
  - platform: http_request
    name: "Firmware"
    source: ${update_manifest_url}
    update_interval: 6h
```

- [ ] **Step 4: Correct the header comment that says there is no updater**

In `esphome/packages/release.yaml`, replace this paragraph:

```
# The released image itself has no OTA server: without a password it would
# let any host on the LAN upload firmware to a mains controller. It also
# has no on-device HTTP updater. 1.0.x tried one: the S2 (no PSRAM, 58 KB
# display buffer) never had the ~17 KB contiguous block a TLS firmware
# download needs, with dynamic or static mbedTLS buffers.
```

with:

```
# The released image has no OTA *server*: without a password it would let
# any host on the LAN upload firmware to a mains controller. Updates are
# pull-only, through the update entity below.
#
# 1.0.x tried this and failed: with ili9xxx's mandatory full frame buffer
# the S2 never had the ~16,749-byte contiguous block a TLS record needs.
# Moving the panel to mipi_spi with a reduced buffer freed it. See
# packages/display-st7789.yaml.
```

and replace the second paragraph, which describes adoption:

```
# The release image carries no credentials (packages/dev-secrets.yaml is
# only in the test builds). The owner sets WiFi through Improv on the USB
# serial port (web.esphome.io does this) or the fallback access point, then
# adopts the unit in ESPHome Device Builder. The adopted YAML holds the
# owner's API key and OTA password, and Device Builder pushes updates with
# ESPHome's native OTA.
```

with:

```
# The release image carries no credentials (packages/dev-secrets.yaml is
# only in the test builds). The owner sets WiFi through Improv on the USB
# serial port (web.esphome.io does this) or the fallback access point, and
# Home Assistant sets the API encryption key when it adopts the device.
# Later updates come from the update entity below; no add-on is needed.
```

- [ ] **Step 5: Validate the production build with no secrets**

```bash
mv esphome/secrets.yaml /tmp/secrets-parked.yaml
docker run --rm -v "$PWD:/config" -w /config --entrypoint bash \
  ghcr.io/esphome/esphome:2026.9.0 -c 'exec /entrypoint.sh config esphome/desiccant-dryer.yaml' \
  | grep -E "update_manifest_url|platform: http_request" 
mv /tmp/secrets-parked.yaml esphome/secrets.yaml
```

Expected: the manifest URL and two `platform: http_request` lines (the `ota` backend and the `update` entity).

- [ ] **Step 6: Compile production and check the heap headroom at link time**

```bash
docker run --rm -v "$PWD:/config" -w /config -v "$PWD/.ci-cache/tools:/cache" \
  --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 \
  -c 'exec /entrypoint.sh compile esphome/desiccant-dryer.yaml'
```

Expected: `INFO Successfully compiled program.` TLS pulls in mbedTLS, so flash usage rises noticeably; that is expected, not a problem.

- [ ] **Step 7: Commit**

```bash
git add esphome/packages/release.yaml
git commit -m "Bring back the on-device update entity

With mipi_spi's reduced frame buffer the S2 finally has the contiguous
block mbedTLS needs, so the http_request updater that 1.0.x had to drop
works. Restores the client, the OTA download backend and the update entity
pointed at the GitHub Pages manifest, and corrects the header that said
the S2 could never do this.

Still no OTA server: nothing listens, so updates stay pull-only.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Retire the ESPHome Device Builder path

**Files:**
- Delete: `esphome/desiccant-dryer-adopt.yaml`
- Delete: `esphome/packages/ui-code-remote.yaml`
- Delete: `esphome/packages/ota-adopted.yaml`
- Modify: `esphome/packages/production.yaml`
- Keep: `esphome/packages/api-provisioned.yaml`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing. This task only removes.

- [ ] **Step 1: Prove nothing else references the files before deleting them**

```bash
grep -rn "desiccant-dryer-adopt\|ui-code-remote\|ota-adopted\|ui_ref\|display_assets\|dashboard_import" \
  --include='*.yaml' --include='*.yml' --include='*.sh' --include='*.py' --include='*.md' . \
  | grep -v '^./docs/superpowers/'
```

Record every hit. Everything outside `esphome/desiccant-dryer-adopt.yaml` itself and the docs listed in Task 6 must be resolved here. In particular check `scripts/release.sh` and `.github/workflows/release.yml`.

- [ ] **Step 2: Delete the three files**

```bash
git rm esphome/desiccant-dryer-adopt.yaml esphome/packages/ui-code-remote.yaml esphome/packages/ota-adopted.yaml
```

- [ ] **Step 3: Remove the dashboard_import block**

In `esphome/packages/production.yaml`, delete:

```yaml
# Lets Device Builder adopt a flashed unit: it writes a short YAML that pulls
# the adopt selector as a package and adds the owner's credentials.
dashboard_import:
  package_import_url: github://jrytio/desiccant-dryer/esphome/desiccant-dryer-adopt.yaml@main
  import_full_config: false
```

- [ ] **Step 4: Correct production.yaml's header**

In `esphome/packages/production.yaml`, replace the opening comment block's first six lines:

```
# Everything in the production firmware except where the screen's drawing
# code and art come from. Two selectors wrap it:
#   esphome/desiccant-dryer.yaml        local sources (CI, release images)
#   esphome/desiccant-dryer-adopt.yaml  GitHub sources at the release tag
#                                       (ESPHome Device Builder adoption)
```

with:

```
# Everything in the production firmware. One selector wraps it:
#   esphome/desiccant-dryer.yaml   CI, and the published release images
```

and replace the `Release:` paragraph:

```
# Release: ../version.yaml + release.yaml (version, provisioning,
#         diagnostics). No secrets: the owner sets WiFi at flash time and
#         adopts the device in Device Builder, which generates the owner's
#         own API key and OTA password and pushes later updates over WiFi.
#         See docs/releasing.md.
```

with:

```
# Release: ../version.yaml + release.yaml (version, provisioning,
#         diagnostics). No secrets: the owner sets WiFi at flash time,
#         Home Assistant sets the API key on adoption, and the unit
#         installs later releases itself. See docs/releasing.md.
```

Then replace the `min_version` rationale paragraph, which justifies the floor by adoption:

```
# The owner's adopted YAML needs 2026.9's `ota: encryption: key:` (an
# explicit OTA key: the API key is provisioned at runtime and cannot be
# inherited at build time), and the release images should match what an
# owner's Device Builder compiles. Only the production and adopt selectors
# carry this floor; the bench builds still run on an older CLI.
```

with:

```
# mipi_spi's buffer_size needs 2026.9. Only the production selector carries
# this floor; the bench builds still run on an older CLI.
```

- [ ] **Step 5: Confirm api-provisioned.yaml survived**

```bash
test -f esphome/packages/api-provisioned.yaml && grep -q "api:" esphome/desiccant-dryer.yaml \
  && echo "OK api provisioning intact"
```

Expected: `OK api provisioning intact`. This file is the flashed image's runtime API-key provisioning, **not** Device Builder plumbing — deleting it would break adoption by Home Assistant itself.

- [ ] **Step 6: Compile production and validate with no secrets**

```bash
mv esphome/secrets.yaml /tmp/secrets-parked.yaml
docker run --rm -v "$PWD:/config" -w /config -v "$PWD/.ci-cache/tools:/cache" \
  --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 \
  -c 'exec /entrypoint.sh compile esphome/desiccant-dryer.yaml'
mv /tmp/secrets-parked.yaml esphome/secrets.yaml
```

Expected: `INFO Successfully compiled program.`

- [ ] **Step 7: Commit**

```bash
git add -A esphome
git commit -m "Retire the ESPHome Device Builder adoption path

With the unit updating itself there is no reason to keep a second update
route, and two vaguely documented routes are worse than one. Deletes the
adopt selector, the remote component source and the adopted OTA server,
and drops dashboard_import.

api-provisioned.yaml stays: that is the flashed image's runtime API key
provisioning, which Home Assistant still uses to adopt the device.

Nothing now resolves sources at a release tag, so scripts/release.sh no
longer has to run immediately after a version bump merges.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Update the docs and bump the version

**Files:**
- Modify: `CLAUDE.md`
- Rewrite: `docs/releasing.md`
- Modify: `docs/screen-in-ha.md`
- Modify: `docs/hardware-bringup.md`
- Modify: `docs/host-preview.md`
- Modify: `esphome/version.yaml`

**Interfaces:**
- Consumes: the decisions made in Tasks 2–5 and the real numbers measured in Task 3.
- Produces: `version: "1.2.0"`.

- [ ] **Step 1: Find every place the old facts are asserted**

```bash
grep -rn "color_palette\|ili9xxx\|Device Builder\|dashboard_import\|adopt\|8BIT\|screen.png" \
  --include='*.md' . | grep -v '^./docs/superpowers/'
```

Record the list. Every hit must be either corrected or deliberately left, with a reason.

- [ ] **Step 2: Correct CLAUDE.md**

Four changes.

In the **Platform decisions** section, replace the display sentence:

```
The full 16-bit 240x240
display buffer (~115 KB) does not allocate once WiFi, API and the web server
are up (seen on the first bench flash), so the display runs
`color_palette: 8BIT` (~58 KB).
```

with:

```
The full 16-bit 240x240
display buffer (~115 KB) does not allocate once WiFi, API and the web server
are up (seen on the first bench flash), so the display runs `mipi_spi` with
`color_depth: 8bit`. Production uses `buffer_size: 50%` to leave the S2 the
~16,749-byte contiguous block mbedTLS needs for on-device updates; the test
builds use 100%. `mipi_spi` re-runs the writer once per band, so
`buffer_size` multiplies redraw cost — see `packages/display-st7789.yaml`.
```

In the **Layout and pin map** section, replace:

```
`packages/screen-mirror.yaml` (hw-test and virtual builds only) serves the panel's frame buffer as `/screen.png` through the local component `esphome/components/screen_mirror`.
```

with:

```
`packages/screen-mirror.yaml` (hw-test and virtual builds only) serves the screen as `/screen.png` through the local component `esphome/components/screen_mirror`, which re-renders `draw_ui()` into its own band buffer rather than reading the driver's.
```

In the same section, replace the sentence describing the production and adopt selectors:

```
`desiccant-dryer.yaml`, `desiccant-dryer-virtual.yaml`,
`desiccant-dryer-hw-test.yaml` and `desiccant-dryer-host.yaml` are short
selectors; the production one wraps `packages/production.yaml`, which
`desiccant-dryer-adopt.yaml` also wraps with the component and art taken from
GitHub at the release tag for ESPHome Device Builder adoption (docs/releasing.md);
```

with:

```
`desiccant-dryer.yaml`, `desiccant-dryer-virtual.yaml`,
`desiccant-dryer-hw-test.yaml` and `desiccant-dryer-host.yaml` are short
selectors; the production one wraps `packages/production.yaml`
(docs/releasing.md);
```

In the **Working conventions** section, replace the whole production bullet (the one beginning "Only `packages/production.yaml` (wrapped by `desiccant-dryer.yaml` and `desiccant-dryer-adopt.yaml`)") with:

```
- Only `packages/production.yaml` (wrapped by `desiccant-dryer.yaml`)
  includes `esphome/version.yaml` (semver, bumped in the PR) and
  `packages/release.yaml` (project version, Improv and captive-portal
  provisioning, safe mode, debug sensors, the update entity). It has no
  ESPHome OTA server and the web server's upload page is off
  (unauthenticated reflash of a mains controller); the API reboot watchdog
  is off. Updates are pull-only: the unit polls the esp-web-tools manifest
  on GitHub Pages and installs over HTTPS, so the owner only supplies WiFi
  and Home Assistant sets the API key. This needs the contiguous heap that
  `mipi_spi`'s reduced buffer frees — do not raise production's
  `display_buffer_size` back to 100% without re-testing an install. There
  is deliberately no second update route: a unit whose updater cannot
  reach a working manifest needs USB. The production build contains no
  secrets and must validate with no `secrets.yaml` present: WiFi, the API
  key and the OTA password of the test builds live in
  `packages/dev-secrets.yaml`. See docs/releasing.md. The 1.x production
  builds log at DEBUG on purpose.
```

- [ ] **Step 3: Rewrite docs/releasing.md**

Read the current file first, then rewrite it around a single update route. It must contain, in this order: how a release is cut (bump `esphome/version.yaml` in the PR, merge, run `scripts/release.sh`), what the workflow publishes (GitHub Release binaries plus the manifest copied to `gh-pages`, which is what the device polls), how an owner does a first install (USB via web.esphome.io, WiFi through Improv, Home Assistant adopts and sets the API key), how updates then happen (the `Firmware` update entity, 6 h poll, install from Home Assistant), and a clearly headed **Recovery** section stating plainly that there is no second route: with no inbound OTA server, a unit whose updater cannot reach a working manifest must be reflashed over USB.

Delete every reference to Device Builder, adoption YAML, `dashboard_import`, `ui_ref` and the minted-key/`ota: encryption:` mechanism. Also delete the note that `scripts/release.sh` must run immediately after the version bump merges — that constraint is gone with the adopt selector.

- [ ] **Step 4: Correct docs/screen-in-ha.md**

Replace any description of the endpoint streaming the panel's frame buffer with the new behaviour: the endpoint re-renders the UI from the last captured state into its own buffer, so it no longer depends on `color_palette: 8BIT`, on rotation 0, or on a full driver frame buffer. Remove the warning that changing those settings makes the endpoint return 500. Keep everything about the Home Assistant `image.dryer_screen` template image and its 2 s refresh automation.

- [ ] **Step 5: Correct docs/hardware-bringup.md §4 and docs/host-preview.md**

In `docs/hardware-bringup.md` §4, correct any statement that the display uses `ili9xxx` or `color_palette: 8BIT`, and any statement that firmware updates come from Device Builder.

In `docs/host-preview.md`, the SDL driver is unchanged, so correct only statements about the device-side driver or the update route if present.

- [ ] **Step 6: Bump the version**

In `esphome/version.yaml`, change:

```yaml
  version: "1.1.0"
```

to:

```yaml
  version: "1.2.0"
```

- [ ] **Step 7: Check no stale reference survived**

```bash
grep -rn "Device Builder\|dashboard_import\|ui-code-remote\|ota-adopted\|desiccant-dryer-adopt\|color_palette" \
  --include='*.md' --include='*.yaml' --include='*.yml' . | grep -v '^./docs/superpowers/'
```

Expected: no output. Hits under `docs/superpowers/` are historical specs and plans and are left alone.

- [ ] **Step 8: Commit**

```bash
git add -A CLAUDE.md docs esphome/version.yaml
git commit -m "Document the single update route and the mipi_spi display

Corrects the platform decision and layout notes that still described
color_palette: 8BIT and the ili9xxx frame buffer, rewrites releasing.md
around the on-device updater with an explicit recovery section saying USB
is the only fallback, and drops every Device Builder reference. Bumps to
1.2.0.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Prove it on hardware and open the PR

**Files:**
- No source changes expected. Any fix found here gets its own commit.

**Interfaces:**
- Consumes: everything above.
- Produces: the acceptance evidence quoted in the PR description.

- [ ] **Step 1: Flash the real production image over USB**

```bash
docker run --rm -v "$PWD:/config" -w /config -v "$PWD/.ci-cache/tools:/cache" \
  --entrypoint bash ghcr.io/esphome/esphome:2026.9.0 \
  -c 'exec /entrypoint.sh compile esphome/desiccant-dryer.yaml'
esptool --chip esp32s2 --port /dev/cu.usbserial-210 --baud 460800 write_flash 0x0 \
  esphome/.esphome/build/desiccant-dryer/build/firmware.factory.bin
```

Note: this image carries **no** WiFi credentials. Provision it through Improv on the serial port (web.esphome.io) or the fallback access point before the next step.

- [ ] **Step 2: Record the contiguous block**

Read the `Largest Free Block` diagnostic sensor, either in Home Assistant or from the device's web server.

Expected: **comfortably above 16,749 B with margin.** Record the actual number. The throwaway 25% build measured 55,296 B; a 50% buffer should land lower but still well clear. If it is under ~25,000 B, report that rather than proceeding to Step 3 — an install that barely fits is not a pass.

- [ ] **Step 3: Install a published release on-device**

From Home Assistant, install from the `Firmware` update entity.

Expected in the device log: `Update complete`, then a reboot.

- [ ] **Step 4: Confirm the new image stayed — this is the real test**

After the reboot, watch the log for at least two minutes:

```bash
esphome logs esphome/desiccant-dryer.yaml --device /dev/cu.usbserial-210 2>&1 | tee /tmp/postupdate.log
grep -iE "rollback|Rolled back|boot partition|Firmware Version" /tmp/postupdate.log
```

Expected: the running `Firmware Version` matches the installed release, and **no** `OTA rollback detected! Rolled back from partition 'app1'`. A rollback is a **failure**, not a success — report it as such.

- [ ] **Step 5: Confirm the control loop is not starved**

```bash
grep -cE "took a long time for an operation" /tmp/postupdate.log
```

Record the count. Then confirm from the log that the 5 s control tick is still running on schedule and that heater and valve states are being re-asserted. Record the measured tick interval.

- [ ] **Step 6: Confirm /screen.png on both test builds**

Flash and check each in turn:

```bash
scripts/check-screen-png.py <board> /tmp/screen-virtual.png
scripts/check-screen-png.py <board> /tmp/screen-hwtest.png
```

Expected: `OK 240x240 indexed PNG, ...` for both.

- [ ] **Step 7: Record the panel sign-off as outstanding**

No panel is attached to the bench board, so criterion 4 cannot be met here.
Compare `/tmp/screen-virtual.png` against the reference PNGs in `docs/display/`
to confirm the drawing itself is right, and record in the PR that the glass
check — colour, banding, tearing, offset on real hardware — is **outstanding**.
**Do not mark acceptance criterion 4 met.**

- [ ] **Step 8: Open the PR**

Rebase onto a fresh `origin/main` first, per the global PR workflow:

```bash
git fetch origin
git rebase origin/main
git push --force-with-lease -u origin claude/st7789-mipi-spi-migration-1a0d84
gh pr create --title "Move the panel to mipi_spi and update the dryer over the air" --body "$(cat <<'EOF'
## What

ili9xxx cannot buffer less than a full frame, so the ESP32-S2 never had the
~16,749-byte contiguous block mbedTLS needs for a TLS record and the 1.0.x
update entity could check for releases but never install one. This moves the
panel to `mipi_spi` with a reduced buffer on production, brings the update
entity back, and retires the ESPHome Device Builder path so there is one
documented update route.

`/screen.png` no longer reads the driver's private frame buffer. It
re-renders `draw_ui()` into its own 24-row band buffer, which works with any
driver and with a partial buffer.

## Measured

<!-- Fill in from Tasks 3 and 7. Quote real numbers only. -->
- Largest Free Block (production, 50% buffer):
- Redraw, per-band draw / SPI write / total:
- `took a long time for an operation` warnings after update:
- On-device install:
- Rollback after reboot:
- Physical panel checked by the user: **NOT DONE — no panel on the bench board**

## Outstanding

The glass has not been looked at. `mipi_spi` with a partial buffer and
`auto_clear_enabled: false` is exactly the combination that could band or tear,
and no board in this change had a panel attached. Colour fidelity, banding,
tearing and image offset must be confirmed on hardware before this ships to the
production unit.

## Trade-off accepted

Retiring Device Builder removes the only non-USB recovery path. A unit whose
updater cannot reach a working manifest must be reflashed over USB. This was
chosen deliberately; `docs/releasing.md` says so under **Recovery**.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 9: Watch CI and address the Copilot review**

Per the global PR workflow: watch the checks, fix any failure at its root and push; then wait for Copilot's review to land and address every comment. Do not consider the task done until CI is green and Copilot's review has been handled.

- [ ] **Step 10: Tag the release after merge**

```bash
scripts/release.sh
```

There is no longer a deadline on this — nothing resolves sources at the tag — but the manifest the update entity polls only refreshes when a release is published, so units stay on 1.1.0 until it runs.

---

## Self-Review

**Spec coverage.** Display split → Task 2. No colour shift → Task 2 Steps 2 and 8. Optimise-but-cap → Task 3. Mirror rewrite → Task 1. On-device updates → Task 4. Device Builder retired → Task 5. Docs and 1.2.0 → Task 6. Five builds, normalised-config diff, scenario shots, bench measurements, install-and-stay, `/screen.png`, panel sign-off → Tasks 2, 3 and 7.

**Known deviation.** The spec's writer-hijack approach for the mirror is replaced; the reason is documented under "Design deviation from the spec" above and should be folded back into the spec if it is revised.

**Type consistency.** `draw_ui(Display &, const UiState &, const UiAssets &)` is used with that exact signature in Task 1 Step 4 and Task 3 Step 4, matching `display_ui.h:243`. `set_display` takes `display::Display *` in both the header (Task 1 Step 3) and the schema (Task 1 Step 5). `BandDisplay::set_band_start(int)` is declared and called under that name. Substitutions `display_buffer_size` and `display_update_interval` are spelled identically in `display-st7789.yaml`, `production.yaml` and both test selectors.

**Ordering.** Task 1 lands before Task 2 on purpose: the driver-agnostic mirror is verified against the old driver first, so a `/screen.png` failure after Task 2 can only be the driver swap.
