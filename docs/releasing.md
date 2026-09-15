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
  (`update.desiccant_dryer_firmware`), an HTTP OTA backend, safe mode and
  diagnostics (free heap, loop time, reset reason, running version). The
  update entity polls
  `https://jrytio.github.io/desiccant-dryer/manifest.json` every six hours
  and whenever Home Assistant asks it to check.
- Pushing a tag `vX.Y.Z` runs `.github/workflows/release.yml`, which
  refuses to build unless the tag equals the version in `version.yaml`,
  compiles with the real secrets, writes the manifest with
  `scripts/make-manifest.sh`, attaches everything to a GitHub Release and
  deploys the same files to GitHub Pages.
- When the manifest's version differs from the running one, Home
  Assistant shows the update under Settings → Updates with the release
  notes and an Install button. Installing downloads the `.ota.bin` over
  HTTPS, checks its md5 and reboots into it. The controller keeps running
  if the manifest is unreachable; only the update entity goes unavailable.

## One-time setup (repository owner)

1. **Repository secret `ESPHOME_SECRETS_YAML`**: the entire contents of
   the real `esphome/secrets.yaml` (WiFi, AP password, API key, OTA
   password). Settings → Secrets and variables → Actions. Without it the
   workflow stops before compiling. Keep it in step with the secrets on
   the developer laptop or the released firmware will not join the network
   or pair with Home Assistant.
2. **GitHub Pages**: Settings → Pages → Build and deployment → Source:
   *GitHub Actions*. The repository is private, and Pages on a private
   repository needs a paid GitHub plan; the alternative is making the
   repository public. Release assets cannot be used instead: the device
   has no GitHub credentials, and assets of a private repository are not
   downloadable anonymously. If the manifest ever moves, change
   `update_manifest_url` in `esphome/packages/release.yaml`.
3. The device must already be running a build that includes
   `release.yaml` (any production flash from this point on) to see
   updates at all. The first such flash is by cable or `esphome run`.

## Cutting a release

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
- The `.factory.bin` in the manifest also lets https://web.esphome.io
  flash a bare board over USB from the same manifest.
- To dry-run the packaging locally:

  ```bash
  esphome compile esphome/desiccant-dryer.yaml && scripts/make-manifest.sh 1.0.0 esphome/.esphome/build/desiccant-dryer/.pioenvs/desiccant-dryer /tmp/site
  ```
