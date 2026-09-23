#!/bin/sh
# Case runner for controls/flow-pr-watch (#1190).
#
# It builds the two binaries the gate shells out to - `gh` and `woodpecker-cli` -
# from the case's own files and runs the REAL scripts/flow-pr-watch.sh against
# them. Only the pipeline's step LOG and the flake BASELINE vary between cases;
# the pipeline identity, head sha and step rows are fixed here, so the log is
# the single variable under test.
#
# THE CASES NAME NO ANSWER, which is what keeps them able to fail. Neither case
# contains a verdict, a test id the runner looks for, or an expected count. The
# discriminator is the GATE'S OWN verdict: with a baseline that covers the one
# failure pytest actually summarised, a scrape bounded to the summary region
# reports `flake` and a scrape that walked the whole log reports `red`, because
# it also harvested the three `FAILED` lines a negative control echoed on
# purpose. Same input, opposite verdicts, decided entirely by the gate.
set -u
case_dir="$1"
gate="$2"

T=$(mktemp -d) || { echo "FLOW_PR_WATCH_CONTROL: unavailable - no tmpdir" >&2; exit 3; }
trap 'rm -rf "$T"' EXIT

HEAD_SHA=aa11bb22cc33dd44ee55ff66aa77bb88cc99dd00
PR_CTX=ci/woodpecker/pr/woodpecker
PIPE=2512
URL="https://wp.example/repos/7/pipeline/$PIPE"

cp "$case_dir/log.txt" "$T/log" || exit 3
cp "$case_dir/baseline.txt" "$T/baseline" || exit 3
printf '%s\n' "$HEAD_SHA" > "$T/heads"
printf '%s|%s|FAILURE\n' "$PR_CTX" "$URL" > "$T/rollup"
printf '%s|failure|%s|pull_request\n' "$PIPE" "$HEAD_SHA" > "$T/ls"
printf 'validate|failure|2026-09-21T19:29:21Z\n' > "$T/ps"

cat > "$T/gh" <<GH
#!/usr/bin/env bash
for arg in "\$@"; do
  case "\$arg" in
    nameWithOwner) echo "o/r"; exit 0 ;;
    headRefOid)    cat "$T/heads"; exit 0 ;;
    statusCheckRollup)
      with_context=0
      for f in "\$@"; do case "\$f" in *'.context // .name'*) with_context=1 ;; esac; done
      if [ "\$with_context" -eq 1 ]; then
        cat "$T/rollup"
      else
        while IFS='|' read -r c u s; do printf '%s|%s\n' "\$u" "\$s"; done < "$T/rollup"
      fi
      exit 0 ;;
  esac
done
exit 1
GH

cat > "$T/wpcli" <<WP
#!/usr/bin/env bash
case "\${2:-}" in
  ls)
    with_event=0
    for f in "\$@"; do case "\$f" in *'.Event'*) with_event=1 ;; esac; done
    if [ "\$with_event" -eq 1 ]; then
      cat "$T/ls"
    else
      while IFS='|' read -r n s c e; do printf '%s|%s|%s\n' "\$n" "\$s" "\$c"; done < "$T/ls"
    fi
    exit 0 ;;
  ps)  cat "$T/ps";  exit 0 ;;
  log) cat "$T/log"; exit 0 ;;
esac
exit 1
WP
chmod +x "$T/gh" "$T/wpcli"

out=$(env FLOW_PR_WATCH_GH="$T/gh" \
          FLOW_PR_WATCH_WPCLI="$T/wpcli" \
          FLOW_PR_WATCH_SLEEP=/bin/true \
          bash "$gate" 42 --repo o/r --baseline "$T/baseline" 2>&1)
status=$?

# A gate that fell over is NOT a detection (#946). green/flake/cancelled are 0
# and red is 1; anything else (usage 2, timeout 5) means it never answered.
case "$status" in
  0|1) : ;;
  *) echo "FLOW_PR_WATCH_CONTROL: unavailable - the watcher exited $status" >&2
     printf '%s\n' "$out" >&2; exit 3 ;;
esac

# THE FINDING IS THE WATCHER'S OWN CAVEAT, not its red/green verdict.
#
# The subject here is whether the watcher declares the REGION its failure set
# came from. A killed run printed no pytest summary, so no scrape can be bounded
# to one; the set may include lines a negative control echoed on purpose, and
# presenting it as authoritative is the defect - unbounded rendering as clean.
#
# Keying on the caveat rather than on red/green is deliberate. The pre-fix
# watcher reports `red` MORE often than the fixed one, never less, so no
# red-keyed case could ever show it missing something. What it cannot do, at
# all, is say that its own scrape was unbounded - and a control has to be able
# to catch the gate REGRESSING to that silence.
if printf '%s\n' "$out" | grep -q '^FLOW_PR_WATCH_SCRAPE_SCOPE=whole-log$'; then
    printf '%s\n' "$out"
    echo "FLOW_PR_WATCH_CONTROL: finding - the failure set is UNBOUNDED and says so"
    exit 1
fi
printf '%s\n' "$out"
exit 0
