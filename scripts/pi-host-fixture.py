#!/usr/bin/env python3
"""Explicit disposable host observations for pi; UNKNOWN without real evidence.

No provider prompt, owner installation or credential discovery is performed.
RPC observation is separate from copier-only syscall observation.
"""
# NEGATIVE-CONTROL: controls/pi-rpc-observer
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.host_update.models import AdapterError  # noqa: E402
from lib.host_update.pi_adapter import PiAdapter, make_request  # noqa: E402


def response(stdout, request_id, command):
    rows = []
    for line in stdout.split("\n"):
        if line:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("non-object RPC record")
            if value.get("id") == request_id:
                rows.append(value)
    if len(rows) != 1 or rows[0].get("success") is not True or rows[0].get("command") != command:
        raise ValueError("no unique successful correlated RPC response")
    return rows[0]["data"]


def rpc_audit(record):
    findings, unknown = [], []
    expected = record["expected"]
    if not expected or len(set(expected)) != len(expected):
        raise ValueError("expected skill population is empty/duplicate")
    baseline, installed = record["baseline"], record["installed"]
    baseline_rows = response(baseline["stdout"], "commands", "get_commands")["commands"]
    rows = response(installed["stdout"], "commands", "get_commands")["commands"]
    if any(not isinstance(population, list) or not all(isinstance(r, dict) for r in population)
           for population in (baseline_rows, rows)):
        raise ValueError("unknown command population")
    if any(r.get("name") in ("skill:" + slug for slug in expected) for r in baseline_rows):
        raise ValueError("baseline already contains expected skills")
    for slug in expected:
        selected = [r for r in rows if r.get("name") == "skill:" + slug]
        if selected and not isinstance(selected[0].get("sourceInfo"), dict):
            raise ValueError("source attribution shape unavailable")
        if len(selected) != 1:
            findings.append("missing/duplicate skill:" + slug)
        elif (selected[0].get("source") != "skill" or selected[0].get("sourceInfo", {}).get("scope") != "user" or
              selected[0].get("sourceInfo", {}).get("path") != record["agent"] + "/skills/" + slug + "/SKILL.md" or
              selected[0].get("sourceInfo", {}).get("baseDir") != record["agent"]):
            findings.append("unexpected source attribution:" + slug)
    other = [r for r in rows if r.get("name") not in {"skill:" + slug for slug in expected}]
    if other != baseline_rows:
        findings.append("unexpected non-topic command population changed")
    if installed["stderr"] != baseline["stderr"]:
        findings.append("added/changed diagnostics")
    for label, result in (("baseline", baseline), ("installed", installed)):
        if result.get("exit") != 0 or result.get("forced_stop") is not False:
            unknown.append(label + " child did not exit normally")
    tools = record.get("tools")
    if tools is None:
        unknown.append("pi 1.6.0 documented RPC has no built-in-tool inventory command")
    elif not isinstance(tools, dict):
        raise ValueError("unknown tool inventory shape")
    elif (not tools.get("baseline") or tools["baseline"] != tools.get("installed") or
          "bash" not in tools["baseline"]):
        findings.append("built-in tools changed or empty")
    return {"state": "finding" if findings else "unknown" if unknown else "matches", "expected": len(expected),
            "examined": len(rows), "findings": findings, "unknown": unknown, "scope": "supplied-RPC-pair"}


