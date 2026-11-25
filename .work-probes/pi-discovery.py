#!/usr/bin/env python3
"""Disposable host probe; never merge. Run only after pi 1.6.0 help review.

No model turn is sent. Results concern discovery, not provider or auth isolation.
Fetch this exact file by commit; launch with env -i PATH="$PATH" python3 FILE.
The fixture and all installs are removed in finally, after child cleanup.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def commands(output):
    responses = []
    for line in output.splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("id") == "cpp-probe":
            responses.append(item)
    if len(responses) != 1 or responses[0].get("success") is not True:
        raise ValueError("no unique successful fixture RPC response")
    rows = responses[0].get("data", {}).get("commands")
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ValueError("unknown command population shape")
    return rows


def require_names(rows, expected):
    names = [r.get("name") for r in rows]
    for name in expected:
        if names.count(name) != 1:
            raise ValueError(f"expected exactly one {name}, observed {names.count(name)}")


def self_test():
    # Committed opposite inputs for the result reader, not simulated pi evidence.
    good = '{"id":"cpp-probe","success":true,"data":{"commands":[{"name":"skill:fixture"}]}}'
    empty = '{"id":"cpp-probe","success":true,"data":{"commands":[]}}'
    require_names(commands(good), ["skill:fixture"])
    for label, value in [("empty-success", empty), ("missing-response", "{}")]:
        try:
            require_names(commands(value), ["skill:fixture"])
        except ValueError:
            print("CONTROL REFUSED", label)
        else:
            raise AssertionError("blind reader: " + label)
    print("CONTROL ACCEPTED populated-response; fixture controls only")


def skill(root, name, label):
    directory = root / name
    directory.mkdir(parents=True, exist_ok=False)
    file = directory / "SKILL.md"
    file.write_text(f"---\nname: {name}\ndescription: CPP fixture {label}\n---\nFixture only. No commands or provider request.\n")
    file.chmod(0o644)


def run():
    binary = shutil.which("pi")
    if not binary:
        raise ValueError("pi binary unavailable")
    fixture = Path(tempfile.mkdtemp(prefix="cpp-pi-probe.", dir="/tmp"))
    if fixture.parent != Path("/tmp") or fixture.is_symlink():
        raise ValueError("unsafe mktemp root")
    fixture.chmod(0o700)
    print("FIXTURE", fixture, flush=True)
    print("UNDO after children stop: rm -r --", fixture, flush=True)
    try:
        for name in ["home", "agent", "work", "config", "data", "cache", "history"]:
            (fixture / name).mkdir(mode=0o700)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"}
        env.update(HOME=str(fixture / "home"), PI_CODING_AGENT_DIR=str(fixture / "agent"),
                   PI_CODING_AGENT_SESSION_DIR=str(fixture / "history"), PI_OFFLINE="1",
                   XDG_CONFIG_HOME=str(fixture / "config"), XDG_DATA_HOME=str(fixture / "data"),
                   XDG_CACHE_HOME=str(fixture / "cache"))
        version = subprocess.run([binary, "--version"], cwd=fixture / "work", env=env,
                                 capture_output=True, text=True, timeout=15, check=True)
        print("VERSION", version.stdout.strip())
        if "1.6.0" not in version.stdout.split():
            raise ValueError("version not confirmed as 1.6.0; inspect output")
        roots = {"global": fixture / "agent/skills", "project": fixture / "work/.pi/skills",
                 "explicit": fixture / "explicit"}
        for label, root in roots.items():
            skill(root, "cpp-probe-" + label, label)

        def probe(label, extra=()):
            argv = [binary, "--mode", "rpc", "--offline", "--no-session", *extra]
            child = subprocess.Popen(argv, cwd=fixture / "work", env=env, text=True,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            forced = False
            try:
                out, err = child.communicate('{"id":"cpp-probe","type":"get_commands"}\n', timeout=8)
            except subprocess.TimeoutExpired:
                forced = True
                child.terminate()
                try:
                    out, err = child.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    out, err = child.communicate()
            print("CASE", label, "EXIT", child.returncode, "FORCED_STOP", forced, flush=True)
            print("STDOUT", out, "STDERR", err, flush=True)
            rows = commands(out)
            # Process status and lifecycle cleanup are never product success.
            return rows, err

        expected = ["skill:cpp-probe-global", "skill:cpp-probe-project"]
        baseline, baseline_err = probe("metadata-baseline")
        require_names(baseline, expected)
        metadata = roots["global"] / ".cpp-managed"
        metadata.mkdir()
        (metadata / "ownership.json").write_text('{"fixture_only":true,"schema":1}\n')
        hidden, hidden_err = probe("hidden-record-no-skill")
        require_names(hidden, expected)
        if hidden != baseline or hidden_err != baseline_err:
            raise ValueError("management directory changed commands or diagnostics; layout unresolved")
        (metadata / "ownership.json").unlink()
        metadata.rmdir()
        restored, restored_err = probe("metadata-restored")
        if restored != baseline or restored_err != baseline_err:
            raise ValueError("restored baseline differs")
        for label, root in roots.items():
            skill(root, "cpp-probe-priority", label + "-priority")
        # Record collision descriptions/sourceInfo/warnings without inventing precedence.
        probe("global-project-collision")
        plus, _ = probe("automatic-plus-explicit", ["--skill", str(roots["explicit"])])
        require_names(plus, ["skill:cpp-probe-explicit"])
        only, _ = probe("explicit-only", ["--no-skills", "--skill", str(roots["explicit"])])
        require_names(only, ["skill:cpp-probe-explicit"])
        gone = roots["global"] / "cpp-probe-global"
        (gone / "SKILL.md").unlink()
        gone.rmdir()
        removed, _ = probe("removed-global-negative")
        if any(r.get("name") == "skill:cpp-probe-global" for r in removed):
            raise ValueError("removed fixture still discovered")
        print("OBSERVED unique discovery, hidden layout comparison, and removal; inspect collision rows for precedence")
    finally:
        shutil.rmtree(fixture)
        print("UNDO_EXECUTED", fixture, "ABSENT", not fixture.exists())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--help-reviewed", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif not args.help_reviewed:
        parser.error("hold until pi 1.6.0 help confirms all requested flags; then --help-reviewed")
    else:
        run()
