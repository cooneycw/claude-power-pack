#!/bin/sh
# Case runner for controls/flow-wave-lexicon (#1189).
#
# WHY AN ADAPTER. The lexicon's `validate` exits 1 for EVERY refusal and for
# nothing else meaningful, but exit 1 is also what a shell gives for a script it
# could not run to completion. The harness needs a detection it can tell from a
# crash (#946), so this reads the gate's OWN verdict line and translates it.
#
# IT DECIDES NOTHING. Each case directory holds one body.md - the message an
# orchestrator would send - and nothing else: no expected verdict, no error text.
# The discriminator is the lexicon's own `FLOW_LEXICON:` line, which is why a
# blind lexicon produces a different answer from the same bytes.
set -u
case_dir="$1"
gate="$2"

# ESTABLISH THE FIXTURE BEFORE BLAMING THE GATE. A missing body would be read
# from an empty stdin as "no reserved token" - `none`, exit 0 - which is a GOOD
# verdict about a message nobody supplied.
if [ ! -s "$case_dir/body.md" ]; then
    echo "FLOW_WAVE_LEXICON_CONTROL: unavailable - body.md is missing or empty" >&2
    exit 3
fi

# `unavailable` means COULD NOT LOOK, and `make negative-controls` runs with
# --allow-unavailable, so it is excused locally. Reserve it for what is verified
# to be absent - the fixture above, the gate file, bash - never for a gate that
# RAN and misbehaved (counter-model review, #1189).
if [ ! -r "$gate" ] || ! command -v bash >/dev/null 2>&1; then
    echo "FLOW_WAVE_LEXICON_CONTROL: unavailable - the gate '$gate' or bash is not present" >&2
    exit 3
fi

out=$(bash "$gate" validate --body-file "$case_dir/body.md" 2>&1)
status=$?
verdict=$(printf '%s\n' "$out" | sed -n 's/^FLOW_LEXICON: //p' | tail -1)

# Only the gate's own verdict line decides. `ok` with exit 0 is a message it
# accepted; `invalid` with exit 1 is a refusal. Anything else - no verdict line,
# `error`, or a verdict that disagrees with its exit - is a gate that RAN and did
# not answer. That scores neither clean nor finding, and NOT unavailable either:
# it exits non-zero carrying neither declared signal, which the harness scores
# UNSIGNALLED and fails even under --allow-unavailable. A lexicon that crashes on
# every input must not be excusable as a missing tool.
case "$status:$verdict" in
  0:ok) exit 0 ;;
  1:invalid)
     printf '%s\n' "$out"
     echo "FLOW_WAVE_LEXICON_CONTROL: finding - the lexicon refused the message"
     exit 1 ;;
  *) echo "flow-wave-lexicon control: the lexicon RAN and gave no answer - exit $status, verdict '${verdict:-<none>}'" >&2
     printf '%s\n' "$out" >&2
     exit 2 ;;
esac
