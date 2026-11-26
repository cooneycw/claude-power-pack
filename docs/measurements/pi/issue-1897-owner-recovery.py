#!/usr/bin/env python3
"""Review-only until owner clearance: recover the unsealed #1897 installation.

Requires the adjacent reviewed probe module. Never starts pi. Dry-run seals an
exact removal plan; execute refuses anything differing from that reviewed plan.
"""

import argparse
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
import shlex
import stat
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "pi_owner_probe", Path(__file__).with_name("issue-1897-owner-probe.py"))
assert SPEC is not None and SPEC.loader is not None
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)
require, physical = PROBE.require, PROBE.physical
PREFIX = "claude-power-pack/.claude/skills/"
ORIGINAL_HASHES = {
    "before-and-undo.json": "03a2f8b8a559e6d61294689ab02e389c2388c2d9f2be5bffad232266ea8aef19",
    "command-build.json": "6ee42e25b9b7237e715433a4d91494afd714f84690f2fbae4febbdbbca14776b",
    "command-install.json": "43190154da7d62a4cd5d39e10fb931f85256ee3def1b55bad259d25c94c46577",
    "command-verify.json": "265ef2059d2f933f26bd0bceb279ed600c6d73da8b9a8773d5689d01301d0eeb",
}


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key refused")
        result[key] = value
    return result


def document(path):
    require(stat.S_ISREG(path.lstat().st_mode), "journal record must be a regular file")
    return json.loads(path.read_text(), object_pairs_hook=unique)


