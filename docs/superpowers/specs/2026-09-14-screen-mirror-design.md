# Screen mirror in Home Assistant — design

Date: 2026-09-14
Status: approved in conversation; spec written for review

## Goal

Show the live screen of a running dryer inside Home Assistant, first the
bench test board, later the production unit, so users can see what the
panel shows without standing in front of it. The board serves its own
frame buffer as an image over the web server it already runs; Home
Assistant's Generic Camera polls that image and presents it as a camera
entity on a dashboard card.

## Context and constraints

- The device builds run ESPHome 2026.1.4 on ESP-IDF with `web_server` on
  port 80. ESPHome's IDF web server dispatches every request through a
  list of `AsyncWebHandler`s (`canHandle` then `handleRequest`) and returns
  after `handleRequest` without sending anything itself, so a handler may
  stream its own reply. `AsyncWebServerRequest` converts to the raw
  `httpd_req_t *`, which gives access to `httpd_resp_set_type`,
  `httpd_resp_set_hdr` and `httpd_resp_send_chunk`. Every stock response
  type buffers its whole body in a `std::string`, which is why chunked
  sends from the raw handle are used instead.
- The ST7789 runs the `ili9xxx` driver with `color_palette: 8BIT`
  (`ILI9XXXColorMode::BITS_8`): the frame buffer is one RGB332 byte per
  pixel, row-major, native width 240 and height 240, so 57,600 bytes. The
  buffer pointer and colour mode are protected members of the driver and
  are read through a pointer-to-member on a helper class derived from
  `ILI9XXXDisplay`, which is standard C++ and needs no header patching.
  `Display::get_native_width()`, `get_native_height()` and
  `get_rotation()` are public.
- The SparkFun ESP32-S2 Thing Plus has no PSRAM and could not allocate a
  115 KB 16-bit frame buffer with WiFi, API and the web server up. Any
  design that copies the frame is out; the image must stream from the
  existing buffer with no allocation. The community component
  `esphome-display-screenshot` builds a 225 KB 16-bit BMP in PSRAM and is
  therefore not usable here, but it validates the pattern (BMP over the
  ESPHome web server, consumed by Home Assistant).
- The bench test board runs the virtual build at `<board>` (its IP address) and answers
  on its web server (HTTP 200 in 0.14 s from the Mac).
- Home Assistant's Generic Camera integration takes a still image URL, a
  content type (default `image/jpeg`) and a frame rate, is configured in the
  UI, and accepts only stills that PIL identifies as PNG, JPEG, GIF, SVG or
  WebP.
