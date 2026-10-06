#!/usr/bin/env python3
"""Regenerate a vendored skill-coverage snapshot for `check-skill-coverage-map.py` (#1370).

THE ONE PLACE skillc RUNTIME IS EVER INVOKED FROM THIS REPOSITORY, and
deliberately not from CI: CPP CI cannot import or run skillc (the same rule
#1369's check-behavioral-eval.py states for itself). This script is the
OPERATOR'S tool - run by hand, locally, whenever a mapped skill's
dependency closure needs re-checking - and it refuses outright under CI
(checked via the WOODPECKER/CI environment variables CPP's own CI sets) and
on a dirty working tree (a snapshot must be reproducible from a named,
committed revision; an uncommitted edit means "current" would mean
something that was never committed).

It takes a path to a LOCAL skillc checkout (`--skillc`) - this repository
has no dependency on skillc and no fixed assumption about where one lives,
so the path is always explicit, never inferred.

What it writes to docs/measurements/skill-coverage/<skill>.json:
  - `reference`: the evaluation-bound description_digest/body_digest,
    copied from skillc's own committed `evals/subjects/cpp-codex-flow-check/
    evidence/inventory.json` at its `85e9b03` pin (Q1: neither #1369 nor
    skillc #272 expose a newer reference; see check-skill-coverage-map.py's
    module docstring for the full answer).
  - `diagnose`: the skillc commit that produced this snapshot, the CPP
    revision it was run against, the exact command, `skillc profile
    diagnose`'s raw result for the skill, and a digest of every file in
    the skill's `codex/skills/<skill>/` closure AT THIS REVISION - the
    staleness check's own input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

USAGE_EXIT = 64
CI_ENV_VARS = ("CI", "WOODPECKER")


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"skill-coverage-snapshot: usage - {message}", file=sys.stderr)
        raise SystemExit(USAGE_EXIT)


def _refuse_ci() -> None:
    present = [v for v in CI_ENV_VARS if os.environ.get(v)]
    if present:
        print(
            f"skill-coverage-snapshot: REFUSED - running under CI ({', '.join(present)} "
            f"set). This script invokes skillc and is an operator tool only; it must "
            f"never run in CI.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _refuse_dirty(repo: Path) -> None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        print(f"skill-coverage-snapshot: REFUSED - 'git status' failed in {repo}: "
              f"{proc.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2)
    if proc.stdout.strip():
        print(
            f"skill-coverage-snapshot: REFUSED - {repo} has uncommitted changes:\n"
            f"{proc.stdout}\nA snapshot must be reproducible from a named, committed "
            f"revision.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def digest_tree(root: Path) -> dict[str, str]:
    """relative posix path -> sha256:<hex> for every FILE under root.

    Deliberately a SEPARATE small copy of check-skill-coverage-map.py's own
    `digest_tree`, not an import: CPP's checker scripts use hyphenated
    filenames (not valid Python module names) and are not meant to be
    imported from each other - ten duplicated lines here is cheaper and more
    robust than an importlib path hack for one function this small.
    """
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _repo_head(repo: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout.strip()


def _skillc_commit(skillc: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(skillc), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout.strip()


def _reference_digests(skillc: Path, skill: str) -> dict[str, str]:
    """Read the evaluation-bound description_digest/body_digest for `skill`
    from skillc's own committed evidence/inventory.json (Q1's answer: this
    is the only reference point that exists until a newer one lands)."""
    inventory_path = skillc / "evals" / "subjects" / "cpp-codex-flow-check" / "evidence" / "inventory.json"
    data = json.loads(inventory_path.read_text(encoding="utf-8"))
    for entry in data.get("skills", []):
        if entry.get("name") == skill:
            return {
                "description_digest": entry["description_digest"],
                "body_digest": entry["body_digest"],
                "source": f"skillc evals/subjects/cpp-codex-flow-check/evidence/inventory.json "
                          f"(profile pinned at {data['subject']['revision']}, pre-#1369; see "
                          f"check-skill-coverage-map.py's module docstring)",
            }
    raise SystemExit(f"skill-coverage-snapshot: {skill!r} not found in {inventory_path}")


def _mint_subject(skillc: Path, cpp_revision: str, out_path: Path) -> None:
    base = json.loads((skillc / "evals" / "subjects" / "cpp-codex" / "subject.json").read_text(encoding="utf-8"))
    base["revision"] = cpp_revision
    out_path.write_text(json.dumps(base, indent=2), encoding="utf-8")


def _mint_profile(skillc: Path, subject_path: Path, out_path: Path) -> None:
    base = json.loads(
        (skillc / "evals" / "subjects" / "cpp-codex-flow-check" / "profile.json").read_text(encoding="utf-8")
    )
    base["subject"] = str(subject_path)
    out_path.write_text(json.dumps(base, indent=2), encoding="utf-8")


def run_diagnose(skillc: Path, cpp: Path, skill: str, cpp_revision: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="skill-coverage-snapshot-") as tmp:
        tmp_path = Path(tmp)
        subject_path = tmp_path / "subject.json"
        profile_path = tmp_path / "profile.json"
        _mint_subject(skillc, cpp_revision, subject_path)
        _mint_profile(skillc, subject_path, profile_path)
        command = ["uv", "run", "--no-sync", "skillc", "profile", "diagnose",
                   str(profile_path), "--repo", str(cpp)]
        proc = subprocess.run(command, cwd=skillc, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise SystemExit(
                f"skill-coverage-snapshot: 'skillc profile diagnose' exited "
                f"{proc.returncode}: {proc.stderr.strip()}"
            )
        return {"command": " ".join(command), "result": json.loads(proc.stdout)}


def write_snapshot(skill: str, cpp: Path, skillc: Path, out_dir: Path) -> Path:
    cpp_revision = _repo_head(cpp)
    skillc_commit = _skillc_commit(skillc)
    reference = _reference_digests(skillc, skill)
    diagnose = run_diagnose(skillc, cpp, skill, cpp_revision)
    closure_root = cpp / "codex" / "skills" / skill
    closure_digests = digest_tree(closure_root)
    snapshot = {
        "skill": skill,
        "reference": reference,
        "diagnose": {
            "skillc_commit": skillc_commit,
            "cpp_revision_snapshot": cpp_revision,
            "command": diagnose["command"],
            "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "result": diagnose["result"],
            "closure_digests": closure_digests,
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{skill}.json"
    out_path.write_text(json.dumps(snapshot, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("skill", help="skill name, e.g. flow-check")
    parser.add_argument("--cpp", required=True, type=Path, help="CPP checkout to snapshot")
    parser.add_argument("--skillc", required=True, type=Path, help="local skillc checkout")
    parser.add_argument("--out-dir", default=Path("docs/measurements/skill-coverage"), type=Path)
    parser.add_argument("--force-ci", action="store_true",
                         help="bypass the CI refusal (tests only - never use this for a real snapshot)")
    args = parser.parse_args(argv)
    if not args.force_ci:
        _refuse_ci()
    _refuse_dirty(args.cpp)
    out_path = write_snapshot(args.skill, args.cpp, args.skillc, args.out_dir)
    print(f"skill-coverage-snapshot: wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
