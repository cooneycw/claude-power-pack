"""Render main-app enrolment jobs from cpp:init's recorded immutable revision.

Infra generators remain path-scoped and are deliberately not enrolled here.
"""
# NEGATIVE-CONTROL: controls/pinned-enrolment
# NEGATIVE-CONTROL: controls/pinned-enrolment-fork-evidence
# NEGATIVE-CONTROL: controls/pinned-enrolment-exit-class
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path


def installed_revision(project: str | Path) -> str:
    """One pin source: .claude/cpp-install.json, written by cpp:init."""
    try:
        value = json.loads((Path(project) / ".claude/cpp-install.json").read_text())
        pin = value.get("cpp_revision") if (isinstance(value, dict) and type(value.get("schema")) is int
                                            and value["schema"] in {1, 2}) else None
        return pin if isinstance(pin, str) and re.fullmatch(r"[0-9a-f]{40}", pin) else ""
    except (OSError, ValueError):
        return ""


def bootstrap_script(pin: str, provider: str) -> str:
    """Self-contained trusted-checkout bootstrap; all undecidable paths exit 5."""
    if provider not in {"github-actions", "woodpecker"}:
        raise ValueError("enrolment provider unavailable")
    return r'''#!/usr/bin/env bash
set -uo pipefail
unknown() { echo "CPP_COUNTER_MODEL_ENROLMENT: unknown ($1; retry or refresh /cpp:init)"; exit 5; }
CPP_SHA=__PIN__
provider=__PROVIDER__
event="${CPP_PR_EVENT:-}"
branch="${CPP_PR_BRANCH:-}"
head_repo="${CPP_PR_HEAD_REPO:-}"
base_repo="${CPP_PR_BASE_REPO:-}"
if [[ "$provider" == woodpecker ]]; then
    event="${CI_PIPELINE_EVENT:-}"
    branch="${CI_COMMIT_SOURCE_BRANCH:-}"
    head_repo=""
    base_repo=""
fi
case "$event" in
    push) echo 'CPP_COUNTER_MODEL_ENROLMENT: not-applicable (push)'; exit 0 ;;
    pull_request) ;;
    *) unknown 'PR event metadata unavailable' ;;
esac
[[ "$CPP_SHA" =~ ^[0-9a-f]{40}$ ]] || unknown 'immutable full CPP SHA unavailable'
for tool in git mktemp sed head grep timeout; do
    command -v "$tool" >/dev/null || unknown "required tool $tool unavailable"
done
consumer_head=$(git rev-parse HEAD) || unknown 'consumer checkout unreadable'
if [[ "$provider" == woodpecker ]]; then
    [[ "${CI_FORGE_TYPE:-}" == github && "${CI_FORGE_URL:-}" == https://github.com ]] ||
        unknown 'unsupported forge metadata'
    [[ "${CI_COMMIT_PULL_REQUEST:-}" =~ ^[1-9][0-9]*$ &&
       "${CI_REPO:-}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || unknown 'PR identity unavailable'
    if ! command -v curl >/dev/null || ! command -v python3 >/dev/null; then
        unknown 'metadata reader unavailable'
    fi
    api="https://api.github.com/repos/$CI_REPO/pulls/$CI_COMMIT_PULL_REQUEST"
    if [[ -n "${GH_TOKEN:-}" ]]; then
        metadata=$(printf 'Authorization: Bearer %s\n' "$GH_TOKEN" |
            curl -fsS --connect-timeout 10 --max-time 30 -H @- "$api") || unknown 'PR metadata API unavailable'
    else
        metadata=$(curl -fsS --connect-timeout 10 --max-time 30 "$api") || unknown 'PR metadata API unavailable'
    fi
    identities=$(printf '%s' "$metadata" | python3 -I -c '
import json,re,sys
value=json.load(sys.stdin)
base=value["base"]["repo"]["full_name"]
head=value["head"]["repo"]["full_name"]
assert all(isinstance(x,str) and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",x) for x in (base,head))
assert base==sys.argv[1] and value["head"]["ref"]==sys.argv[2] and value["head"]["sha"]==sys.argv[3]
print(head);print(base)
' "$CI_REPO" "$branch" "$consumer_head" 2>/dev/null) || unknown 'PR metadata cannot be attributed to this checkout'
    head_repo=$(printf '%s\n' "$identities" | head -1)
    base_repo=$(printf '%s\n' "$identities" | sed -n '2p')
fi
[[ -n "$branch" && "$head_repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ &&
   "$base_repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || unknown 'fork status unestablished'
if [[ "$head_repo" != "$base_repo" ]]; then
    echo 'CPP_COUNTER_MODEL_ENROLMENT: warn (known fork PR; counter-model receipt not required)'
    exit 0
fi
shallow=$(git rev-parse --is-shallow-repository) || unknown 'consumer history unreadable'
case "$shallow" in
    true)
        timeout 300s git fetch --quiet --unshallow origin || unknown 'consumer history fetch failed'
        [[ "$(git rev-parse --is-shallow-repository)" == false ]] || unknown 'consumer history still shallow'
        ;;
    false) ;;
    *) unknown 'consumer history state invalid' ;;
esac
cpp_tmp=$(mktemp -d) || unknown 'temporary checkout unavailable'
trap 'rm -rf -- "$cpp_tmp"' EXIT
git -C "$cpp_tmp" init --quiet || unknown 'CPP checkout init failed'
timeout 120s git -C "$cpp_tmp" fetch --quiet --no-tags --depth=1 \
    https://github.com/cooneycw/claude-power-pack.git "$CPP_SHA" || unknown 'CPP fetch failed'
git -C "$cpp_tmp" checkout --quiet --detach FETCH_HEAD || unknown 'CPP checkout failed'
resolved=$(git -C "$cpp_tmp" rev-parse HEAD) || unknown 'CPP checkout revision unreadable'
[[ "$resolved" == "$CPP_SHA" ]] || unknown 'resolved CPP SHA mismatch'
[[ "$(git rev-parse HEAD)" == "$consumer_head" ]] || unknown 'consumer head changed during bootstrap'
[[ -r "$cpp_tmp/scripts/flow-finish-gate.sh" && -r "$cpp_tmp/scripts/counter-model-receipt.py" ]] ||
    unknown 'CPP enrolment bootstrap incomplete'
if output=$(PYTHONPATH='' PYTHONNOUSERSITE=1 \
    CM_RECEIPT_HELPER="$cpp_tmp/scripts/counter-model-receipt.py" FLOW_GATE_CPP_DIR="$cpp_tmp" \
    bash "$cpp_tmp/scripts/flow-finish-gate.sh" --enrolment-only --branch "$branch" </dev/null 2>&1); then
    status=0
else
    status=$?
fi
printf '%s\n' "$output"
[[ "$(grep -c '^FLOW_FINISH_GATE: ' <<<"$output")" == 1 ]] || unknown 'ambiguous checker verdict'
if [[ "$status" == 0 && "$(grep -cx 'FLOW_FINISH_GATE: ok' <<<"$output")" == 1 ]]; then
    echo 'CPP_COUNTER_MODEL_ENROLMENT: ok'; exit 0
elif [[ "$status" == 1 && "$(grep -c '^FLOW_FINISH_GATE: fail' <<<"$output")" == 1 ]]; then
    echo 'CPP_COUNTER_MODEL_ENROLMENT: fail (same-repository PR has no valid receipt)'; exit 1
fi
unknown 'trusted enrolment checker could not decide'
'''.replace("__PIN__", shlex.quote(pin)).replace("__PROVIDER__", shlex.quote(provider))


