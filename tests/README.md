# Verification cases

Data-driven test cases, one YAML file per test ID from
`docs/verification-plan.md`. Two runners read them, chosen by each case's
`harness`:

- `lint_config.py` (`harness: ci-lint`) dumps `esphome config` for the
  case's `selectors` and evaluates its `assert` lines. It runs in the
  `lint-config` job in `.github/workflows/build.yml`. Run it locally with
  `tests/lint_config.py` (optionally naming case IDs), or through the CI
  image if your local ESPHome is older than the production `min_version`.
- `run_cases.py` (`harness: host`, not yet written; see the plan) connects
  to a headless host build over the ESPHome native API, applies `setup`,
  walks `steps`, and reports pass/fail.

Both exit non-zero if a `green` case fails or a `red` case passes: a
passing `red` case means the gap closed and the case must be marked
`green` in the same change.

Add a case by copying an existing file, changing `id`, `covers`, `status`
and the steps. Entity names are the Home Assistant friendly names exactly
as `esphome/packages/base.yaml` and `hw-virtual.yaml` declare them.
