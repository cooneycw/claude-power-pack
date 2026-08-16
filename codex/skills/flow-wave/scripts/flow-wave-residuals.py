#!/usr/bin/env python3
"""flow-wave-residuals.py - Residual candidate ledger for /flow:wave (issue #719).

Issue #714 established that complete review does not require filing every
observation. This helper makes that distinction executable: worker and reviewer
sessions record residual candidates while a wave is active, and only a closed
wave can receive an explicitly attributed human promotion. It shares the
host-local lifetime and namespace used by the #638 role registry and the #645
verdict ledger:

    $XDG_RUNTIME_DIR/cc-flow-wave/<wave>/residuals.json

The ledger contains canonical candidates plus duplicate-link records. A
duplicate record merges its consequence, evidence, source issues, and source
links into the named canonical candidate instead of creating another canonical
candidate. Every mutation holds an ``fcntl.flock`` lock, writes a temporary
sibling, and atomically replaces the ledger so concurrent wave sessions cannot
drop one another's observations.

Successful commands emit one JSON object on stdout. Diagnostics go to stderr.
This tool never calls GitHub or files an issue; promotion records the gate and
the approving human for a later manual issue-creation step.

Exit codes: 0 success, 1 policy/state refusal, 2 usage/input validation error,
3 lock/ledger I/O error.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

SCHEMA_VERSION = 1
CLASSIFICATION_DISPOSITIONS = {
    "current-issue-failure": "fix-before-close",
    "active-pr-defect": "fix-current-pr",
    "pre-existing-oos": "eligible",
    "emergency": "eligible-emergency",
    "speculative": "ledger-only",
    "duplicate": "duplicate",
}
PROMOTABLE_DISPOSITIONS = {"eligible", "eligible-emergency"}
WAVE_NAME_RE = re.compile(r"^(?!\.)[A-Za-z0-9_.-]+$")
COMMIT_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._/-]*$")
LOCK_TIMEOUT_SECONDS = 10.0

USAGE = """usage: flow-wave-residuals.py <verb> --wave <name> [options]
  record --wave W --root-issue N --source-issue N --classification CLASS
         --consequence TEXT --evidence TEXT [--generation N]
         [--dedupe-of CANDIDATE_ID] [--source-link TEXT ...]
  close --wave W --at-commit SHA
  promote --wave W --candidate-id ID --approved-by IDENTITY
          [--emergency-override --override-reason TEXT]
  metrics --wave W --seed-count N

  stdout: one JSON object for every successful command
  state:  $XDG_RUNTIME_DIR/cc-flow-wave/<wave>/residuals.json
  exit:   0 success, 1 policy refusal, 2 usage/input error, 3 lock/ledger I/O error
