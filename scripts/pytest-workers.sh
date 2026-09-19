#!/usr/bin/env sh
# Resolve the pytest worker cap, and REFUSE `auto` (issues #640, #1086).
#
# POSIX sh on purpose: `make test` runs it on a dev box and the CI `validate`
# step runs it inside `ghcr.io/astral-sh/uv:python3.11-bookworm-slim`, which has
# sh and no bash.
#
# CONTRACT
#   stdout  the resolved integer, ALONE, so `-n "$(sh scripts/pytest-workers.sh)"`
#           is the whole call site
#   stderr  `pytest-workers: -n <N> (source: <where>)`, so the cap is in the run's
#           output rather than something a reader reconstructs from the yaml
#   exit 0  resolved to a positive integer
#   exit 2  REFUSED - `auto`, or anything that is not a positive integer. Refused
#           is not "fall back to a default": a caller who asked for a specific
#           parallelism and got silently overridden would be told nothing, and
#           the wrong number is the whole hazard here.
#
# PRECEDENCE, identical to `resolve_pytest_workers()` in `lib/cicd/steps.py`:
#
#     PYTEST_WORKERS  ->  CPP_TEST_WORKERS  ->  the default below
#
# That is #640's convention and this script does not invent a second one. #640
# shipped the precedence FOR CONSUMER PROJECTS - its issue body names this very
# host's contention as the reason - and CPP never applied it to itself, so CPP's
# own `make test` was the one suite on the box with no cap at all.
#
# WHY `auto` IS REFUSED RATHER THAN CLAMPED. `-n auto` means one worker per core.
# `nproc` is 24 on this host, one Woodpecker agent serves it with
# WOODPECKER_MAX_WORKFLOWS=2 and no per-step CPU limit, and flow sessions run full
# suites from worktrees beside the pipeline - nine of them were live while issue
# #1086 was being measured. Multiply 24 by the invocations actually in flight and
# the first symptom is not a slow machine, it is intermittent reds that read as
# regressions in whatever changed most recently. Clamping would make the caller's
# stated intention silently untrue; refusing makes them state a real one.
#
# THE DEFAULT LIVES HERE, in one place, because both callers need it: `make test`
# has a Makefile to declare things in and the CI step does not, and two
# declarations agreeing today is exactly the shape this repository keeps finding
# broken later. CI declares only its OVERRIDE (`PYTEST_WORKERS: "8"` on the
# `validate` step), which is a different statement from the default and belongs
# where it is made.
set -u

#: Dev-box default. 4, not 8, and the difference is contention rather than
#: caution: 8 is where #1086 measured 5.34x, but that was ONE suite. This box
#: routinely carries four to nine concurrent CPP suites from flow worktrees, and
#: 9x4=36 workers on 24 cores is already oversubscribed where 9x8=72 is threefold.
#: CI overrides it to 8 because WOODPECKER_MAX_WORKFLOWS=2 bounds that host to two
#: pipelines, so the same number means something different there.
DEFAULT_WORKERS=4

workers=""
source=""

if [ -n "${PYTEST_WORKERS:-}" ]; then
    workers="$PYTEST_WORKERS"
    source="PYTEST_WORKERS"
elif [ -n "${CPP_TEST_WORKERS:-}" ]; then
    workers="$CPP_TEST_WORKERS"
    source="CPP_TEST_WORKERS"
else
    workers="$DEFAULT_WORKERS"
    source="pytest-workers.sh default"
fi

case "$workers" in
    auto)
        echo "pytest-workers: REFUSED - $source=auto." >&2
        echo "  \`-n auto\` is one worker per core, and this host has $(nproc 2>/dev/null || echo many)" >&2
        echo "  cores shared with concurrent suites and CI. Set an explicit integer:" >&2
        echo "    PYTEST_WORKERS=8 make test" >&2
        exit 2
        ;;
    ''|*[!0-9]*)
        echo "pytest-workers: REFUSED - $source='$workers' is not a positive integer." >&2
        exit 2
        ;;
    0)
        echo "pytest-workers: REFUSED - $source=0 would run no workers at all." >&2
        exit 2
        ;;
esac

# Advisory only. A cap above the core count is usually a typo, and it is also a
# legitimate choice for a suite that WAITS rather than computes - which this one
# does. Reporting it keeps the reader informed without deciding for them.
cores=$(nproc 2>/dev/null || echo "")
if [ -n "$cores" ] && [ "$workers" -gt "$cores" ]; then
    echo "pytest-workers: note - $workers workers on $cores cores (oversubscribed)." >&2
fi

echo "pytest-workers: -n $workers (source: $source)" >&2
echo "$workers"
