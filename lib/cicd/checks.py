"""Derive unconditional PR contexts from CPP-shaped emitted pipelines (#1608).

No network or protection API is used. Unsupported expressions/shapes are unknown;
push-only and path-filtered workflows cannot supply mandatory checks on every PR.
"""

from __future__ import annotations

import importlib
import itertools
import json
import os
import stat
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import CICDConfig
from .providers import PROVIDERS, ProviderError, require_providers


class UnknownChecks(ValueError):
    """The input cannot establish an unconditional PR check population."""


@dataclass(frozen=True)
class RequiredChecks:
    status: str
    checks: tuple[str, ...] = ()
    reason: str = ""
    examined_files: int = 0
    excluded: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise UnknownChecks(f"{label}: expected mapping")
    return value


def _yaml(text: str, filename: str) -> dict[str, Any]:
    def plain_data(node: yaml.Node) -> Any:
        if isinstance(node, yaml.MappingNode):
            seen = set()
            data = {}
            for key, value in node.value:
                if not isinstance(key, yaml.ScalarNode) or key.value in seen:
                    raise UnknownChecks(f"{filename}: duplicate or complex YAML key")
                seen.add(key.value)
                data[key.value] = plain_data(value)
            return data
        if isinstance(node, yaml.SequenceNode):
            return [plain_data(value) for value in node.value]
        if isinstance(node, yaml.ScalarNode):
            if node.style is None and node.value.lower() in ("", "null", "~"):
                return None
            return node.value
        raise UnknownChecks(filename + ": unsupported YAML node")

    try:
        # BaseLoader keeps `on` and numeric matrix values as strings, and has
        # no application/object constructors. SafeLoader's YAML 1.1 `on` is bool.
        if any(isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken, yaml.tokens.TagToken))
               for token in yaml.scan(text, Loader=yaml.BaseLoader)):
            raise UnknownChecks(filename + ": aliases/anchors/tags are outside CPP-generated shapes")
        node = yaml.compose(text, Loader=yaml.BaseLoader)
        if node is None:
            raise UnknownChecks(filename + ": empty YAML")
        return _mapping(plain_data(node), filename)
    except (yaml.YAMLError, RecursionError) as exc:
        raise UnknownChecks(f"{filename}: malformed YAML") from exc


def _events(value: Any, label: str, *, allow_mapping: bool = False) -> set[str]:
    if isinstance(value, str):
        events = {value}
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        events = set(value)
    elif allow_mapping and isinstance(value, dict):
        events = set(value)
    else:
        raise UnknownChecks(f"{label}: unsupported event shape")
    if not events or events - {"push", "pull_request", "workflow_dispatch"}:
        raise UnknownChecks(f"{label}: unsupported event name")
    return events


def _main_branch(value: Any, label: str) -> None:
    branches = [value] if isinstance(value, str) else value
    if branches is not None and branches != ["main"]:
        raise UnknownChecks(f"{label}: unsupported branch filter")


def github_actions_checks(files: dict[str, str]) -> RequiredChecks:
    selected = {name: text for name, text in files.items()
                if name.startswith(".github/workflows/") and name.endswith((".yml", ".yaml"))}
    if not selected:
        raise UnknownChecks("GitHub Actions workflow files missing")
    names: list[str] = []
    excluded: list[str] = []
    for filename, text in sorted(selected.items()):
        workflow = _yaml(text, filename)
        trigger = workflow.get("on")
        events = _events(trigger, filename, allow_mapping=True)
        if isinstance(trigger, dict):
            for event, options in trigger.items():
                if options is None:
                    continue
                options = _mapping(options, filename + " " + event)
                allowed = {"branches", "paths", "paths-ignore"} if event != "workflow_dispatch" else set()
                if event == "pull_request":
                    allowed.add("types")
                if {"paths", "paths-ignore"} <= set(options):
                    raise UnknownChecks(filename + ": mutually exclusive path filters")
                if set(options) - allowed:
                    raise UnknownChecks(filename + ": unsupported " + event + " filter")
                for key, values in options.items():
                    if not isinstance(values, list) or not values or not all(
                        isinstance(value, str) and value for value in values
                    ):
                        raise UnknownChecks(filename + ": invalid " + event + " " + key + " filter")
                _main_branch(options.get("branches"), filename)
        if "pull_request" not in events:
            excluded.append(filename + ": no pull_request event")
            continue
        if isinstance(trigger, dict):
            filters = trigger["pull_request"]
            if filters is None:
                filters = {}
            filters = _mapping(filters, filename + " pull_request")
            _main_branch(filters.get("branches"), filename)
            if any(key in filters for key in ("paths", "paths-ignore", "types")):
                excluded.append(filename + ": conditional pull_request filter")
                continue
            if set(filters) - {"branches"}:
                raise UnknownChecks(filename + ": unsupported pull_request filter")
        jobs = _mapping(workflow.get("jobs"), filename + " jobs")
        if not jobs:
            raise UnknownChecks(filename + ": no jobs examined")
        for job_id, raw_job in jobs.items():
            job = _mapping(raw_job, filename + " job " + job_id)
            condition = job.get("if")
            if condition == "github.ref == 'refs/heads/main' && github.event_name == 'push'":
                excluded.append(filename + ": " + job_id + " is push-only")
                continue
            if condition:
                raise UnknownChecks(filename + ": unsupported job condition")
            runner = job.get("runs-on")
            steps = job.get("steps")
            if not isinstance(runner, str) or not runner or "${{" in runner:
                raise UnknownChecks(filename + ": unsupported job runner")
            if "needs" in job:
                raise UnknownChecks(filename + ": conditional job dependency is outside CPP-generated PR jobs")
            if not isinstance(steps, list) or not steps or any(
                not isinstance(step, dict) or not ({"run", "uses"} & set(step)) for step in steps
            ):
                raise UnknownChecks(filename + ": incomplete job steps")
            name = job.get("name", job_id)
            if not isinstance(name, str) or not name or "${{" in name or "\n" in name:
                raise UnknownChecks(filename + ": dynamic/invalid job name")
            strategy = job.get("strategy")
            if strategy is None:
                names.append(name)
                continue
            if "name" in job:
                raise UnknownChecks(filename + ": explicit matrix job names are outside CPP-generated shapes")
            matrix = _mapping(_mapping(strategy, filename + " strategy").get("matrix"), filename + " matrix")
            if not matrix or {"include", "exclude"} & set(matrix):
                raise UnknownChecks(filename + ": unsupported matrix shape")
            axes = []
            cells = 1
            for values in matrix.values():
                if not isinstance(values, list) or not values or any(
                    not isinstance(value, str) or "${{" in value for value in values
                ):
                    raise UnknownChecks(filename + ": dynamic/invalid matrix values")
                axes.append(values)
                cells *= len(values)
            if cells > 256:
                raise UnknownChecks(filename + ": matrix exceeds 256 cells")
            names.extend(name + " (" + ", ".join(cell) + ")" for cell in itertools.product(*axes))
    return RequiredChecks("known", tuple(names), examined_files=len(selected), excluded=tuple(excluded))


