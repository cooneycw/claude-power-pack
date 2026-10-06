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

**The profile DIRECTORY under skillc's `evals/subjects/` is also an
explicit, required input (`--profile-dir`), never a fixed path** (#1370
refresh). skillc re-declares a profile as a NEW directory when it needs a
new pin - `evals/subjects/cpp-codex-flow-check/` (85e9b03) stayed untouched
when `evals/subjects/cpp-codex-flow-check-ea6dbfa/` was declared for the
later one - so a hardcoded directory name would silently keep reading the
OLD profile forever after a re-declaration. No default: the whole point is
that the operator must say which profile they mean, every time.

What it writes to docs/measurements/skill-coverage/<skill>.json:
  - `reference`: the evaluation-bound description_digest/body_digest,
    copied from skillc's own committed `evals/subjects/<profile-dir>/
    evidence/inventory.json` (Q1: neither #1369 nor skillc #272 expose a
    newer reference derived any other way; see check-skill-coverage-map.py's
    module docstring for the full answer).
  - `diagnose`: the skillc commit that produced this snapshot, the PROFILE
    DIRECTORY NAME used (so a reader never has to guess which profile a
    snapshot was taken against), the CPP revision it was run against, the
    exact command, `skillc profile diagnose`'s raw result for the skill,
    and a digest of every file in the skill's `codex/skills/<skill>/`
    closure AT THIS REVISION - the staleness check's own input.
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


def _refuse_escaping_profile_dir(skillc: Path, profile_dir: str) -> None:
    """`--profile-dir` must name a DIRECTORY, never a path (counter-model
    review, 2026-10-06). Unvalidated, an absolute path discards the
    `evals/subjects/` prefix and a `../` component escapes it - either lets
    `--profile-dir` point at content OUTSIDE the skillc checkout whose
    cleanliness `_refuse_dirty` just verified, so the snapshot's provenance
    (`skillc_commit`) would name a clean commit that cannot reproduce data
    that never came from it. Checked by STRING first (no separator, not `.`
    or `..`) and then by RESOLVED PATH containment, because the string check
    alone would not catch a symlink named as a plain component that itself
    points outside `evals/subjects/`.
    """
    if not profile_dir or "/" in profile_dir or "\\" in profile_dir or profile_dir in (".", ".."):
        print(
            f"skill-coverage-snapshot: REFUSED - --profile-dir {profile_dir!r} must be a "
            f"single directory name under evals/subjects/, not a path",
            file=sys.stderr,
        )
        raise SystemExit(2)
    subjects_root = (skillc / "evals" / "subjects").resolve()
    candidate = (subjects_root / profile_dir).resolve()
    try:
        candidate.relative_to(subjects_root)
    except ValueError:
        print(
            f"skill-coverage-snapshot: REFUSED - --profile-dir {profile_dir!r} resolves to "
            f"{candidate}, outside {subjects_root} (symlink escape?)",
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


def _reference_files(entry: dict[str, object], skill: str, inventory_path: Path) -> dict[str, str]:
    """Per-file evaluation-bound digests for `skill`, keyed EXACTLY as
    `digest_tree()` keys the current tree (#1390): relative-posix-path
    under `codex/skills/<skill>/`.

    The inventory's `files[].source` is relative to the CPP repo root at
    the pin (e.g. `codex/skills/flow-check/reference.md`) - a DIFFERENT
    base than `digest_tree()`'s keys (relative to the skill's own closure
    root). A silent mismatch here would either mark every file changed (a
    loud false-stale, if the prefix were simply left on) or compare nothing
    at all (a silent false-current, if the two key sets never intersected) -
    so the prefix is stripped explicitly and any entry that does not carry
    it is a REFUSAL, never a skipped row.
    """
    prefix = f"codex/skills/{skill}/"
    files: dict[str, str] = {}
    for file_entry in entry.get("files", []):  # type: ignore[union-attr]
        source = file_entry.get("source", "")
        if not source.startswith(prefix):
            raise SystemExit(
                f"skill-coverage-snapshot: {inventory_path} skill {skill!r} file entry "
                f"{source!r} does not start with {prefix!r} - cannot key it to match "
                f"digest_tree()'s relative paths"
            )
        files[source[len(prefix):]] = file_entry["digest"]
    return files


def _reference_digests(skillc: Path, skill: str, profile_dir: str) -> dict[str, object]:
    """Read the evaluation-bound description_digest/body_digest, and every
    shipped file's digest, for `skill` from skillc's own committed
    evidence/inventory.json under the EXPLICIT `profile_dir` (Q1's answer:
    this is the only reference point that exists until a newer one lands -
    and #1370's refresh is "a newer one landed", as a new directory, not an
    edit to this one). `files` covers EVERY file under
    codex/skills/<skill>/ the generator ships - not only SKILL.md (#1390) -
    so a change to reference.md or a bundled helper is caught too."""
    inventory_path = skillc / "evals" / "subjects" / profile_dir / "evidence" / "inventory.json"
    data = json.loads(inventory_path.read_text(encoding="utf-8"))
    for entry in data.get("skills", []):
        if entry.get("name") == skill:
            return {
                "description_digest": entry["description_digest"],
                "body_digest": entry["body_digest"],
                "files": _reference_files(entry, skill, inventory_path),
                "source": f"skillc evals/subjects/{profile_dir}/evidence/inventory.json "
                          f"(profile pinned at {data['subject']['revision']}; see "
                          f"check-skill-coverage-map.py's module docstring)",
            }
    raise SystemExit(f"skill-coverage-snapshot: {skill!r} not found in {inventory_path}")


def _mint_subject(skillc: Path, profile_dir: str, cpp_revision: str, out_path: Path) -> None:
    """Base the minted subject on the PROFILE'S OWN subject.json, never a
    fixed `cpp-codex/subject.json` (#1370 refresh). Each re-declared profile
    directory ships its own subject.json pinned at the revision it was
    declared for (skillc's own stated rule: "Own subject.json (never
    evals/subjects/cpp-codex/subject.json...)") - reading a fixed path would
    keep minting against whichever profile happened to be current when this
    script was first written, silently ignoring every later re-declaration.
    The revision is still bumped to the CURRENT cpp_revision being
    snapshotted, so a later regeneration against a newer CPP commit does not
    need yet another skillc-side re-declaration just to move the pin."""
    base = json.loads((skillc / "evals" / "subjects" / profile_dir / "subject.json").read_text(encoding="utf-8"))
    base["revision"] = cpp_revision
    out_path.write_text(json.dumps(base, indent=2), encoding="utf-8")


def _mint_profile(skillc: Path, profile_dir: str, subject_path: Path, out_path: Path) -> None:
    base = json.loads(
        (skillc / "evals" / "subjects" / profile_dir / "profile.json").read_text(encoding="utf-8")
    )
    base["subject"] = str(subject_path)
    out_path.write_text(json.dumps(base, indent=2), encoding="utf-8")


def run_diagnose(skillc: Path, cpp: Path, skill: str, profile_dir: str, cpp_revision: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="skill-coverage-snapshot-") as tmp:
        tmp_path = Path(tmp)
        subject_path = tmp_path / "subject.json"
        profile_path = tmp_path / "profile.json"
        _mint_subject(skillc, profile_dir, cpp_revision, subject_path)
        _mint_profile(skillc, profile_dir, subject_path, profile_path)
        command = ["uv", "run", "--no-sync", "skillc", "profile", "diagnose",
                   str(profile_path), "--repo", str(cpp)]
        proc = subprocess.run(command, cwd=skillc, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise SystemExit(
                f"skill-coverage-snapshot: 'skillc profile diagnose' exited "
                f"{proc.returncode}: {proc.stderr.strip()}"
            )
        return {"command": " ".join(command), "result": json.loads(proc.stdout)}


def write_snapshot(skill: str, cpp: Path, skillc: Path, profile_dir: str, out_dir: Path) -> Path:
    cpp_revision = _repo_head(cpp)
    skillc_commit = _skillc_commit(skillc)
    reference = _reference_digests(skillc, skill, profile_dir)
    diagnose = run_diagnose(skillc, cpp, skill, profile_dir, cpp_revision)
    closure_root = cpp / "codex" / "skills" / skill
    closure_digests = digest_tree(closure_root)
    snapshot = {
        "skill": skill,
        "reference": reference,
        "diagnose": {
            "skillc_commit": skillc_commit,
            "profile_dir": profile_dir,
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
    parser.add_argument("--profile-dir", required=True,
                         help="directory name under <skillc>/evals/subjects/ for this profile "
                              "(e.g. cpp-codex-flow-check-ea6dbfa) - no default, so a re-declared "
                              "profile can never be read by stale habit")
    parser.add_argument("--out-dir", default=Path("docs/measurements/skill-coverage"), type=Path)
    parser.add_argument("--force-ci", action="store_true",
                         help="bypass the CI refusal (tests only - never use this for a real snapshot)")
    args = parser.parse_args(argv)
    if not args.force_ci:
        _refuse_ci()
    # RESOLVED BEFORE ANYTHING ELSE (counter-model review, 2026-10-06):
    # `run_diagnose` below shells out with `cwd=skillc`, so a RELATIVE `--cpp`
    # (e.g. `--cpp .` from the CPP checkout) would resolve against the WRONG
    # directory in that one call while every other call here (`git -C`,
    # `_repo_head`) resolves it against the caller's cwd as intended -
    # diagnosing a repository that is not the one just checked clean.
    cpp = args.cpp.resolve()
    skillc = args.skillc.resolve()
    _refuse_dirty(cpp)
    # SKILLC MUST BE CLEAN TOO. `run_diagnose`/`_mint_subject`/`_mint_profile`/
    # `_reference_digests` all read skillc's WORKING TREE (profile.json,
    # subject.json, evidence/inventory.json, the skillc module itself) while
    # the snapshot records only `skillc_commit` (its HEAD) as provenance. An
    # uncommitted edit to any of those would run silently and be attributed to
    # a commit that cannot reproduce it - the same hazard `_refuse_dirty`
    # exists to close for `cpp`, just on the other checkout.
    _refuse_dirty(skillc)
    _refuse_escaping_profile_dir(skillc, args.profile_dir)
    out_path = write_snapshot(args.skill, cpp, skillc, args.profile_dir, args.out_dir)
    print(f"skill-coverage-snapshot: wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
