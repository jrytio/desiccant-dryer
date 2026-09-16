# ST7789 on mipi_spi, and on-device firmware updates

**Goal.** Give the production dryer enough contiguous heap to install its own
firmware over HTTPS, by moving the ST7789 panel from `ili9xxx` to ESPHome's
`mipi_spi` driver with a reduced frame buffer. With the block available, the
`update:` entity comes back and Home Assistant alone updates the unit, so the
ESPHome Device Builder adoption path is retired. The test builds keep
`/screen.png` for checking screen changes without hardware.

## Why the frame buffer is the constraint

Measured 2026-09-16 on the real board, ESPHome 2026.9.0. mbedTLS needs one
contiguous ~16,749-byte block for a TLS record, and the board never had it.

| Build | Largest free block | Free heap | On-device install |
|---|---|---|---|
| `ili9xxx`, `color_palette: 8BIT` | 14,848 B | ~47 KB | fails `alloc(16749 bytes) failed` |
| same, `web_server` removed | 14,848 B | ~47 KB | fails identically |
| `mipi_spi`, `color_depth: 8bit`, `buffer_size: 25%` | 55,296 B | ~92 KB | succeeded, `Update complete` |

The web server is not the problem and neither is the ESPHome version (2026.8.2
and 2026.9.0 ship the same ESP-IDF v5.5.5 and a byte-identical `update`
component). `ili9xxx` cannot buffer less than a full frame: `get_buffer_length_()`
is hard-coded to `width * height`, so 240x240x1 = 57,600 B is its floor.

## The redraw multiplier — established before designing, not discovered late

`MipiSpiBuffer::update()` (ESPHome `components/mipi_spi/mipi_spi.h`) does not
render once into a partial buffer. It loops over bands and **re-runs the whole
writer lambda for every band**, discarding pixels outside the current band in
`draw_pixel_at`:

```cpp
auto increment = (this->get_height_internal() / FRACTION / ROUNDING) * ROUNDING;
for (this->start_line_ = 0; this->start_line_ < this->get_height_internal();
     this->start_line_ = this->end_line_) {
  this->end_line_ = clamp_at_most(this->start_line_ + increment, ...);
  (*this->writer_)(*this);          // the entire draw_ui(), once per band
  this->write_to_display_(...);
}
```

So `buffer_size` is a direct multiplier on draw cost. The observed numbers match:
the `ili9xxx` build ran `draw_ui()` once (historically ~480 ms), the `mipi_spi`
25% build logged `display took a long time for an operation (1401-1837 ms)`,
which is about 4 x 460 ms.

| `buffer_size` | writer runs | est. redraw | buffer | heap freed |
|---|---|---|---|---|
| 100% | 1x | ~480 ms | 57,600 B | none — no TLS win |
| 50% | 2x | ~960 ms | 28,800 B | ~29 KB |
| 25% | 4x | ~1,800 ms | 14,400 B | ~43 KB |

**No `buffer_size` gives both a free contiguous block and a ~500 ms redraw.**
The only lever that escapes the trade is making one pass of `draw_ui()` cheaper.

### What a slow redraw actually costs

ESPHome has no preemption: the display update and the `apply_outputs` interval
both run in `loop()`. A long redraw therefore **delays** the 5 s control tick; it
never skips it. Outputs are re-asserted late, not dropped, and the invariant that
outputs are applied from state every tick still holds. On minute-scale thermal
dynamics a 1-2 s delay is very unlikely to matter. This is stated plainly here
because the decision below trades against it.

## Decisions

- **`mipi_spi` with two profiles from one package.** `packages/display-st7789.yaml`
  keeps the SPI bus, LEDC backlight, pin map and `invert_colors` byte-identical
  and swaps the platform. It declares `display_buffer_size` and
  `display_update_interval` as substitutions with its own defaults; selectors
  override them, because substitutions in the main file win over package ones.

  | Selector | `display_buffer_size` | `display_update_interval` |
  |---|---|---|
  | production | tuned, starting at `50%` | `5s` |
  | virtual, hw-test | `100%` | `5s` |
  | host, scenarios | n/a — `display-sdl.yaml`, unchanged | n/a |

- **No colour shift.** `color_depth: 8bit` replaces `color_palette: 8BIT`.
  mipi_spi's 8-bit `convert_color` is `(r & 0xE0) | (g & 0xE0) >> 3 | b >> 6` —
  the same RGB 3-3-2 grid every designed colour already sits on. `color_depth:
  8bit` is only valid on a single-wire SPI bus, which this is.

- **Optimise the draw, but cap the effort.** mipi_spi at VERBOSE already logs
  `Drawing from line N took Xms` and `Write to display took Xms` per band, which
  separates draw cost from SPI cost with no new instrumentation. Procedure:
  flash a VERBOSE build, read the split, then take only the obvious wins — most
  likely the 240x240 `schematic.svg` blit and the full-screen `it.fill()`, which
  are re-run whole on every band. If the redraw does not come under ~500 ms after
  those, stop: raise production's `update_interval` far enough to bound the tick
  delay and report the real measured number. Do not chase it further, and do not
  restate the acceptance bar as met when it is not.

