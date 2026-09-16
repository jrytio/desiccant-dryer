#!/usr/bin/env python3
"""Run the `host` verification cases against a headless host build.

For every case file in tests/cases/ without `harness: ci-lint`, start the
native host build (esphome/desiccant-dryer-host.yaml) with a private prefs
directory, connect over the ESPHome native API, apply `setup`, walk `steps`
and report the result against the case's declared `status`.

Per docs/verification-plan.md, a `green` case that fails is an error, and so
is a `red` case that passes: a passing `red` case means the gap closed and the
case must be marked `green` in the same change. A case that needs a `Sim *`
knob the plant model does not have yet is skipped with a reason, not failed.

The display is compiled in as usual; SDL_VIDEODRIVER=dummy keeps it from
opening a window, so this runs on a CI runner with no display server.

Usage: tests/run_cases.py [case-id ...]      (default: every host case)
Options: --no-build (use the binary already compiled), --keep-logs DIR
"""
import argparse
import asyncio
import contextlib
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

try:
    import yaml
    from aioesphomeapi import APIClient
except ImportError:  # not the interpreter ESPHome is installed under
    # aioesphomeapi and PyYAML come with ESPHome; find its interpreter from the
    # launcher's shebang the way scripts/scenario-shots.sh finds Pillow, and
    # re-exec there once (the env flag stops a loop if that one lacks them too).
    launcher = shutil.which("esphome")
    if launcher is None or os.environ.get("RUN_CASES_REEXEC"):
        raise SystemExit("run_cases.py needs aioesphomeapi and PyYAML: "
                         "run it with ESPHome's own interpreter")
    with open(launcher) as fh:
        interpreter = fh.readline().removeprefix("#!").strip()
    os.execve(interpreter, [interpreter, __file__, *sys.argv[1:]],
              dict(os.environ, RUN_CASES_REEXEC="1"))

ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES = pathlib.Path(__file__).resolve().parent / "cases"
SELECTOR = "esphome/desiccant-dryer-host.yaml"
BINARY = ROOT / "esphome/.esphome/build/desiccant-dryer-host/.pioenvs/desiccant-dryer-host/program"
SECRETS = ROOT / "esphome/secrets.yaml"

API_HOST, API_PORT = "127.0.0.1", 6053
# The control tick in base.yaml. Real seconds, never scaled: Sim Speed scales
# the time the logic *counts*, not how often the interval fires.
TICK_S = 5.0
# A bare `expect` allows one tick plus a margin, because the derived sensors
# it reads (Control Humidity, Standby State, Fault Message) republish on their
# own 5 s interval. `{within_ticks: n}` asks for n ticks instead.
DEFAULT_GRACE_S = TICK_S + 1.0
POLL_S = 0.1


class CaseFailure(Exception):
    """A step did not hold. The message is the reason printed under the case."""


class Skip(Exception):
    """The case needs something that does not exist yet."""


# ---------------------------------------------------------------- the device


