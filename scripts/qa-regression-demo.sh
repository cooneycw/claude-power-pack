#!/usr/bin/env bash
# Three-arm demonstration of the QA regression export (issue #1291).
#
# Copies the fixture consumer project to a scratch directory, installs its pinned
# Playwright runner with its own lockfile, EXPORTS the committed repro spec with
# scripts/qa-regression-export.py, and then runs the exported test three times:
#
#   buggy app  -> must classify `reproduced`   (the test can fail)
#   fixed app  -> must classify `passed`       (the test can pass)
#   no app     -> must classify `unavailable`  (a down app is not a reproduction)
#
# THE BUGGY ARM IS THE NEGATIVE CONTROL, AND IT HAS ALREADY EARNED ITS PLACE. The
# first draft of the fixture registered the same listener twice; the DOM drops a
# duplicate registration, so the "bug" never happened and the buggy arm passed.
# Without that arm the handoff would have shipped a regression test that cannot
# fail, green on every run.
#
# --negative-control runs the SAME demonstration with the buggy arm served the
# fixed app - the mutation the buggy arm exists to catch - and exits 0 only when
# the demonstration reports exactly that arm as a mismatch. It is what shows this
# script can report red (ADR 0008): a demo that printed `ok` regardless would
# pass the plain run and fail this one.
#
# Every arm must match or this exits 1. An arm whose runner could not start
# prints `error` and fails the demonstration - never skipped, never a pass.
# Exit 3 means a prerequisite (node/npm/python3/pyyaml) is missing here: the
# demonstration did NOT run, and that is reported, not rendered as green.
set -u

if [ "${1:-}" = "--negative-control" ]; then
    out="$(QA_DEMO_BUGGY_STATE=fixed bash "${BASH_SOURCE[0]}")"
    rc=$?
    printf '%s\n' "$out" | sed 's/^/[negative-control] /'
    if [ "$rc" -eq 1 ] \
        && printf '%s\n' "$out" | grep -q '^QA_REGRESSION_ARM: buggy MISMATCH (want reproduced, got passed' \
        && printf '%s\n' "$out" | grep -q '^QA_REGRESSION_DEMO: fail - 1 of 3 arms'; then
        echo "QA_REGRESSION_DEMO_CONTROL: ok - with the bug removed, the demonstration reported the buggy arm red"
        exit 0
    fi
    echo "QA_REGRESSION_DEMO_CONTROL: BLIND - the mutated run did not report the buggy arm as a mismatch (exit $rc)"
    exit 1
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE="$REPO/tests/fixtures/qa_regression/consumer"
HELPER="$REPO/scripts/qa-regression-export.py"
SPEC_REL="repro/cart-double-increment.json"

missing=0
for tool in node npm python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "QA_REGRESSION_DEMO_MISSING: $tool"
        missing=1
    fi
done
if command -v python3 >/dev/null 2>&1 && ! python3 -c 'import yaml' 2>/dev/null; then
    echo "QA_REGRESSION_DEMO_MISSING: python3 pyyaml"
    missing=1
fi
if [ "$missing" -ne 0 ]; then
    echo "QA_REGRESSION_DEMO: unavailable - prerequisites missing; the demonstration did not run"
    exit 3
fi

WORK="$(mktemp -d -t qa-regression-demo-XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
cp -R "$FIXTURE/." "$WORK/"
rm -rf "$WORK/node_modules" "$WORK/test-results" "$WORK/playwright-report" "$WORK/tests/e2e/regressions"

if ! (cd "$WORK" && npm ci --no-audit --no-fund >"$WORK/.npm-ci.log" 2>&1); then
    tail -20 "$WORK/.npm-ci.log"
    echo "QA_REGRESSION_DEMO: error - npm ci failed in the fixture consumer"
    exit 1
fi

export_out="$(python3 "$HELPER" export --root "$WORK" --spec "$WORK/$SPEC_REL")"
export_rc=$?
printf '%s\n' "$export_out"
if [ "$export_rc" -ne 0 ]; then
    echo "QA_REGRESSION_DEMO: error - export failed (exit $export_rc)"
    exit 1
fi
TEST_REL="$(printf '%s\n' "$export_out" | sed -n 's/^QA_REGRESSION_TEST: //p')"

free_port() {
    python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'
}

failures=0
arm() {
    local name="$1" want="$2"; shift 2
    local out rc got
    out="$(env "$@" FIXTURE_PORT="$(free_port)" python3 "$HELPER" run --root "$WORK" --test "$TEST_REL")"
    rc=$?
    got="$(printf '%s\n' "$out" | sed -n 's/^QA_REGRESSION_RESULT: \([a-z]*\).*/\1/p')"
    printf '%s\n' "$out" | sed "s/^/[$name] /"
    if [ "$got" = "$want" ]; then
        echo "QA_REGRESSION_ARM: $name ok (want $want, got $got, exit $rc)"
    else
        echo "QA_REGRESSION_ARM: $name MISMATCH (want $want, got ${got:-nothing}, exit $rc)"
        failures=$((failures + 1))
    fi
}

arm buggy reproduced FIXTURE_STATE="${QA_DEMO_BUGGY_STATE:-buggy}"
arm fixed passed FIXTURE_STATE=fixed
arm unavailable unavailable QA_FIXTURE_NO_SERVER=1

if [ "$failures" -ne 0 ]; then
    echo "QA_REGRESSION_DEMO: fail - $failures of 3 arms disagreed; the exported test does not discriminate as claimed"
    exit 1
fi
echo "QA_REGRESSION_DEMO: ok - 3 of 3 arms matched (fixture population: one local app, one bug; says nothing about other apps)"
exit 0
