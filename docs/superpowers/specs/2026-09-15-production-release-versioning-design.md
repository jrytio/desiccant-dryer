# Production release versioning and Home Assistant updates

**Goal.** Every merge to `main` that is meant for the real dryer becomes a
numbered release. The device reports that version to Home Assistant and
checks a published manifest, so HA shows an "update available" entry (and
can notify) when a newer production build exists. Test builds (virtual,
host, and any developer flash of the production yaml) keep being flashed
by hand from a laptop and are not part of this.

## Decisions

- **Semantic versioning, one source.** `esphome/version.yaml` holds
  `substitutions: version: "X.Y.Z"`. It is a package included only by the
  production selector. Bumping it is a normal PR change. The release
  workflow refuses to build a tag whose name does not match it.
- **ESPHome's own mechanism, nothing custom on the device.** The standard
  pattern for HA-only ESPHome products (Apollo, Athom, esphome/firmware):
  `esphome.project` name + version, the `http_request` component, an
  `ota: platform: http_request` backend, and an `update: platform:
  http_request` entity whose `source` is an esp-web-tools style
  `manifest.json`. HA discovers the update entity through the native API
  with no HA-side configuration. The device compares the manifest's
  `version` with its own project version by string inequality.
- **No secrets in the release image.** WiFi credentials, the API
  encryption key and the OTA password move from `base.yaml` and
  `platform-esp32.yaml` into `packages/dev-secrets.yaml`, included only by
  the hand-flashed test builds. The production image ships with an open
  fallback access point, captive portal, Improv serial and a plain API;
  the owner enters WiFi at flash time and Home Assistant sets the API key
  on adoption. `dashboard_import` points at this repo so the ESPHome
  dashboard can adopt the device. The production yaml validates without
  any `secrets.yaml` present.
- **Hosting: the GitHub Release itself.** The repository is public, so
  the device polls
  `https://github.com/jrytio/desiccant-dryer/releases/latest/download/manifest.json`
  anonymously (the redirect is followed) and the manifest's relative
  `ota.path` resolves through the same URL. No Pages, no extra setup. The
  URL is a substitution so it can move.
- **v1.x is verbose on purpose.** The production build sets the logger to
  DEBUG and adds diagnostic entities (free heap, reset reason, project
  version, safe mode) so a remote agent can inspect and drive the unit
  through HA and the web server. A later release drops the log level.
- **Version strings.** Release binaries carry exactly the version in
  `version.yaml`. A developer flash of the production yaml carries the
  same string, so it will not be offered the release of the same number;
  it will be offered the next one. Accepted; no `-dev` suffix machinery.

## Components

| Unit | Purpose | Depends on |
|---|---|---|
| `esphome/version.yaml` | the version number | nothing |
| `esphome/packages/release.yaml` | project id, provisioning (Improv, dashboard_import), http_request, OTA backends, update entity, diagnostics | `${version}`, `${update_manifest_url}` |
| `esphome/packages/dev-secrets.yaml` | WiFi, API key, OTA password from secrets.yaml; test builds only | `secrets.yaml` |
| `esphome/desiccant-dryer.yaml` | includes the two above, sets DEBUG logging | |
| `.github/workflows/release.yml` | tag `vX.Y.Z` → check version, build, manifest, GitHub Release | nothing beyond the repo token |
| `scripts/release.sh` | tags and pushes the merged `main` at the version in `version.yaml` | |
| `docs/releasing.md` | the procedure, one-time setup, how HA shows it | |

## Data flow

PR bumps `version.yaml` → merge → `scripts/release.sh` tags `main` →
workflow builds `esphome/desiccant-dryer.yaml` (no secrets) →
`firmware.ota.bin` and `firmware.factory.bin` renamed with the version,
md5 computed, `manifest.json` written (`chipFamily: ESP32-S2`, relative
`ota.path`, `release_url` of the GitHub Release) → attached to the Release → device polls the manifest every 6 h (and on
HA's "check for update") → HA shows `update.desiccant_dryer_firmware`
with the release notes → user presses Install → device fetches the
`.ota.bin` over HTTPS, verifies the md5, reboots.

## Error handling

- Tag / version mismatch: workflow fails before building.
- Manifest unreachable: the update entity goes unavailable, nothing else
  changes; the controller keeps running (WiFi-independent invariant holds).
- Bad OTA (md5 mismatch or interrupted): ESPHome aborts the update and
  keeps the running image; safe mode remains reachable.

## Testing

- `esphome config` and a full compile of the production yaml locally and
  in the existing build workflow.
- Manifest generation exercised on a local compile with the same shell
  the workflow uses.
- The production yaml is validated with `secrets.yaml` absent.
- End-to-end (device sees the update in HA) can only be proven after the
  first tag is pushed; documented as the acceptance step in
  `docs/releasing.md`.
