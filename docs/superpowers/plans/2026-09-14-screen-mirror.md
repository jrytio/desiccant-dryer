# Screen Mirror Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the ST7789's frame buffer from the board as `/screen.png` on its existing web server, with no frame copy and no per-request allocation, so Home Assistant's Generic Camera can show the live dryer screen on a dashboard.

**Architecture:** A local ESPHome external component `screen_mirror` (Python schema plus a C++ class that is both a `Component` and an `AsyncWebHandler`) registers one GET path on `web_server_base`. On request it reads the `ili9xxx` driver's 8-bit RGB332 buffer through a pointer-to-member helper and streams an 8-bit indexed PNG (signature and IHDR, a 1 KB palette chunk from flash, stored deflate blocks of scanlines with CRC-32 and Adler-32 computed on the fly) with `httpd_resp_send_chunk` on the raw IDF request handle; the only RAM is one scanline allocated at setup. Tasks 1-5 describe the original BMP implementation as executed; Task 6 records the switch to PNG after Home Assistant rejected BMP stills. A package `packages/screen-mirror.yaml` wires it into both device builds; the display gains `id: panel`.

**Tech Stack:** ESPHome 2026.1.4 on ESP-IDF (`web_server_idf`, `esp_http_server`), `ili9xxx` driver in `BITS_8` mode, Home Assistant Generic Camera, Pillow (from ESPHome's own Python) for verification.

**Spec:** `docs/superpowers/specs/2026-09-14-screen-mirror-design.md`

## Global Constraints

- Work in the worktree `/Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1` on branch `screen-mirror` (stacked on `claude/display-mirroring-laptop-c13ab1`, PR #4). Never `cd` to the main checkout. Never use bare `git stash`. Never touch local `main`.
- ESPHome 2026.1.4 (`esphome` on PATH). Its own Python, which has Pillow, is `"$(dirname "$(readlink -f "$(which esphome)")")/python"`.
- The image must stream from the driver's existing buffer: no heap allocation for the frame, no second buffer. The board has no PSRAM.
- The buffer is one RGB332 byte per pixel, row-major, native 240 wide by 240 high. Output is an 8-bit indexed PNG with stored deflate blocks (see Task 6); file size for 240x240 is 58,688 bytes.
- Endpoint path `/screen.png`, content type `image/png`, header `Cache-Control: no-store`. Query strings after `?` are ignored when matching the path.
- The component is included in both device selectors and never in `desiccant-dryer-host.yaml`. `.github/workflows/build.yml` does not change. Nothing the display draws changes.
- The ili9xxx display id is `panel`. Component config key `screen_mirror`, option `display_id`, optional `path`.
- Bench test board: virtual build at `10.42.14.100`, reachable from the Mac; OTA uses the real `esphome/secrets.yaml` (gitignored; never print or commit it).
- The device-build equivalence convention does not apply to this feature; config dumps are expected to differ.
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. The PR description ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

## File map

| Path | Responsibility | Task |
|---|---|---|
| `esphome/components/screen_mirror/__init__.py` | Config schema and code generation | 1 |
| `esphome/components/screen_mirror/screen_mirror.h` | `ScreenMirror` class declaration | 1 |
| `esphome/components/screen_mirror/screen_mirror.cpp` | Handler: buffer access, BMP header, palette, chunked streaming | 1 |
| `esphome/packages/screen-mirror.yaml` | `external_components` (local) and the `screen_mirror:` block | 1 |
| `esphome/packages/display-st7789.yaml` | The ili9xxx display gains `id: panel` | 1 |
| `esphome/desiccant-dryer.yaml`, `esphome/desiccant-dryer-virtual.yaml` | Add `mirror:` package | 1 |
| `.superpowers/run/screen.bmp`, `screen.png` (gitignored) | Fetched frame and its PNG conversion for inspection | 2 |
| `docs/screen-in-ha.md` | Endpoint, Home Assistant setup, limits | 3 |
| `README.md`, `CLAUDE.md` | Pointers and layout | 3 |

---

### Task 1: The component, wired into both device builds

**Files:**
- Create: `esphome/components/screen_mirror/__init__.py`
- Create: `esphome/components/screen_mirror/screen_mirror.h`
- Create: `esphome/components/screen_mirror/screen_mirror.cpp`
- Create: `esphome/packages/screen-mirror.yaml`
- Modify: `esphome/packages/display-st7789.yaml` (the `display:` entry gains `id: panel`)
- Modify: `esphome/desiccant-dryer.yaml`, `esphome/desiccant-dryer-virtual.yaml` (one line each)

**Interfaces:**
- Consumes: the `ili9xxx` display in `display-st7789.yaml`; `web_server_base` from `platform-esp32.yaml`'s `web_server:`.
- Produces: config key `screen_mirror:` with `display_id` (required) and `path` (default `/screen.bmp`); C++ class `esphome::screen_mirror::ScreenMirror(web_server_base::WebServerBase *)` with `set_display(ili9xxx::ILI9XXXDisplay *)` and `set_path(const std::string &)`; a GET endpoint returning `image/bmp`.

- [ ] **Step 1: Show that the config key is unknown before the component exists**

Add the package to the virtual selector first (Step 5 below shows the full file), then run:

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && esphome config esphome/desiccant-dryer-virtual.yaml 2>&1 | grep -iE "screen_mirror|not found|Component not found|Failed" | head -3
```

Expected: an error naming `screen_mirror` (component or file not found). This is the failing check the rest of the task makes pass.

- [ ] **Step 2: Create `esphome/components/screen_mirror/__init__.py`**

```python
import esphome.codegen as cg
from esphome.components import web_server_base
from esphome.components.ili9xxx.display import ILI9XXXDisplay
from esphome.components.web_server_base import CONF_WEB_SERVER_BASE_ID
import esphome.config_validation as cv
from esphome.const import CONF_DISPLAY_ID, CONF_ID, CONF_PATH

# Serves an ili9xxx display's 8-bit frame buffer as a BMP on the web server.
# ESP-IDF only: the handler streams with esp_http_server directly so the
# 58 KB image never has to sit in RAM.

DEPENDENCIES = ["web_server_base", "display"]
AUTO_LOAD = ["web_server_base"]

screen_mirror_ns = cg.esphome_ns.namespace("screen_mirror")
ScreenMirror = screen_mirror_ns.class_("ScreenMirror", cg.Component)


def _validate_path(value):
    value = cv.string_strict(value)
    if not value.startswith("/"):
        raise cv.Invalid("path must start with '/'")
    return value


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(ScreenMirror),
            cv.GenerateID(CONF_WEB_SERVER_BASE_ID): cv.use_id(
                web_server_base.WebServerBase
            ),
            cv.Required(CONF_DISPLAY_ID): cv.use_id(ILI9XXXDisplay),
            cv.Optional(CONF_PATH, default="/screen.bmp"): _validate_path,
        }
    ).extend(cv.COMPONENT_SCHEMA),
    cv.only_with_esp_idf,
)