- **The screen mirror stops reaching into the driver.** `screen_mirror` currently
  defeats access control on `ILI9XXXDisplay` through a `Peek` struct to read
  `buffer_`, `buffer_color_mode_` and `writer_`. `MipiSpiBuffer` is a template
  with fifteen-odd parameters and a protected buffer; porting the hack would be
  far worse than the hack it replaces, and with `buffer_size < 100%` there is no
  full frame in RAM to read at all.

  Instead the mirror renders into **its own** `display::Display`, which is
  already the proven pattern in this repo: `packages/preview_capture.h` does
  exactly this on the host build, snapping each pixel to RGB 3-3-2. The device
  mirror keeps the existing writer-hijack purely to obtain `ui_draw`, then
  replays that writer against a band-sized scratch buffer and streams PNG rows as
  it goes. PNG is row-sequential, so band rendering falls out naturally.

  This knows nothing about the driver, costs a band rather than a frame, and
  cannot be broken by an ESPHome driver refactor. Test builds still use `100%`
  so the panel path on the bench stays simple.

- **One update route: on-device, pull-only.** The 1.0.x block returns to
  `packages/release.yaml`: `http_request` (`verify_ssl: true`,
  `buffer_size_rx: 1024`), `ota: platform: http_request`, and the `update:`
  entity polling the esp-web-tools manifest on GitHub **Pages**. The
  hard-won reason keeps its comment: the release download URL redirects to an
  RSA-certificate host with a ~900-byte signed URL, and the S2 has too little
  free heap for that second handshake. The Pages-publishing half of
  `.github/workflows/release.yml` was never removed, so the server side already
  works.

  Production still has **no inbound OTA server**, so the property that an
  unauthenticated LAN host cannot reflash a mains controller is preserved:
  updates are strictly pull-based.

- **ESPHome Device Builder is retired.** Delete `esphome/desiccant-dryer-adopt.yaml`,
  `packages/ui-code-remote.yaml`, `packages/ota-adopted.yaml` and the
  `dashboard_import` block in `packages/production.yaml`.
  `packages/api-provisioned.yaml` **stays**: it is the flashed image's runtime
  API-key provisioning, not Device Builder plumbing.

  Side effect worth having: nothing resolves sources at a tag any more, so
  `scripts/release.sh` no longer has to run immediately after a version bump
  merges.

  **Accepted risk, recorded deliberately.** This removes the recovery path for a
  unit whose updater cannot reach a working manifest. With no inbound OTA, such a
  unit needs USB. This was chosen knowingly in favour of one documented route;
  `docs/releasing.md` must say so rather than imply updates can never wedge.

## Files

Changed: `packages/display-st7789.yaml` (driver), `packages/production.yaml`
(substitutions, drop `dashboard_import`), `packages/release.yaml` (update
entity), `desiccant-dryer-virtual.yaml` and `desiccant-dryer-hw-test.yaml`
(substitutions), `components/screen_mirror/*` (rewrite), `esphome/version.yaml`.

Deleted: `desiccant-dryer-adopt.yaml`, `packages/ui-code-remote.yaml`,
`packages/ota-adopted.yaml`.

Unchanged: `components/dryer_ui/display_ui.h` (generic `display::Display` API
only, so it ports as-is), `packages/display-draw.yaml`, `packages/display-sdl.yaml`,
`packages/base.yaml`.

Version: **1.2.0** — behaviour change, minor bump.

## Docs to correct

- `CLAUDE.md` — the `color_palette: 8BIT` platform decision, the layout section's
  description of the display packages, the production/adoption bullet, and the
  `/screen.png` note.
- `docs/releasing.md` — rewritten to the single on-device route, including the
  recovery caveat above.
- `docs/screen-in-ha.md` — the mirror no longer streams the panel's buffer.
- `docs/hardware-bringup.md` §4.
- `docs/host-preview.md`.

## Verification

1. All five selectors compile under 2026.9.0 in Docker
   (`ghcr.io/esphome/esphome:2026.9.0`; host and scenarios need `libsdl2-dev`
   and `g++` installed in the container first, as `.github/workflows/build.yml`
   does). Local CLI is 2026.8.2, below `min_version`.
2. `scripts/normalize-config.py` diff of `esphome config` before and after, to
   show nothing moved that was not meant to.
3. `scripts/scenario-shots.sh` re-run and the PNGs in `docs/display/` reviewed.
   These render through SDL and **will not** catch a mipi_spi regression; the
   physical panel has to be looked at by the user.
4. Bench board: Largest Free Block comfortably above 16,749 B with margin;
   redraw timing from the VERBOSE band logs; no missed 5 s control ticks.
5. A published release installs on-device, reports `Update complete`, and the
   new image **boots and stays** — watch for
   `OTA rollback detected! Rolled back from partition 'app1'`. A rolled-back
   install is a failure, not a success.
6. `/screen.png` fetches correctly on virtual and hw-test.
7. User confirms the physical panel looks right: no banding or tearing with a
   partial buffer and `auto_clear_enabled: false`.

Measurements not yet taken are marked untested until they are taken. The redraw
target in particular is a bar to report against, not a bar to assume.