- This branch, `screen-mirror`, is stacked on `claude/display-mirroring-laptop-c13ab1`
  (PR #4, open) because it needs the split display packages from that
  branch. Its PR targets that branch until PR #4 merges, then `main`.
- The device-build equivalence convention does not apply: this is a
  feature, and `esphome config` dumps will legitimately differ (new
  component, new display id).

## Decisions made during brainstorming

| Question | Decision |
|---|---|
| What is mirrored | The real device's frame buffer, not a re-implementation of the layout in a Lovelace card |
| Transport | A GET endpoint on the existing ESPHome web server, streamed in chunks from the raw IDF request handle |
| Image format | 8-bit indexed PNG with stored deflate blocks, 58,688 bytes. BMP was the first choice; Home Assistant's Generic Camera validates stills with PIL and accepts only PNG, JPEG, GIF, SVG and WebP |
| Where it lives | A local external component `screen_mirror` under `esphome/components/`, wired by `packages/screen-mirror.yaml` |
| Which builds | Both device builds (production and virtual). Not the host build, which has no web server |
| Home Assistant side | Generic Camera entity with content type `image/png`, shown in a Picture Entity card |
| Concurrent redraw | Accepted: the handler reads while the main loop may draw; an occasional torn frame is fine for a preview |

## Non-goals

- MJPEG or any push streaming; the camera polls.
- JPEG, WebP or real deflate compression; the board has no spare RAM for an
  encoder, so the PNG uses stored blocks.
- Authentication on the endpoint beyond what `web_server` already applies.
- Any change to what the display draws.
- Touch or control from the camera card.
- Serving the host build's window.

## 1. Repo layout

```
esphome/
  components/
    screen_mirror/
      __init__.py          # schema: display_id, path; registers the component
      screen_mirror.h      # ScreenMirror: Component + AsyncWebHandler
      screen_mirror.cpp    # handler, PNG chunks, palette, chunked streaming
  packages/
    screen-mirror.yaml     # external_components (local) + screen_mirror: block
    display-st7789.yaml    # the ili9xxx display gains id: panel
  desiccant-dryer.yaml            # adds mirror: !include packages/screen-mirror.yaml
  desiccant-dryer-virtual.yaml    # same
docs/
  screen-in-ha.md          # endpoint, Home Assistant setup, limits
  superpowers/specs/2026-09-14-screen-mirror-design.md   # this file
```

`README.md` gains one sentence and `CLAUDE.md`'s layout paragraph names the
new package. The host selector is untouched. CI is untouched: the two
device jobs compile the component.

## 2. The component

### Python (`__init__.py`)

- `DEPENDENCIES = ["display"]`, `AUTO_LOAD = ["web_server_base"]`.
- Schema: `id` (`ScreenMirror`), `web_server_base_id` (generated,
  `cv.use_id(web_server_base.WebServerBase)`), `display_id`
  (`cv.use_id(ILI9XXXDisplay)` from `esphome.components.ili9xxx.display`,
  required), `path` (string, default `/screen.png`, must start with `/`).
  Wrapped in `cv.only_on_esp32`, because the handler uses the ESP32 httpd
  backend (`esp_http_server`) directly, which ESPHome loads for every ESP32
  build.
- `to_code`: `new_Pvariable(id, base)`, `set_display(display)`,
  `set_path(path)`, `register_component`.

### C++

`class ScreenMirror : public Component, public AsyncWebHandler` with
`base_`, `display_` (`ili9xxx::ILI9XXXDisplay *`) and `path_`.

- `setup()`: `base_->init()` then `base_->add_handler(this)`.
  `get_setup_priority()` returns `setup_priority::LATE`.
- `dump_config()`: logs the path and the frame size.
- `canHandle(request)`: `request->method() == HTTP_GET && request->url() == path_`; ESPHome's `url()` already strips any `?query`, so a cache-busting suffix still matches.
- `handleRequest(request)`:
  1. `httpd_req_t *req = *request;`
  2. Read the buffer pointer and colour mode through the helper
     `struct Peek : public ili9xxx::ILI9XXXDisplay` that exposes
     `static uint8_t *buffer(ILI9XXXDisplay *d)` and
     `static ILI9XXXColorMode mode(ILI9XXXDisplay *d)` via
     `d->*(&Peek::buffer_)` and `d->*(&Peek::buffer_color_mode_)`.
  3. If the buffer is null, the mode is not `BITS_8`, or
     `display_->get_rotation()` is not 0 degrees: reply
     `httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "screen_mirror: needs an 8-bit, unrotated frame buffer")`
     and log a warning once.
  4. Otherwise `w = get_native_width()`, `h = get_native_height()`; each
     PNG scanline is `w + 1` bytes (filter byte 0 plus the row, whose RGB332
     bytes are already the palette indices). Stored deflate blocks hold at
     most 65,535 bytes, so whole scanlines are grouped into blocks.
  5. `httpd_resp_set_type(req, "image/png")`,
     `httpd_resp_set_hdr(req, "Cache-Control", "no-store")`.
  6. Send, as chunks, stopping at the first send error:
     - the PNG signature and the IHDR chunk (8-bit, colour type 3, no
       interlace) with its CRC;
     - the PLTE chunk, 256 entries of `R,G,B` with each channel stretched to
       0..255, built at compile time with its CRC and kept in flash;
     - the IDAT chunk header (length known in advance), the zlib header
       `78 01`, then per block a 5-byte stored-block header and the
       scanlines, each copied into the setup-time scanline buffer so the
       filter byte travels with the row;
     - the Adler-32 of the scanlines, the IDAT CRC-32 (both computed while
       streaming), and the IEND chunk.

The only RAM is one scanline (241 bytes for 240 pixels) allocated at setup;
the palette chunk and the CRC table are compile-time constants in flash. One
request moves 58,688 bytes.

**History:** the first implementation served a bottom-up BMP of 58,678 bytes.
Home Assistant's Generic Camera rejected it ("URL did not return a valid
still image") because its still-image check accepts only PNG, JPEG, GIF, SVG
and WebP, so the endpoint became PNG; see plan Task 6.

## 3. Configuration

`esphome/packages/screen-mirror.yaml`:

```yaml
# Serves the panel's frame buffer as /screen.png on the web server so Home
# Assistant's Generic Camera can show the live screen. Device builds only:
# the host build has no web server. See docs/screen-in-ha.md.

external_components:
  - source:
      type: local
      path: components
    components: [screen_mirror]

screen_mirror:
  display_id: panel
```

`display-st7789.yaml`: the ili9xxx display gains `id: panel`. Both device
selectors add `mirror: !include packages/screen-mirror.yaml` after
`display:`. `path:` is relative to the config directory, so it resolves to
`esphome/components`.

## 4. Home Assistant

Settings, Devices & services, Add integration, Generic Camera:

| Field | Value |
|---|---|
| Still Image URL | `http://<board>/screen.png` (the board's address, or `http://desiccant-dryer-virtual.local/screen.png` if mDNS resolves from Home Assistant) |
| Content Type | `image/png` |
| Frame Rate (Hz) | 0.5 (the display redraws every 2 s) |
| Verify SSL certificate | off (plain HTTP) |

Name the entity "Dryer Screen". Add a Picture Entity card for it to the
dryer dashboard. The production unit gets a second camera with its own
address once it exists.

## 5. Docs

- `docs/screen-in-ha.md` (new, short): what the endpoint returns, how to
  fetch it with curl, the Home Assistant steps above, refresh behaviour,
  and the limits (torn frames possible; palette rounding is the panel's
  own; colour inversion and offset not reproduced; no auth).
- `README.md`: one sentence pointing at the doc.
- `CLAUDE.md`: the layout paragraph lists `screen-mirror.yaml` and
  `components/screen_mirror`; the conventions gain one line saying the
  frame endpoint is `/screen.png` on the device builds.

## 6. Verification

1. `esphome config` and `esphome compile` pass for both device builds.
2. Flash the bench board over the air:
   `esphome run esphome/desiccant-dryer-virtual.yaml --device "<board>"`.
   The boot log shows the component's `dump_config` line with the path
   and 240x240.
3. `curl -s "http://<board>/screen.png" -o screen.png`: 58,688 bytes,
   `Content-Type: image/png`. Decoded with ESPHome's own Python (Pillow and
   zlib): PIL reports the format as `png`, which is what Home Assistant
   checks; every chunk CRC and the zlib stream verify; size 240x240, mode
   `P`; pixel (0, 0) is index 0 (nothing draws
   there); pixel (231, 200), the right end of the humidity bar, is one of
   146 (grey outline, `909090`), 89 (green fill) or 244 (orange fill),
   depending on how far the board's simulated humidity has climbed; and
   row y=200 holds at least two distinct values between x=8 and x=231
   unless RH is at or above the swap threshold, when the full bar leaves
   a single fill colour. Viewed as an image,
   the image matches the panel: "AIR: A" at the top, the sensor lines,
   the bar, the IP at the bottom.
4. Two polls one second apart both succeed; the board's log shows no
   "took a long time" warning attributable to the request.
5. The user adds the Generic Camera in Home Assistant as in section 4 and
   sees the same frame on a Picture Entity card, updating within a few
   seconds of a change on the panel (toggle `Simulate Humidity` to force
   one).

## 7. Edge cases

- Client disconnects mid-frame: `httpd_resp_send_chunk` returns an error,
  the loop stops, nothing else is affected.
- Display redraw during a fetch: the frame may mix two updates. Accepted.
- Several clients polling: each request streams independently in the
  httpd task; the main loop is not blocked.
- `web_server` with `auth:` enabled later: `add_handler` wraps the handler
  in ESPHome's auth middleware, so the image is protected the same way.
- A build with `color_palette` other than `8BIT`, or a rotated display:
  the endpoint returns 500 with a clear message rather than a corrupt
  image.
- The host build never includes the package, so the `only_with_esp_idf`
  guard is never hit in practice.

## 8. Follow-ups (not in this work)

- Gzip or PNG if the transfer size ever matters (it is 58 KB every 2 s on
  the LAN today).
- A Home Assistant `image` entity via the native API if ESPHome ever
  supports one, which would remove the web server dependency.
- Real deflate compression would shrink the 58 KB to a few KB (Pillow gets
  2.2 KB for a typical screen) but needs an encoder and RAM the board does
  not have; the stored-block PNG is the compromise.