async def to_code(config):
    base = await cg.get_variable(config[CONF_WEB_SERVER_BASE_ID])
    var = cg.new_Pvariable(config[CONF_ID], base)
    await cg.register_component(var, config)
    disp = await cg.get_variable(config[CONF_DISPLAY_ID])
    cg.add(var.set_display(disp))
    cg.add(var.set_path(config[CONF_PATH]))
```

- [ ] **Step 3: Create `esphome/components/screen_mirror/screen_mirror.h`**

```cpp
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
```

- [ ] **Step 4: Create `esphome/components/screen_mirror/screen_mirror.cpp`**

```cpp
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
```

- [ ] **Step 5: Create the package and wire it in**

`esphome/packages/screen-mirror.yaml`:

```yaml
# Serves the panel's frame buffer as /screen.bmp on the web server so Home
# Assistant's Generic Camera can show the live screen. Device builds only:
# the host build has no web server. See docs/screen-in-ha.md.
# `path` is relative to the config directory, so this is esphome/components.

external_components:
  - source:
      type: local
      path: components
    components: [screen_mirror]

screen_mirror:
  display_id: panel
```

In `esphome/packages/display-st7789.yaml`, change the display entry's first lines from

```yaml
display:
  - platform: ili9xxx
    model: ST7789V
```

to

```yaml
display:
  - platform: ili9xxx
    id: panel
    model: ST7789V
