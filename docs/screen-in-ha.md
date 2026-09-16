# The dryer screen in Home Assistant

The hw-test and virtual builds serve the dryer screen as an image
(the production build does not):

```bash
curl -o screen.png "http://<board>/screen.png"     # <board>: the board's IP address
```

It is a 240x240 8-bit indexed PNG, 58,688 bytes (uncompressed, so it
streams without a compressor). Home Assistant's Generic Camera accepts only
PNG, JPEG, GIF, SVG and WebP stills, which is why it is not a BMP.

The endpoint does not read the display driver's frame buffer. It re-renders
the UI itself, an 80-row band at a time into its own 19,200-byte scratch
buffer, from the state the panel captured on its last redraw. So it works
whatever the driver's colour depth, buffer size or rotation are. The image
is the drawing as of the last panel redraw, so it can be up to one redraw
interval behind the panel.

**It is cheap in RAM, not in CPU.** Each band is a complete `draw_ui()`
pass, so one fetch runs three of them back to back on the web-server task —
roughly 300 ms each on the S2, so on the order of **1 s of CPU per fetch**.
(Before the band was widened to 80 rows it was ten passes and about 3 s,
which was enough to time out a fetch when three were issued with no gap.)
Control ticks are driven by their own ESPHome interval and were not seen to
slip, but do not treat `/screen.png` as free: leave a comfortable gap
between fetches so two never overlap.

## Image entity

Show the screen on dashboards through a template **image** entity. Home
Assistant fetches `/screen.png` itself, caches it, and gives browsers a
plain still from `/api/image_proxy/...`. The browser never talks to the
board, and a single short request per frame passes through a remote proxy
such as the Cloudflare tunnel the same way it does on the LAN.

Settings, Devices & services, Helpers, Create helper, **Template**,
**Image**:

| Field | Value |
|---|---|
| Name | `Dryer Screen` (entity `image.dryer_screen`) |
| URL | `http://<board>/screen.png?t={{ now().timestamp() \| int }}` |
| Verify SSL certificate | off (plain HTTP) |

A template image only refetches when its URL changes, and a template using
`now()` re-renders on its own only once a minute. An automation forces the
re-render. **Use 10 s** — not the display's 5 s redraw interval and
certainly not 2 s: a fetch costs about a second of CPU (above), and at a
short interval fetches queue up behind each other. This endpoint exists to
check what the screen is doing without a board in front of you, so a
screenshot that is a few seconds stale is fine. 5 s is the shortest worth
using; 2 s overlaps.

```yaml
alias: Dryer Screen refresh
mode: single
max_exceeded: silent
triggers:
  - trigger: time_pattern
    seconds: "/10"
actions:
  - action: homeassistant.update_entity
    target:
      entity_id: image.dryer_screen
```

Each re-render changes the `?t=` value (the board ignores the query
string), which drops Home Assistant's cached copy and changes the entity's
state, so the dashboard loads the new still.

Show it with the Dryer Screen card, `docs/ha/dryer-screen-card.js`. Register
the file's contents as a dashboard resource (JavaScript module; the dev
instance has it inline), then:

```yaml
type: custom:dryer-screen-card
entity: image.dryer_screen
```

The card downloads and decodes each new frame off-screen and swaps it in
only when it is complete, skipping to the newest frame if it falls behind
and keeping the current one if a load fails. The built-in **Picture
Entity** card points its image at each new URL straight away, so through
the Cloudflare tunnel it blinks on every refresh while the frame arrives;
on the LAN it is usable. Tapping the card opens the entity's more-info
dialog.

Home Assistant fetches the board only when someone is viewing, and viewers
share one fetch per refresh. The cost is a recorded state change every 10 s
for both the image entity and the automation, plus about a second of the
board's CPU per fetch. The production unit has no `/screen.png` endpoint at
all, so it gets neither.

## Camera entity (LAN only)

A Generic Camera on the same URL (Still Image URL
`http://<board>/screen.png`, no stream source, content type
`image/png`, frame rate `0.1` Hz — keep it low for the same CPU reason)
also works on the LAN, but not remotely at its useful rate. A Picture
Entity card with `camera_view: live` holds
an endless MJPEG response open (`/api/camera_proxy_stream/...`); through
the Cloudflare tunnel the card stays blank, and the Cloudflared app logs
each attempt as `stream ... canceled by remote`. The default
`camera_view: auto` loads stills instead, but only every 10 s, and it has
not been tried through the tunnel.

## Moving between sites

The device builds carry both sites' WiFi (`wifi: networks:` in
`esphome/packages/platform-esp32.yaml`) and join whichever is in range,
taking a new DHCP address there. Home Assistant does not follow the board:
it learns a device's address only through mDNS or DHCP discovery on its
own LAN, and mDNS does not cross the site-to-site VPN. After a move:

1. Find the new address: the boot log prints `IP x.x.x.x` two seconds
   after WiFi connects, or look in the site router's DHCP leases.
2. Settings, Devices & services, ESPHome, the device's entry menu,
   **Reconfigure**: enter the new address, port 6053. Device and entity
   ids are kept.
3. Edit the `image.dryer_screen` helper's URL to the new address.

Home Assistant reaches a board at the other site by IP across the VPN;
the API (6053) and `/screen.png` (80) both worked from home to the
workshop on 2026-09-15.

## Limits

- The image is the drawing, not the panel. The panel's `invert_colors`,
  `transform` and any offset are applied by the panel, so they do not
  appear here.
- No authentication beyond what `web_server` applies; the web server is
  already open on the LAN.
- The host preview build has no web server and no endpoint; use its
  window instead (`docs/host-preview.md`).
- Before the panel's first redraw there is no captured state to render, so
  the endpoint returns HTTP 500 "screen has not been drawn yet" rather than
  a blank frame.
