# Releasing the production firmware

The real dryer runs numbered releases. An owner installs the first one over
USB and the unit installs every later one itself, over HTTPS, from the
manifest published on this repository's GitHub Pages site. Test builds
(virtual, host, hw-test) are flashed by hand and never go through this.

## How it works

- `esphome/version.yaml` holds the semantic version. The production build
  (`packages/production.yaml`) includes it, and two selectors wrap that
  build, one per supported board: `esphome/desiccant-dryer.yaml` (SparkFun
  ESP32-S2 Thing Plus, `packages/board-s2.yaml`) and
  `esphome/desiccant-dryer-c6.yaml` (SparkFun Thing Plus ESP32-C6,
  `packages/board-c6.yaml`). They differ only in the board package: the
  chip, the port the log uses and the GPIO behind each header position.
  Both take the screen's drawing component (`components/dryer_ui`) and SVG
  art from this checkout. CI compiles both, and the release workflow builds
  the published images from them under one version number.
- `esphome/packages/release.yaml` gives the firmware a project name and
  version, Improv serial provisioning, safe mode, diagnostics (free heap,
  largest free block, loop time, reset reason, running version) and the
  `Firmware` update entity.
- **The release image carries no secrets.** WiFi credentials, the API
  encryption key and the OTA password of the test builds live in
  `packages/dev-secrets.yaml`, which the release never includes. A released
  dryer gets its WiFi from its owner at flash time, and Home Assistant sets
  the API encryption key when it adopts the device
  (`packages/api-provisioned.yaml`).
- **There is no inbound OTA server, and the web server's firmware-upload
  page is off.** Either would be an unauthenticated LAN reflash path into a
  mains controller. Updates are pull-only. The one exception is the captive
  portal's own upload handler — see **Recovery** below; it is not a small
  footnote.
- **The unit updates itself.** `ota: platform: http_request` plus
  `update: platform: http_request` in `packages/release.yaml` poll
  `https://jrytio.github.io/desiccant-dryer/firmware/manifest.json` every
  6 h. When the manifest's version differs from the running `${version}`,
  Home Assistant shows an update on the `Firmware` entity; installing pulls
  the `.ota.bin` over HTTPS (relative path, resolved next to the manifest)
  and checks its md5. The manifest lists one build per chip (`chipFamily`
  `ESP32-S2` and `ESP32-C6`); a unit takes the one that names its own chip
  and ignores the other.
  - GitHub Pages, not the GitHub Release download URL: that one redirects to
    an RSA-certificate host behind a ~900-byte signed URL, and the S2 has
    too little free heap for the second handshake. `follow_redirects: false`
    enforces that rather than assuming it.
  - This only became possible when the panel moved from `ili9xxx` to
    `mipi_spi` with `buffer_size: 50%` (`packages/display-st7789.yaml`).
    `ili9xxx` could not buffer less than a full frame, and the S2 then never
    had the ~16,749-byte contiguous block mbedTLS needs for a TLS record —
    which is why 1.0.x could check the manifest but never install. Do not
    raise production's `display_buffer_size` back to 100% without re-testing
    an install; `Largest Free Block` shows the headroom.
  - Installing an update reboots the unit, possibly mid drying-cycle. That
    fails safe: all outputs use `restore_mode: ALWAYS_OFF` and are forced
    off in `on_boot`, so the reboot drops the heaters and valves.
- Pushing a tag `vX.Y.Z` runs `.github/workflows/release.yml`, which
  refuses to build unless the tag equals the version in `version.yaml`,
  compiles `desiccant-dryer.yaml` and `desiccant-dryer-c6.yaml`, writes one
  esp-web-tools manifest listing both with `scripts/make-manifest.sh`
  (which refuses an image whose header names the other chip), attaches
  everything to a GitHub Release and
  copies the same files to `firmware/` on the `gh-pages` branch (GitHub
  Pages). The copy on `gh-pages` is what web.esphome.io installs from and
  what deployed units poll; the GitHub Release is for humans.

## Installing a release on a dryer (owner)

1. Open https://web.esphome.io in Chrome or Edge, plug the board in over
   USB, and point it at
   `https://jrytio.github.io/desiccant-dryer/firmware/manifest.json`, which
   picks the image for the chip it finds. To install a file from the GitHub
   Release by hand instead, take the `.factory.bin` named for the board:
   `-esp32s2` for the ESP32-S2 Thing Plus, `-esp32c6` for the Thing Plus
   ESP32-C6. An ESP32-C6 board is flashed out of its socket
   (docs/hardware.md, "Fitting an ESP32-C6 Thing Plus").
