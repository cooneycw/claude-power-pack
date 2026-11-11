"""Recorded-provider dispatch for flow CI consumers (#1610 A).

Provider implementations retain their diagnostics; selection and aggregation are
shared here. Unsupported or unreadable populations are unknown, never green.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from .providers import PROVIDERS, REMEDY, ProviderError, read_provider_record, require_providers

_children: set[subprocess.Popen] = set()


def command(argv: list[str], *, timeout: float = 120, check: bool = False, **kwargs) -> subprocess.CompletedProcess:
    """Own each provider command's process group through timeout or signals."""
    if kwargs.pop("capture_output", False):
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    input_value = kwargs.pop("input", None)
    child = subprocess.Popen(argv, start_new_session=True, **kwargs)
    _children.add(child)
    try:
        stdout, stderr = child.communicate(input=input_value, timeout=timeout)
        result = subprocess.CompletedProcess(argv, child.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result
    except BaseException:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.communicate()
        raise
    finally:
        _children.discard(child)


def stop_children(signum: int, frame) -> None:
    for child in list(_children):
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass
    raise SystemExit(128 + signum)


def provider_lanes(project: str | Path) -> list[tuple[str, str]]:
    names = require_providers(read_provider_record(project).providers)
    result = []
    for name in names:
        lane = PROVIDERS[name].ci_lane
        if any(":" not in hook for hook in (PROVIDERS[name].flow_status, PROVIDERS[name].flow_watch)):
            raise ProviderError(f"registered CI lane {lane!r} is unavailable for {name}; install its lane handler")
        result.append((name, lane))
    return result


def lane_plan(project: str | Path, *, allow_fallback: bool = False) -> dict:
    """Stable offline API for doctor: no probes, subprocesses or record writes.

    One exception, local and read-only (issue #1677): a linked worktree with no
    record of its own, whose main checkout has one, costs a single
    `git ls-files` to learn whether that record is tracked.

    `status=ok` establishes a recorded plan only. An explicitly allowed fallback
    remains unknown until probing actually happens; `would_trigger` describes
    that future action rather than claiming any provider answered.
    """
    try:
        lanes = provider_lanes(project)
        return {"status": "ok", "source": "recorded", "reason": None,
                "providers": [name for name, _ in lanes],
                "lanes": [{"provider": name, "lane": lane} for name, lane in lanes],
                "fallback": {"requested": allow_fallback, "would_trigger": False}}
    except (ProviderError, OSError, ValueError, ImportError) as exc:
        return {"status": "unknown", "source": "fallback" if allow_fallback else "unknown",
                "reason": str(exc), "providers": [], "lanes": [],
                "fallback": {"requested": allow_fallback, "would_trigger": allow_fallback},
                "remedy": REMEDY}


def markers(output: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for line in output.splitlines():
        if line.startswith("FLOW_CI_") and ": " in line:
            key, value = line.split(": ", 1)
            result.setdefault(key, []).append(value)
    return result


def aggregate(states: list[str]) -> str:
    if "failure" in states:
        return "failure"
    if "stalled" in states:
        return "stalled"
    if any(state in {"running", "pending"} for state in states):
        return "running"
    if not states or any(state not in {"success", "not-found"} for state in states):
        return "unknown"
    return "not-found" if "not-found" in states else "success"


def callback(hook: str):
    module, separator, name = hook.partition(":")
    if not separator:
        raise ProviderError("registered CI callback unavailable")
    return getattr(importlib.import_module(module), name)


def shell_status(script: str, argv: list[str], lane: str) -> subprocess.CompletedProcess[str]:
    return command(["bash", script, *argv, "--wait", "0"],
                          env={**os.environ, "CPP_FLOW_CI_BACKEND": lane},
                          capture_output=True, text=True, timeout=120)


def shell_watch(script: str, argv: list[str], lane: str) -> subprocess.CompletedProcess[str]:
    return command(["bash", script, *argv],
                          env={**os.environ, "CPP_FLOW_PR_WATCH_BACKEND": lane},
                          capture_output=True, text=True, timeout=120)


def child_stderr(stderr: str, marker: str) -> None:
    for line in stderr.splitlines():
        if not line.startswith(marker + "="):
            print(line, file=sys.stderr)


def entry(function, marker: str, *args) -> int:
    code = 1
    previous = {sig: signal.signal(sig, stop_children) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        code = function(*args)
        return code
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        raise
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        print(f"{marker}={code}", file=sys.stderr)


def status_entry(script: str, argv: list[str]) -> int:
    return entry(status_main, "FLOW_CI_EXIT", script, argv)


def watch_entry(script: str, argv: list[str]) -> int:
    return entry(watch_main, "FLOW_PR_WATCH_EXIT", script, argv)


def status_main(script: str, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--path", default=os.getcwd())
    parser.add_argument("sha", nargs="?")
    parser.add_argument("--repo")
    parser.add_argument("--event")
    parser.add_argument("--secret-name")
    parser.add_argument("--region")
    parser.add_argument("--strict-event", action="store_true")
    parser.add_argument("--wait", nargs="?", const=600, type=int, default=0)
    parser.add_argument("--exit-code", action="store_true")
    parser.add_argument("--fallback-provider-probes", action="store_true")
    args, remaining = parser.parse_known_args(argv)
    if args.wait < 0:
        parser.error("--wait needs nonnegative seconds")
    # --path is re-supplied explicitly to every backend, independent of cwd.
    backend_args = [*remaining, "--path", args.path]
    for attribute in ("repo", "event", "secret_name", "region"):
        value = getattr(args, attribute)
        if value is not None:
            backend_args.extend(["--" + attribute.replace("_", "-"), value])
    if args.strict_event:
        backend_args.append("--strict-event")
    plan = lane_plan(args.path, allow_fallback=args.fallback_provider_probes)
    if plan["fallback"]["would_trigger"]:
        env = {**os.environ, "CPP_FLOW_CI_BACKEND": "probe"}
        fallback_argv = ["bash", script, *([args.sha] if args.sha else []),
                         *backend_args, "--wait", str(args.wait)]
        if args.exit_code:
            fallback_argv.append("--exit-code")
        try:
            result = command(fallback_argv, env=env, capture_output=True, text=True,
                             timeout=max(120, args.wait + 120))
        except subprocess.TimeoutExpired:
            print("flow-ci-status: explicit provider-probe fallback exceeded its wait budget", file=sys.stderr)
            print("FLOW_CI_SELECTION: fallback")
            print("FLOW_CI_PROVIDER: unknown")
            print("FLOW_CI_STATUS: unknown")
            return 2
        print(result.stdout, end="")
        child_stderr(result.stderr, "FLOW_CI_EXIT")
        return result.returncode
    if plan["status"] != "ok":
        print(f"flow-ci-status: {plan['reason']}; {REMEDY}", file=sys.stderr)
        print("FLOW_CI_SELECTION: unknown")
        print("FLOW_CI_PROVIDER: none")
        print("FLOW_CI_STATUS: unknown")
        return 2
    lanes = [(item["provider"], item["lane"]) for item in plan["lanes"]]
    # Capture mutable refs ONCE. Independent lanes must describe the same
    # commit even if the checkout moves during dispatch or a long wait.
    pinned = args.sha or "HEAD"
    if re.fullmatch(r"[0-9a-fA-F]{40}", pinned):
        pinned = pinned.lower()
    else:
        try:
            resolved = command(["git", "-C", args.path, "rev-parse", "--verify", "--end-of-options",
                                pinned + "^{commit}"], capture_output=True, text=True, timeout=10, check=True)
            pinned = resolved.stdout.strip()
            if not re.fullmatch(r"[0-9a-f]{40}", pinned):
                raise ProviderError("commit ref did not resolve to a full SHA")
        except (OSError, ValueError, subprocess.SubprocessError):
            print("flow-ci-status: commit ref unreadable; name the full commit SHA", file=sys.stderr)
            print("FLOW_CI_STATUS: unknown")
            return 2
    backend_args.insert(0, pinned)
    deadline = time.monotonic() + args.wait
    reports: list[tuple[str, str, dict[str, list[str]]]] = []
    expired = False
    # Lanes that have ANSWERED during this wait. Each poll is a fresh backend
    # process, so a listing that fails after the pipeline was already seen
    # arrives as a bare `unknown`, identical to a missing tool (counter-model
    # review, #1684). A lane that answered once and then cannot is having a
    # transient failure, not a structural one.
    answered: set[str] = set()
    while True:
        reports = []
        retry_lanes: set[str] = set()
        for name, lane in lanes:
            try:
                result = callback(PROVIDERS[name].flow_status)(script, backend_args, lane)
                child_stderr(result.stderr, "FLOW_CI_EXIT")
                report = markers(result.stdout)
                values = report.get("FLOW_CI_STATUS", [])
                state = values[0] if len(values) == 1 and (
                    result.returncode == 0 or result.returncode == 1 and values[0] in {"failure", "stalled"}
                ) else "unknown"
                if report.get("FLOW_CI_REF") != [pinned] or report.get("FLOW_CI_PROVIDER") != [name]:
                    state = "unknown"
                    report.pop("FLOW_CI_RETRYABLE", None)
            except (OSError, ValueError, ImportError, AttributeError, subprocess.SubprocessError):
                report, state = {}, "unknown"
            # A validated "found it, could not read it yet" IS an answer: the
            # lane reached its provider (counter-model review, pass 2).
            if state != "unknown" or report.get("FLOW_CI_RETRYABLE"):
                answered.add(name)
            if state == "unknown" and name in answered:
                retry_lanes.add(name)
            reports.append((name, state, report))
        verdict = aggregate([state for _, state, _ in reports])
        # An `unknown` is worth another look only when EVERY unknown lane
        # either said its pipeline or listing could not be read yet, or has
        # already answered during this wait (issue #1684). Any other unknown -
        # no record, a lane that never answered, a final lane judgement - is
        # not resolved by polling and still ends the wait at once.
        unknown_lanes = [name for name, state, _ in reports if state == "unknown"]
        retryable = verdict == "unknown" and bool(unknown_lanes) and all(
            name in retry_lanes for name in unknown_lanes)
        if verdict in {"success", "failure", "stalled"} or (verdict == "unknown" and not retryable) \
                or args.wait <= 0:
            break
        if time.monotonic() >= deadline:
            expired = True
            break
        time.sleep(min(15, max(0, deadline - time.monotonic())))
    print("FLOW_CI_SELECTION: recorded")
    print("FLOW_CI_PROVIDERS: " + ",".join(name for name, _ in lanes))
    # Keep the complete single-provider contract; for multiple providers keep
    # decisive diagnostics and publish every lane's independent population.
    decisive = next((item for item in reports if item[1] == verdict), reports[0])
    for key, values in decisive[2].items():
        if key in {"FLOW_CI_STATUS", "FLOW_CI_PROVIDER", "FLOW_CI_WAIT"}:
            continue
        for value in values:
            print(f"{key}: {value}")
    print("FLOW_CI_PROVIDER: " + ",".join(name for name, _ in lanes))
    print("FLOW_CI_LANES: " + json.dumps({name: {"status": state, "evidence": report}
                                           for name, state, report in reports}, sort_keys=True))
    wait = "none" if args.wait <= 0 else f"expired ({args.wait}s)" if expired else "settled"
    print("FLOW_CI_WAIT: " + wait)
    print("FLOW_CI_STATUS: " + verdict)
    # A wait that ran out is never exit 0, whatever it last saw (issue #1684).
    if expired:
        print(f"flow-ci-status: the --wait window of {args.wait}s expired with status "
              f"'{verdict}' (exit 5)", file=sys.stderr)
        return 5
    if verdict in {"unknown", "not-found"}:
        return 2
    return 1 if args.exit_code and verdict in {"failure", "stalled"} else 0


def github_actions_context(context: str) -> bool:
    return bool(context) and not context.startswith("ci/woodpecker/")


def woodpecker_context(context: str) -> bool:
    return context.startswith(("ci/woodpecker/pr/", "ci/woodpecker/pull_request/"))


def required_contexts(repo: str, branch: str, gh: str) -> list[str]:
    """Union classic names, app-keyed names and applicable branch rules."""
    contexts: set[str] = set()
    answered = False
    for endpoint in (f"repos/{repo}/branches/{branch}/protection/required_status_checks",
                     f"repos/{repo}/rules/branches/{branch}"):
        response = command([gh, "api", endpoint], capture_output=True, text=True, timeout=30)
        if response.returncode:
            # Classic protection's explicit 404 means no classic rule; a 403,
            # transport failure or malformed response leaves an unexamined
            # source and cannot be hidden by readable rulesets.
            if endpoint.endswith("required_status_checks") and "(HTTP 404)" in response.stderr:
                answered = True
                continue
            raise ProviderError("required checks unreadable from " + endpoint)
        value = json.loads(response.stdout)
        if endpoint.endswith("required_status_checks"):
            if not isinstance(value, dict):
                raise ProviderError("classic required checks malformed")
            names = value.get("contexts", [])
            checks = value.get("checks", [])
            if not isinstance(names, list) or not isinstance(checks, list):
                raise ProviderError("classic required checks malformed")
            entries = [*names, *(item.get("context") if isinstance(item, dict) else None for item in checks)]
        else:
            if not isinstance(value, list):
                raise ProviderError("required-check rules malformed")
            entries = []
            for rule in value:
                if not isinstance(rule, dict):
                    raise ProviderError("required-check rule malformed")
                if rule.get("type") == "required_status_checks":
                    checks = rule.get("parameters", {}).get("required_status_checks", [])
                    if not isinstance(checks, list):
                        raise ProviderError("required-check rules malformed")
                    entries.extend(item.get("context") if isinstance(item, dict) else None for item in checks)
        if any(not isinstance(name, str) or not name or "\n" in name for name in entries):
            raise ProviderError("required-check context malformed")
        contexts.update(entries)
        answered = True
    if not answered:
        raise ProviderError("required checks unreadable from classic protection and rulesets")
    if not contexts:
        raise ProviderError("no required-check population established")
    return sorted(contexts)


def context_lanes(project: str | Path, contexts: list[str]) -> list[tuple[str, str, str]]:
    lanes = provider_lanes(project)
    result = []
    for context in contexts:
        matches = []
        for name, lane in lanes:
            hook = PROVIDERS[name].flow_context
            module, separator, function = hook.partition(":")
            if not separator:
                raise ProviderError(name + ": required-context matcher unavailable")
            if getattr(importlib.import_module(module), function)(context):
                matches.append((PROVIDERS[name].flow_context_priority, name, lane))
        if matches:
            priority = max(item[0] for item in matches)
            matches = [item for item in matches if item[0] == priority]
        if len(matches) != 1:
            raise ProviderError(f"required context {context!r} cannot be attributed to one recorded provider")
        result.append((context, matches[0][1], matches[0][2]))
    # Every selected provider needs an examined required context population.
    if any(name not in {name for _, name, _ in result} for name, _ in lanes):
        raise ProviderError("selected provider has no required PR context population")
    return result


def observed_watch_failure(output: str) -> bool:
    return any(line.lower() in {
        "flow_pr_watch_state=failure", "flow_pr_watch_state=error", "flow_pr_watch_state=killed",
        "flow_pr_watch_state=cancelled", "flow_pr_watch_state=timed_out", "flow_pr_watch_state=startup_failure",
        "flow_pr_watch_state=action_required", "flow_pr_watch_state=stale",
    } for line in output.splitlines())


def cancellation_evidence(output: str) -> bool:
    fields: dict[str, list[str]] = {}
    for line in output.splitlines():
        if line.startswith("FLOW_PR_WATCH_") and "=" in line:
            key, value = line.split("=", 1)
            fields.setdefault(key, []).append(value)
    pipeline = fields.get("FLOW_PR_WATCH_PIPELINE", [])
    return (fields.get("FLOW_PR_WATCH_KILL_SIGNATURE") == ["1"]
            and fields.get("FLOW_PR_WATCH_FAILED") == ["-"]
            and fields.get("FLOW_PR_WATCH_SUMMARY_FAILED") in (["0"], ["-"])
            and len(pipeline) == 1 and pipeline[0].isdigit() and int(pipeline[0]) > 0)


def emit_watch(reports: list[tuple[str, str, str]], verdict: str, head: str) -> int:
    candidates = [item for item in reports if item[1] == verdict]
    if verdict == "red":
        candidates = [item for item in candidates if not cancellation_evidence(item[2])] or candidates
    elif verdict == "cancelled":
        candidates = [item for item in reports if cancellation_evidence(item[2])]
    decisive = (candidates or reports)[0] if reports else None
    if decisive:
        for line in decisive[2].splitlines():
            if not line.startswith(("FLOW_PR_WATCH: ", "FLOW_PR_WATCH_HEAD=")):
                print(line)
    print("FLOW_PR_WATCH_HEAD=" + head)
    print("FLOW_PR_WATCH_CONTEXTS=" + json.dumps({context: state for context, state, _ in reports}))
    print("FLOW_PR_WATCH: " + verdict)
    return {"red": 1, "unknown": 2, "timeout": 5}.get(verdict, 0)


def moved_watch(reports: list[tuple[str, str, str]], original: dict, current: dict) -> int:
    if any(state == "red" and not cancellation_evidence(output) for _, state, output in reports):
        verdict = "red"
    elif current["headRefOid"] != original["headRefOid"] and any(
        cancellation_evidence(output) for _, _, output in reports
    ):
        verdict = "cancelled"
    else:
        verdict = "unknown"
    print("flow-pr-watch: PR head/base changed; cancellation needs witnessed kill evidence.", file=sys.stderr)
    return emit_watch(reports, verdict, original["headRefOid"])


def watch_main(script: str, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="flow-pr-watch.sh")
    parser.add_argument("pr")
    parser.add_argument("--path", default=os.getcwd())
    parser.add_argument("--repo")
    parser.add_argument("--context")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--baseline")
    parser.add_argument("--fallback-provider-probes", action="store_true")
    args = parser.parse_args(argv)
    gh = os.environ.get("FLOW_PR_WATCH_GH", "gh")
    reports: list[tuple[str, str, str]] = []
    original: dict = {}
    try:
        if not args.pr.lstrip("#").isdigit() or args.timeout < 0:
            parser.error("numeric PR and nonnegative timeout required")
        # Validate the canonical record before any remote probe.
        plan = lane_plan(args.path, allow_fallback=args.fallback_provider_probes)
        if plan["fallback"]["would_trigger"]:
            fallback_args = [arg for arg in argv if arg != "--fallback-provider-probes"]
            result = command(["bash", script, *fallback_args],
                             env={**os.environ, "CPP_FLOW_PR_WATCH_BACKEND": "probe"},
                             capture_output=True, text=True, timeout=max(120, args.timeout + 120))
            print(result.stdout, end="")
            child_stderr(result.stderr, "FLOW_PR_WATCH_EXIT")
            return result.returncode
        if plan["status"] != "ok":
            raise ProviderError(plan["reason"])
        repo = args.repo
        if not repo:
            response = command([gh, "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
                                      cwd=args.path, capture_output=True, text=True, timeout=30, check=True)
            repo = response.stdout.strip()
        pr = args.pr.lstrip("#")
        def head() -> dict:
            response = command([gh, "pr", "view", pr, "--repo", repo,
                                       "--json", "headRefOid,baseRefName"],
                                      capture_output=True, text=True, timeout=30, check=True)
            value = json.loads(response.stdout)
            if not isinstance(value, dict) or not all(isinstance(value.get(key), str) and value[key]
                                                     for key in ("headRefOid", "baseRefName")):
                raise ProviderError("PR head/base unreadable")
            return value
        original = head()
        contexts = required_contexts(repo, original["baseRefName"], gh)
        selected = context_lanes(args.path, contexts)
        if args.context:
            if args.context not in contexts:
                raise ProviderError("requested context is not required by this PR base")
            selected = [item for item in selected if item[0] == args.context]
        deadline = time.monotonic() + args.timeout
        reports = []
        while True:
            current = head()
            if current != original:
                return moved_watch(reports, original, current)
            reports = []
            for context, name, lane in selected:
                watch_argv = [pr, "--path", args.path, "--repo", repo,
                              "--context", context, "--timeout", "0", "--watch-head", original["headRefOid"]]
                if args.baseline:
                    watch_argv.extend(["--baseline", args.baseline])
                response = callback(PROVIDERS[name].flow_watch)(script, watch_argv, lane)
                child_stderr(response.stderr, "FLOW_PR_WATCH_EXIT")
                verdicts = [line.removeprefix("FLOW_PR_WATCH: ") for line in response.stdout.splitlines()
                            if line.startswith("FLOW_PR_WATCH: ")]
                verdict = verdicts[0] if len(verdicts) == 1 and response.returncode in {0, 1, 5} else "unknown"
                if verdict == "unknown" and observed_watch_failure(response.stdout):
                    verdict = "red"  # Unknown attribution cannot erase an observed red check.
                if verdict == "cancelled" and not cancellation_evidence(response.stdout):
                    verdict = "red" if observed_watch_failure(response.stdout) else "unknown"
                if [line for line in response.stdout.splitlines() if line.startswith("FLOW_PR_WATCH_HEAD=")] != [
                    "FLOW_PR_WATCH_HEAD=" + original["headRefOid"]
                ]:
                    verdict = "unknown"
                reports.append((context, verdict, response.stdout))
            states = [verdict for _, verdict, _ in reports]
            if "red" in states:
                verdict = "red"
            elif all(state in {"green", "flake"} for state in states):
                verdict = "flake" if "flake" in states else "green"
            elif "cancelled" in states:
                verdict = "cancelled"
            else:
                verdict = "unknown"
            if verdict != "unknown" or args.timeout == 0 or time.monotonic() >= deadline:
                break
            time.sleep(min(max(1, args.interval), max(0, deadline - time.monotonic())))
        current = head()
        if current != original:
            return moved_watch(reports, original, current)
        if verdict == "unknown" and args.timeout > 0 and time.monotonic() >= deadline:
            verdict = "timeout"
        return emit_watch(reports, verdict, original["headRefOid"])
    except (ProviderError, OSError, ValueError, ImportError, AttributeError, subprocess.SubprocessError) as exc:
        print(f"flow-pr-watch: {exc}; {REMEDY}", file=sys.stderr)
        if any(state == "red" for _, state, _ in reports):
            # Later unreadable evidence cannot erase a failure already tied
            # to the pinned head by the provider response contract.
            return emit_watch(reports, "red", original["headRefOid"])
        print("FLOW_PR_WATCH: unknown")
        return 2


def host_preflight(project: str | Path) -> dict:
    """A recorded missing capability stops; unknown is an explicit warning."""
    from .host import read_host_record
    lanes = provider_lanes(project)
    record = read_host_record(project)
    selected = {name: record["providers"][name] for name, _ in lanes}
    statuses = {state["status"] for state in selected.values()}
    verdict = "missing" if "missing" in statuses else "warn" if "unknown" in statuses else "ok"
    return {"status": verdict, "checked_at": record["checked_at"], "providers": selected,
            "lanes": [lane for _, lane in lanes], "refresh": "Run /cpp:init Tier 4 on the host to refresh capability."}


def host_preflight_main(project: str) -> int:
    try:
        report = host_preflight(project)
    except (ProviderError, OSError, ValueError, ImportError) as exc:
        print(f"flow-host-preflight: {exc}; {REMEDY}", file=sys.stderr)
        print("FLOW_CI_HOST: unknown (project provider unreadable)")
        return 2
    print("FLOW_CI_HOST_PROVIDERS: " + ",".join(report["providers"]))
    print("FLOW_CI_HOST_LANES: " + ",".join(report["lanes"]))
    checked = report["checked_at"] or "no recorded timestamp"
    for name, state in report["providers"].items():
        print(f"FLOW_CI_HOST_PROVIDER: {name}: last recorded {state['status']} at {checked} ({state['reason']})")
    if report["status"] != "ok":
        print(report["refresh"], file=sys.stderr)
    print("FLOW_CI_HOST: " + report["status"])
    return 1 if report["status"] == "missing" else 0