```

In both `esphome/desiccant-dryer.yaml` and `esphome/desiccant-dryer-virtual.yaml`, add after the `display:` include line:

```yaml
  mirror: !include packages/screen-mirror.yaml
```

so each `packages:` block ends `draw`, `display`, `mirror`. Update the header comment of `esphome/desiccant-dryer.yaml` by adding the line `# Screen: packages/screen-mirror.yaml  (/screen.bmp for Home Assistant)` after the `# Wiring:` line. Do not touch `esphome/desiccant-dryer-host.yaml`.

- [ ] **Step 6: Validate both device configs**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && mkdir -p .superpowers/run && for y in desiccant-dryer desiccant-dryer-virtual; do if esphome config esphome/$y.yaml > .superpowers/run/config-$y.txt 2>&1; then echo "VALID $y: $(grep -c '^screen_mirror:' .superpowers/run/config-$y.txt) screen_mirror block(s), path $(grep -A3 '^screen_mirror:' .superpowers/run/config-$y.txt | grep path | head -1)"; else echo "INVALID $y"; tail -25 .superpowers/run/config-$y.txt; fi; done; echo "host untouched: $(git diff --stat -- esphome/desiccant-dryer-host.yaml | wc -l | tr -d ' ') changed lines"
```

Expected: `VALID desiccant-dryer: 1 screen_mirror block(s), path     path: /screen.bmp`, the same for `desiccant-dryer-virtual`, and `host untouched: 0 changed lines`. A Python error here points at `__init__.py`; fix and re-run.

- [ ] **Step 7: Compile the virtual build, then the production build**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && esphome compile esphome/desiccant-dryer-virtual.yaml > .superpowers/run/compile-virtual.txt 2>&1; tail -3 .superpowers/run/compile-virtual.txt; grep -nE "error|Error" .superpowers/run/compile-virtual.txt | grep -i screen_mirror | head
```

Use a 600000 ms timeout; a full ESP-IDF build takes a few minutes. Expected: `[SUCCESS]` and no error lines mentioning `screen_mirror`. If the compiler rejects the pointer-to-member in `Peek`, the error names `buffer_` or `buffer_color_mode_`; report it with the exact message rather than working around it. Then:

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && esphome compile esphome/desiccant-dryer.yaml > .superpowers/run/compile-prod.txt 2>&1; tail -3 .superpowers/run/compile-prod.txt
```

Expected: `[SUCCESS]`.

- [ ] **Step 8: Commit**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && git add esphome/components/screen_mirror esphome/packages/screen-mirror.yaml esphome/packages/display-st7789.yaml esphome/desiccant-dryer.yaml esphome/desiccant-dryer-virtual.yaml && git commit -m "Serve the panel's frame buffer as /screen.bmp for Home Assistant

A local external component, screen_mirror, registers one GET path on the
web server the device builds already run and streams the ili9xxx 8-bit
buffer as a bottom-up indexed BMP with chunked sends, so the 58 KB image
never sits in RAM. Both device builds include it; the host build does
not.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git log --oneline -1
```

---

### Task 2: Flash the bench board and verify the image

**Files:**
- Create (gitignored): `.superpowers/run/screen.bmp`, `.superpowers/run/screen.png`, `.superpowers/run/screen-headers.txt`

**Interfaces:**
- Consumes: the virtual build compiled in Task 1; the bench board at `10.42.14.100`; `esphome/secrets.yaml` for the OTA password.
- Produces: a decoded frame the controller inspects visually.

- [ ] **Step 1: Confirm the board is up and does not serve the image yet**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && curl -s -m 5 -o /dev/null -w "root %{http_code}\n" http://10.42.14.100/ && curl -s -m 5 -o /dev/null -w "screen %{http_code}\n" http://10.42.14.100/screen.bmp
```

Expected: `root 200` and `screen 000` (no handler and no not-found page yet, so the server closes the connection without a status line). If root does not answer, stop and report BLOCKED: the board is off or moved.

- [ ] **Step 2: Upload over the air**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && esphome upload esphome/desiccant-dryer-virtual.yaml --device 10.42.14.100 > .superpowers/run/upload.txt 2>&1; tail -4 .superpowers/run/upload.txt
```