def woodpecker_checks(files: dict[str, str]) -> RequiredChecks:
    selected = {name: text for name, text in files.items() if
                name in (".woodpecker.yml", ".woodpecker.yaml") or
                name.startswith(".woodpecker/") and name.endswith((".yml", ".yaml"))}
    if not selected:
        raise UnknownChecks("Woodpecker pipeline files missing")
    roots = [name for name in selected if "/" not in name]
    if len(roots) > 1 or roots and len(selected) > 1:
        raise UnknownChecks("ambiguous Woodpecker root/directory configuration")
    names = []
    excluded = []
    for filename, text in sorted(selected.items()):
        pipeline = _yaml(text, filename)
        if set(pipeline) - {"when", "steps", "clone"}:
            raise UnknownChecks(filename + ": unsupported Woodpecker shape")
        if "clone" in pipeline:
            clone = pipeline["clone"]
            if (not isinstance(clone, list) or len(clone) != 1 or
                    clone[0] != {"name": "git", "image": "woodpeckerci/plugin-git:2",
                                 "settings": {"depth": "0", "merge_pull_request": "false"}}):
                raise UnknownChecks(filename + ": unsupported clone configuration")
        when = _mapping(pipeline.get("when"), filename + " when")
        _main_branch(when.get("branch"), filename)
        if "pull_request" not in _events(when.get("event"), filename):
            excluded.append(filename + ": no pull_request event")
            continue
        if "path" in when:
            excluded.append(filename + ": conditional path filter")
            continue
        if set(when) - {"branch", "event"}:
            raise UnknownChecks(filename + ": unsupported Woodpecker filter")
        steps = pipeline.get("steps")
        if not isinstance(steps, list) or not steps:
            raise UnknownChecks(filename + ": no steps examined")
        eligible = False
        for raw_step in steps:
            step = _mapping(raw_step, filename + " step")
            if not isinstance(step.get("name"), str) or not isinstance(step.get("image"), str):
                raise UnknownChecks(filename + ": incomplete pipeline step")
            commands = step.get("commands")
            if not isinstance(commands, list) or not commands or not all(isinstance(cmd, str) for cmd in commands):
                raise UnknownChecks(filename + ": incomplete pipeline commands")
            step_when = step.get("when")
            if step_when is None:
                eligible = True
            else:
                step_when = _mapping(step_when, filename + " step when")
                _main_branch(step_when.get("branch"), filename)
                if set(step_when) - {"event", "branch"}:
                    raise UnknownChecks(filename + ": unsupported step filter")
                if "pull_request" in _events(step_when.get("event"), filename):
                    eligible = True
        if not eligible:
            excluded.append(filename + ": no unconditional PR steps")
            continue
        context = "woodpecker" if filename in roots else Path(filename).stem
        names.append("ci/woodpecker/pr/" + context)
    return RequiredChecks("known", tuple(names), examined_files=len(selected), excluded=tuple(excluded))


