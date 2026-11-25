#!/usr/bin/env python3
"""Scratch-only #1888 live consumer experiment, invoked by the host helper.

Fetch this exact file with git show <frozen-sha>:<path>, then run:
python3 <fetched-file> --checkout <CPP-checkout> --revision <frozen-sha>
No credentials are read, copied or printed. HOME is set only on fresh child
processes. JSON/stdout artifacts remain private for the helper to sanitize.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}, sort_keys=True), flush=True)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def listing(root):
    """Names/metadata only: never open any file in the real config root."""
    if not root.exists():
        return {"status": "absent", "entries": []}
    entries = []
    with os.scandir(root) as rows:
        for row in rows:
            info = row.stat(follow_symlinks=False)
            entries.append([row.name, info.st_mode, info.st_size, info.st_mtime_ns])
    return {"status": "listed", "entries": sorted(entries)}


def files(root):
    return {p.relative_to(root).as_posix(): {"sha256": digest(p.read_bytes()), "mode": p.stat().st_mode & 0o777}
            for p in root.rglob("*") if p.is_file()}


def response_payload(stdout):
    outer = json.loads(stdout)
    response = outer.get("response")
    if isinstance(response, dict):
        return response
    if not isinstance(response, str):
        raise ValueError("native response field unavailable")
    return json.loads(response.strip().removeprefix("```json").removesuffix("```").strip())


def profile_paths_safe(profile, paths):
    """Reject aliases forward, before touching descendants through them."""
    for path in paths:
        current = profile.parent
        for part in path.relative_to(profile.parent).parts:
            current /= part
            if current.is_symlink():
                raise RuntimeError("probe profile alias refused")


def matches_response(label, payload, guide, expected_hash, tail, native_exit):
    if not isinstance(payload, dict) or native_exit != 0:
        return False
    return (payload.get("path") == str(guide) and
            ((label == "positive" and payload.get("status") == "read" and
              payload.get("sha256") == expected_hash and payload.get("tail") == tail)
             or (label == "missing-guide" and payload.get("status") == "missing" and
                 payload.get("sha256") == "" and payload.get("tail") == "" and not guide.exists())))


def checked_help(result):
    if result.returncode:
        raise RuntimeError("AGY help command failed")
    help_text = result.stdout + result.stderr
    for flag in ("--print", "--dangerously-skip-permissions", "--output-format", "--print-timeout"):
        if flag not in help_text:
            raise RuntimeError("AGY help differs from the confirmed contract")
    if "json" not in help_text or not re.search(r"(?m)^\s*-p(?:[,\s]|$)", help_text):
        raise RuntimeError("AGY prompt/print alias or JSON form changed")
    return help_text


def consumer_argv(agy, prompt):
    # AGY 1.5.17 help (pinned in the argv test): booleans take no value,
    # output-format enum is text/json/stream-json, and -p aliases --print.
    # Native parsing rejected integer '180'; Go duration '180s' is required.
    # Keep the prompt one final argv element; never join/shell-evaluate it.
    return [str(agy), "--dangerously-skip-permissions", "--output-format", "json",
            "--print-timeout", "180s", "-p", prompt]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        parser.error("full frozen revision required")
    real_home = Path.home()
    profile = real_home / ".agy-probe-home"
    work = profile / "work"
    config = profile / ".gemini/config"
    real_config = real_home / ".gemini/config"
    agy = real_home / ".local/bin/agy"
    token = uuid.uuid4().hex
    scratch = work / f"cpp1888-{token}"
    marker = config / f"cpp1888-marker-{token}.txt"
    absent = f"cpp1888-never-created-{token}.txt"
    installed = config / "skills/python-packaging"
    # Log undo BEFORE any mutation; never remove a pre-existing package.
    emit("undo-first", owned_new_paths=[str(installed), str(marker)],
         empty_parent_undo="remove probe skills directory only if this run created it and it is empty",
         scratch=str(scratch), artifact_retention="retain scratch until helper archives evidence, then remove scratch")
    profile_paths_safe(profile, (profile, work, config, config / "skills", installed,
                                 profile / ".config", profile / ".local/share", profile / ".local/state"))
    if not work.is_dir() or not config.is_dir() or not agy.is_file():
        raise RuntimeError("pre-existing agy-probe profile/binary unavailable")
    if installed.exists() or marker.exists() or scratch.exists():
        raise RuntimeError("scratch/package collision; no adoption authorized")
    before = listing(real_config)
    emit("boundary-before", probe=listing(config), real=before)
    scratch.mkdir(mode=0o700)
    runtime = scratch / "runtime"
    runtime.mkdir(mode=0o700)
    env = dict(os.environ)
    env.update({"HOME": str(profile), "DBUS_SESSION_BUS_ADDRESS": "", "XDG_RUNTIME_DIR": str(runtime),
                "XDG_CONFIG_HOME": str(profile / ".config"), "XDG_DATA_HOME": str(profile / ".local/share"),
                "XDG_STATE_HOME": str(profile / ".local/state"), "XDG_CACHE_HOME": str(scratch / "cache"),
                "UV_CACHE_DIR": str(scratch / "uv-cache")})
    for key in tuple(env):
        if key.startswith("GIT_"):
            del env[key]
    emit("isolation-env", values={key: env[key] for key in (
        "HOME", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
        "XDG_STATE_HOME", "XDG_CACHE_HOME", "UV_CACHE_DIR")},
        auto_update="no documented disable variable; version checked before each fresh invocation")
    copied = False
    created_skills_parent = False

    def command(argv, *, cwd=scratch, label, timeout=240):
        emit("argv", label=label, argv=list(map(str, argv)), cwd=str(cwd))
        result = subprocess.run(list(map(str, argv)), cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=timeout)
        (scratch / f"{label}.stdout").write_text(result.stdout)
        (scratch / f"{label}.stderr").write_text(result.stderr)
        emit("command-result", label=label, exit=result.returncode,
             stdout_sha256=digest(result.stdout.encode()), stderr_sha256=digest(result.stderr.encode()))
        return result

    def require(result):
        if result.returncode:
            raise RuntimeError("command failed; private stdout/stderr retained in scratch")
        return result.stdout

    try:
        marker.write_text("CPP1888_ISOLATED_PROFILE\n")
        positive = marker.exists() and not (real_config / marker.name).exists()
        negative = not (config / absent).exists() and not (real_config / absent).exists()
        emit("boundary-control", positive=positive, absent_marker_negative=negative)
        if not positive or not negative:
            raise RuntimeError("isolation boundary control failed")
        version = require(command([agy, "--version"], label="version")).strip()
        emit("version", observed=version, expected="1.5.17")
        if version != "1.5.17":
            raise RuntimeError("AGY version changed; re-confirm invocation contract")
        help_text = checked_help(command([agy, "--help"], label="help"))
        # All option/value pairs precede -p; the prompt is its final argument.
        emit("argv-order", form=" ".join(consumer_argv("agy", "PROMPT")),
             help_sha256=digest(help_text.encode()), reconstruction="validated against this run's version/help")
        source = scratch / "cpp-source"
        output = scratch / "built-skills"
        require(command(["git", "clone", "--quiet", "--no-hardlinks", args.checkout.absolute(), source],
                        label="source-clone"))
        require(command(["git", "-C", source, "checkout", "--quiet", "--detach", args.revision],
                        label="source-pin"))
        report = json.loads(require(command([
            "uv", "run", "--project", source, "python", source / "scripts/antigravity-skill-sync.py",
            "--write", "--source-root", source, "--revision", args.revision, "--output-root", output, "--json"],
            label="actual-topic-build", timeout=300)))
        if report["exit_code"] != 0 or report["results"][0]["after"]["expected_packages"] != 18:
            raise RuntimeError("complete real topic build not established")
        expected = files(output / "python-packaging")
        created_skills_parent = not installed.parent.exists()
        installed.parent.mkdir(exist_ok=True)
        shutil.copytree(output / "python-packaging", installed)
        copied = True
        if files(installed) != expected:
            raise RuntimeError("probe copy differs from real generated package")
        guide = installed / "references/docs/skills/python-packaging.md"
        content = guide.read_bytes()
        expected_hash, tail = digest(content), content[-120:].decode()
        emit("published-copy", revision=args.revision, members=expected, guide_sha256=expected_hash)
        repo = scratch / "unrelated-project"
        repo.mkdir()
        require(command(["git", "init", "--quiet", repo], label="unrelated-init"))
        for relative in ("docs/skills/python-packaging.md", "references/docs/skills/python-packaging.md"):
            decoy = repo / relative
            decoy.parent.mkdir(parents=True, exist_ok=True)
            decoy.write_text(f"# PROJECT DECOY\nCPP1888_DECOY_{token}\n")
        shutil.rmtree(source)
        shutil.rmtree(output)
        if source.exists() or output.exists():
            raise RuntimeError("source/build visibility negative precondition failed")
        emit("consumer-preconditions", source_unavailable=True, build_tree_unavailable=True,
             unrelated_cwd=str(repo), project_decoy_sha256=digest(decoy.read_bytes()))
        prompt = (
            "Use the installed python-packaging skill. Read its full package-local guide using a file tool, "
            "resolving the guide path from the directory of that skill's SKILL.md, never from this project. "
            "Do not use the network or repair/create files. Do not substitute your own packaging knowledge. "
            "Return ONLY JSON with status ('read' or 'missing'), path (absolute guide path), sha256 "
            "(compute it with a tool after reading), and tail (the exact last 120 characters of the guide). "
            "If the bundled guide is absent, return status 'missing', empty sha256 and empty tail; do not "
            "read a same-named project file or another source."
        )
        observed = []
        for label in ("positive", "missing-guide"):
            if label == "missing-guide":
                guide.unlink()
                if guide.exists():
                    raise RuntimeError("missing-guide negative precondition failed")
            now = require(command([agy, "--version"], label=f"{label}-version")).strip()
            if now != version:
                raise RuntimeError("AGY changed version during experiment")
            result = command(consumer_argv(agy, prompt), cwd=repo, label=label)
            try:
                payload = response_payload(result.stdout)
                matches = matches_response(label, payload, guide, expected_hash, tail, result.returncode)
            except (ValueError, TypeError, KeyError):
                payload, matches = {"status": "unparseable"}, False
            observed.append({"case": label, "matches_expected": matches, "response": payload})
            emit("consumer-observation", **observed[-1])
        (scratch / "observations.json").write_text(json.dumps(observed, indent=2))
        # Keep the oracle out of files accessible to either fresh model turn.
        # Persist it only after both responses are complete.
        (scratch / "expected-guide.json").write_text(json.dumps({"sha256": expected_hash, "tail": tail}))
        emit("acceptance", state="observed" if all(row["matches_expected"] for row in observed) else "unknown",
             note="helper must inspect retained tool/output evidence before publishing any acceptance claim")
        return 0 if all(row["matches_expected"] for row in observed) else 4
    finally:
        if copied:
            shutil.rmtree(installed)
        if created_skills_parent:
            try:
                installed.parent.rmdir()
            except OSError:
                pass  # foreign profile output is retained
        marker.unlink(missing_ok=True)
        after = listing(real_config)
        emit("undo-complete", package_removed=not installed.exists(), marker_removed=not marker.exists(),
             real_listing_unchanged=after == before, private_artifacts=str(scratch))
        if after != before:
            raise RuntimeError("real config listing changed; acceptance not established")


if __name__ == "__main__":
    raise SystemExit(main())