Use a 300000 ms timeout. Expected: the tail shows the OTA progress reaching 100 % and `INFO Upload took ...` / `OTA successful`. The board reboots.

- [ ] **Step 3: Fetch the frame with headers**

Wait for the board to be back (poll until the root answers), then fetch:

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && for i in $(seq 1 30); do curl -s -m 2 -o /dev/null http://10.42.14.100/ && break; perl -e 'select(undef,undef,undef,1)'; done; curl -s -m 10 -D .superpowers/run/screen-headers.txt -o .superpowers/run/screen.bmp http://10.42.14.100/screen.bmp; grep -iE "^HTTP|content-type|cache-control|transfer-encoding" .superpowers/run/screen-headers.txt; ls -l .superpowers/run/screen.bmp | awk '{print $5, $9}'
```

Expected: `HTTP/1.1 200 OK`, `Content-Type: image/bmp`, `Cache-Control: no-store`, `Transfer-Encoding: chunked`, and a file of exactly `58678` bytes. A `500` here means the buffer check failed; the board log (`esphome logs esphome/desiccant-dryer-virtual.yaml --device 10.42.14.100`, run for a few seconds) shows the warning.

- [ ] **Step 4: Decode and check the frame**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && "$(dirname "$(readlink -f "$(which esphome)")")/python" - <<'EOF'
from PIL import Image
im = Image.open(".superpowers/run/screen.bmp")
print("size", im.size, "mode", im.mode)
px = im.load()
print("p(0,0)", px[0, 0])
print("p(231,200)", px[231, 200], "expected one of 146 grey / 89 green / 244 orange")
row = {px[x, 200] for x in range(8, 232)}
print("distinct values on row 200 x=8..231:", len(row))
nonblack = sum(1 for y in range(240) for x in range(240) if px[x, y] != 0)
print("non-black pixels:", nonblack)
im.convert("RGB").save(".superpowers/run/screen.png")
print("wrote .superpowers/run/screen.png")
EOF
```

Expected: `size (240, 240) mode P`, `p(0,0) 0`, `p(231,200)` one of 146, 89 or 244, at least 2 distinct values on row 200 (a single value if the humidity bar is completely full), and a few thousand non-black pixels. Then the controller views `.superpowers/run/screen.png` and confirms it shows the dryer screen: "AIR: A" (or B) at the top, the humidity and temperature lines, the bar, the IP at the bottom.

- [ ] **Step 5: Two fetches a second apart, and the board is unaffected**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && for i in 1 2; do curl -s -m 10 -o /dev/null -w "fetch $i: %{http_code} %{size_download} bytes in %{time_total}s\n" http://10.42.14.100/screen.bmp; perl -e 'select(undef,undef,undef,1)'; done; perl -e 'alarm 12; exec @ARGV' esphome logs esphome/desiccant-dryer-virtual.yaml --device 10.42.14.100 > .superpowers/run/board-log.txt 2>&1; grep -cE "took a long time|\[E\]" .superpowers/run/board-log.txt
```

Expected: two lines `200 58678 bytes` each well under a second, and `0` matching log lines during the 12 s window. Nothing to commit in this task; record the outputs in the report.

---

### Task 3: Documentation

**Files:**
- Create: `docs/screen-in-ha.md`
- Modify: `README.md` (one sentence), `CLAUDE.md` (layout paragraph and one convention line)

- [ ] **Step 1: Create `docs/screen-in-ha.md`**

````markdown
# The dryer screen in Home Assistant

Both device builds serve the panel's frame buffer as an image:

```bash
curl -o screen.bmp http://10.42.14.100/screen.bmp     # bench board
```

It is a 240x240 8-bit BMP, 58,678 bytes, exactly what the ST7789 is
showing, palette rounding included. The board streams it straight from the
display buffer, so a request costs no RAM; the display keeps redrawing
every 2 s while you fetch, so a frame can occasionally mix two updates.

## Camera entity

Settings, Devices & services, Add integration, **Generic Camera**:

| Field | Value |
|---|---|
| Still Image URL | `http://10.42.14.100/screen.bmp` (the board's address; `desiccant-dryer-virtual.local` if mDNS resolves from Home Assistant) |
| Stream Source URL | leave empty |
| Content Type | `image/bmp` |
| Frame Rate (Hz) | `0.5` (the display redraws every 2 s) |
| Verify SSL certificate | off (plain HTTP) |