2. Enter the WiFi network when asked (Improv over the USB serial port), or
   join the open `Desiccant Dryer Setup` access point the board raises when
   it has no network and enter the WiFi there.
3. Accept the device in Home Assistant under Settings → Devices & services →
   ESPHome. Home Assistant generates and stores the API encryption key; the
   owner edits no YAML.
4. From then on the unit checks for new releases itself every 6 h. When one
   appears, install it from the `Firmware` update entity in Home Assistant.
   The unit downloads and flashes it with no computer involved.

Units on **1.0.x or 1.1.0** cannot install anything over WiFi by themselves.
1.0.x has an updater that can check the manifest but never allocate enough
contiguous heap to install; 1.1.0 has no updater at all, because updates
were handed to ESPHome Device Builder in that release. 1.1.0 is what is
actually in the field today.

**USB is the only way forward for them, adopted or not.** A stock 1.1.0
image has no inbound OTA server, so nothing can be pushed to it. A 1.1.0
unit still adopted in ESPHome Device Builder does have one, but there is
nothing to push: `esphome/desiccant-dryer-adopt.yaml` is gone from `main` as
of 1.2.0, so an adopted config pointing at
`...desiccant-dryer-adopt.yaml@main` stops building. Repointing it at
`@v1.1.0` does build — the file still exists at that tag — but a remote
package resolves its whole include tree at the ref it was fetched from, so
that rebuilds **1.1.0**, updater and all, which leaves the unit exactly
where it started. There is no remote-safe selector for 1.2.0: the production
selector pulls `packages/ui-code-local.yaml`, a local external component a
remote package cannot read.

So: reflash 1.2.0 or later once over USB with web.esphome.io, and the unit
self-updates from then on.

## Recovery

**There is no second update route.** The released image has no inbound OTA
server on the normal LAN path, so nothing can push firmware to a running,
provisioned unit. If the updater cannot reach a working manifest — GitHub
Pages down, `gh-pages` publishing a broken or mismatched build, the unit's
own network gone, or a release that boots but breaks networking — the only
way back is to reflash the board over USB with web.esphome.io. That means
physical access, and on an installed unit it means opening the enclosure.
Weigh that before publishing a release.

A USB reflash needs the image for the chip that is fitted. web.esphome.io
chooses it from the manifest. By hand, use the `-esp32s2` or `-esp32c6`
factory file to match, and tell esptool which chip the file is for
(`--chip esp32s2` or `--chip esp32c6`): it then stops if the board is the
other kind. Do not count on esptool to notice by itself. Read from its
source (5.1.0), not tried on these boards: without `--chip` it checks only
a file that begins with an image header, which the C6 factory file does
and the S2 factory file, whose header sits at 0x1000, does not. A board
flashed with the other chip's file does not boot and drives no output;
flash the right file over it. An ESP32-C6 board comes out of its socket
first.

Two security properties of this arrangement were raised during the 1.2.0
work and **deliberately accepted** rather than fixed. They are recorded here
so that anyone maintaining the fleet knows what they are relying on.

### Accepted risk 1: unauthenticated firmware upload over the fallback AP

Production ships an **open** access point named `"<friendly name> Setup"`
(no password) together with `captive_portal:`. `captive_portal:` AUTO_LOADs
`ota.web_server`, whose `POST /update` handler stays reachable whenever the
captive portal is active. Setting `web_server: ota: false` does **not** close
it — ESPHome's own source says so explicitly
(`web_server/ota/ota_web_server.cpp`).

Stated plainly: while that portal is up, anyone within WiFi range can join
the AP with no credential and flash arbitrary firmware onto a unit switching
two 120 VAC heaters.

The portal is up on any unprovisioned unit, and whenever the configured
network is unreachable. An attacker can force the latter, so this is not
only a rare-outage window. This is a deliberate trade for provisioning
convenience, not an oversight. The two ways to close it are to password the
access point, or to drop `captive_portal:`; this repo does neither.

### Accepted risk 2: the update trust root is push access to `gh-pages`

The `update:` entity fetches the manifest and the md5 it verifies comes from
that same manifest. The md5 therefore proves only that the download was not
corrupted in transit; it proves nothing about who produced the binary.
`ota: platform: http_request` supports no code signing of any kind.

