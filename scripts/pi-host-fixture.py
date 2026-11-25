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
import stat
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.host_update.models import AdapterError  # noqa: E402
from lib.host_update.pi_adapter import PiAdapter, make_request  # noqa: E402
from lib.pi_skills import nofollow  # noqa: E402


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
            "examined": len(rows), "findings": findings, "unknown": unknown, "scope": "supplied-RPC-pair",
            "diagnostics_scope": "runtime/extension/provider/flag stderr; skill-loader diagnostics unobserved"}


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


def fixture_environment(fixture):
    git = shutil.which("git")
    if not git:
        raise ValueError("Git executable unavailable")
    # Do not carry real-HOME PATH entries into either lane. Executable choices
    # are recorded; Git inside the copier resolves through this same PATH.
    directories = [str(Path(git).parent), str(Path(sys.executable).parent), "/usr/bin", "/bin"]
    env = {"PATH": os.pathsep.join(dict.fromkeys(directories)), "LANG": "C.UTF-8",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
           "HOME": str(fixture / "home"), "PI_CODING_AGENT_DIR": str(fixture / "agent"),
           "PI_CODING_AGENT_SESSION_DIR": str(fixture / "history"), "PI_OFFLINE": "1",
           **{"XDG_" + k.upper() + "_HOME": str(fixture / k) for k in ("config", "data", "cache")}}
    return env, git


def source_git_directories(source, env, git, cwd):
    isolated = {k: v for k, v in env.items() if not k.startswith("GIT_")}
    isolated.update(GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                    GIT_NO_REPLACE_OBJECTS="1")
    answer = run_child([git, "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
                        "-C", str(source), "rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir"],
                       cwd, isolated)
    if answer["exit"] or answer["forced_stop"]:
        raise ValueError("source Git storage unavailable")
    paths = answer["stdout"].splitlines()
    if len(paths) != 2:
        raise ValueError("ambiguous Git storage population")
    result = []
    for value in paths:
        path = Path(value)
        if not path.is_absolute() or path == Path("/"):
            raise ValueError("unbounded Git storage root")
        nofollow(path)
        result.append(str(path))
    return {"git_dir": result[0], "git_common_dir": result[1], "command": answer}


def localtime_target(path=Path("/etc/localtime"), zoneinfo=Path("/usr/share/zoneinfo")):
    """Bind one system clock file without authorizing a zoneinfo tree/escape."""
    nofollow(path.parent)
    mode = path.lstat().st_mode
    if stat.S_ISREG(mode):
        return {"path": str(path), "target": str(path)}
    if not stat.S_ISLNK(mode):
        raise ValueError("localtime is not a regular file or bounded symlink")
    target = Path(os.path.abspath(path.parent / os.readlink(path)))
    nofollow(zoneinfo)
    seen = set()
    for _ in range(32):
        if not target.is_relative_to(zoneinfo) or target in seen:
            raise ValueError("localtime target escapes or cycles within system zoneinfo root")
        seen.add(target)
        current = zoneinfo
        parts = target.relative_to(zoneinfo).parts
        for index, part in enumerate(parts):
            current /= part
            try:
                mode = current.lstat().st_mode
            except FileNotFoundError as error:
                raise ValueError("localtime target missing") from error
            if stat.S_ISLNK(mode):
                target = Path(os.path.abspath(current.parent / os.readlink(current) / Path(*parts[index + 1:])))
                break
        else:
            if not parts or not stat.S_ISREG(mode):
                raise ValueError("localtime target is not a regular file")
            return {"path": str(path), "target": str(target)}
    raise ValueError("localtime target symlink depth exceeded")


def runtime_allowance(env, cwd, git):
    # Derive interpreter paths under the fixture environment, with cwd and user
    # site excluded. Never borrow the parent helper's real-HOME sys.path.
    code = ("import json,sys,sysconfig; print(json.dumps({'paths':sys.path,"
            "'multiarch':sysconfig.get_config_var('MULTIARCH'),'version':list(sys.version_info[:2])}))")
    result = run_child([sys.executable, "-I", "-c", code], cwd, env)
    if result["exit"] or result["forced_stop"]:
        raise ValueError("interpreter runtime paths unavailable")
    runtime = json.loads(result["stdout"])
    roots, files = [], []
    for value in runtime["paths"]:
        if not value or not Path(value).is_absolute() or value == "/":
            raise ValueError("unbounded interpreter path")
        (files if value.endswith(".zip") else roots).append(value)
    files += [sys.executable, str(Path(sys.executable).resolve()), git, str(Path(git).resolve()),
              "/etc/locale.alias", "/etc/ssl/openssl.cnf", "/proc/sys/crypto/fips_enabled",
              "/sys/devices/system/cpu/online", "/etc/gitattributes", "/dev/null", "/etc/ld.so.cache",
              "/etc/ld.so.preload", "/etc/localtime", "/proc/self/exe",
              str(Path(env["XDG_CONFIG_HOME"]) / "git/attributes"),
              str(Path(env["XDG_CONFIG_HOME"]) / "git/ignore"), "/usr/lib/locale/locale-archive"]
    major, minor = runtime["version"]
    metadata = []
    for executable in {Path(sys.executable), Path(sys.executable).resolve()}:
        binary = executable.parent
        files += [str(binary / "pyvenv.cfg"), str(binary.parent / "pyvenv.cfg"),
                  str(binary / "pybuilddir.txt"), str(binary / "Modules/Setup.local"),
                  str(binary / f"lib/python{major}{minor}.zip"), str(binary / f"python{major}._pth"),
                  str(binary / f"python{major}.{minor}._pth")]
        metadata += [str(binary / f"lib/python{major}.{minor}" / name)
                     for name in ("os.py", "os.pyc", "lib-dynload")]
    files += ["/usr/lib/ssl/openssl.cnf", "/usr/share/locale/locale.alias",
              "/usr/share/locale/C.UTF-8/LC_MESSAGES/messages.mo",
              "/usr/share/locale-langpack/C.UTF-8/LC_MESSAGES/messages.mo"]
    for language in ("C", "C.utf8", "C.UTF-8"):
        for category in ("CTYPE", "NUMERIC", "TIME", "COLLATE", "MONETARY", "MESSAGES", "PAPER", "NAME",
                         "ADDRESS", "TELEPHONE", "MEASUREMENT", "IDENTIFICATION"):
            files.append(f"/usr/lib/locale/{language}/LC_{category}")
        files += [f"/usr/lib/locale/{language}/LC_MESSAGES/SYS_LC_MESSAGES",
                  f"/usr/share/locale/{language}/LC_MESSAGES/git.mo"]
    arch = runtime["multiarch"]
    if not isinstance(arch, str) or not arch or not all(c.isalnum() or c in "_-" for c in arch):
        raise ValueError("native library architecture unavailable")
    localtime = localtime_target()
    files.append(localtime["target"])
    return {"runtime_reads": sorted(set(roots)), "runtime_files": sorted(set(files)),
            "runtime_metadata": sorted(set(metadata)), "localtime": localtime,
            "native_library_dirs": [f"/usr/lib/{arch}", f"/lib/{arch}", "/usr/lib64", "/lib64"],
            "probe": result}