Name it "Dryer Screen". Add a **Picture Entity** card for it to the dryer
dashboard; it refreshes on its own. The production unit gets a second
camera pointed at its own address.

## Limits

- The image is the drawing as the driver holds it. The panel's
  `invert_colors` and any offset are applied by the panel, not the buffer,
  so they do not appear here.
- No authentication beyond what `web_server` applies; the web server is
  already open on the LAN.
- The host preview build has no web server and no endpoint; use its
  window instead (`docs/host-preview.md`).
- The endpoint returns HTTP 500 with a short message if the display is
  not in `color_palette: 8BIT` or is rotated. Both device builds are.
````

- [ ] **Step 2: Add the README sentence**

In `README.md`, extend the sentence that lists the docs so it ends with `` `docs/host-preview.md` for the display on your Mac, `docs/screen-in-ha.md` for the live screen in Home Assistant. `` (replace the current ending `` `docs/host-preview.md` for the display on your Mac. ``).

- [ ] **Step 3: Update `CLAUDE.md`**

In the layout paragraph, after the sentence ending `` (window on the Mac). ``, insert: `` `packages/screen-mirror.yaml` (device builds only) serves the panel's frame buffer as `/screen.bmp` through the local component `esphome/components/screen_mirror`. ``

In the working conventions, after the bullet about the host preview, add:

```
- The device builds serve the live screen at `http://<board>/screen.bmp`
  for Home Assistant's Generic Camera (docs/screen-in-ha.md). It streams
  from the ST7789's 8-bit buffer; keep `color_palette: 8BIT` and rotation
  0 or the endpoint returns 500.
```

- [ ] **Step 4: Check and commit**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && grep -n "screen-in-ha\|screen.bmp" README.md CLAUDE.md docs/screen-in-ha.md | head && git add docs/screen-in-ha.md README.md CLAUDE.md && git commit -m "Document the screen endpoint and the Home Assistant camera setup

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git log --oneline -1
```

Expected: matches in all three files, then the commit line.

---

### Task 4: Open the stacked pull request

The base is PR #4's branch, because this work needs the display split. After PR #4 merges, the PR is retargeted to `main` (GitHub does this on its own when the base branch is deleted after merge) and rebased if needed.

- [ ] **Step 1: Confirm the base branch has not moved**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && git fetch origin && git log --oneline HEAD..origin/claude/display-mirroring-laptop-c13ab1 && echo "(empty above = base unchanged)" && git log --oneline origin/claude/display-mirroring-laptop-c13ab1..HEAD
```

If the first log is not empty (PR #4 gained commits from its Copilot review), rebase with `git rebase origin/claude/display-mirroring-laptop-c13ab1`, re-run Task 1 Step 6 and, if `display-st7789.yaml` or the selectors conflicted, Task 1 Step 7 for the virtual build.

- [ ] **Step 2: Push and open the PR**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && git push --force-with-lease -u origin screen-mirror && gh pr create --base claude/display-mirroring-laptop-c13ab1 --title "Serve the panel's frame buffer as /screen.bmp for Home Assistant" --body "$(cat <<'EOF'
## Summary

- Adds a local ESPHome external component, `screen_mirror`, that registers `GET /screen.bmp` on the web server the device builds already run and streams the ST7789's 8-bit frame buffer as a bottom-up indexed BMP with chunked sends. Nothing is allocated for the frame; the palette is 1 KB of flash.
- `packages/screen-mirror.yaml` wires it into both device builds; the display gains `id: panel`. The host build is untouched.
- `docs/screen-in-ha.md` covers the Home Assistant Generic Camera setup (content type `image/bmp`, 0.5 Hz) and the limits.

Stacked on #4 (needs the split display packages); retarget to `main` once #4 merges.

## Verification

- Both device builds compile with ESPHome 2026.1.4.
- Flashed to the bench board over the air: `/screen.bmp` returns 200, `image/bmp`, 58,678 bytes, decodes as a 240x240 palette image showing the dryer screen; two fetches a second apart succeed with no board log warnings.
- Home Assistant camera card: pending the user's setup.

Spec: `docs/superpowers/specs/2026-09-14-screen-mirror-design.md`
Plan: `docs/superpowers/plans/2026-09-14-screen-mirror.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: a PR URL. The controller then binds it and watches CI and the Copilot review as for PR #4.