class Device:
    """One host-build process plus an API connection to it."""

    def __init__(self, home: pathlib.Path, log: pathlib.Path):
        self.home, self.log = home, log
        self.proc = None
        self.client = None
        self.states = {}        # entity key -> state object
        self.by_name = {}       # friendly name -> entity info

    async def start(self):
        env = dict(os.environ, HOME=str(self.home), SDL_VIDEODRIVER="dummy")
        # Line-buffered through a file so a failing case can show the tail.
        self.logfile = self.log.open("ab")
        self.proc = await asyncio.create_subprocess_exec(
            str(BINARY), cwd=str(ROOT), env=env,
            stdout=self.logfile, stderr=asyncio.subprocess.STDOUT,
        )
        await self.connect()

    async def connect(self):
        # Poll the listening socket rather than retrying APIClient.connect:
        # a refused connection logs an error line through aioesphomeapi, and
        # every case would start with one.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 30
        while True:
            try:
                writer = (await asyncio.open_connection(API_HOST, API_PORT))[1]
                writer.close()
                break
            except OSError:
                if self.proc.returncode is not None:
                    raise CaseFailure(f"the host build exited with {self.proc.returncode}")
                if loop.time() > deadline:
                    raise CaseFailure("the host build's API never came up")
                await asyncio.sleep(0.1)

        key = yaml.safe_load(SECRETS.read_text())["api_key"]
        self.client = APIClient(API_HOST, API_PORT, None, noise_psk=key)
        await self.client.connect(login=True)
        entities, _ = await self.client.list_entities_services()
        self.by_name = {e.name: e for e in entities}
        self.states = {}
        self.client.subscribe_states(lambda state: self.states.update({state.key: state}))
        # subscribe_states replays the current state of everything that has
        # one; buttons never do, so settle on "nothing new arrived" instead of
        # a count, and give the 5 s derived sensors one interval to publish.
        settled = loop.time() + TICK_S + 1.0
        seen = -1
        while loop.time() < settled or len(self.states) != seen:
            seen = len(self.states)
            await asyncio.sleep(0.25)
            if loop.time() > deadline + 30:
                raise CaseFailure("the host build never published its initial states")

    async def stop(self):
        if self.client is not None:
            with contextlib.suppress(Exception):
                await self.client.disconnect(force=True)
            self.client = None
        if self.proc is not None and self.proc.returncode is None:
            self.proc.terminate()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self.proc.wait(), 10)
            if self.proc.returncode is None:
                self.proc.kill()
                await self.proc.wait()
        if self.proc is not None:
            self.proc = None
            self.logfile.close()

    async def restart(self):
        """Press Restart (host's reboot is exit(0)), then run the binary again.

        Going through the button rather than a signal means ESPHome's shutdown
        hooks run, so persisted globals reach the prefs file exactly as they
        would on the board. The prefs directory is unchanged, so restored state
        survives and ALWAYS_OFF state does not.
        """
        await self.press("Restart")
        with contextlib.suppress(Exception):
            await self.client.disconnect(force=True)
        self.client = None
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self.proc.wait(), 15)
        if self.proc.returncode is None:
            raise CaseFailure("the host build did not exit when Restart was pressed")
        self.logfile.close()
        await self.start()

    # -------------------------------------------------------------- entities

    def entity(self, name):
        try:
            return self.by_name[name]
        except KeyError:
            raise CaseFailure(f"the host build has no entity named {name!r}")

    def state_of(self, name):
        info = self.entity(name)
        state = self.states.get(info.key)
        if state is None or getattr(state, "missing_state", False):
            return None
        return state.state

    async def set(self, name, value):
        info = self.entity(name)
        kind = type(info).__name__
        if kind == "SwitchInfo":
            self.client.switch_command(info.key, bool(value))
        elif kind == "NumberInfo":
            self.client.number_command(info.key, float(value))
        else:
            raise CaseFailure(f"cannot set {name!r} ({kind}); only switches and numbers take a value")

    async def press(self, name):
        info = self.entity(name)
        if type(info).__name__ != "ButtonInfo":
            raise CaseFailure(f"{name!r} is not a button")
        self.client.button_command(info.key)

    async def wait_for(self, predicate, timeout_s, message):
        deadline = asyncio.get_running_loop().time() + timeout_s
        while True:
            if predicate():
                return
            if asyncio.get_running_loop().time() >= deadline:
                raise CaseFailure(message)
            await asyncio.sleep(POLL_S)


# ------------------------------------------------------------- expectations


def matches(got, want):
    """Compare a published state against a case's expectation value."""
    if isinstance(want, dict):
        if "not" in want:
            return not matches(got, want["not"])
        if "min" in want and not (got is not None and float(got) >= float(want["min"])):
            return False
        if "max" in want and not (got is not None and float(got) <= float(want["max"])):
            return False
        if "value" in want:
            return matches(got, want["value"])
        return "min" in want or "max" in want
    if got is None:
        return want is None
    if isinstance(want, bool):
        return bool(got) is want
    if isinstance(want, (int, float)):
        try:
            return abs(float(got) - float(want)) < 0.05
        except (TypeError, ValueError):
            return False
    return str(got) == str(want)


def describe(value):
    return "unavailable" if value is None else value


async def expect(dev, wants, grace_s):
    """Every name must hold its expectation at the same moment, within grace."""
    deadline = asyncio.get_running_loop().time() + grace_s
    while True:
        bad = []
        for name, want in wants.items():
            got = dev.state_of(name)
            if not matches(got, want):
                bad.append((name, got))
        if not bad:
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise CaseFailure("; ".join(
                f"{n} is {describe(got)}, expected {wants[n]}" for n, got in bad))
        await asyncio.sleep(POLL_S)


# -------------------------------------------------------------------- cases


def referenced_names(case):
    """Every entity name the case touches, in source order."""
    names = list(case.get("setup", {}))
    for step in case.get("steps", []) or []:
        if isinstance(step, str):
            continue
        for verb in ("set", "expect", "wait_until"):
            names += list(step.get(verb, {}) or {})
        if "press" in step:
            names.append(step["press"])
    return names


async def run_steps(dev, case, speed):
    def real_s(sim_min):
        return float(sim_min) * 60.0 / speed

    for step in case.get("steps", []) or []:
        if step == "restart" or (isinstance(step, dict) and "restart" in step):
            await dev.restart()
            continue
        if "set" in step:
            for name, value in step["set"].items():
                await dev.set(name, value)
        if "press" in step:
            await dev.press(step["press"])
        if "wait_sim_min" in step:
            await asyncio.sleep(real_s(step["wait_sim_min"]))
        if "wait_until" in step:
            wants = step["wait_until"]
            # One tick of slack: a transition decided inside a tick is visible
            # only when the derived sensors next publish.
            budget = real_s(step.get("timeout_sim_min", 10)) + TICK_S
            try:
                await expect(dev, wants, budget)
            except CaseFailure as err:
                raise CaseFailure(f"wait_until timed out after "
                                  f"{step.get('timeout_sim_min', 10)} sim min: {err}")
        if "expect" in step:
            ticks = max((w.get("within_ticks") for w in step["expect"].values()
                         if isinstance(w, dict) and "within_ticks" in w), default=None)
            await expect(dev, step["expect"],
                         DEFAULT_GRACE_S if ticks is None else ticks * TICK_S)


