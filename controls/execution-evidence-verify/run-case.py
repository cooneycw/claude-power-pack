#!/usr/bin/env python3
"""Case runner for controls/execution-evidence-verify (issue #1366).

Each case is a `case.json`: a record TEMPLATE plus how to lay it out. A record is
only meaningful against a real tree, so this builds one: a scratch git repository
holding `a.txt`, its HEAD and content signature substituted into the template
(`@HEAD@`, `@SIG@`), the record stored under `@INV@.json` (or the case's
`filename`), and then `edit_after` applied - the edit made AFTER the run that a
stale record must not survive. The gate is then asked about that record.

The FINDING is the gate's own `EXECUTION_EVIDENCE: not-supported` line; this
script adds no verdict. Nothing runs but git and the gate - no network, no model,
nothing uid-dependent (CI runs as root).

Markers:
  unavailable - git is not installed     the case needs a real repository
  cannot-run - ...                       anything else; matches no declared signal
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CPP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CPP_ROOT))

INVOCATION = "1366c0ffee1366c0ffee1366c0ffee13"


def main(case_dir: str, gate: str) -> int:
    if shutil.which("git") is None:
        print("EXECUTION_EVIDENCE_CONTROL: unavailable - git is not installed")
        return 3
    try:
        spec = json.loads((Path(case_dir) / "case.json").read_text())
    except (OSError, ValueError) as exc:
        print(f"EXECUTION_EVIDENCE_CONTROL: cannot-run - case.json unreadable: {exc}")
        return 3
    from lib.cicd.state import compute_tree_signature

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        env_git = ["git", "-c", "user.email=c@c", "-c", "user.name=c", "-c", "commit.gpgsign=false"]
        try:
            subprocess.run(env_git + ["init", "-q"], cwd=repo, check=True, capture_output=True)
            (repo / "a.txt").write_text("one\n")
            subprocess.run(env_git + ["add", "a.txt"], cwd=repo, check=True, capture_output=True)
            subprocess.run(env_git + ["commit", "-q", "-m", "c"], cwd=repo, check=True, capture_output=True)
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"EXECUTION_EVIDENCE_CONTROL: cannot-run - scratch repository failed: {exc}")
            return 3
        sig = compute_tree_signature(repo)
        if sig is None:
            print("EXECUTION_EVIDENCE_CONTROL: cannot-run - no tree signature for the scratch repository")
            return 3
        text = json.dumps(spec["record"])
        text = text.replace("@HEAD@", head).replace("@SIG@", sig).replace("@INV@", INVOCATION)
        text = text.replace("@WORKTREE@", str(repo))
        store = Path(tmp) / "store"
        store.mkdir()
        record = store / spec.get("filename", f"{INVOCATION}.json")
        record.write_text(text)
        for rel, content in spec.get("edit_after", {}).items():
            (repo / rel).write_text(content)
        proc = subprocess.run(
            [sys.executable, gate, str(record), "--path", str(repo)],
            capture_output=True,
            text=True,
            check=False,
        )
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return proc.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
