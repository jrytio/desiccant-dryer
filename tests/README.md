# Verification cases

Data-driven test cases for the host build, one YAML file per test ID from
`docs/verification-plan.md`. The runner (`run_cases.py`, not yet written;
see the plan) connects to a headless host build over the ESPHome native
API, applies `setup`, walks `steps`, and reports pass/fail against each
case's declared `status`.

Add a case by copying an existing file, changing `id`, `covers`, `status`
and the steps. Entity names are the Home Assistant friendly names exactly
as `esphome/packages/base.yaml` and `hw-virtual.yaml` declare them.
