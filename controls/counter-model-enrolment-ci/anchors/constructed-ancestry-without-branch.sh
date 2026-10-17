#!/usr/bin/env bash
# CONSTRUCTED ANCHOR for controls/counter-model-enrolment-ci (issue #1452).
#
# THE PLAUSIBLE WEAKER CI STEP: the finish gate's enrolment evaluation run on a
# detached CI checkout WITHOUT naming the PR's branch. There, git has no branch
# to compare, so ancestry alone decides: ANY receipt whose head is reachable from
# HEAD satisfies it - a receipt recorded for a different branch included. That is
# what this step would do if it dropped `--branch "$CI_COMMIT_SOURCE_BRANCH"`.
#
# It keeps the gate's refusal on shallow history (exit 5, undecidable), so it
# AGREES with the gate on the UNKNOWN case and differs only in the blindness
# under test: it reports ok on both BAD cases.
dir=docs/measurements/counter-model
[ -d "$dir" ] || { echo "FLOW_FINISH_GATE: ok"; exit 0; }
for f in "$dir"/*.json; do
    [ -e "$f" ] || continue
    head=$(sed -n 's/^[[:space:]]*"head"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$f" | head -1)
    if git merge-base --is-ancestor "$head" HEAD >/dev/null 2>&1; then
        echo "FLOW_FINISH_GATE: ok"; exit 0
    fi
done
if [ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = true ]; then
    echo "FLOW_FINISH_GATE: undecidable (counter-model line undecidable)"; exit 5
fi
echo "FLOW_FINISH_GATE: fail (counter-model line missing)"; exit 1
