#!/bin/sh
# Offline cancellation verdict control; curl stub mirrors flow-ci-status.
set -u
case_dir="$1"
gate="$2"
case "$gate" in /*) ;; *) gate="$PWD/$gate" ;; esac
case "$case_dir" in /*) ;; *) case_dir="$PWD/$case_dir" ;; esac

command -v bash >/dev/null 2>&1 || { echo "FLOW_CI_CANCELLATION_CONTROL: unavailable - bash is not installed"; exit 3; }
command -v jq >/dev/null 2>&1 || { echo "FLOW_CI_CANCELLATION_CONTROL: unavailable - jq is not installed"; exit 3; }

if ! step_json=$(jq -ce 'select(.name == "validate" and .type == "commands" and .state == "failure" and .exit_code == 126)' "$case_dir/step.json"); then
    echo "FLOW_CI_CANCELLATION_CONTROL: cannot-run - invalid failure fixture"
    exit 3
fi

T=$(mktemp -d "${TMPDIR:-/tmp}/flow-ci-status-control.XXXXXX") || { echo "FLOW_CI_CANCELLATION_CONTROL: cannot-run - no tmpdir"; exit 3; }
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
    $step_json
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
    echo "FLOW_CI_CANCELLATION_CONTROL: cannot-run - curl resolves to '$resolved', not the stub; refusing a real network call"
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
    echo "FLOW_CI_CANCELLATION_CONTROL: cannot-run - the gate did not report exactly one failure verdict:"
    printf '%s\n' "$out" | sed 's/^/  /'
    exit 3
fi

case "$origin" in
    canceled) echo "FLOW_CI_CANCELLATION_CONTROL: canceled"; exit 1 ;;
    code)    echo "FLOW_CI_CANCELLATION_CONTROL: code"; exit 0 ;;
    *)
        echo "FLOW_CI_CANCELLATION_CONTROL: cannot-run - unexpected FLOW_CI_FAILURE_ORIGIN '$origin'"
        exit 3
        ;;
esac
