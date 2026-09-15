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
copies the frame or allocates a buffer; the display keeps redrawing every
2 s while you fetch, so a frame can occasionally mix two updates.

## Camera entity

Settings, Devices & services, Add integration, **Generic Camera**:

| Field | Value |
|---|---|
| Still Image URL | `http://10.42.14.100/screen.png` (the board's address; `desiccant-dryer-virtual.local` if mDNS resolves from Home Assistant) |
| Stream Source URL | leave empty |
| Content Type | `image/png` |
| Frame Rate (Hz) | `0.5` (the display redraws every 2 s) |
| Verify SSL certificate | off (plain HTTP) |

Name it "Dryer Screen". Add a **Picture Entity** card for it to the dryer
dashboard; by default the card fetches a new still about every 10 s; set
`camera_view: live` on the card to follow the camera's own 0.5 Hz rate. The
production unit gets a second camera pointed at its own address.

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