---

### Task 5: Home Assistant camera (user at Home Assistant)

- [ ] **Step 1:** Add the Generic Camera exactly as the table in `docs/screen-in-ha.md`, pointed at `http://10.42.14.100/screen.bmp`, content type `image/bmp`, 0.5 Hz. Expected: the integration's preview shows the dryer screen.
- [ ] **Step 2:** Add a Picture Entity card for `camera.dryer_screen` to the dryer dashboard. Expected: the card shows the same frame as the board.
- [ ] **Step 3:** Toggle `Simulate Humidity` on the virtual device. Expected: within a few seconds the card's humidity line turns orange and reads "SIM", matching the panel.
- [ ] **Step 4:** Report anything that differs, with a screenshot, in the conversation and on the PR.

---

### Task 6: Serve PNG instead of BMP (Home Assistant rejects BMP stills)

**Why:** Home Assistant's Generic Camera config flow opens the still with PIL and accepts only `png`, `jpeg`, `gif`, `svg+xml` and `webp` (`SUPPORTED_IMAGE_TYPES` in `homeassistant/components/generic/config_flow.py`); anything else fails with "URL did not return a valid still image", regardless of the content type field. Reproduced locally: PIL reports the served frame as `bmp`. An 8-bit indexed PNG can be streamed the same zero-copy way by using stored (uncompressed) deflate blocks: a PNG scanline is one filter byte plus the row, so the RGB332 buffer bytes are the palette indices unchanged. The image grows from 58,678 to 58,688 bytes.

**Files:**
- Modify: `esphome/components/screen_mirror/screen_mirror.cpp` (whole file replaced)
- Modify: `esphome/components/screen_mirror/screen_mirror.h` (row buffer member, comment)
- Modify: `esphome/components/screen_mirror/__init__.py` (default path)
- Modify: `esphome/packages/screen-mirror.yaml` (comment)
- Modify: `docs/screen-in-ha.md`, `CLAUDE.md`, the spec and this plan's Global Constraints (BMP references)

**Interfaces:**
- Consumes: the same driver buffer as before.
- Produces: `GET /screen.png`, `image/png`, an 8-bit indexed PNG with one stored deflate block per up to 271 rows; 58,688 bytes for 240x240. `ScreenMirror::row_` is a `std::vector<uint8_t>` of native width + 1 bytes allocated once in `setup()`.

- [ ] **Step 1: Reproduce the rejection (the failing test)**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && curl -s -m 10 -o .superpowers/run/before.img http://10.42.14.100/screen.bmp && "$(dirname "$(readlink -f "$(which esphome)")")/python" -c "
from PIL import Image
im = Image.open('.superpowers/run/before.img'); fmt = im.format.lower()
print('format', fmt, '-> accepted by Home Assistant:', fmt in {'png','jpeg','gif','svg+xml','webp'})"
```

Expected: `format bmp -> accepted by Home Assistant: False`.

- [ ] **Step 2: Replace `esphome/components/screen_mirror/screen_mirror.cpp`**

```cpp
#include "screen_mirror.h"

#include <esp_http_server.h>

#include <algorithm>
#include <cstring>

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
  this->base_->init();
  this->base_->add_handler(this);
}

void ScreenMirror::dump_config() {
  ESP_LOGCONFIG(TAG, "Screen mirror:\n  Path: %s\n  Frame: %dx%d, 8-bit indexed PNG", this->path_.c_str(),
                this->display_->get_native_width(), this->display_->get_native_height());
}

