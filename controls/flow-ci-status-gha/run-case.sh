#!/bin/sh
# Offline GitHub Actions aggregation control (issue #1604). A stub `gh`,
# handed to the gate through FLOW_CI_GH, answers `run list` from the case's
# runs.json, fails every `run view` (step naming is not under test here), and
# - when the case carries a `contexts` file - answers the branch-protection
# reads with it. Every case asks one question: does a red run on the commit
# surface as FLOW_CI_STATUS: failure under --strict-event?
set -u
case_dir="$1"
gate="$2"
case "$gate" in /*) ;; *) gate="$PWD/$gate" ;; esac
case "$case_dir" in /*) ;; *) case_dir="$PWD/$case_dir" ;; esac

command -v bash >/dev/null 2>&1 || { echo "FLOW_CI_GHA_CONTROL: unavailable - bash is not installed"; exit 3; }
command -v jq >/dev/null 2>&1 || { echo "FLOW_CI_GHA_CONTROL: unavailable - jq is not installed"; exit 3; }

if ! jq -e 'type == "array" and length > 0' "$case_dir/runs.json" >/dev/null 2>&1; then
    echo "FLOW_CI_GHA_CONTROL: cannot-run - invalid runs fixture"
    exit 3
fi

T=$(mktemp -d "${TMPDIR:-/tmp}/flow-ci-status-gha-control.XXXXXX") || { echo "FLOW_CI_GHA_CONTROL: cannot-run - no tmpdir"; exit 3; }
trap 'rm -rf "$T"' EXIT INT TERM

cat > "$T/gh" <<STUB
#!/bin/sh
if [ "\$1 \$2" = "run list" ]; then cat "$case_dir/runs.json"; exit 0; fi
if [ "\$1" = "api" ] && [ -f "$case_dir/contexts" ]; then
    case "\$2" in
        *required_status_checks) cat "$case_dir/contexts"; exit 0 ;;
        repos/*/*/*) exit 1 ;;
        repos/*) echo main; exit 0 ;;
    esac
fi
exit 1
STUB
chmod +x "$T/gh"

out=$(env FLOW_CI_GH="$T/gh" \
          FLOW_CI_CURL=/nonexistent/curl FLOW_CI_AWS=/nonexistent/aws \
          FLOW_CI_WPCLI=/nonexistent/woodpecker-cli FLOW_CI_SLEEP=/bin/true \
          WOODPECKER_API_TOKEN="" WOODPECKER_SERVER="" WOODPECKER_HOST="" \
          bash "$gate" 2b308175a757e0b17c30caead6aabbe9356b43cc --repo o/r --strict-event 2>&1)

provider=$(printf '%s\n' "$out" | sed -n 's/^FLOW_CI_PROVIDER: //p' | head -1)
status=$(printf '%s\n' "$out" | sed -n 's/^FLOW_CI_STATUS: //p' | head -1)
if [ "$provider" != "github-actions" ]; then
    echo "FLOW_CI_GHA_CONTROL: cannot-run - the gate did not answer on the GitHub Actions lane:"
    printf '%s\n' "$out" | sed 's/^/  /'
    exit 3
fi

case "$status" in
    failure) echo "FLOW_CI_GHA_CONTROL: red surfaced"; exit 1 ;;
    # `not-found` is a MISS, not a refusal: under --strict-event it is what the
    # pre-#1604 gate said for a pull_request-only commit, and it made
    # /flow:merge wait out its window instead of seeing the red.
    success|not-found) echo "FLOW_CI_GHA_CONTROL: no red ($status)"; exit 0 ;;
    *)
        echo "FLOW_CI_GHA_CONTROL: cannot-run - unexpected FLOW_CI_STATUS '$status'"
        exit 3
        ;;
esac
