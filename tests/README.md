# Verification cases

Data-driven test cases, one YAML file per test ID from
`docs/verification-plan.md`. Two runners read them, chosen by each case's
`harness`:

- `lint_config.py` (`harness: ci-lint`) dumps `esphome config` for the
  case's `selectors` and evaluates its `assert` lines. It runs in the
  `lint-config` job in `.github/workflows/build.yml`. Run it locally with
  `tests/lint_config.py` (optionally naming case IDs). It needs PyYAML: in
  the CI image the plain `python3` has it, but a local ESPHome installed in
  its own venv may not, in which case run it with ESPHome's interpreter the
  way `scripts/normalize-config.py` documents. Running it through the CI
  image covers both that and a local ESPHome older than the production
  build's `min_version`.
- `run_cases.py` (`harness: host`, the default) starts the host build
  headless — `SDL_VIDEODRIVER=dummy`, one process and one prefs directory
  per case — connects over the ESPHome native API, applies `setup`, walks
  `steps`, and reports pass/fail. It runs in the `host-cases` job in
  `.github/workflows/build.yml`. Run it locally with `tests/run_cases.py`
  (optionally naming case IDs, and `--no-build` to reuse the compiled
  binary); it re-execs itself under ESPHome's interpreter if the one it
  started under has no `aioesphomeapi`. A case needing a `Sim *` knob the
  plant model does not have yet is skipped, with the knob named.

Both exit non-zero if a `green` case fails or a `red` case passes: a
passing `red` case means the gap closed and the case must be marked
`green` in the same change.

Add a case by copying an existing file, changing `id`, `covers`, `status`
and the steps. Entity names are the Home Assistant friendly names exactly
as `esphome/packages/base.yaml` and `hw-virtual.yaml` declare them.
