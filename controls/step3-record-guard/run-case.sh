#!/bin/sh
# Runs one step3-record-guard case (issue #1083).
#
# THE FIXTURE IS BUILT, NEVER THE LIVE WORKTREE. This guard's subject is "does a
# flow worktree carry an approved-plan record", which is a fact about a RUN, and
# a control that read the ambient checkout would measure the repository it lives
# in instead of its subject. Six sibling controls fell into exactly that trap and
# #1203 dug them out; this one is built to not need digging out.
#
# So each case gets a REAL, THROWAWAY git repository outside every checkout, with
# a branch named issue-<N>-<slug> so the guard's own branch test is exercised
# rather than stubbed.
#
# UNAVAILABLE, NEVER CLEAN, if that context cannot be built.
set -u
case_dir="$1"
guard="$2"

command -v git >/dev/null 2>&1 || { echo "STEP3_GUARD_CONTROL: unavailable - git is not installed"; exit 2; }
command -v bash >/dev/null 2>&1 || { echo "STEP3_GUARD_CONTROL: unavailable - bash is not installed"; exit 2; }
[ -f "$case_dir/input.json" ] || { echo "STEP3_GUARD_CONTROL: unavailable - case has no input.json"; exit 2; }

work=$(mktemp -d "${TMPDIR:-/tmp}/step3-guard-control.XXXXXX") || {
    echo "STEP3_GUARD_CONTROL: unavailable - could not create the fixture directory"; exit 2; }
trap 'rm -rf "$work"' EXIT INT TERM

# The fixture must be outside every repository, or the guard would resolve the
# ENCLOSING checkout's branch and record and the case would measure that.
if (cd "$work" && git rev-parse --git-dir >/dev/null 2>&1); then
    echo "STEP3_GUARD_CONTROL: unavailable - TMPDIR is inside a git repository, so the"
    echo "  fixture is not isolated and this case would measure the enclosing checkout"
    exit 2
fi

( cd "$work" \
  && git init -q . \
  && git checkout -q -b issue-4242-a-fixture-branch \
  && mkdir -p docs/flow-runs scripts \
  && git -c user.email=fixture@example.invalid -c user.name=fixture \
        commit -q --allow-empty -m "fixture base" ) || {
    echo "STEP3_GUARD_CONTROL: unavailable - could not build the fixture repository"; exit 2; }

# A case supplies its record by PRESENCE. No record file, no record.
if [ -f "$case_dir/record.md" ]; then
    cp "$case_dir/record.md" "$work/docs/flow-runs/issue-4242.md" || {
        echo "STEP3_GUARD_CONTROL: unavailable - could not install the case record"; exit 2; }
fi

# {WORK} in input.json is substituted with the fixture root so a case can name an
# absolute target without knowing where mktemp put it.
sed "s|{WORK}|$work|g" "$case_dir/input.json" > "$work/.input.json" || {
    echo "STEP3_GUARD_CONTROL: unavailable - could not prepare the hook input"; exit 2; }

cd "$work" || { echo "STEP3_GUARD_CONTROL: unavailable - could not enter the fixture"; exit 2; }
bash "$guard" < "$work/.input.json"
