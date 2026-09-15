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
- **Hosting: GitHub Pages of this repo.** The release workflow deploys
  `manifest.json`, `desiccant-dryer-X.Y.Z.ota.bin` and
  `desiccant-dryer-X.Y.Z.factory.bin` to Pages with actions/deploy-pages,
  and also attaches the same files to a GitHub Release for the record.
  Pages is used because the device has no credentials: release assets of
  a private repository are not fetchable anonymously. The repository is
  private today, so Pages must be enabled (Settings → Pages → Source:
  GitHub Actions), which on a private repo needs a paid GitHub plan; the
  alternative is making the repository public. Either is a one-time
  setting; the manifest URL is a substitution so it can move.
- **Secrets.** CI compile checks keep using `esphome/secrets.ci.yaml`. The
  release workflow instead writes `esphome/secrets.yaml` from one
  repository secret, `ESPHOME_SECRETS_YAML`, holding the whole file, so
  new secret keys never require a workflow change. It fails early if the
  secret is unset.
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
| `esphome/packages/release.yaml` | project id, http_request, OTA backend, update entity, diagnostics | `${version}`, `${update_manifest_url}` |
| `esphome/desiccant-dryer.yaml` | includes the two above, sets DEBUG logging | |
| `.github/workflows/release.yml` | tag `vX.Y.Z` → check version, build, manifest, Release, Pages | `ESPHOME_SECRETS_YAML` secret, Pages enabled |
| `scripts/release.sh` | tags and pushes the merged `main` at the version in `version.yaml` | |
| `docs/releasing.md` | the procedure, one-time setup, how HA shows it | |

## Data flow

PR bumps `version.yaml` → merge → `scripts/release.sh` tags `main` →
workflow builds `esphome/desiccant-dryer.yaml` with real secrets →
`firmware.ota.bin` and `firmware.factory.bin` renamed with the version,
md5 computed, `manifest.json` written (`chipFamily: ESP32-S2`, relative
`ota.path`, `release_url` of the GitHub Release) → deployed to Pages and
attached to the Release → device polls the manifest every 6 h (and on
HA's "check for update") → HA shows `update.desiccant_dryer_firmware`
with the release notes → user presses Install → device fetches the
`.ota.bin` over HTTPS, verifies the md5, reboots.

## Error handling

- Tag / version mismatch: workflow fails before building.
- Missing secrets secret: workflow fails before building.
- Manifest unreachable: the update entity goes unavailable, nothing else
  changes; the controller keeps running (WiFi-independent invariant holds).
- Bad OTA (md5 mismatch or interrupted): ESPHome aborts the update and
  keeps the running image; safe mode remains reachable.

## Testing

- `esphome config` and a full compile of the production yaml locally and
  in the existing build workflow.
- Manifest generation exercised on a local compile with the same shell
  the workflow uses.
- End-to-end (device sees the update in HA) can only be proven after
  Pages is enabled and the first tag is pushed; documented as the
  acceptance step in `docs/releasing.md`.
