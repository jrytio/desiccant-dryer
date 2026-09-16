# Releasing the production firmware

The real dryer runs numbered releases. An owner installs the first one over
USB and later ones from ESPHome Device Builder over WiFi. Test builds
(virtual, host, hw-test) are flashed by hand and never go through this.

## How it works

- `esphome/version.yaml` holds the semantic version. The production build
  (`packages/production.yaml`) includes it.
- Two selectors wrap `packages/production.yaml`:
  - `esphome/desiccant-dryer.yaml` takes the screen's drawing component
    (`components/dryer_ui`) and SVG art from this checkout. CI compiles it
    and the release workflow builds the published images from it.
  - `esphome/desiccant-dryer-adopt.yaml` takes both from GitHub at the tag
    `v<version>`. It is what Device Builder imports: a remote package cannot
    reach files inside this repository by relative path (includes, local
    external components and image files resolve next to the owner's YAML).
    It only validates once that tag exists, so CI does not build it.
- `esphome/packages/release.yaml` gives the firmware a project name and
  version, Improv serial provisioning, safe mode and diagnostics (free
  heap, largest free block, loop time, reset reason, running version).
- **The release image carries no secrets.** WiFi credentials, the API
  encryption key and the OTA password of the test builds live in
  `packages/dev-secrets.yaml`, which the release never includes. A released
  dryer gets its WiFi from its owner at flash time. It has no OTA server
  and the web server's firmware-upload page is off: unauthenticated, either
  would let anyone on the LAN upload firmware to a mains controller. The
  captive portal can still take firmware, but only while the unit has no
  WiFi and is broadcasting its setup access point.
- **Updates come from Device Builder, not from the device.** The production
  firmware carries `dashboard_import` pointing at
  `github://jrytio/desiccant-dryer/esphome/desiccant-dryer-adopt.yaml@main`.
  Adopting writes a short YAML on the owner's Home Assistant that pulls that
  file as a package and adds the owner's own API key and WiFi; the owner
  adds an OTA block (see below). Device Builder compiles it and pushes it
  with ESPHome's native OTA, authenticated by the API encryption key or a
  password, with no TLS on the device.
- Why not the on-device updater (1.0.x had `update: platform: http_request`):
  the S2 has no PSRAM and a 58 KB display buffer, and never had the ~17 KB
  contiguous block that mbedTLS needs to receive a firmware download over
  HTTPS. Dynamic buffers checked the manifest but failed on the first full
  record of the `.ota.bin`; static buffers could not open the connection
  at all. The release download URL was worse still (a redirect to an RSA
  host through a ~900-byte signed URL). `Largest Free Block` shows the
  headroom.
- Pushing a tag `vX.Y.Z` runs `.github/workflows/release.yml`, which
  refuses to build unless the tag equals the version in `version.yaml`,
  compiles `desiccant-dryer.yaml`, writes an esp-web-tools manifest with
  `scripts/make-manifest.sh`, attaches everything to a GitHub Release and
  copies the same files to `firmware/` on the `gh-pages` branch (GitHub
  Pages), where web.esphome.io can install them.

## Installing a release on a dryer (owner)

1. Open https://web.esphome.io in Chrome or Edge, plug the board in over
   USB, and install the release's `.factory.bin` (from the GitHub Release)
   or point it at `https://jrytio.github.io/desiccant-dryer/firmware/manifest.json`.
   Enter the WiFi network when asked (Improv over the USB serial port), or
   join the open `Desiccant Dryer Setup` access point the board raises when
   it has no network and enter the WiFi there.
2. Install the ESPHome Device Builder add-on in Home Assistant if it is not
   there. The dryer shows up as discovered; click **Adopt**. Device Builder
   writes `desiccant-dryer.yaml` with a new API key. The released image has
   no OTA server, so add one next to the generated `api:` block. On ESPHome
   2026.9 or newer, let it reuse the API encryption key, which costs no
   extra flash, RAM or secret:

   ```yaml
   ota:
     - platform: esphome
       encryption: {}
   ```

   On older ESPHome that option does not exist; use a password instead and
   put the secret in Device Builder's secrets:

   ```yaml
   ota:
     - platform: esphome
       password: !secret desiccant_dryer_ota_password
   ```

   ESPHome 2026.9 warns that OTA encryption does not cover the web_server
   OTA platform. It does not apply here: `web_server: ota: false` compiles
   `/update` to refuse uploads unless the setup access point is active.
3. Install the adopted YAML **over USB once** (Device Builder → Install →
   Plug into the computer running ESPHome Device Builder, or download the
   binary and flash it with web.esphome.io). The released image has no OTA
   server, so this first adopted install cannot go over WiFi.
4. Accept the device in Home Assistant under Settings → Devices → ESPHome
   with the key from the adopted YAML.
5. From then on, install new releases from Device Builder → **Install** →
   Wirelessly. Home Assistant does not announce them; watch the GitHub
   releases.

Units still on 1.0.x update the same way: they need the one USB install of
the adopted YAML (1.0.x cannot install anything over WiFi).

## Cutting a release (developer)

1. In the PR, bump `esphome/version.yaml` (semver: patch for fixes, minor
   for new behaviour or tunables, major for anything that changes wiring
   or breaks the HA entities). Describe the user-visible changes in the
   PR; the release notes are generated from the merged PRs.
2. Merge, and tag straight away from any checkout:

   ```bash
   scripts/release.sh
   ```

   It tags `origin/main` as `vX.Y.Z` and pushes the tag. Until the tag
   exists, an owner's Device Builder build of `main` fails to fetch the
   `dryer_ui` component and art for the new version. Watch the run with
   `gh run list --workflow release.yml`.
3. Acceptance: an adopted unit installs the new version from Device Builder
   over WiFi and reports it in `Firmware Version`.

## Notes

- Release binaries carry exactly the version in `version.yaml`. There is no
  `-dev` suffix. A test flash can relabel it, but with the adopt selector
  `ui_ref` and `display_assets` are derived from `version`, so pin them to
  the real tag as well or the build looks for a tag that does not exist:

  ```bash
  esphome -s version 1.1.0-test -s ui_ref v1.1.0 \
    -s display_assets https://raw.githubusercontent.com/jrytio/desiccant-dryer/v1.1.0/esphome/assets/display \
    run --device <board> desiccant-dryer.yaml
  ```
- The first 1.x releases log at DEBUG (set in `packages/production.yaml`)
  so the unit can be brought up and tested remotely through `esphome logs`,
  the web server on port 80 and Home Assistant; a later release lowers it.
- There is no `/screen.png` mirror in production (its local component
  would not resolve from a remote package either). The hw-test and virtual
  builds keep it.
- To dry-run the packaging locally:

  ```bash
  esphome compile esphome/desiccant-dryer.yaml && scripts/make-manifest.sh 1.1.0 esphome/.esphome/build/desiccant-dryer/build /tmp/site
  ```

- To test adoption before a tag exists, write an adopted-style YAML that
  pulls `esphome/desiccant-dryer-adopt.yaml` from a branch and overrides
  `ui_ref` and `display_assets` to that branch.