def run_child(argv, cwd, env, payload=None, timeout=30):
    child = subprocess.Popen(argv, cwd=cwd, env=env, text=True, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    forced = False
    try:
        out, err = child.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        forced = True
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            out, err = child.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            out, err = child.communicate(timeout=3)
    return {"argv": argv, "stdout": out, "stderr": err, "exit": child.returncode,
            "forced_stop": forced, "pid": child.pid}


def load_auditor():
    spec = importlib.util.spec_from_file_location("pi_syscall_audit", ROOT / "scripts/pi-syscall-audit.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def host_lane(args):
    fixture = Path(tempfile.mkdtemp(prefix="cpp-pi-a2-"))
    fixture.chmod(0o700)
    record = {"fixture": str(fixture), "revision": args.revision, "lane": args.lane,
              "python": sys.version, "observations": []}
    try:
        if not args.source.is_absolute():
            raise ValueError("absolute reviewed source checkout required")
        for name in ("home", "agent", "work", "config", "data", "cache", "history", "evidence"):
            (fixture / name).mkdir(mode=0o700)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
               "HOME": str(fixture / "home"), "PI_CODING_AGENT_DIR": str(fixture / "agent"),
               "PI_CODING_AGENT_SESSION_DIR": str(fixture / "history"), "PI_OFFLINE": "1",
               **{"XDG_" + k.upper() + "_HOME": str(fixture / k) for k in ("config", "data", "cache")}}
        record["environment_names"] = sorted(env)
        adapter = PiAdapter(cwd=fixture / "work", home=fixture / "home", agent=fixture / "agent", environ=env)
        request = make_request(adapter, args.source, revision=args.revision)
        # Force both binding and actual expected build before reporting any lane.
        policy = adapter.preflight(request)
        expected = adapter.build(request.revision, policy)
        base = [sys.executable, str(ROOT / "scripts/pi-skill-sync.py"), "--root", str(args.source),
                "--revision", args.revision, "--home", env["HOME"], "--agent-dir", env["PI_CODING_AGENT_DIR"], "--json"]
        record["expected"] = [p.name for p in expected.packages]
        record["script_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in (Path(__file__), ROOT / "scripts/pi-syscall-audit.py")}
        if args.lane == "rpc":
            if not args.pi_bin or not args.pi_bin.is_absolute():
                raise ValueError("explicit absolute pi executable required")
            version = run_child([str(args.pi_bin), "--version"], fixture / "work", env)
            record["version"] = version
            if version["exit"] != 0 or version["stdout"].strip() != "1.6.0":
                raise ValueError("only source-reviewed pi 1.6.0 is supported by this probe")

            def rpc():
                return run_child([str(args.pi_bin), "--mode", "rpc", "--offline", "--no-session"],
                                 fixture / "work", env, '{"id":"commands","type":"get_commands"}\n')

            baseline = rpc()
            installed = run_child([*base, "--install"], fixture / "work", env, timeout=120)
            record["installation"] = installed
            if installed["exit"] != 0 or installed["forced_stop"]:
                raise ValueError("actual installation did not complete")
            verified = run_child([*base, "--verify-installed"], fixture / "work", env, timeout=120)
            record["verification"] = verified
            if verified["exit"] != 0 or verified["forced_stop"]:
                raise ValueError("actual installed verification did not complete")
            observed = rpc()
            pair = {"agent": str(fixture / "agent"), "expected": record["expected"],
                    "baseline": baseline, "installed": observed, "tools": None}
            record["pair"] = pair
            record["audit"] = rpc_audit(pair)
            first = record["expected"][0]
            package = fixture / "agent/skills" / first
            removed = fixture / "evidence/removed-package"
            package.rename(removed)
            absent = rpc()
            absence_pair = dict(pair, installed=absent)
            record["removal_control"] = {"observation": absent, "audit": rpc_audit(absence_pair)}
            removed.rename(package)
            restored = rpc()
            record["restored"] = restored
            restored_audit = rpc_audit(dict(pair, installed=restored))
            if (not any("missing/duplicate" in f for f in record["removal_control"]["audit"]["findings"])
                    or restored_audit["findings"]):
                record["audit"]["unknown"].append("presence/removal/restoration comparison unresolved")
                if record["audit"]["state"] == "matches":
                    record["audit"]["state"] = "unknown"
            project = fixture / "work/.pi/skills" / first / "SKILL.md"
            project.parent.mkdir(parents=True)
            project.write_text(f"---\nname: {first}\ndescription: Synthetic shadow fixture\n---\nFixture only.\n")
            settings_file = fixture / "agent/settings.json"
            old_settings = settings_file.read_bytes() if settings_file.exists() else None
            settings_file.write_text('{"defaultProjectTrust":"always"}\n')
            shadow = rpc()
            selected = [row for row in response(shadow["stdout"], "commands", "get_commands")["commands"]
                        if row.get("name") == "skill:" + first]
            record["shadowing"] = {"observation": shadow, "selected": selected,
                                   "global_installation": "separate file fidelity",
                                   "context": "synthetic trusted project"}
            if len(selected) != 1 or selected[0].get("sourceInfo", {}).get("scope") != "project":
                record["audit"]["unknown"].append("bounded project shadowing not observed")
            project.unlink()
            if old_settings is None:
                settings_file.unlink()
            else:
                settings_file.write_bytes(old_settings)
            malformed = fixture / "agent/skills/cpp-malformed-probe/SKILL.md"
            malformed.parent.mkdir()
            malformed.write_text("---\nname: invalid name\n---\nMalformed fixture only.\n")
            bad = rpc()
            record["malformed_diagnostic_control"] = {"observation": bad,
                                                       "detected": bad["stderr"] != observed["stderr"]}
            if not record["malformed_diagnostic_control"]["detected"]:
                record["audit"]["unknown"].append("malformed fixture did not add a diagnostic")
                if record["audit"]["state"] == "matches":
                    record["audit"]["state"] = "unknown"
        else:
            if not args.strace_bin or not args.strace_bin.is_absolute():
                raise ValueError("explicit absolute strace executable required")
            record["version"] = run_child([str(args.strace_bin), "--version"], fixture / "work", env)
            allowance = {"skills": str(policy.install_root), "lock": str(policy.lock_path), "source": str(args.source),
                         "histories": [str(fixture / "history"), str(fixture / "agent/sessions")],
                         "settings": [str(fixture / "agent/settings.json"), str(fixture / "work/.pi/settings.json")],
                         "cwd": str(fixture / "work"), "metadata": [str(fixture / "work"), str(fixture / "home")],
                         "mode": "install", "runtime_reads": ["/usr", "/bin", "/lib", "/lib64", sys.base_prefix,
                                                               "/dev/null", "/etc/ld.so.cache", "/etc/localtime",
                                                               "/etc/ld.so.preload", "/proc/self/exe", "/proc/self/fd"]}

            def trace(label, argv, operation, expected_exit=0, overrides=None, environment=None,
                      expected_audit="matches"):
                prefix = fixture / "evidence" / label
                child = run_child([str(args.strace_bin), "-ff", "-ttt", "-yy", "-s", "65535", "-o", str(prefix),
                                   "-e", "trace=%file,%desc,%process", *argv], fixture / "work",
                                  environment or env, timeout=180)
                traces = {p.name.rsplit(".", 1)[1]: p.read_text() for p in prefix.parent.glob(prefix.name + ".*")}
                # The initial execve, rather than a later write/string mention,
                # identifies the top-level Python command.
                roots = [pid for pid, value in traces.items()
                         if any("execve(" in line and str(argv[0]) in line and str(argv[1]) in line
                                for line in value.split("\n"))]
                root_pid = roots[0] if len(roots) == 1 else ""
                supplied = {"allowance": dict(allowance, mode=operation, **(overrides or {})),
                            "root_pid": root_pid, "traces": traces, "exit_codes": {root_pid: expected_exit}}
                answer = load_auditor().audit(supplied)
                record["observations"].append({"case": label, "child": child,
                                                "trace_record": supplied, "audit": answer,
                                                "expected_audit": expected_audit, "expected_exit": expected_exit})
                return child, answer

            traced, observed = trace("actual-install", [*base, "--install"], "install")
            record["installation"] = traced
            record["audit"] = dict(observed, findings=list(observed["findings"]), unknown=list(observed["unknown"]))
            if traced["exit"] != 0 or traced["forced_stop"]:
                record["audit"]["state"] = "unknown"
                record["audit"]["unknown"].append("traced installation did not complete")
            verify, verify_audit = trace("actual-verify", [*base, "--verify-installed"], "verify")
            record["verification"] = verify
            if verify["exit"] != 0 or verify_audit["state"] != "matches":
                record["audit"]["state"] = "unknown"
                record["audit"]["unknown"].append("traced no-create verification not established")
            # Actual live observer controls operate solely on synthetic paths.
            auth = fixture / "agent/auth.json"
            auth.write_text("synthetic non-secret sentinel\n")
            trusted = fixture / "agent/extensions"
            trusted.mkdir()
            seeds = {
                "seeded-auth-stat": [sys.executable, "-c", "import os,sys; os.stat(sys.argv[1])", str(auth)],
                "transient-trusted-write": [sys.executable, "-c",
                                            "import pathlib,sys; p=pathlib.Path(sys.argv[1]); "
                                            "p.write_text('synthetic'); p.unlink()", str(trusted / "transient")],
            }
            for label, argv in seeds.items():
                child, answer = trace(label, argv, "install", expected_audit="finding")
                if child["exit"] != 0 or answer["state"] != "finding":
                    record["audit"]["state"] = "unknown"
                    record["audit"]["unknown"].append(label + " live opposite not established")
            assert auth.read_text() == "synthetic non-secret sentinel\n"
            assert not (trusted / "transient").exists()
            # Refusal inputs are prepared before tracing; the subject must not
            # touch protected descendants while classifying their roots.
            build_base = [v for v in base]
            index = build_base.index("--revision")
            del build_base[index:index + 2]
            legal_parent = fixture / "legal-build"
            legal_parent.mkdir()
            child, answer = trace("legal-isolated-build",
                                  [*build_base, "--write", "--output-root", str(legal_parent / "skills")],
                                  "build", overrides={"skills": str(legal_parent / "skills")})
            if child["exit"] != 0 or answer["state"] != "matches":
                record["audit"]["unknown"].append("legal isolated output comparison unresolved")
            trusted_outputs = [("trusted-" + name, fixture / "agent" / name / "skills")
                               for name in ("extensions", "tools", "settings.json", "prompts")]
            for label, output in [*trusted_outputs, ("project-trusted", fixture / "work/.pi/skills"),
                                  ("history-default", fixture / "agent/sessions/skills"),
                                  ("history-default-nested", fixture / "agent/sessions/nested/skills")]:
                child, answer = trace(label, [*build_base, "--write", "--output-root", str(output)],
                                      "build", expected_exit=1)
                if child["exit"] != 1 or answer["state"] != "matches":
                    record["audit"]["unknown"].append(label + " zero-touch refusal not established")
            for origin in ("cli", "environment", "global", "project"):
                history = fixture / ("history-" + origin)
                history.mkdir()
                settings_path = fixture / ("agent/settings.json" if origin == "global" else "work/.pi/settings.json")
                if origin in ("global", "project"):
                    settings_path.parent.mkdir(exist_ok=True)
                    settings_path.write_text(json.dumps({"sessionDir": str(history)}))
                extra = ["--session-dir", str(history)] if origin == "cli" else []
                child_env = dict(env, PI_CODING_AGENT_SESSION_DIR=str(history)) if origin == "environment" else env
                child, answer = trace("history-" + origin,
                                      [*build_base, "--write", "--output-root", str(history / "skills"), *extra],
                                      "build", expected_exit=1, environment=child_env,
                                      overrides={"histories": [*allowance["histories"], str(history)]})
                if child["exit"] != 1 or answer["state"] != "matches":
                    record["audit"]["unknown"].append("history-" + origin + " zero-touch refusal unresolved")
                child, answer = trace("history-" + origin + "-nested",
                                      [*build_base, "--write", "--output-root", str(history / "nested/skills"),
                                       *extra], "build", expected_exit=1, environment=child_env,
                                      overrides={"histories": [*allowance["histories"], str(history)]})
                if child["exit"] != 1 or answer["state"] != "matches":
                    record["audit"]["unknown"].append("nested history refusal unresolved: " + origin)
                if origin in ("global", "project"):
                    settings_path.unlink()
            inverse = fixture / "inverse/skills/history"
            inverse.mkdir(parents=True)
            child, answer = trace("history-inverse",
                                  [*build_base, "--write", "--output-root", str(inverse.parent),
                                   "--session-dir", str(inverse)], "build", expected_exit=1,
                                  overrides={"histories": [*allowance["histories"], str(inverse)]})
            if child["exit"] != 1 or answer["state"] != "matches":
                record["audit"]["unknown"].append("inverse history refusal unresolved")
            history_alias = fixture / "history-alias"
            history_alias.symlink_to(fixture / "history", target_is_directory=True)
            child, answer = trace("history-symlink",
                                  [*build_base, "--write", "--output-root", str(history_alias / "skills"),
                                   "--session-dir", str(history_alias)], "build", expected_exit=1,
                                  overrides={"histories": [*allowance["histories"], str(history_alias)],
                                             "aliases": {str(history_alias): str(fixture / "history")}})
            if child["exit"] != 1 or answer["state"] != "matches":
                record["audit"]["unknown"].append("history symlink refusal unresolved")
            protected = fixture / "protected-agent"
            protected.mkdir()
            (protected / "settings.json").write_text('{"fixture_sentinel":true}\n')
            alias = fixture / "agent-alias"
            alias.symlink_to(protected, target_is_directory=True)
            aliased = list(base)
            aliased[aliased.index("--agent-dir") + 1] = str(alias)
            child, answer = trace("agent-prefix-alias", [*aliased, "--install"], "install", expected_exit=1,
                                  overrides={"metadata": [*allowance["metadata"], str(alias)],
                                             "aliases": {str(alias): str(protected)}})
            if child["exit"] != 1 or answer["state"] != "matches":
                record["audit"]["unknown"].append("above-root alias zero-touch refusal unresolved")
            if (protected / "settings.json").read_text() != '{"fixture_sentinel":true}\n':
                raise ValueError("protected synthetic settings changed")
            ledger = policy.ledger_path
            if ledger.exists() and traced["exit"] == 0:
                owned = json.loads(ledger.read_bytes())
                # Use a real available predecessor commit; only metadata is
                # made stale, never the immutable candidate source.
                predecessor = run_child(["git", "-C", str(args.source), "rev-parse", "HEAD^"],
                                        fixture / "work", env)["stdout"].strip()
                if len(predecessor) == 40:
                    for row in owned["adapters"]["pi"].values():
                        row["revision"] = predecessor
                    ledger.write_text(json.dumps(owned))
                    before = {str(p): (p.stat().st_ino, p.stat().st_mtime_ns) for package in expected.packages
                              for p in (policy.install_root / package.name).rglob("*") if p.is_file()}
                    child, answer = trace("record-only-refresh", [*base, "--install"], "record-only")
                    after = {str(p): (p.stat().st_ino, p.stat().st_mtime_ns) for package in expected.packages
                             for p in (policy.install_root / package.name).rglob("*") if p.is_file()}
                    if child["exit"] != 0 or answer["state"] != "matches" or before != after:
                        record["audit"]["unknown"].append("record-only no-republish observation unresolved")
            # Small, independently committed topic inputs test the delivered
            # copier's refusal paths without editing the immutable candidate.
            payload_source, payload_agent = fixture / "payload-source", fixture / "payload-agent"
            payload_source.mkdir()
            payload_agent.mkdir()
            topic = payload_source / ".claude/skills/cpp-fixture/SKILL.md"
            topic.parent.mkdir(parents=True)
            valid_topic = ("---\nname: cpp-fixture\ndescription: Synthetic boundary fixture\n---\n"
                           "[guide](../../../docs/skills/guide.md)\n")
            topic.write_text(valid_topic)
            guide = payload_source / "docs/skills/guide.md"
            guide.parent.mkdir(parents=True)
            guide.write_text("Synthetic guide.\n")
            git_env = dict(env, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

            def fixture_git(*words):
                result = run_child(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                                    "-C", str(payload_source), *words], fixture / "work", git_env)
                if result["exit"] != 0 or result["forced_stop"]:
                    raise ValueError("synthetic source Git preparation failed")
                return result["stdout"].strip()

            fixture_git("init", "-q", "-b", "main")
            fixture_git("config", "user.email", "fixture@example.invalid")
            fixture_git("config", "user.name", "fixture")

            def commit_payload():
                fixture_git("add", "--all")
                fixture_git("commit", "-qm", "synthetic fixture input")
                return fixture_git("rev-parse", "HEAD")

            payload_allowance = {
                "source": str(payload_source), "skills": str(payload_agent / "skills"),
                "lock": str(payload_agent / ".cpp-skills.lock"),
                "settings": [str(payload_agent / "settings.json"), str(fixture / "work/.pi/settings.json")],
                "histories": [str(fixture / "history"), str(payload_agent / "sessions")],
                "runtime_reads": [*allowance["runtime_reads"], str(ROOT)],
            }

            def payload_command(revision):
                return [sys.executable, str(ROOT / "scripts/pi-skill-sync.py"), "--root", str(payload_source),
                        "--revision", revision, "--home", str(fixture / "home"),
                        "--agent-dir", str(payload_agent), "--json"]

            for kind in ("auth-helper", "symlink", "manifest", "executable", "traversal"):
                topic.write_text(valid_topic)
                topic.chmod(0o644)
                extra = None
                if kind == "auth-helper":
                    topic.write_text(valid_topic + "[synthetic-auth](auth.json)\n")
                elif kind == "symlink":
                    extra = topic.parent / "references/escape.md"
                    extra.parent.mkdir()
                    extra.symlink_to(protected / "settings.json")
                elif kind == "manifest":
                    extra = topic.parent / "package.json"
                    extra.write_text("{}")
                elif kind == "executable":
                    topic.chmod(0o755)
                else:
                    topic.write_text(valid_topic + "[escape](../../../../protected-agent/settings.json)\n")
                revision = commit_payload()
                child, answer = trace("payload-" + kind, [*payload_command(revision), "--install"], "install",
                                      expected_exit=1, overrides=payload_allowance)
                if child["exit"] != 1 or answer["state"] != "matches":
                    record["audit"]["unknown"].append("payload-" + kind + " zero-probe refusal unresolved")
                if extra:
                    extra.unlink()
                    if kind == "symlink":
                        extra.parent.rmdir()
            topic.write_text(valid_topic)
            topic.chmod(0o644)
            revision = commit_payload()
            foreign = payload_agent / "skills/cpp-fixture/SKILL.md"
            neighbor = payload_agent / "skills/personal/SKILL.md"
            for p in (foreign, neighbor):
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("synthetic foreign sentinel\n")
            child, answer = trace("foreign-collision", [*payload_command(revision), "--install"], "install",
                                  expected_exit=1, overrides=payload_allowance)
            if child["exit"] != 1 or answer["state"] != "matches" or foreign.read_text() != neighbor.read_text():
                record["audit"]["unknown"].append("foreign collision preservation unresolved")
            adoption_argv = [*payload_command(revision), "--install", "--adopt", "cpp-fixture"]
            child, answer = trace("explicit-adoption", adoption_argv, "install", overrides=payload_allowance)
            backup_root = payload_agent / "skills/.cpp-managed/work"
            backups = list(backup_root.glob("transaction-*/backup/cpp-fixture/SKILL.md"))
            if (child["exit"] != 0 or answer["state"] != "matches" or len(backups) != 1
                    or backups[0].read_text() != "synthetic foreign sentinel\n"
                    or neighbor.read_text() != "synthetic foreign sentinel\n"):
                record["audit"]["unknown"].append("explicit adoption backup/preservation unresolved")
            # Other B1-B6 live opposite cases require their own returned traces;
            # a legal installation trace cannot stand in for those observations.
            record["remaining_host_cases"] = ["tool-preservation"]
            for observation in record["observations"]:
                if observation["expected_audit"] == "matches" and observation["audit"]["state"] == "finding":
                    record["audit"]["findings"].extend(observation["audit"]["findings"])
                if (observation["child"]["forced_stop"] or
                        observation["child"]["exit"] != observation["expected_exit"]):
                    record["audit"]["unknown"].append(observation["case"] + " child lifecycle unexpected")
            if record["audit"]["findings"]:
                record["audit"]["state"] = "finding"
            if record["audit"]["unknown"] and record["audit"]["state"] == "matches":
                record["audit"]["state"] = "unknown"
        record["state"] = record["audit"]["state"]
    except (AdapterError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        record["state"] = "unknown"
        record["reason"] = str(error)
    finally:
        try:
            shutil.rmtree(fixture)
            record["cleanup"] = not fixture.exists()
        except OSError as error:
            record["cleanup"] = False
            record["cleanup_error"] = str(error)
            record["state"] = "unknown"
        record["host_acceptance"] = "unknown: per-row execution evidence still required"
    # Preserve a known forbidden operation even if a later fixture operation or
    # cleanup was unexaminable. Deliberate observer-control violations are not
    # product findings and are explicitly labelled in observations.
    product_findings = [o for o in record["observations"]
                        if o["expected_audit"] == "matches" and o["audit"]["state"] == "finding"]
    if product_findings or record.get("audit", {}).get("state") == "finding":
        record["state"] = "finding"
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-rpc", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--revision")
    parser.add_argument("--lane", choices=("rpc", "syscalls"))
    parser.add_argument("--pi-bin", type=Path)
    parser.add_argument("--strace-bin", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        count = 0
        for path in sorted((ROOT / "controls/pi-rpc-observer/cases").glob("*/case.json")):
            seed = json.loads(path.read_text())
            try:
                state = rpc_audit(seed["record"])["state"]
            except (ValueError, KeyError, TypeError):
                state = "unknown"
            if state != {"GOOD": "matches", "BAD": "finding", "UNKNOWN": "unknown"}[seed["expect"]]:
                raise ValueError("self-test failed: " + path.parent.name)
            count += 1
        if count < 9:
            raise ValueError("incomplete self-test population")
        print("PI_RPC_SELFTEST:", count, "committed reader cases; no host execution claim")
        return 0
    if args.read_rpc:
        try:
            result = rpc_audit(json.loads(args.read_rpc.read_text()))
        except (OSError, ValueError, KeyError, TypeError) as error:
            result = {"state": "unknown", "reason": str(error)}
    else:
        if not args.source or not args.revision or not args.lane:
            parser.error("host lane requires --source, --revision and --lane")
        result = host_lane(args)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("PI_RPC:", result["state"], json.dumps(result, sort_keys=True))
    return {"matches": 0, "finding": 1, "unknown": 4}[result["state"]]


if __name__ == "__main__":
    raise SystemExit(main())
