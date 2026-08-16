#!/usr/bin/env python3
"""Verify completed-spec knowledge mapping and record its lifecycle decision.

The checker is offline. The caller supplies the reviewed tracker or PR URL; the
script validates the local spec, tasks, explicit mapping, and durable artifacts,
then atomically updates ``.specify/graduation-ledger.json``.

Usage:
    python3 scripts/knowledge-graduation-check.py SPEC_DIR --mapping FILE \
        --evidence-url https://github.com/owner/repo/pull/123
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

GRADUATION_LEDGER = Path(".specify/graduation-ledger.json")
# Duplicated from scripts/project-next.py so this checker remains a standalone
# offline tool. tests/test_knowledge_graduation_check.py pins both constants.
GRADUATION_LEDGER_VERSION = 1
MAPPING_VERSION = 1
LOCK_TIMEOUT_SECONDS = 10.0

DURABLE_HOMES = frozenset(
    {
        "code-tests",
        "types-schemas",
        "local-intent-comment",
        "adr",
        "domain-glossary",
        "runbook-checks",
        "maintained-docs",
        "issue-or-rejection",
    }
)
INDEPENDENT_VALUES = frozenset(
    {"none", "contractual", "regulatory", "compliance", "public-protocol", "cross-team"}
)
TASK_RESOLUTIONS = frozenset({"closed-issue", "rejected"})
ACCEPTANCE_HEADING_RE = re.compile(
    r"^(?:(#{1,6})\s+Acceptance Criteria:?|\*\*Acceptance Criteria:?\*\*)\s*$",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^(#{1,6})\s+")
CHECKBOX_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s+(.+?)\s*$")
TASK_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s+(?:\*\*)?(T\d{3,})(?:\*\*)?\b", re.IGNORECASE)


class GraduationError(Exception):
    """A fail-closed validation or persistence error."""


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GraduationError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise GraduationError(f"{label} must be a JSON object")
    return payload


def _clean_markdown(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def parse_acceptance_criteria(spec_path: Path) -> tuple[str, ...]:
    """Extract checkbox criteria only from Acceptance Criteria sections."""
    lines = spec_path.read_text(encoding="utf-8").splitlines()
    criteria: list[str] = []
    section_level: int | None = None
    current: list[str] | None = None
    for line in lines:
        acceptance = ACCEPTANCE_HEADING_RE.match(line.strip())
        if acceptance:
            if current:
                criteria.append(_clean_markdown(" ".join(current)))
            current = None
            section_level = len(acceptance.group(1)) if acceptance.group(1) else 6
            continue
        heading = HEADING_RE.match(line.strip())
        if heading and section_level is not None and len(heading.group(1)) <= section_level:
            if current:
                criteria.append(_clean_markdown(" ".join(current)))
            current = None
            section_level = None
            continue
        if section_level is None:
            continue
        checkbox = CHECKBOX_RE.match(line)
        if checkbox:
            if current:
                criteria.append(_clean_markdown(" ".join(current)))
            current = [checkbox.group(1)]
        elif current is not None and line.startswith((" ", "\t")) and line.strip():
            current.append(line.strip())
    if current:
        criteria.append(_clean_markdown(" ".join(current)))
    return tuple(criteria)


def parse_tasks(tasks_path: Path) -> tuple[str, ...]:
    tasks = {
        match.group(1).upper()
        for line in tasks_path.read_text(encoding="utf-8").splitlines()
        if (match := TASK_RE.match(line))
    }
    return tuple(sorted(tasks))


def _required_string(payload: dict[str, object], field: str, label: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise GraduationError(f"{label} requires a non-empty {field}")
    return value.strip()


def _is_evidence_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _verify_artifact(root: Path, value: str, *, criterion: str) -> None:
    if _is_evidence_url(value):
        return
    artifact = Path(value)
    if artifact.is_absolute() or ".." in artifact.parts:
        raise GraduationError(f"acceptance criterion {criterion!r} has unsafe artifact path {value!r}")
    if not (root / artifact).exists():
        raise GraduationError(f"acceptance criterion {criterion!r} maps to missing artifact {value!r}")


def _validate_criterion_mapping(
    root: Path,
    criterion: str,
    raw: dict[str, object],
) -> None:
    durable_home = _required_string(raw, "durable_home", f"acceptance criterion {criterion!r}")
    if durable_home not in DURABLE_HOMES:
        raise GraduationError(
            f"acceptance criterion {criterion!r} has unknown durable_home {durable_home!r}"
        )
    artifacts = raw.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts or not all(
        isinstance(item, str) and item.strip() for item in artifacts
    ):
        raise GraduationError(f"acceptance criterion {criterion!r} requires non-empty artifacts")
    cleaned = [item.strip() for item in artifacts if isinstance(item, str)]
    for artifact in cleaned:
        _verify_artifact(root, artifact, criterion=criterion)
    if durable_home == "code-tests":
        local = [artifact for artifact in cleaned if not _is_evidence_url(artifact)]
        test_artifacts = [
            artifact
            for artifact in local
            if "tests" in Path(artifact).parts or Path(artifact).name.startswith("test_")
        ]
        production_artifacts = [artifact for artifact in local if artifact not in test_artifacts]
        if not production_artifacts or not test_artifacts:
            raise GraduationError(
                f"acceptance criterion {criterion!r} with durable_home 'code-tests' requires "
                "a production artifact and a test artifact"
            )
    if durable_home == "issue-or-rejection" and not any(_is_evidence_url(item) for item in cleaned):
        raise GraduationError(
            f"acceptance criterion {criterion!r} with durable_home 'issue-or-rejection' "
            "requires an http(s) evidence URL"
        )


def validate_mapping(
    root: Path,
    spec_dir: Path,
    mapping: dict[str, object],
) -> tuple[str, str, str | None]:
    if mapping.get("version") != MAPPING_VERSION:
        raise GraduationError(f"mapping version must be {MAPPING_VERSION}")
    slug = _required_string(mapping, "spec_slug", "mapping")
    if slug != spec_dir.name:
        raise GraduationError(f"mapping spec_slug {slug!r} does not match spec directory {spec_dir.name!r}")
    state = _required_string(mapping, "state", "mapping")
    if state not in {"graduated", "retained"}:
        raise GraduationError("mapping state must be exactly 'graduated' or 'retained'")
    independent_value = _required_string(mapping, "independent_value", "mapping")
    if independent_value not in INDEPENDENT_VALUES:
        raise GraduationError(
            f"mapping independent_value must be one of {', '.join(sorted(INDEPENDENT_VALUES))}"
        )
    owner_value = mapping.get("owner")
    owner = owner_value.strip() if isinstance(owner_value, str) and owner_value.strip() else None
    if independent_value != "none" and state != "retained":
        raise GraduationError(
            f"independently valuable {independent_value} spec cannot be graduated for deletion; "
            "mark it retained with a named owner"
        )
    if state == "retained" and owner is None:
        raise GraduationError("retained spec requires a non-empty owner")
    if state == "graduated" and owner is not None:
        raise GraduationError("graduated ledger entries must not carry an owner")

    criteria = parse_acceptance_criteria(spec_dir / "spec.md")
    if not criteria:
        raise GraduationError("spec.md contains no checkbox acceptance criteria")
    raw_criteria = mapping.get("acceptance_criteria")
    if not isinstance(raw_criteria, list):
        raise GraduationError("mapping acceptance_criteria must be a list")
    mapped: dict[str, dict[str, object]] = {}
    for index, raw in enumerate(raw_criteria):
        if not isinstance(raw, dict):
            raise GraduationError(f"acceptance_criteria entry {index} must be an object")
        criterion = _required_string(raw, "criterion", f"acceptance_criteria entry {index}")
        if criterion in mapped:
            raise GraduationError(f"acceptance criterion {criterion!r} is mapped more than once")
        mapped[criterion] = raw
    for criterion in criteria:
        raw = mapped.get(criterion)
        if raw is None:
            raise GraduationError(f"unmapped acceptance criterion: {criterion}")
        _validate_criterion_mapping(root, criterion, raw)
    extras = sorted(set(mapped) - set(criteria))
    if extras:
        raise GraduationError(f"mapping contains unknown acceptance criterion: {extras[0]}")

    tasks = parse_tasks(spec_dir / "tasks.md")
    if not tasks:
        raise GraduationError("tasks.md contains no T-numbered checkbox tasks")
    raw_tasks = mapping.get("tasks")
    if not isinstance(raw_tasks, list):
        raise GraduationError("mapping tasks must be a list")
    resolutions: dict[str, tuple[str, str]] = {}
    for index, raw in enumerate(raw_tasks):
        if not isinstance(raw, dict):
            raise GraduationError(f"tasks entry {index} must be an object")
        task_id = _required_string(raw, "task_id", f"tasks entry {index}").upper()
        resolution = _required_string(raw, "resolution", f"task {task_id}")
        evidence_url = _required_string(raw, "evidence_url", f"task {task_id}")
        if resolution not in TASK_RESOLUTIONS:
            raise GraduationError(f"task {task_id} resolution must be closed-issue or rejected")
        if not _is_evidence_url(evidence_url):
            raise GraduationError(f"task {task_id} evidence_url must be an http(s) URL")
        if task_id in resolutions:
            raise GraduationError(f"task {task_id} is resolved more than once")
        resolutions[task_id] = (resolution, evidence_url)
    unresolved = [task_id for task_id in tasks if task_id not in resolutions]
    if unresolved:
        raise GraduationError(f"unresolved task: {unresolved[0]}")
    extras = sorted(set(resolutions) - set(tasks))
    if extras:
        raise GraduationError(f"mapping contains unknown task: {extras[0]}")
    return slug, state, owner


def _load_ledger(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    payload = _read_json_object(path, "graduation ledger")
    if payload.get("version") != GRADUATION_LEDGER_VERSION:
        raise GraduationError(
            "graduation ledger version mismatch: "
            f"expected {GRADUATION_LEDGER_VERSION}, found {payload.get('version')!r}"
        )
    raw_specs = payload.get("specs")
    if not isinstance(raw_specs, list):
        raise GraduationError("graduation ledger 'specs' must be a list")
    specs: list[dict[str, str]] = []
    for index, raw in enumerate(raw_specs):
        if not isinstance(raw, dict):
            raise GraduationError(f"graduation ledger entry {index} must be an object")
        slug = _required_string(raw, "spec_slug", f"graduation ledger entry {index}")
        state = _required_string(raw, "state", f"graduation ledger entry {index}")
        evidence = _required_string(raw, "evidence_url", f"graduation ledger entry {index}")
        recorded = _required_string(raw, "recorded_at", f"graduation ledger entry {index}")
        if state not in {"graduated", "retained"}:
            raise GraduationError(f"graduation ledger {slug}: state must be graduated or retained")
        entry = {
            "spec_slug": slug,
            "state": state,
            "evidence_url": evidence,
            "recorded_at": recorded,
        }
        if state == "retained":
            entry["owner"] = _required_string(raw, "owner", f"graduation ledger {slug}")
        specs.append(entry)
    return specs


@contextmanager
def _ledger_lock(ledger_path: Path) -> Iterator[None]:
    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()))
    lock_dir = runtime_dir / "cpp-knowledge-graduation-locks"
    digest = hashlib.sha256(str(ledger_path).encode("utf-8")).hexdigest()
    try:
        lock_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock_file = (lock_dir / f"{digest}.lock").open("a+", encoding="utf-8")
    except OSError as exc:
        raise GraduationError(f"cannot prepare graduation ledger lock: {exc}") from exc
    with lock_file:
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise GraduationError(f"could not lock graduation ledger {ledger_path} within 10 seconds") from exc
                time.sleep(0.05)
            except OSError as exc:
                raise GraduationError(f"cannot lock graduation ledger {ledger_path}: {exc}") from exc
        try:
            yield
        finally:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


def _atomic_write_ledger(path: Path, specs: list[dict[str, str]]) -> None:
    temp_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, raw_temp_path = tempfile.mkstemp(prefix=".graduation-ledger.", dir=path.parent)
        temp_path = Path(raw_temp_path)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"version": GRADUATION_LEDGER_VERSION, "specs": specs}, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, 0o644)
        os.replace(temp_path, path)
        temp_path = None
    except OSError as exc:
        raise GraduationError(f"cannot atomically write graduation ledger {path}: {exc}") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def graduate(
    root: Path,
    spec_dir: Path,
    mapping_path: Path,
    evidence_url: str,
    recorded_at: str,
) -> dict[str, str]:
    root = root.resolve()
    spec_dir = spec_dir.resolve()
    mapping_path = mapping_path.resolve()
    try:
        spec_dir.relative_to(root)
        mapping_path.relative_to(root)
    except ValueError as exc:
        raise GraduationError("spec directory and mapping must be inside the repository") from exc
    for name in ("spec.md", "tasks.md"):
        if not (spec_dir / name).is_file():
            raise GraduationError(f"spec directory is missing {name}: {spec_dir / name}")
    if not _is_evidence_url(evidence_url):
        raise GraduationError("evidence_url must be an http(s) tracker or PR URL")
    try:
        parsed_date = date.fromisoformat(recorded_at)
    except ValueError as exc:
        raise GraduationError("recorded_at must be an ISO date (YYYY-MM-DD)") from exc
    if parsed_date.isoformat() != recorded_at:
        raise GraduationError("recorded_at must be an ISO date (YYYY-MM-DD)")
    mapping = _read_json_object(mapping_path, "mapping")
    slug, state, owner = validate_mapping(root, spec_dir, mapping)
    entry = {
        "spec_slug": slug,
        "state": state,
        "evidence_url": evidence_url,
        "recorded_at": recorded_at,
    }
    if owner is not None:
        entry["owner"] = owner

    ledger_path = root / GRADUATION_LEDGER
    with _ledger_lock(ledger_path):
        specs = _load_ledger(ledger_path)
        specs = [existing for existing in specs if existing["spec_slug"] != slug]
        specs.append(entry)
        specs.sort(key=lambda item: item["spec_slug"])
        _atomic_write_ledger(ledger_path, specs)
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec_dir", type=Path, help="directory containing spec.md and tasks.md")
    parser.add_argument("--mapping", required=True, type=Path, help="explicit graduation mapping JSON")
    parser.add_argument("--evidence-url", required=True, help="reviewed tracker or PR URL")
    parser.add_argument("--recorded-at", default=date.today().isoformat(), help="ISO date (default: today)")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root (default: cwd)")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    spec_dir = args.spec_dir if args.spec_dir.is_absolute() else root / args.spec_dir
    mapping_path = args.mapping if args.mapping.is_absolute() else root / args.mapping
    try:
        entry = graduate(root, spec_dir, mapping_path, args.evidence_url, args.recorded_at)
    except GraduationError as exc:
        print(f"knowledge-graduation: {exc}", file=sys.stderr)
        return 1
    print(
        f"knowledge-graduation: ok - {entry['spec_slug']} recorded as {entry['state']} "
        f"in {GRADUATION_LEDGER}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