async def run_case(case, keep_logs):
    home = pathlib.Path(tempfile.mkdtemp(prefix=f"{case['id']}-"))
    log = (keep_logs / f"{case['id']}.log") if keep_logs else (home / "host.log")
    dev = Device(home, log)
    try:
        await dev.start()
        setup = case.get("setup", {}) or {}
        timed = any(k in step for step in (case.get("steps") or []) if isinstance(step, dict)
                    for k in ("wait_sim_min", "timeout_sim_min"))
        if timed and "Sim Speed" not in setup:
            raise Skip("the case waits in simulated time but its setup does not set Sim Speed")
        speed = float(setup.get("Sim Speed", 1))
        for name, value in setup.items():
            await dev.set(name, value)
        # Sim Speed reaches time_scale on the plant model's next 1 s tick, and
        # the control tick must see it too before any timed step starts.
        await asyncio.sleep(TICK_S + 1.0)
        await run_steps(dev, case, speed)
        return None
    finally:
        await dev.stop()
        if log.exists():
            case["_tail"] = log.read_text(errors="replace").splitlines()[-10:]
        shutil.rmtree(home, ignore_errors=True)


def missing_knobs(case, names_present):
    return sorted({n for n in referenced_names(case)
                   if n.startswith("Sim ") and n not in names_present})


async def device_entity_names():
    """The entity names this build actually has, for the Sim-knob skip check."""
    home = pathlib.Path(tempfile.mkdtemp(prefix="probe-"))
    dev = Device(home, home / "host.log")
    try:
        await dev.start()
        return set(dev.by_name)
    finally:
        await dev.stop()
        shutil.rmtree(home, ignore_errors=True)


async def main_async(argv, keep_logs):
    cases = []
    for path in sorted(CASES.glob("*.yaml")):
        case = yaml.safe_load(path.read_text())
        if case.get("harness") == "ci-lint":
            continue
        if argv and case["id"] not in argv:
            continue
        cases.append(case)
    if not cases:
        raise SystemExit("no host cases to run")

    present = await device_entity_names()
    failures = []
    for case in cases:
        missing = missing_knobs(case, present)
        if missing:
            print(f"{case['id']:8} {case['status']:6} skip ok")
            print(f"           the plant model has no {', '.join(missing)} yet")
            continue
        reason = None
        try:
            await run_case(case, keep_logs)
        except Skip as err:
            print(f"{case['id']:8} {case['status']:6} skip ok")
            print(f"           {err}")
            continue
        except CaseFailure as err:
            reason = str(err)
        except Exception as err:                      # a runner bug, not a case result
            reason = f"{type(err).__name__}: {err}"

        passed = reason is None
        expected = case["status"] == "green"
        ok = passed == expected
        print(f"{case['id']:8} {case['status']:6} {'pass' if passed else 'FAIL':4} "
              f"{'ok' if ok else 'UNEXPECTED'}")
        if reason:
            print(f"           {reason}")
        if not ok:
            for line in case.get("_tail", []):
                print(f"           | {line}")
            failures.append(
                f"{case['id']}: green case failed" if expected else
                f"{case['id']}: red case passed — the gap closed, mark it green")

    for failure in failures:
        print(f"error: {failure}", file=sys.stderr)
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ids", nargs="*", help="case ids to run (default: all host cases)")
    ap.add_argument("--no-build", action="store_true",
                    help="use the host binary already compiled")
    ap.add_argument("--keep-logs", metavar="DIR",
                    help="write each case's host-build log here instead of a temp dir")
    args = ap.parse_args()

    if not SECRETS.exists():
        raise SystemExit(f"{SECRETS} is missing; copy esphome/secrets.ci.yaml to it")
    if not args.no_build:
        build = subprocess.run(["esphome", "compile", SELECTOR], cwd=ROOT,
                               capture_output=True, text=True)
        if build.returncode != 0:
            raise SystemExit(f"esphome compile {SELECTOR} failed:\n{build.stdout}{build.stderr}")
    if not BINARY.exists():
        raise SystemExit(f"no host binary at {BINARY}; run without --no-build")

    keep = pathlib.Path(args.keep_logs) if args.keep_logs else None
    if keep:
        keep.mkdir(parents=True, exist_ok=True)
    return asyncio.run(main_async(args.ids, keep))


if __name__ == "__main__":
    sys.exit(main())