def github_actions_job(pin: str) -> list[str]:
    # Bootstrap extraction remains stdlib-only; the workflow renderer shares pins.
    from .actions import CHECKOUT

    lines = ["  counter-model-enrolment:", "    runs-on: ubuntu-latest", "    timeout-minutes: 10", "    permissions:",
             "      contents: read", "    env:", "      CPP_PR_EVENT: ${{ github.event_name }}",
             "      CPP_PR_BRANCH: ${{ github.head_ref }}",
             "      CPP_PR_HEAD_REPO: ${{ github.event.pull_request.head.repo.full_name }}",
             "      CPP_PR_BASE_REPO: ${{ github.event.pull_request.base.repo.full_name }}",
             "    steps:", f"      - uses: {CHECKOUT}", "        with:", "          fetch-depth: 0",
             "          persist-credentials: false",
             "          ref: ${{ github.event.pull_request.head.sha || github.sha }}",
             "      - name: Check counter-model enrolment", "        shell: bash", "        run: |"]
    lines.extend("          " + line for line in bootstrap_script(pin, "github-actions").splitlines())
    return [*lines, ""]


def woodpecker_step(pin: str) -> list[str]:
    lines = ["  - name: counter-model-enrolment",
             "    # Enrolment runtime is a tag-only exception to the clone/scanner digest pins.",
             "    image: python:3.11-bookworm",
             "    when:", "      event: pull_request", "    commands:",
             "      - >-", "        timeout 120s sh -c",
             '        "apt-get update && apt-get install -y --no-install-recommends bash git curl ca-certificates"',
             "        || { echo 'CPP_COUNTER_MODEL_ENROLMENT: unknown (tool bootstrap failed; retry)'; exit 5; }",
             "      - |", "        bash -s <<'CPP_ENROLMENT_BOOTSTRAP'"]
    # Woodpecker expands ${...} before starting the shell. Escape every dollar
    # so event values and shell substitutions remain data until runtime.
    lines.extend("        " + line.replace("$", "$$") for line in bootstrap_script(pin, "woodpecker").splitlines())
    lines.extend(["        CPP_ENROLMENT_BOOTSTRAP", ""])
    return lines


def woodpecker_enrolment_graph(lines: list[str]) -> list[str]:
    """Keep enrolment independent while retaining application step ordering."""
    result: list[str] = []
    previous: str | None = None
    in_steps = False
    for line in lines:
        result.append(line)
        if line == "steps:":
            in_steps = True
        if in_steps and line.startswith("  - name: "):
            name = line.removeprefix("  - name: ")
            parents = [] if name == "counter-model-enrolment" or previous is None else [previous]
            result.append("    depends_on: " + json.dumps(parents))
            if name != "counter-model-enrolment":
                previous = name
    return result
