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

case "$(basename "$case_dir")" in
  unresolved-attribution-reads-unknown)
    [ "$(grep -c '^=== short test summary info ===$' "$case_dir/log.txt")" -eq 2 ] || exit 3
    grep -q '^FAILED .*::' "$case_dir/log.txt" || exit 3 ;;
  scoped-scrape-does-not-borrow-another-steps-failure)
    ! grep -q 'short test summary info' "$case_dir/log-36.txt" || exit 3
    grep -q '^FAILED .*::' "$case_dir/log-39.txt" || exit 3 ;;
  cancelled-single-step)
    [ "$(wc -l < "$case_dir/ps.txt")" -eq 1 ] || exit 3
    grep -q '|36|Canceled$' "$case_dir/ps.txt" || exit 3 ;;
esac

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
printf 'validate|failure|2026-09-21T19:29:21Z|36|\n' > "$T/ps"

[ ! -f "$case_dir/ps.txt" ] || cp "$case_dir/ps.txt" "$T/ps"
[ ! -f "$case_dir/ls.txt" ] || cp "$case_dir/ls.txt" "$T/ls"
cp "$case_dir"/log-*.txt "$T/" 2>/dev/null || :

cat > "$T/gh" <<GH
#!/usr/bin/env bash
for arg in "\$@"; do
  case "\$arg" in
    nameWithOwner) echo "o/r"; exit 0 ;;
    headRefOid)
      if [ -f "$case_dir/superseded.txt" ] && [ -f "$T/head-read" ]; then
        cat "$case_dir/superseded.txt"
      else
        cat "$T/heads"
        touch "$T/head-read"
      fi
      exit 0 ;;
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
  log)
    if [ -f "$T/log-\${6:-}.txt" ]; then
      cat "$T/log-\${6}.txt"
    else
      cat "$T/log"
    fi
    exit 0 ;;
esac
exit 1
WP
chmod +x "$T/gh" "$T/wpcli"

if [ "$(basename "$case_dir")" = signal-exit-reports-real-status ]; then
    # Signal after the watcher installs its traps, while its CLI stub blocks.
    printf '#!/bin/sh\n: > "%s/ready"\nsleep 1\n' "$T" > "$T/gh"
    chmod +x "$T/gh"
    env FLOW_PR_WATCH_GH="$T/gh" bash "$gate" 42 --repo o/r >"$T/out" 2>"$T/err" &
    watcher=$!
    while [ ! -f "$T/ready" ]; do sleep 0.01; done
    kill -TERM "$watcher"
    wait "$watcher"
    status=$?
    cat "$T/err"
    if [ "$status" -eq 143 ] && [ "$(grep -c '^FLOW_PR_WATCH_EXIT=' "$T/err")" -eq 1 ] && grep -qx 'FLOW_PR_WATCH_EXIT=143' "$T/err"; then
        echo 'FLOW_PR_WATCH_CONTROL: finding - signal status reported exactly once'
        exit 1
    fi
    echo 'FLOW_PR_WATCH_CONTROL: missed - signal status contract absent'
    exit 0
fi

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

case "$(basename "$case_dir")" in
  unresolved-attribution-reads-unknown|scoped-scrape-does-not-borrow-another-steps-failure) expected=unknown ;;
  cancelled-single-step) expected=cancelled ;;
  single-summary-real-failure|ordinary-step-failure) expected=red ;;
  *) expected="" ;;
esac
if [ -n "$expected" ]; then
    printf '%s\n' "$out"
    matched=1
    printf '%s\n' "$out" | grep -qx "FLOW_PR_WATCH: $expected" || matched=0
    if [ "$(basename "$case_dir")" = scoped-scrape-does-not-borrow-another-steps-failure ]; then
        printf '%s\n' "$out" | grep -qx 'FLOW_PR_WATCH_FAILED=-' || matched=0
        printf '%s\n' "$out" | grep -qx 'FLOW_PR_WATCH_SCRAPE_SCOPE=whole-log' || matched=0
    fi
    if [ "$matched" -eq 1 ]; then
        case "$expected" in
          red) echo 'FLOW_PR_WATCH_CONTROL: ok - real failure retained'; exit 0 ;;
          *) echo 'FLOW_PR_WATCH_CONTROL: finding - verdict defect detected'; exit 1 ;;
        esac
    fi
    if [ "$expected" = red ]; then
        echo 'FLOW_PR_WATCH_CONTROL: finding - real failure lost'
        exit 1
    fi
    echo 'FLOW_PR_WATCH_CONTROL: missed - verdict contract absent' 
    exit 0
fi

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
echo 'FLOW_PR_WATCH_CONTROL: ok - bounded scrape'
exit 0
