#!/bin/sh
# Runs one flow-helpers-install.sh integrity case (issue #1185).
#
# The control runner substitutes {gate} and {case} into an argv and runs it with
# no environment control, but this gate is steered entirely by two env vars -
# FLOW_HELPERS_HOME (where it installs) and FLOW_HELPERS_SOURCE (what it installs
# from). This wrapper supplies both and nothing else.
#
# IT PASSES THE GATE'S OWN OUTPUT AND EXIT CODE THROUGH UNCHANGED. A wrapper that
# re-derived a verdict would be the thing under test, and the control would be
# measuring the wrapper.
#
# THE GATE IS RUN THROUGH ITS OWN SHEBANG, never `sh "$gate"`. It is a bash
# program - `set -o pipefail`, arrays, `declare -A`, `[[ ]]` - and dash is /bin/sh
# on Debian and Ubuntu, where forcing it dies at line 50 with "Illegal option -o
# pipefail" BEFORE the gate can emit any verdict. That failure is indistinguishable
# from a crash by design, which is correct: the control must not be able to score
# a case the gate never got to judge.
set -u
gate="$1"
case_dir="$2"

# An absent interpreter is UNAVAILABLE - unexamined - and must never read as a
# clean case. The gate cannot speak, so the control says so in its own words
# rather than letting a 127 be scored as a refusal.
if ! command -v bash >/dev/null 2>&1; then
    echo "FLOW_HELPERS_CONTROL: unavailable - bash is not installed"
    exit 2
fi
if [ ! -x "$gate" ]; then
    echo "FLOW_HELPERS_CONTROL: unavailable - $gate is not executable"
    exit 2
fi

home="$(mktemp -d "${TMPDIR:-/tmp}/flow-helpers-control.XXXXXX")" || exit 2
trap 'rm -rf "$home"' EXIT INT TERM

# The install target is a throwaway directory, never the developer's real
# ~/.claude/scripts. That is not hygiene: a control that installed into the live
# host would make its verdict depend on host state, which is exactly the
# contamination this battery exists to detect.
# A case may ship a bin/ directory to seam the environment - the same device
# controls/flow-finish-gate uses. It is how the DIGEST-TOOL-UNAVAILABLE state
# becomes a committed case rather than only a unit test, and that state is the
# whole point of this change: "the bytes disagree" and "I could not ask" are
# different facts and must never collapse into one word.
case_path="$case_dir"
if [ -d "$case_path/bin" ]; then
    PATH="$case_path/bin:$PATH"
    export PATH
fi
FLOW_HELPERS_HOME="$home" \
FLOW_HELPERS_SOURCE="$case_dir/bundle/scripts" \
    "$gate"
status=$?

# Report whether anything was installed, so a BAD case that refuses LOUDLY but
# installs anyway is still visible. A refusal that installs is a warning.
count=0
if [ -d "$home/.claude/scripts" ]; then
    count=$(find "$home/.claude/scripts" -maxdepth 1 \( -type f -o -type l \) | wc -l | tr -d ' ')
fi
echo "FLOW_HELPERS_CONTROL_INSTALLED: $count"
exit "$status"
