# The dryer screen in Home Assistant

Both device builds serve the panel's frame buffer as an image:

```bash
curl -o screen.png http://10.42.14.100/screen.png     # bench board
```

It is a 240x240 8-bit indexed PNG, 58,688 bytes (uncompressed, so it
streams without a compressor), exactly what the ST7789 is showing,
palette rounding included. Home Assistant's Generic Camera accepts only
PNG, JPEG, GIF, SVG and WebP stills, which is why it is not a BMP. The
board streams it straight from the display buffer, so a request never
copies the frame or allocates a buffer. Each redraw clears the buffer and
repaints it over a few hundred milliseconds, so fetches and redraws take
turns: a fetch waits for a redraw in progress to finish, and a redraw that
falls due during a fetch (about 0.6 s) runs as soon as the fetch ends. The
panel can therefore lag by up to one fetch while something is watching.

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
| URL | `http://10.42.14.100/screen.png?t={{ now().timestamp() \| int }}` |
| Verify SSL certificate | off (plain HTTP) |

A template image only refetches when its URL changes, and a template using
`now()` re-renders on its own only once a minute. An automation forces a
re-render every 2 s, matching the display's redraw:

```yaml
alias: Dryer Screen refresh
mode: single
max_exceeded: silent
triggers:
  - trigger: time_pattern
    seconds: "/2"
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
share one fetch per refresh. The cost is a recorded state change every 2 s
for both the image entity and the automation. The production unit gets its
own image entity and automation pointed at its own address.

## Camera entity (LAN only)

A Generic Camera on the same URL (Still Image URL
`http://10.42.14.100/screen.png`, no stream source, content type
`image/png`, frame rate `0.5` Hz) also works on the LAN, but not remotely
at its useful rate. A Picture Entity card with `camera_view: live` holds
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
own LAN, and mDNS does not cross the site-to-site VPN. The addresses on
this page are the bench board at home. After a move:

1. Find the new address: the boot log prints `IP x.x.x.x` two seconds
   after WiFi connects, or look in the site router's DHCP leases (at the
   workshop the router's DNS also answers `<name>.t3d.lan`).
2. Settings, Devices & services, ESPHome, the device's entry menu,
   **Reconfigure**: enter the new address, port 6053. Device and entity
   ids are kept.
3. Edit the `image.dryer_screen` helper's URL to the new address.

Home Assistant reaches a board at the other site by IP across the VPN;
the API (6053) and `/screen.png` (80) both worked from home to the
workshop on 2026-09-15.

## Limits

- The image is the drawing as the driver holds it. The panel's
  `invert_colors`, `transform` and any offset are applied by the panel, not
  the buffer, so they do not appear here.
- No authentication beyond what `web_server` applies; the web server is
  already open on the LAN.
- The host preview build has no web server and no endpoint; use its
  window instead (`docs/host-preview.md`).
- The endpoint returns HTTP 500 with a short message if the display is
  not in `color_palette: 8BIT` or is rotated. Both device builds are.
