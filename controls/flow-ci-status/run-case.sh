#!/bin/sh
# Case runner for controls/flow-ci-status (issue #1411, ADR 0008 row 10).
#
# NO NETWORK, NO WOODPECKER SERVER. The gate's one outside dependency here is
# `curl` (the direct-API lane `tests/test_flow_ci_status.py` already exercises
# this way); this runner puts a stub curl first on PATH and answers the
# gate's three calls - the repo lookup, the pipeline list, and the one
# pipeline's workflow detail - from fixed JSON plus the ONE thing this
# control varies: the failed step's `exit_code`, read from the case's own
# `exit_code` file.
#
# The gate's own exit code does not vary with its FAILURE_ORIGIN verdict (it
# is 0 unless `--exit-code` is passed, and then it is 1 for ANY failure,
# precode or not) - so this runner does not pass the gate's exit through. It
# reads `FLOW_CI_FAILURE_ORIGIN` from the gate's stdout and recomputes a
# verdict-shaped exit itself: 0 when the origin is `code` (the GOOD case's
# own correct answer, and the bad case's WRONG one on a blind anchor), 1 when
# it is `precode` (the bad case's correct answer, on the fixed gate).
set -u
case_dir="$1"
gate="$2"
case "$gate" in /*) ;; *) gate="$PWD/$gate" ;; esac
case "$case_dir" in /*) ;; *) case_dir="$PWD/$case_dir" ;; esac

command -v bash >/dev/null 2>&1 || { echo "FLOW_CI_CONTROL: unavailable - bash is not installed"; exit 3; }
command -v jq >/dev/null 2>&1 || { echo "FLOW_CI_CONTROL: unavailable - jq is not installed"; exit 3; }

if [ ! -f "$case_dir/exit_code" ]; then
    echo "FLOW_CI_CONTROL: cannot-run - case supplies no exit_code file"
    exit 3
fi
exit_code=$(cat "$case_dir/exit_code")
case "$exit_code" in
    ''|*[!0-9]*)
        echo "FLOW_CI_CONTROL: cannot-run - exit_code file is not a plain integer: '$exit_code'"
        exit 3
        ;;
esac

T=$(mktemp -d "${TMPDIR:-/tmp}/flow-ci-status-control.XXXXXX") || { echo "FLOW_CI_CONTROL: cannot-run - no tmpdir"; exit 3; }
trap 'rm -rf "$T"' EXIT INT TERM
mkdir "$T/bin"

SHA="2b308175a757e0b17c30caead6aabbe9356b43cc"

cat > "$T/bin/curl" <<STUB
#!/bin/sh
# POSIX-safe "last argument": \${@: -1} is a bash-only slice and is a
# silent "Bad substitution" under dash, which /bin/sh is here (measured) -
# every call would fail with no output, and wp_api's "2>/dev/null" would
# swallow that into an empty REPO_ID, reading as "no provider answered".
for url in "\$@"; do :; done
case "\$url" in
    *"/api/repos/lookup/"*)
        cat <<'JSON'
{"id": 17}
JSON
        ;;
    *"pipelines?per_page"*)
        cat <<JSON
[{"number": 1275, "commit": "$SHA", "status": "failure", "event": "push"}]
JSON
        ;;
    *"pipelines/1275"*)
        cat <<JSON
{"workflows": [{"name": "woodpecker", "children": [
    {"name": "clone", "type": "clone", "state": "success", "exit_code": 0},
    {"name": "jq-stage", "type": "commands", "state": "failure", "exit_code": $exit_code}
]}]}
JSON
        ;;
    *)
        echo '{}'
        ;;
esac
exit 0
STUB
chmod +x "$T/bin/curl"

resolved=$(PATH="$T/bin:$PATH" command -v curl)
if [ "$resolved" != "$T/bin/curl" ]; then
    echo "FLOW_CI_CONTROL: cannot-run - curl resolves to '$resolved', not the stub; refusing a real network call"
    exit 3
fi

out=$(env PATH="$T/bin:$PATH" \
          FLOW_CI_CURL="$T/bin/curl" \
          FLOW_CI_AWS=/nonexistent/aws FLOW_CI_WPCLI=/nonexistent/woodpecker-cli \
          FLOW_CI_GH=/nonexistent/gh FLOW_CI_SLEEP=/bin/true \
          WOODPECKER_SERVER="https://wp.example.invalid" \
          WOODPECKER_API_TOKEN="control-token-canary" \
          bash "$gate" "$SHA" --repo o/r 2>&1)

origin=$(printf '%s\n' "$out" | sed -n 's/^FLOW_CI_FAILURE_ORIGIN: //p' | head -1)
origins=$(printf '%s\n' "$out" | grep -c '^FLOW_CI_FAILURE_ORIGIN: ' || true)
status=$(printf '%s\n' "$out" | sed -n 's/^FLOW_CI_STATUS: //p' | head -1)

if [ "$status" != "failure" ] || [ "$origins" -ne 1 ]; then
    echo "FLOW_CI_CONTROL: cannot-run - the gate did not report exactly one failure verdict:"
    printf '%s\n' "$out" | sed 's/^/  /'
    exit 3
fi

case "$origin" in
    precode) echo "FLOW_CI_CONTROL: precode"; exit 1 ;;
    code)    echo "FLOW_CI_CONTROL: code"; exit 0 ;;
    *)
        echo "FLOW_CI_CONTROL: cannot-run - unexpected FLOW_CI_FAILURE_ORIGIN '$origin'"
        exit 3
        ;;
esac