@contextmanager
def existing_locks(paths):
    descriptors = []
    try:
        for path in paths:
            descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
            descriptors.append(descriptor)
            info = os.fstat(descriptor)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "invalid existing lock")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            current = path.lstat()
            require((info.st_dev, info.st_ino) == (current.st_dev, current.st_ino), "lock identity changed")
        yield
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def run(args):
    require(args.exclusive_window_confirmed, "exclusive writer window required even for dry-run")
    source, journal, evidence = map(physical, (args.source, args.journal, args.evidence))
    # These are the original unsanitized host bytes, authenticated by master's
    # relay. No CLI override or skip option exists, including during dry-run.
    for name, digest in ORIGINAL_HASHES.items():
        path = physical(journal / name)
        require(stat.S_ISREG(path.lstat().st_mode), "original journal file is not regular")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, "original journal hash differs: " + name)
    record_path = physical(journal / "before-and-undo.json")
    record = document(record_path)
    home, agent = map(physical, (record["home"], record["agent"]))
    require(physical(args.home) == home, "explicit home differs from original record")
    require(source == physical(record["source"]) and record["revision"] == PROBE.REVISION,
            "recovery source binding differs from original record")
    require(record["exclusive_window"] is True and type(record["skills_existed"]) is bool,
            "unsupported original pre-state")
    require(not os.path.lexists(journal / "sealed-post.json"), "this recovery is only for the unsealed stop")
    for left, right in ((source, home), (source, agent), (journal, home), (journal, agent),
                        (journal, source), (evidence, home), (evidence, agent),
                        (evidence, source), (evidence, journal)):
        require(not left.is_relative_to(right) and not right.is_relative_to(left), "recovery roots overlap")
    require(source.is_dir() and home.is_dir() and agent.is_dir(), "existing physical roots required")
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
           "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_REPLACE_OBJECTS": "1"}

    def git(*arguments):
        return subprocess.check_output(["git", "-c", "core.fsmonitor=false", "-C", str(source),
                                        *arguments], env=env, text=True).strip()

    require(git("rev-parse", "HEAD") == PROBE.REVISION and not git("status", "--porcelain"),
            "original source is not clean at the recorded revision")
    # Inventory the approved source, never the owner agent or personal skills.
    slugs = sorted(path.name for path in (source / ".claude/skills").iterdir())
    require(len(slugs) == 18 and set(record["expected"]) == set(slugs), "recorded population incomplete")
    skills = physical(agent / "skills")
    management, primary = physical(skills / ".cpp-managed"), physical(agent / ".cpp-skills.lock")
    targets = [physical(skills / slug) for slug in slugs] + [management, primary]
    require(record["targets"] == [str(path) for path in targets], "recorded target list differs")
    require(record["before"] == {str(path): {} for path in targets}, "original targets were not all absent")
    for name in ("install", "verify"):
        prior = document(physical(journal / f"command-{name}.json"))
        report = json.loads(prior["stdout"], object_pairs_hook=unique)
        require(prior["make_exit"] == report["exit_code"] == 0 and report["after"]["state"] == "current"
                and report["after"]["expected_packages"] == 18
                and report["after"]["expected_members"] == report["after"]["examined_members"] == 36,
                "original install/verify did not finish completely")
    if args.dry_run:
        require(not os.path.lexists(evidence), "dry-run evidence must be a new private path")
        evidence.mkdir(mode=0o700)
        for name in ("home", "history", "config", "data", "cache"):
            (evidence / name).mkdir(mode=0o700)
    else:
        require(evidence.is_dir() and (evidence / "removal-plan.json").is_file(),
                "execute requires the previously reviewed dry-run plan")
    env.update(HOME=str(evidence / "home"), PI_CODING_AGENT_DIR=str(agent),
               PI_CODING_AGENT_SESSION_DIR=str(evidence / "history"),
               XDG_CONFIG_HOME=str(evidence / "config"), XDG_DATA_HOME=str(evidence / "data"),
               XDG_CACHE_HOME=str(evidence / "cache"))

    def verify(label, code):
        arguments = ["--root", str(source), "--revision", PROBE.REVISION, "--home", str(home),
                     "--agent-dir", str(agent), "--session-dir", str(evidence / "history"), "--json"]
        argv = ["make", "--no-print-directory", "-s", "-C", str(source), "pi-skills-verify",
                "PI_SKILL_ARGS=" + shlex.join(arguments)]
        answer = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=120)
        PROBE.save(evidence / (label + ".json"), {"argv": argv, "make_exit": answer.returncode,
                                                 "stdout": answer.stdout, "stderr": answer.stderr})
        report = json.loads(answer.stdout)
        require(report["exit_code"] == code and (answer.returncode == 0) == (code == 0),
                "delivered verifier rejected recovery state")
        require(report["after"]["expected_packages"] == 18 and report["after"]["expected_members"] == 36
                and report["after"]["examined_members"] == (36 if code == 0 else 0),
                "unexpected verifier population")
        require(report["after"]["state"] == ("current" if code == 0 else "absent"),
                "unexpected verifier state")

    verify("dry-run-verify" if args.dry_run else "execute-verify", 0)
    normalized = {slug: PROBE.installer_expected(record["expected"][slug]) for slug in slugs}
    records = {}
    for slug in slugs:
        require(PROBE.projected(PROBE.manifest(skills / slug)) == normalized[slug],
                "recovery refused: topic bytes/modes/membership differ")
        marker = "  source: " + PREFIX + slug
        front = (skills / slug / "SKILL.md").read_text().split("---", 2)
        require(len(front) == 3 and marker in front[1].splitlines(), "topic is not CPP-marked")
        members = {name: {"sha256": row["sha256"], "mode": 0o644}
                   for name, row in normalized[slug].items() if row["kind"] == "file"}
        records[slug] = {"source": PREFIX + slug, "revision": PROBE.REVISION, "members": members}
    ledger = (json.dumps({"schema": 1, "producer": "claude-power-pack", "adapters": {"pi": records}},
                         sort_keys=True, indent=2) + "\n").encode()
    empty_hash = hashlib.sha256(b"").hexdigest()
    lock_row = {"kind": "file", "mode": 0o600, "sha256": empty_hash}
    dir_row = {"kind": "dir", "mode": 0o755}
    expected_management = {".": dir_row, "work": dir_row, ".ownership.json.cpp-lock": lock_row,
                           ".work.cpp-lock": lock_row, "ownership.json": {
                               "kind": "file", "mode": 0o644, "sha256": hashlib.sha256(ledger).hexdigest()}}
    require(PROBE.projected(PROBE.manifest(management)) == expected_management,
            "recovery refused: management is not the exact completed CPP installation")
    require(PROBE.projected(PROBE.manifest(primary)) == {".": lock_row}, "primary lock content/mode differs")
    sealed = PROBE.state(targets)
    operations = []
    for target in targets:
        for relative in sorted(sealed[str(target)], key=lambda key: len(Path(key).parts), reverse=True):
            row = sealed[str(target)][relative]
            operations.append({"operation": "unlink" if row["kind"] == "file" else "rmdir",
                               "path": str(target if relative == "." else target / relative)})
    if record["skills_existed"] is False:
        operations.append({"operation": "rmdir", "path": str(skills), "only_if_empty": True,
                           "recorded_created_root": True})
    root_info = skills.lstat()
    plan = {"revision": PROBE.REVISION, "source": str(source), "journal": str(journal),
            "record_sha256": hashlib.sha256(record_path.read_bytes()).hexdigest(),
            "home": str(home), "agent": str(agent), "targets": record["targets"],
            "sealed": sealed, "operations": operations,
            "skills_root_identity": {"dev": root_info.st_dev, "ino": root_info.st_ino,
                                     "mode": stat.S_IMODE(root_info.st_mode)}}
    locks = [primary, management / ".ownership.json.cpp-lock", management / ".work.cpp-lock"]
    with existing_locks(locks):
        require(PROBE.state(targets) == sealed, "recovery post-state changed before lock acquisition")
        if args.dry_run:
            PROBE.save(evidence / "removal-plan.json", plan)
            print(json.dumps(operations, indent=2))
            print("DRY RUN ONLY: no owner paths removed. Keep the exclusive writer window; review the plan.")
            return
        require(document(evidence / "removal-plan.json") == plan, "reviewed dry-run plan changed; refuse execution")
        PROBE.save(evidence / "execute-plan.json", plan)
        for operation in operations:
            path = Path(operation["path"])
            if operation.get("recorded_created_root"):
                info = path.lstat()
                require(record["skills_existed"] is False and stat.S_ISDIR(info.st_mode),
                        "created skills-root removal refused")
                require((info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode)) ==
                        (root_info.st_dev, root_info.st_ino, stat.S_IMODE(root_info.st_mode)),
                        "created skills-root identity/mode changed")
                try:
                    path.rmdir()  # Atomic empty-directory check; never list then delete.
                except OSError as error:
                    if error.errno == errno.ENOTEMPTY:
                        restored = PROBE.state(targets) == record["before"]
                        print(f"STOP: recorded CPP target restoration completed={restored}; "
                              "skills root retained because it is not empty.", file=sys.stderr)
                        PROBE.save(evidence / "root-retained.json", {"recorded_targets_restored": restored,
                                                                   "skills_root_removed": False,
                                                                   "reason": "not-empty"})
                    raise
            elif operation["operation"] == "unlink":
                path.unlink()
            else:
                path.rmdir()
    if record["skills_existed"] is False:
        require(not os.path.lexists(skills), "new skills root was not restored to absent")
    require(PROBE.state(targets) == record["before"], "recorded target baseline was not restored")
    verify("after-recovery-verify", 1)
    require(PROBE.state(targets) == record["before"], "post-recovery verifier left CPP artifacts")
    PROBE.save(evidence / "recovered.json", {"before": record["before"], "after": PROBE.state(targets),
                                            "skills_existed_before": record["skills_existed"],
                                            "skills_exists_after": skills.exists()})
    print("Recorded CPP targets restored to absent. In the SAME existing pi session, /reload again and "
          "compare the relevant list with baseline. Owner sign-off remains separate.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("source", "journal", "home", "evidence"):
        parser.add_argument("--" + option, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--execute", action="store_true")
    parser.add_argument("--exclusive-window-confirmed", action="store_true")
    try:
        run(parser.parse_args())
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"STOP: {error}. Preserve the journal and state; no automatic cleanup.", file=sys.stderr)
        sys.exit(1)