Consequently, **anyone who can push to the `gh-pages` branch can run
arbitrary firmware on every deployed unit within one 6 h poll interval.**
Push access to that branch is the security boundary for the whole fleet, and
should be protected accordingly.

## Cutting a release (developer)

1. In the PR, bump `esphome/version.yaml` (semver: patch for fixes, minor
   for new behaviour or tunables, major for anything that changes wiring
   or breaks the HA entities). Describe the user-visible changes in the
   PR; the release notes are generated from the merged PRs.
2. Merge, and tag from any checkout:

   ```bash
   scripts/release.sh
   ```

   It tags `origin/main` as `vX.Y.Z` and pushes the tag. Watch the run with
   `gh run list --workflow release.yml`.
3. Acceptance: a deployed unit shows the new version on its `Firmware`
   update entity within 6 h (or immediately after a manual entity refresh),
   installs it, and reports the new number in `Firmware Version`.

## PCB revisions

The board under `hardware/` has its own revision letter, separate from the
firmware's semver. It feeds the silkscreen, the title block and the fab
file names.

1. In the PR, bump `REVISION` in `hardware/dryer_board/circuit.py` (A, B,
   ...) along with the change.
2. `scripts/hardware.sh generate`, then `scripts/hardware.sh route`,
   then `scripts/hardware.sh check` (must pass), then
   `scripts/hardware.sh export` (refreshes `docs/hardware/`). Commit the
   KiCad project and the review files.
3. After the PR merges, tag `origin/main` and push the tag:

   ```bash
   git fetch origin && git tag pcb-revB origin/main && git push origin pcb-revB
   ```

4. The `hardware` workflow runs on the tag and creates a GitHub release
   with the gerber zip, the JLCPCB BOM and CPL, and the schematic PDF
   attached. Order from those files, not from a local export, so what was
   sent to the fab is recoverable.

## Notes

- The production selector sets `min_version: 2026.9.0`
  (`packages/production.yaml`). That is the version CI and the release
  workflow pin, and therefore the only version the release images are built
  and tested with — it is not a feature requirement. Nothing in the config
  needs 2026.9 specifically: `mipi_spi`'s `buffer_size` and `color_depth`
  are both present in 2026.8.2, and `packages/display-st7789.yaml` is shared
  by the production, virtual and hw-test builds, so it emits those keys for
  all of them. The bench builds (virtual, host, hw-test, scenarios) carry no
  floor only because they are never released. Homebrew may still ship an
  older ESPHome, in which case build the production image with the Docker
  image (`ghcr.io/esphome/esphome:2026.9.0`) or pipx.
- `provisioning:` (ESPHome 2026.9) closes the window in which the API key
  may be set. It is not used here: adoption can happen days after the unit
  is flashed, and closing the window would also shut down the setup access
  point, which may be the unit's only way back onto a network.
- Release binaries carry exactly the version in `version.yaml`. There is no
  `-dev` suffix. A test flash can relabel it:

  `-s` is a global option: it must come before the subcommand, or ESPHome
  exits with "unrecognized arguments".

  ```bash
  esphome -s version 1.2.0-test run --device <board> desiccant-dryer.yaml
  ```
- Production redraws the panel every 10 s and each redraw blocks for about
  699 ms on the S2 (not yet measured on the C6), because the halved frame
  buffer makes `mipi_spi` run the writer twice
  (`packages/display-st7789.yaml` has the measurements). A fault or
  overtemp indication can therefore be up to 10 s stale on the panel.
- The first 1.x releases log at DEBUG (set in `packages/production.yaml`)
  so the unit can be brought up and tested remotely through `esphome logs`,
  the web server on port 80 and Home Assistant; a later release lowers it.
- To dry-run the packaging locally:

  ```bash
  esphome compile esphome/desiccant-dryer.yaml && esphome compile esphome/desiccant-dryer-c6.yaml && scripts/make-manifest.sh 1.3.0 /tmp/site "" esp32s2=esphome/.esphome/build/desiccant-dryer/build esp32c6=esphome/.esphome/build/desiccant-dryer-c6/build
  ```

- To test the update path before publishing a release, serve a manifest and
  `.ota.bin` built from your branch at any HTTPS URL the unit can reach and
  override `update_manifest_url` (`-s update_manifest_url <url>`). The
  substitution is defined in `packages/release.yaml`, which only the
  production selectors include, so override it on `desiccant-dryer.yaml`
  or `desiccant-dryer-c6.yaml` — the virtual, host, hw-test and scenarios builds have no updater
  and no such substitution.