def derive_required_checks(providers: list[str], files: dict[str, str]) -> RequiredChecks:
    names: list[str] = []
    excluded: list[str] = []
    examined = 0
    try:
        for name in require_providers(providers):
            hook = PROVIDERS[name].required_check
            module, separator, function = hook.partition(":")
            if not separator:
                raise UnknownChecks(name + ": no required-check derivation registered")
            derive = getattr(importlib.import_module(module), function)
            result = derive(files)
            if result.status != "known":
                raise UnknownChecks(result.reason)
            if not result.checks or result.examined_files <= 0:
                raise UnknownChecks(name + ": no unconditional PR context population")
            names.extend(result.checks)
            excluded.extend(result.excluded)
            examined += result.examined_files
        if not names:
            raise UnknownChecks("no unconditional PR contexts derived")
        if len(names) != len(set(names)):
            raise UnknownChecks("duplicate context names across generated jobs/cells")
        return RequiredChecks("known", tuple(sorted(names)), examined_files=examined, excluded=tuple(excluded))
    except (UnknownChecks, ProviderError, ImportError, AttributeError) as exc:
        return RequiredChecks("unknown", reason=str(exc), examined_files=examined, excluded=tuple(excluded))


def read_pipeline_files(project: str | Path) -> dict[str, str]:
    root = Path(project)
    paths = [*root.glob(".github/workflows/*.yml"), *root.glob(".github/workflows/*.yaml"),
             *root.glob(".woodpecker/*.yml"), *root.glob(".woodpecker/*.yaml")]
    paths.extend(path for path in (root / ".woodpecker.yml", root / ".woodpecker.yaml") if path.is_file())
    return {str(path.relative_to(root)): path.read_text() for path in paths}


def check_posture(result: RequiredChecks, posture: Any) -> dict[str, Any]:
    if result.status != "known" or not result.checks or result.examined_files <= 0:
        return {"status": "unknown", "reason": result.reason or "no established PR context population"}
    try:
        checks = posture["protection"]["required_status_checks"]
        contexts = checks.get("contexts", [])
        keyed = checks.get("checks", [])
        if not isinstance(contexts, list) or not all(isinstance(name, str) for name in contexts):
            raise ValueError("contexts must be strings")
        if not isinstance(keyed, list) or not all(isinstance(item, dict) and isinstance(item.get("context"), str)
                                                for item in keyed):
            raise ValueError("checks must name contexts")
        if any(item.get("app_id") not in (None, -1) for item in keyed):
            return {"status": "unknown", "reason": "required-check app binding cannot be verified from local pipelines"}
        actual = [*contexts, *(item["context"] for item in keyed)]
    except (KeyError, TypeError, AttributeError, ValueError):
        return {"status": "unknown", "reason": "required-check posture missing or malformed"}
    if not isinstance(posture.get("branch"), str):
        return {"status": "unknown", "reason": "protection branch missing or malformed"}
    if posture["branch"] != "main":
        return {"status": "drift", "reason": "protection branch must match supported PR target main"}
    missing = sorted(set(result.checks) - set(actual))
    extra = sorted(set(actual) - set(result.checks))
    return {"status": "drift" if missing or extra else "ok", "missing": missing, "extra": extra,
            "examined_files": result.examined_files, "required_contexts": len(result.checks)}


def protection_record(config: CICDConfig, result: RequiredChecks) -> dict[str, Any]:
    if result.status != "known" or not result.checks or result.examined_files <= 0:
        reason = result.reason or "no established PR context population"
        raise UnknownChecks("cannot record required checks: " + reason)
    policy = config.branch_protection
    if policy.require_status_checks and set(policy.require_status_checks) != set(result.checks):
        raise UnknownChecks("configured branch_protection.require_status_checks disagrees with emitted PR contexts")
    policy = policy.model_copy(update={"require_status_checks": list(result.checks)})
    return {"branch": "main", "protection": {
        "required_status_checks": {"strict": policy.require_up_to_date, "contexts": policy.require_status_checks},
        "required_pull_request_reviews": {"required_approving_review_count": 1 if policy.require_pr_review else 0},
        "enforce_admins": False, "restrictions": None, "allow_force_pushes": False, "allow_deletions": False,
    }}


def host_capability(project: str | Path, providers: list[str]) -> dict[str, dict[str, Any]]:
    """Report the canonical host record as historical evidence, without probes."""
    from .host import read_host_record
    record = read_host_record(project)
    checked_at = record["checked_at"]
    refresh = "Refresh host capability with /cpp:init Tier 4 on the host."
    result = {}
    for name in require_providers(providers):
        state = record["providers"][name]
        summary = (f"last recorded {state['status']} at {checked_at}" if checked_at else
                   f"unknown: {state['reason']} (no recorded timestamp)")
        result[name] = {**state, "checked_at": checked_at, "summary": summary, "refresh": refresh}
    return result


def write_protection(project: str | Path, record: dict[str, Any]) -> None:
    path = Path(project) / ".claude/branch-protection.json"
    if path.is_symlink():
        raise ValueError("refusing to replace protection symlink; edit its source explicitly")
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    fd, temporary = tempfile.mkstemp(prefix=".protection-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(json.dumps(record, indent=2) + "\n")
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
