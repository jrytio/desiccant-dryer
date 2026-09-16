#!/usr/bin/env python3
"""Run the `ci-lint` verification cases against `esphome config` output.

For every case file in tests/cases/ with `harness: ci-lint`, dump the
configuration for each of its `selectors` and evaluate the case's `assert`
lines against it.

Per docs/verification-plan.md, a `green` case that fails is an error, and so
is a `red` case that passes: a passing `red` case means the gap closed and the
case must be marked `green` in the same change.

Usage: tests/lint_config.py [case-id ...]      (default: every ci-lint case)
"""
import pathlib, re, subprocess, sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES = pathlib.Path(__file__).resolve().parent / "cases"


class Loader(yaml.SafeLoader):
    """`esphome config` emits !lambda tags; keep them as plain strings."""


Loader.add_multi_constructor("!", lambda loader, suffix, node: node.value)


def dump(selector):
    out = subprocess.run(
        ["esphome", "config", selector], cwd=ROOT,
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise SystemExit(f"esphome config {selector} failed:\n{out.stdout}{out.stderr}")
    return yaml.load(out.stdout, Loader=Loader)


# ------------------------------------------------------------------ asserts
#
# Three shapes cover every lint case in the plan. Values are matched against
# the entity's own dict first, so `initial_value <= max_value` compares two
# keys of the same entity; anything else is a literal.

EVERY = re.compile(r"^every (\w+) in \[([^\]]+)\] has (\w+) (<=|>=|<|>|is|) ?(.+)$")
ONE = re.compile(r"^(\w+) (\w+) has (\w+) (<=|>=|<|>|is|) ?(.+)$")
INCLUDES = re.compile(r"^(\w+)\.(\w+) includes (\w+)$")


def entity(config, domain, eid):
    for item in config.get(domain, []) or []:
        if isinstance(item, dict) and item.get("id") == eid:
            return item
    raise AssertionError(f"no {domain} with id {eid} in the config")


def find(config, eid):
    for domain, items in config.items():
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("id") == eid:
                    return item
    raise AssertionError(f"no entity with id {eid} in the config")


def compare(ent, key, op, want, where):
    if key not in ent:
        raise AssertionError(f"{where}: no {key}")
    got = ent[key]
    want = ent[want] if want in ent else want
    if isinstance(got, (int, float)) and not isinstance(got, bool):
        want = float(want)
    ok = {
        "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b,
        "<": lambda a, b: a < b, ">": lambda a, b: a > b,
        "": lambda a, b: a == b, "is": lambda a, b: a == b,
    }[op](got, want)
    if not ok:
        raise AssertionError(f"{where}: {key} is {got}, expected {op or '=='} {want}")


def check(config, line):
    for clause in line.split(" and "):
        clause = clause.strip()
        if m := EVERY.match(clause):
            domain, ids, key, op, want = m.groups()
            for eid in [i.strip() for i in ids.split(",")]:
                compare(entity(config, domain, eid), key, op, want, f"{domain} {eid}")
        elif m := INCLUDES.match(clause):
            eid, key, want = m.groups()
            got = find(config, eid).get(key) or []
            if want not in got:
                raise AssertionError(f"{eid}.{key} is {got}, expected it to include {want}")
        elif m := ONE.match(clause):
            domain, eid, key, op, want = m.groups()
            compare(entity(config, domain, eid), key, op, want, f"{domain} {eid}")
        else:
            raise SystemExit(f"lint_config.py cannot parse the assertion: {clause!r}")


def main(argv):
    cases = []
    for path in sorted(CASES.glob("*.yaml")):
        case = yaml.safe_load(path.read_text())
        if case.get("harness") != "ci-lint":
            continue
        if argv and case["id"] not in argv:
            continue
        cases.append(case)
    if not cases:
        raise SystemExit("no ci-lint cases to run")

    configs, failures = {}, []
    for case in cases:
        reasons = []
        for selector in case["selectors"]:
            if selector not in configs:
                configs[selector] = dump(selector)
            for line in case["assert"]:
                try:
                    check(configs[selector], line)
                except AssertionError as err:
                    reasons.append(f"{selector}: {err}")
        passed = not reasons
        expected = case["status"] == "green"
        ok = passed == expected
        print(f"{case['id']:8} {case['status']:6} {'pass' if passed else 'FAIL':4} "
              f"{'ok' if ok else 'UNEXPECTED'}")
        for reason in reasons:
            print(f"           {reason}")
        if not ok:
            failures.append(
                f"{case['id']}: green case failed" if expected else
                f"{case['id']}: red case passed — the gap closed, mark it green")

    for failure in failures:
        print(f"error: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