"""


class ResidualError(Exception):
    """Base class for expected command failures."""


class PolicyError(ResidualError):
    """The requested state transition is forbidden."""


class ValidationError(ResidualError):
    """The caller supplied invalid input."""


class LedgerIOError(ResidualError):
    """The ledger could not be locked, read, or written safely."""


T = TypeVar("T")


def _timestamp(value: str | None = None) -> str:
    return value or datetime.now(timezone.utc).isoformat()


def _validate_wave(wave: str) -> None:
    if not WAVE_NAME_RE.fullmatch(wave):
        raise ValidationError(
            f"invalid wave name {wave!r} (letters, digits, '_', '.', '-'; no leading dot)"
        )


def ledger_path(wave: str) -> Path:
    """Return the canonical host-local ledger path for ``wave``."""
    _validate_wave(wave)
    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    return runtime_dir / "cc-flow-wave" / wave / "residuals.json"


def _new_ledger(wave: str, now: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "wave": wave,
        "state": "active",
        "created_at": now,
        "updated_at": now,
        "closed_at": None,
        "closed_at_commit": None,
        "close_history": [],
        "candidates": [],
        "duplicate_links": [],
    }


def _validate_ledger(ledger: object, wave: str) -> dict[str, Any]:
    if not isinstance(ledger, dict):
        raise LedgerIOError("residual ledger must be a JSON object")
    if ledger.get("schema_version") != SCHEMA_VERSION:
        raise LedgerIOError(
            f"unsupported residual ledger schema version: {ledger.get('schema_version')!r}"
        )
    if ledger.get("wave") != wave:
        raise LedgerIOError(
            f"residual ledger belongs to wave {ledger.get('wave')!r}, not {wave!r}"
        )
    if ledger.get("state") not in {"active", "closed"}:
        raise LedgerIOError(f"invalid residual ledger state: {ledger.get('state')!r}")
    if not isinstance(ledger.get("candidates"), list) or not isinstance(
        ledger.get("duplicate_links"), list
    ):
        raise LedgerIOError("residual ledger candidates and duplicate_links must be arrays")
    return ledger


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock_file = path.with_name(f"{path.name}.lock").open("a+", encoding="utf-8")
    except OSError as exc:
        raise LedgerIOError(f"cannot prepare ledger directory or lock: {exc}") from exc

    with lock_file:
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise LedgerIOError(f"could not lock {path} within 10 seconds") from exc
                time.sleep(0.05)
            except OSError as exc:
                raise LedgerIOError(f"cannot lock {path}: {exc}") from exc
        try:
            yield
        finally:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


def _read_unlocked(path: Path, wave: str, now: str, *, create: bool) -> dict[str, Any]:
    if not path.exists():
        if create:
            return _new_ledger(wave, now)
        raise LedgerIOError(f"residual ledger does not exist: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LedgerIOError(f"cannot read residual ledger {path}: {exc}") from exc
    return _validate_ledger(raw, wave)


def _atomic_write(path: Path, ledger: dict[str, Any]) -> None:
    temp_path: Path | None = None
    try:
        fd, raw_temp_path = tempfile.mkstemp(prefix=".residuals.", dir=path.parent)
        temp_path = Path(raw_temp_path)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(ledger, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
        temp_path = None
    except OSError as exc:
        raise LedgerIOError(f"cannot atomically write residual ledger {path}: {exc}") from exc
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _mutate(
    path: Path,
    wave: str,
    now: str,
    operation: Callable[[dict[str, Any]], T],
) -> T:
    _validate_wave(wave)
    with _locked(path):
        ledger = _read_unlocked(path, wave, now, create=True)
        result = operation(ledger)
        ledger["updated_at"] = now
        _atomic_write(path, ledger)
        return result


def read_ledger(path: Path, wave: str) -> dict[str, Any]:
    """Read and validate a ledger under the same lock used by writers."""
    _validate_wave(wave)
    with _locked(path):
        return _read_unlocked(path, wave, _timestamp(), create=False)


def _positive_int(value: int | str, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a positive integer, got {value!r}") from exc
    if number < 1:
        raise ValidationError(f"{field} must be a positive integer, got {value!r}")
    return number


def _nonnegative_int(value: int | str, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a nonnegative integer, got {value!r}") from exc
    if number < 0:
        raise ValidationError(f"{field} must be a nonnegative integer, got {value!r}")
    return number


def _merge_unique(existing: list[Any], incoming: list[Any]) -> list[Any]:
    merged = list(existing)
    for value in incoming:
        if value not in merged:
            merged.append(value)
    return merged


def _merge_text(existing: str, incoming: str) -> str:
    if not incoming or incoming == existing or incoming in existing.split("\n\n"):
        return existing
    if not existing:
        return incoming
    return f"{existing}\n\n{incoming}"


def _candidate_by_id(ledger: dict[str, Any], candidate_id: str) -> dict[str, Any] | None:
    return next(
        (candidate for candidate in ledger["candidates"] if candidate["candidate_id"] == candidate_id),
        None,
    )


def _duplicate_by_id(ledger: dict[str, Any], candidate_id: str) -> dict[str, Any] | None:
    return next(
        (link for link in ledger["duplicate_links"] if link["candidate_id"] == candidate_id),
        None,
    )


def record_candidate(
    path: Path,
    *,
    wave: str,
    root_issue: int,
    source_issue: int,
    classification: str,
    consequence: str,
    evidence: str,
    generation: int = 1,
    dedupe_of: str | None = None,
    source_links: list[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Record one canonical candidate or merge one duplicate-link finding."""
    root_issue = _positive_int(root_issue, "root_issue")
    source_issue = _positive_int(source_issue, "source_issue")
    generation = _positive_int(generation, "generation")
    if classification not in CLASSIFICATION_DISPOSITIONS:
        allowed = ", ".join(CLASSIFICATION_DISPOSITIONS)
        raise ValidationError(f"unknown classification {classification!r}; expected one of: {allowed}")
    if classification == "duplicate" and not dedupe_of:
        raise ValidationError("duplicate classification requires --dedupe-of CANDIDATE_ID")
    if classification != "duplicate" and dedupe_of:
        raise ValidationError("--dedupe-of is valid only with classification 'duplicate'")
    links = [str(link) for link in source_links or []]
    timestamp = _timestamp(now)

    def operation(ledger: dict[str, Any]) -> dict[str, Any]:
        if ledger["state"] != "active":
            raise PolicyError("wave is closed; residual recording cannot silently reopen it")

        if classification == "duplicate":
            canonical = _candidate_by_id(ledger, str(dedupe_of))
            if canonical is None:
                raise ValidationError(f"--dedupe-of names no canonical candidate: {dedupe_of}")
            duplicate_id = f"duplicate-{len(ledger['duplicate_links']) + 1:06d}"
            duplicate = {
                "candidate_id": duplicate_id,
                "canonical_candidate_id": canonical["candidate_id"],
                "root_issue": root_issue,
                "source_issue": source_issue,
                "generation": generation,
                "classification": classification,
                "consequence": consequence,
                "evidence": evidence,
                "disposition": "duplicate",
                "dedupe_of": canonical["candidate_id"],
                "source_links": links,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            ledger["duplicate_links"].append(duplicate)
            canonical["source_issues"] = _merge_unique(
                canonical.get("source_issues", [canonical["source_issue"]]), [source_issue]
            )
            canonical["source_links"] = _merge_unique(canonical.get("source_links", []), links)
            canonical["consequence"] = _merge_text(canonical["consequence"], consequence)
            canonical["evidence"] = _merge_text(canonical["evidence"], evidence)
            canonical.setdefault("evidence_entries", []).append(
                {
                    "source_issue": source_issue,
                    "source_links": links,
                    "consequence": consequence,
                    "evidence": evidence,
                    "recorded_at": timestamp,
                    "duplicate_link": duplicate_id,
                }
            )
            canonical["updated_at"] = timestamp
            return duplicate

        candidate_id = f"candidate-{len(ledger['candidates']) + 1:06d}"
        disposition = CLASSIFICATION_DISPOSITIONS[classification]
        candidate = {
            "candidate_id": candidate_id,
            "root_issue": root_issue,
            "source_issue": source_issue,
            "source_issues": [source_issue],
            "generation": generation,
            "classification": classification,
            "consequence": consequence,
            "evidence": evidence,
            "evidence_entries": [
                {
                    "source_issue": source_issue,
                    "source_links": links,
                    "consequence": consequence,
                    "evidence": evidence,
                    "recorded_at": timestamp,
                }
            ],
            "disposition": disposition,
            "disposition_history": [{"disposition": disposition, "at": timestamp}],
            "dedupe_of": None,
            "source_links": links,
            "revalidation": None,
            "promotion": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        ledger["candidates"].append(candidate)
        return candidate

    return _mutate(path, wave, timestamp, operation)


def close_wave(
    path: Path,
    *,
    wave: str,
    at_commit: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Close a wave and revalidate every canonical candidate at the final tree."""
    if not at_commit or not COMMIT_RE.fullmatch(at_commit):
        raise ValidationError(f"at_commit must be a nonempty commit identifier, got {at_commit!r}")
    timestamp = _timestamp(now)

    def operation(ledger: dict[str, Any]) -> dict[str, Any]:
        old_commit = ledger.get("closed_at_commit")
        if ledger["state"] == "closed" and old_commit == at_commit:
            return {
                "wave": wave,
                "state": "closed",
                "closed_at": ledger["closed_at"],
                "at_commit": at_commit,
                "revalidated": len(ledger["candidates"]),
            }

        ledger["state"] = "closed"
        if ledger.get("closed_at") is None:
            ledger["closed_at"] = timestamp
        ledger["closed_at_commit"] = at_commit
        ledger.setdefault("close_history", []).append({"at_commit": at_commit, "closed_at": timestamp})

        for candidate in ledger["candidates"]:
            candidate["revalidation"] = {
                "at_commit": at_commit,
                "revalidated_at": timestamp,
                "consequence_reviewed": bool(candidate.get("consequence", "").strip()),
                "evidence_reviewed": bool(candidate.get("evidence", "").strip()),
                "deduplicated": candidate.get("dedupe_of") is None,
            }
            promotion = candidate.get("promotion")
            if old_commit and old_commit != at_commit and promotion and promotion.get("status") == "promoted":
                promotion["status"] = "stale-final-tree"
                promotion["invalidated_at"] = timestamp
                promotion["invalidated_by_commit"] = at_commit
            candidate["updated_at"] = timestamp

        return {
            "wave": wave,
            "state": "closed",
            "closed_at": ledger["closed_at"],
            "at_commit": at_commit,
            "revalidated": len(ledger["candidates"]),
        }

    return _mutate(path, wave, timestamp, operation)


def promote_candidate(
    path: Path,
    *,
    wave: str,
    candidate_id: str,
    approved_by: str,
    emergency_override: bool = False,
    override_reason: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Persist one human-approved promotion after every policy guard passes."""
    if not candidate_id:
        raise ValidationError("candidate_id must not be empty")
    if not approved_by.strip():
        raise ValidationError("approved_by must identify the approving human")
    if override_reason is not None and not override_reason.strip():
        raise ValidationError("override_reason must not be empty when supplied")
    timestamp = _timestamp(now)

    def operation(ledger: dict[str, Any]) -> dict[str, Any]:
        if ledger["state"] != "closed":
            raise PolicyError("promotion refused while the wave is active; close the final tested tree first")
        duplicate = _duplicate_by_id(ledger, candidate_id)
        if duplicate is not None:
            raise PolicyError(
                f"promotion refused: {candidate_id} is a duplicate of {duplicate['canonical_candidate_id']}"
            )
        candidate = _candidate_by_id(ledger, candidate_id)
        if candidate is None:
            raise ValidationError(f"unknown candidate_id: {candidate_id}")
        if candidate.get("dedupe_of") is not None or candidate["disposition"] == "duplicate":
            raise PolicyError("promotion refused: duplicate candidates link canonical records")
        if candidate["disposition"] not in PROMOTABLE_DISPOSITIONS:
            raise PolicyError(
                f"promotion refused: disposition {candidate['disposition']!r} is never promotable"
            )
        revalidation = candidate.get("revalidation") or {}
        if revalidation.get("at_commit") != ledger.get("closed_at_commit"):
            raise PolicyError("promotion refused: candidate was not revalidated against the final tree")
        if not revalidation.get("consequence_reviewed"):
            raise PolicyError("promotion refused: candidate has no reviewable consequence")
        if not revalidation.get("evidence_reviewed"):
            raise PolicyError("promotion refused: candidate has no reproducible evidence")
        promotion = candidate.get("promotion")
        if promotion and promotion.get("status") == "promoted":
            raise PolicyError(f"promotion refused: {candidate_id} is already promoted")

        generation = int(candidate["generation"])
        emergency = candidate["disposition"] == "eligible-emergency"
        if generation >= 2 and not emergency:
            raise PolicyError(
                "promotion refused: generation-2+ candidates require an emergency classification and explicit override"
            )
        if emergency and (not emergency_override or not override_reason):
            raise PolicyError(
                "promotion refused: emergency candidates require --emergency-override and --override-reason"
            )
        if not emergency and emergency_override:
            raise PolicyError("promotion refused: --emergency-override applies only to emergency candidates")
        if override_reason and not emergency_override:
            raise PolicyError("promotion refused: --override-reason requires --emergency-override")

        candidate["promotion"] = {
            "status": "promoted",
            "approved_by": approved_by,
            "emergency_override": emergency_override,
            "override_reason": override_reason if emergency_override else None,
            "revalidated_at_commit": ledger["closed_at_commit"],
            "promoted_at": timestamp,
        }
        candidate["updated_at"] = timestamp
        return {
            "candidate_id": candidate_id,
            "disposition": candidate["disposition"],
            "promotion": candidate["promotion"],
        }

    return _mutate(path, wave, timestamp, operation)


def metrics(path: Path, *, wave: str, seed_count: int) -> dict[str, int | float | str]:
    """Return issue-economy counts and ratios for one wave."""
    seed_count = _nonnegative_int(seed_count, "seed_count")
    ledger = read_ledger(path, wave)
    candidates = ledger["candidates"]
    duplicate_links = ledger["duplicate_links"]
    promoted = sum(
        1
        for candidate in candidates
        if (candidate.get("promotion") or {}).get("status") == "promoted"
    )
    ever_promotable = sum(
        1
        for candidate in candidates
        if any(
            entry.get("disposition") in PROMOTABLE_DISPOSITIONS
            for entry in candidate.get("disposition_history", [])
        )
    )
    return {
        "seed_count": seed_count,
        "recorded": len(candidates) + len(duplicate_links),
        "duplicates": len(duplicate_links),
        "promoted": promoted,
        "amplification": promoted / seed_count if seed_count else "not-applicable",
        "promotion_rate": promoted / ever_promotable if ever_promotable else "not-applicable",
    }


def _parse_options(args: list[str], *, boolean: set[str], repeatable: set[str]) -> dict[str, Any]:
    options: dict[str, Any] = {name: [] for name in repeatable}
    index = 0
    while index < len(args):
        argument = args[index]
        if argument in {"-h", "--help"}:
            raise ValidationError("help requested")
        if not argument.startswith("--"):
            raise ValidationError(f"unexpected argument: {argument}")
        raw = argument[2:]
        if "=" in raw:
            name, value = raw.split("=", 1)
            if name in boolean:
                raise ValidationError(f"--{name} does not take a value")
            index += 1
        else:
            name = raw
            if name in boolean:
                options[name] = True
                index += 1
                continue
            if index + 1 >= len(args):
                raise ValidationError(f"--{name} requires a value")
            value = args[index + 1]
            index += 2
        if name in options and name not in repeatable:
            raise ValidationError(f"--{name} may be supplied only once")
        if name in repeatable:
            options[name].append(value)
        else:
            options[name] = value
    return options


def _required(options: dict[str, Any], *names: str) -> None:
    missing = [f"--{name}" for name in names if name not in options]
    if missing:
        raise ValidationError(f"missing required option(s): {', '.join(missing)}")


def _reject_unknown(options: dict[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(options) - allowed)
    if unknown:
        raise ValidationError(f"unknown option(s): {', '.join(f'--{name}' for name in unknown)}")


def _emit(payload: object) -> None:
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args or args[0] in {"-h", "--help"}:
        sys.stderr.write(USAGE)
        return 2
    verb = args[0]
    try:
        options = _parse_options(
            args[1:],
            boolean={"emergency-override"},
            repeatable={"source-link"},
        )
        _required(options, "wave")
        wave = str(options["wave"])
        path = ledger_path(wave)

        if verb == "record":
            allowed = {
                "wave",
                "root-issue",
                "source-issue",
                "classification",
                "consequence",
                "evidence",
                "generation",
                "dedupe-of",
                "source-link",
            }
            _reject_unknown(options, allowed)
            _required(
                options,
                "root-issue",
                "source-issue",
                "classification",
                "consequence",
                "evidence",
            )
            result = record_candidate(
                path,
                wave=wave,
                root_issue=options["root-issue"],
                source_issue=options["source-issue"],
                classification=str(options["classification"]),
                consequence=str(options["consequence"]),
                evidence=str(options["evidence"]),
                generation=options.get("generation", 1),
                dedupe_of=options.get("dedupe-of"),
                source_links=options["source-link"],
            )
        elif verb == "close":
            _reject_unknown(options, {"wave", "at-commit", "source-link"})
            if options["source-link"]:
                raise ValidationError("--source-link is valid only with record")
            _required(options, "at-commit")
            result = close_wave(path, wave=wave, at_commit=str(options["at-commit"]))
        elif verb == "promote":
            allowed = {
                "wave",
                "candidate-id",
                "approved-by",
                "emergency-override",
                "override-reason",
                "source-link",
            }
            _reject_unknown(options, allowed)
            if options["source-link"]:
                raise ValidationError("--source-link is valid only with record")
            _required(options, "candidate-id", "approved-by")
            result = promote_candidate(
                path,
                wave=wave,
                candidate_id=str(options["candidate-id"]),
                approved_by=str(options["approved-by"]),
                emergency_override=bool(options.get("emergency-override", False)),
                override_reason=options.get("override-reason"),
            )
        elif verb == "metrics":
            _reject_unknown(options, {"wave", "seed-count", "source-link"})
            if options["source-link"]:
                raise ValidationError("--source-link is valid only with record")
            _required(options, "seed-count")
            result = metrics(path, wave=wave, seed_count=options["seed-count"])
        else:
            raise ValidationError(f"unknown verb: {verb}")
    except PolicyError as exc:
        sys.stderr.write(f"flow-wave-residuals: {exc}\n")
        return 1
    except ValidationError as exc:
        if str(exc) != "help requested":
            sys.stderr.write(f"flow-wave-residuals: {exc}\n")
        sys.stderr.write(USAGE)
        return 2
    except LedgerIOError as exc:
        sys.stderr.write(f"flow-wave-residuals: {exc}\n")
        return 3

    _emit(result)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