def audit_blockers(answer, expected):
    """Expose exact per-row causes of unresolved checks without changing verdicts."""
    if answer["state"] == expected:
        return {}
    return {"expected": expected, "observed": answer["state"],
            "findings": dict(Counter(answer["findings"])), "unknown": dict(Counter(answer["unknown"]))}


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
        env, git = fixture_environment(fixture)
        record["environment_names"] = sorted(env)
        record["selected_git"] = git
        record["fixture_path"] = env["PATH"]
        record["python_isolated"] = True
        adapter = PiAdapter(cwd=fixture / "work", home=fixture / "home", agent=fixture / "agent", environ=env)
        request = make_request(adapter, args.source, revision=args.revision)
        # Force both binding and actual expected build before reporting any lane.
        policy = adapter.preflight(request)
        expected = adapter.build(request.revision, policy)
        base = [sys.executable, "-I", str(ROOT / "scripts/pi-skill-sync.py"), "--root", str(args.source),
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
            record["management_layout_observation"] = {
                "scope": "actual installed hidden .cpp-managed directory",
                "ledger_present": policy.ledger_path.is_file(),
                "work_root_present": policy.work_root.is_dir(),
                "management_skill_absent": not (policy.ledger_path.parent / "SKILL.md").exists(),
                "diagnostics_equal": observed["stderr"] == baseline["stderr"],
                "no_added_non_topic_commands": "unexpected non-topic command population changed"
                not in record["audit"]["findings"],
                "diagnostics_scope": "runtime/extension/provider/flag stderr only",
                "skill_warning_observation": "unknown: pi 1.6.0 RPC does not expose skill-loader diagnostics",
            }
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
                                                       "detected": bad["stderr"] != observed["stderr"],
                                                       "scope": "skill-loader diagnostics unavailable in RPC stderr"}
            # Even an unrelated stderr difference cannot establish observation
            # of the skill-loader warning array omitted by this RPC channel.
            record["audit"]["unknown"].append("skill-loader warnings unobserved: RPC stderr omits that channel")
            if record["audit"]["state"] == "matches":
                record["audit"]["state"] = "unknown"
        else:
            if not args.strace_bin or not args.strace_bin.is_absolute():
                raise ValueError("explicit absolute strace executable required")
            record["version"] = run_child([str(args.strace_bin), "--version"], fixture / "work", env)
            storage = source_git_directories(args.source, env, git, fixture / "work")
            runtime = runtime_allowance(env, fixture / "work", git)
            record["source_git_storage"] = storage
            record["runtime_allowance"] = runtime
            allowance = {"skills": str(policy.install_root), "lock": str(policy.lock_path), "source": str(args.source),
                         "histories": [str(fixture / "history"), str(fixture / "agent/sessions")],
                         "settings": [str(fixture / "agent/settings.json"), str(fixture / "work/.pi/settings.json")],
                         "cwd": str(fixture / "work"), "metadata": [str(fixture / "work"), str(fixture / "home")],
                         "mode": "install", "runtime_reads": runtime["runtime_reads"],
                         "runtime_files": runtime["runtime_files"],
                         "runtime_metadata": runtime["runtime_metadata"],
                         "native_library_dirs": runtime["native_library_dirs"],
                         "git_metadata_roots": list(dict.fromkeys([storage["git_dir"], storage["git_common_dir"]]))}

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
                                                "audit_blockers": audit_blockers(answer, expected_audit),
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
                "seeded-auth-stat": [sys.executable, "-I", "-c", "import os,sys; os.stat(sys.argv[1])", str(auth)],
                "transient-trusted-write": [sys.executable, "-I", "-c",
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
            payload_storage = source_git_directories(payload_source, env, git, fixture / "work")
            payload_allowance["git_metadata_roots"] = list(dict.fromkeys(
                [payload_storage["git_dir"], payload_storage["git_common_dir"]]))
            record["payload_git_storage"] = payload_storage

            def payload_command(revision):
                return [sys.executable, "-I", str(ROOT / "scripts/pi-skill-sync.py"), "--root", str(payload_source),
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
