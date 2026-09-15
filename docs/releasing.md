# Releasing the production firmware

The real dryer runs numbered releases and learns about new ones through
Home Assistant. Test builds (virtual, host, or a developer's own flash of
`esphome/desiccant-dryer.yaml`) are still flashed by hand and never go
through this.

## How it works

- `esphome/version.yaml` holds the semantic version. Only the production
  selector includes it.
- `esphome/packages/release.yaml` gives the firmware a project name and
  that version, adds ESPHome's `update` entity
  (`update.desiccant_dryer_firmware`), an HTTP OTA backend, Improv serial
  provisioning, safe mode and diagnostics (free heap, largest free block,
  loop time, reset reason, running version). The update entity polls
  `https://jrytio.github.io/desiccant-dryer/firmware/manifest.json`
  every six hours, shortly after boot, and whenever Home Assistant asks it
  to check.
- **The release image carries no secrets.** WiFi credentials, the API
  encryption key and the OTA password live in `packages/dev-secrets.yaml`,
  which only the test builds include. A released dryer gets its WiFi from
  its owner at flash time and its API key from Home Assistant when it is
  adopted. It also has no ESPHome OTA server and the web server's
  firmware-upload page is off: unauthenticated, either would let anyone on
  the LAN upload firmware to a mains controller. Firmware reaches a
  released unit only through the update entity or the USB port (plus the
  captive portal, which exists only while the unit has no WiFi and is
  broadcasting its setup access point), so `esphome run` over the network
  does not work against a released dryer; that is intended.
- Pushing a tag `vX.Y.Z` runs `.github/workflows/release.yml`, which
  refuses to build unless the tag equals the version in `version.yaml`,
  compiles the production yaml, writes the manifest with
  `scripts/make-manifest.sh`, attaches everything to a GitHub Release and
  copies the same files to `firmware/` on the `gh-pages` branch, which
  GitHub Pages serves. The repository is public, so the device reads it
  anonymously.
- Why Pages and not the release download URL: that URL redirects to
  `release-assets.githubusercontent.com` through a ~900-byte signed URL
  and an RSA certificate chain. With the display, web server and API up,
  the S2 has a 12–16 KB largest free block, and that second TLS handshake
  failed for lack of memory (1.0.0 could never check for updates). Pages
  answers directly. `platform-esp32.yaml` also trims the mbedTLS and WiFi
  buffers; `Largest Free Block` shows the remaining headroom.
- When the manifest's version differs from the running one, Home
  Assistant shows the update under Settings → Updates with the release
  notes and an Install button. Installing downloads the `.ota.bin` over
  HTTPS, checks its md5 and reboots into it. The controller keeps running
  if the manifest is unreachable; only the update entity goes unavailable.

## Installing a release on a dryer (owner)

1. Open https://web.esphome.io in Chrome or Edge, plug the board in over
   USB, and install the release: the GitHub Release page carries the
   `.factory.bin`, and the manifest is in esp-web-tools format. Enter the
   WiFi network when asked (Improv over the USB serial port). Alternatively join the open `Desiccant Dryer Setup`
   access point the board raises when it has no network and enter the
   WiFi there.
2. Home Assistant discovers the device; accept it under Settings →
   Devices → ESPHome. Home Assistant sets the API encryption key itself.
3. From then on new releases appear under Settings → Updates.

## Cutting a release (developer)

1. In the PR, bump `esphome/version.yaml` (semver: patch for fixes, minor
   for new behaviour or tunables, major for anything that changes wiring
   or breaks the HA entities). Describe the user-visible changes in the
   PR; the release notes are generated from the merged PRs.
2. Merge. Then from any checkout:

   ```bash
   scripts/release.sh
   ```

   It tags `origin/main` as `vX.Y.Z` and pushes the tag. Watch the run
   with `gh run list --workflow release.yml`.
3. Acceptance: within six hours (or after pressing *Check for update* on
   the update entity, or restarting the device) Home Assistant lists
   "Desiccant Dryer" under Settings → Updates. Install from there.

Home Assistant only lists updates in Settings by default. For a push
notification, add an automation triggered by
`update.desiccant_dryer_firmware` turning `on` that calls a `notify`
service.

## Notes

- Release binaries carry exactly the version in `version.yaml`. A laptop
  flash of the same commit reports the same version and is therefore not
  offered that release, only the next one. There is no `-dev` suffix.
- The first 1.x releases log at DEBUG (set in `esphome/desiccant-dryer.yaml`)
  so the unit can be brought up and tested remotely through `esphome logs`,
  the web server on port 80 and Home Assistant; a later release lowers it.
- The manifest's relative `ota.path` resolves next to the manifest, so
  `firmware/` on Pages serves the matching binary. Filenames carry the
  version so nothing caches stale. Pages can take a minute after the
  workflow before it serves the new files.
- 1.0.0 cannot update itself (see above); a unit on 1.0.0 needs one USB
  flash of 1.0.1 or later.
- To dry-run the packaging locally:

  ```bash
  esphome compile esphome/desiccant-dryer.yaml && scripts/make-manifest.sh 1.0.0 esphome/.esphome/build/desiccant-dryer/build /tmp/site
  ```