bool ScreenMirror::canHandle(AsyncWebServerRequest *request) const {
  // url() already strips any ?query, so a cache-busting suffix still matches.
  return request->method() == HTTP_GET && request->url() == this->path_;
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
```

- [ ] **Step 3: Update `esphome/components/screen_mirror/screen_mirror.h`**

Add `#include <vector>` after `#include <string>`. Replace the class comment with:

```cpp
// Answers GET <path> with the display's frame buffer as an 8-bit indexed PNG
// (stored deflate blocks, so no compressor and no frame copy). Rows are
// streamed with chunked sends; the only RAM is one scanline allocated at
// setup, and the palette and CRC table live in flash.
```

Add the member `std::vector<uint8_t> row_;` after `std::string path_;`.

- [ ] **Step 4: Default path and comments**

In `esphome/components/screen_mirror/__init__.py`: the header comment's first line becomes `# Serves an ili9xxx display's 8-bit frame buffer as a PNG on the web server.` and the default becomes `cv.Optional(CONF_PATH, default="/screen.png"): _validate_path,`. In `esphome/packages/screen-mirror.yaml` the comment's first line becomes `# Serves the panel's frame buffer as /screen.png on the web server so Home`.

- [ ] **Step 5: Docs, spec and plan**

`docs/screen-in-ha.md`: every `/screen.bmp` becomes `/screen.png` and `screen.bmp` becomes `screen.png`; the sentence `It is a 240x240 8-bit BMP, 58,678 bytes, exactly what the ST7789 is\nshowing, palette rounding included.` becomes `It is a 240x240 8-bit indexed PNG, 58,688 bytes (uncompressed, so it\nstreams without a compressor), exactly what the ST7789 is showing,\npalette rounding included. Home Assistant's Generic Camera accepts only\nPNG, JPEG, GIF, SVG and WebP stills, which is why it is not a BMP.`; the table row `| Content Type | \`image/bmp\` |` becomes `| Content Type | \`image/png\` |`.

`CLAUDE.md`: in the conventions bullet, `/screen.bmp` becomes `/screen.png`.

Spec `docs/superpowers/specs/2026-09-14-screen-mirror-design.md`: the Decisions row `| Image format | ... |` becomes `| Image format | 8-bit indexed PNG with stored deflate blocks, 58,688 bytes. BMP was the first choice; Home Assistant's Generic Camera validates stills with PIL and accepts only PNG, JPEG, GIF, SVG and WebP |`; every other `/screen.bmp` becomes `/screen.png`; add to the end of section 2 (before `## 3.`) the paragraph: `**Amended during execution:** the endpoint serves PNG, not BMP. Structure: signature, IHDR (8-bit, colour type 3), a PLTE chunk built at compile time, one IDAT chunk whose zlib stream is stored deflate blocks of whole scanlines (filter byte 0 plus the row, which is already the palette index), Adler-32 and CRC-32 computed while streaming, IEND. See plan Task 6.`

This plan file: in Global Constraints, replace the sentence starting `Output is a bottom-up 8-bit indexed BMP:` through `File size for 240x240 is 58,678 bytes.` with `Output is an 8-bit indexed PNG with stored deflate blocks (see Task 6); file size for 240x240 is 58,688 bytes.`, and `Endpoint path \`/screen.bmp\`, content type \`image/bmp\`` with `Endpoint path \`/screen.png\`, content type \`image/png\``.

- [ ] **Step 6: Validate, compile, flash, verify**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && for y in desiccant-dryer desiccant-dryer-virtual; do esphome config esphome/$y.yaml > .superpowers/run/config-$y-png.txt 2>&1 && echo "VALID $y $(grep -c 'path: /screen.png' .superpowers/run/config-$y-png.txt) png path(s)" || { echo "INVALID $y"; tail -20 .superpowers/run/config-$y-png.txt; }; done; esphome compile esphome/desiccant-dryer-virtual.yaml > .superpowers/run/compile-virtual-png.txt 2>&1; tail -2 .superpowers/run/compile-virtual-png.txt; grep -n "error" .superpowers/run/compile-virtual-png.txt | grep -i screen_mirror | head -5
```

Use a 600000 ms timeout. Expected: both VALID with `1 png path(s)`, `[SUCCESS]`, no errors. A constexpr evaluation error names `PlteChunk` or `Crc32Table`; report it verbatim rather than restructuring.

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && esphome upload esphome/desiccant-dryer-virtual.yaml --device 10.42.14.100 > .superpowers/run/upload-png.txt 2>&1; tail -2 .superpowers/run/upload-png.txt; for i in $(seq 1 30); do curl -s -m 2 -o /dev/null http://10.42.14.100/ && break; perl -e 'select(undef,undef,undef,1)'; done; curl -s -m 10 -D .superpowers/run/png-headers.txt -o .superpowers/run/screen.png "http://10.42.14.100/screen.png?t=2"; grep -iE "^HTTP|content-type" .superpowers/run/png-headers.txt; ls -l .superpowers/run/screen.png | awk '{print $5}'; curl -s -m 5 -o /dev/null -w "old bmp path now: %{http_code}\n" http://10.42.14.100/screen.bmp
```

Expected: OTA success, `HTTP/1.1 200 OK`, `Content-Type: image/png`, `58688`, and the old path `000` or `404`.

Then decode and verify with ESPHome's Python (Pillow and zlib); write this to `.superpowers/run/check-png.py` and run it with `"$(dirname "$(readlink -f "$(which esphome)")")/python" .superpowers/run/check-png.py`:

```python
import io, struct, zlib
from PIL import Image
data = open(".superpowers/run/screen.png", "rb").read()
im = Image.open(io.BytesIO(data)); im.load()   # load() verifies chunk CRCs and the zlib stream
fmt = im.format.lower()
print("format", fmt, "size", im.size, "mode", im.mode, "bytes", len(data))
print("accepted by Home Assistant's generic camera:", fmt in {"png", "jpeg", "gif", "svg+xml", "webp"})
pos, idat, types = 8, b"", []
while pos < len(data):
    ln, typ = struct.unpack(">I4s", data[pos:pos + 8]); body = data[pos + 8:pos + 8 + ln]
    crc = struct.unpack(">I", data[pos + 8 + ln:pos + 12 + ln])[0]
    assert zlib.crc32(typ + body) & 0xFFFFFFFF == crc, ("bad CRC in", typ)
    types.append(typ.decode()); idat += body if typ == b"IDAT" else b""; pos += 12 + ln
raw = zlib.decompress(idat)   # verifies the Adler-32
print("chunks", types, "all CRCs ok; scanline bytes", len(raw), "expected", 240 * 241)
px = im.load(); print("p(0,0)", px[0, 0], "p(231,200)", px[231, 200])
im.convert("RGB").save(".superpowers/run/screen-from-png.png"); print("wrote .superpowers/run/screen-from-png.png")
```

Expected: `format png size (240, 240) mode P bytes 58688`, `accepted ... True`, chunks `['IHDR', 'PLTE', 'IDAT', 'IEND']` with all CRCs ok and `scanline bytes 57840 expected 57840`, `p(0,0) 0`. The controller views the written PNG.

- [ ] **Step 7: Commit and update the PR**

```bash
cd /Users/josh/GitHub/desiccant-dryer/.claude/worktrees/display-mirroring-laptop-c13ab1 && git add esphome/components/screen_mirror esphome/packages/screen-mirror.yaml docs/screen-in-ha.md CLAUDE.md docs/superpowers/specs/2026-09-14-screen-mirror-design.md docs/superpowers/plans/2026-09-14-screen-mirror.md && git commit -m "screen_mirror: serve an indexed PNG, which Home Assistant accepts, not BMP

Home Assistant's Generic Camera opens the still with PIL and accepts only
PNG, JPEG, GIF, SVG and WebP, so the BMP failed setup with \"URL did not
return a valid still image\". The endpoint is now /screen.png: an 8-bit
indexed PNG whose zlib stream is stored deflate blocks of whole
scanlines, so it still streams straight from the driver buffer with no
compressor; CRC-32 and Adler-32 are computed on the fly, the palette and
CRC table are compile-time constants in flash, and the only RAM is one
scanline allocated at setup. 58,688 bytes for 240x240.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git push origin screen-mirror && git log --oneline -1
```

Then update the PR description so it no longer says BMP: fetch the body with `gh pr view 5 --json body -q .body > .superpowers/run/pr5-body.md`, edit that file so every `BMP` becomes `PNG`, `/screen.bmp` becomes `/screen.png`, `58,678` becomes `58,688`, and add under Summary the bullet `- Serves PNG rather than BMP: Home Assistant's Generic Camera validates stills with PIL and accepts only PNG, JPEG, GIF, SVG and WebP.`; then `gh pr edit 5 --body-file .superpowers/run/pr5-body.md`.
