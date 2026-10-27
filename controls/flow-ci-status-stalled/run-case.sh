#!/bin/sh
# Offline stalled-verdict control (issue #1552); curl stub mirrors flow-ci-status.
# The pipeline shape is CPP pipeline 3374 as the server listed it before any
# cancel: status running, workflow running, two steps running, repo timeout 60.
# Only the elapsed time differs between cases. No --wait: the pre-#1552 anchor
# would otherwise poll its whole window.
set -u
case_dir="$1"
gate="$2"
case "$gate" in /*) ;; *) gate="$PWD/$gate" ;; esac
case "$case_dir" in /*) ;; *) case_dir="$PWD/$case_dir" ;; esac

command -v bash >/dev/null 2>&1 || { echo "FLOW_CI_STALLED_CONTROL: unavailable - bash is not installed"; exit 3; }
command -v jq >/dev/null 2>&1 || { echo "FLOW_CI_STALLED_CONTROL: unavailable - jq is not installed"; exit 3; }

if ! elapsed=$(jq -er '.elapsed_min | select(type == "number" and . >= 0)' "$case_dir/case.json"); then
    echo "FLOW_CI_STALLED_CONTROL: cannot-run - invalid case fixture"
    exit 3
fi

T=$(mktemp -d "${TMPDIR:-/tmp}/flow-ci-stalled-control.XXXXXX") || { echo "FLOW_CI_STALLED_CONTROL: cannot-run - no tmpdir"; exit 3; }
trap 'rm -rf "$T"' EXIT INT TERM
mkdir "$T/bin"

SHA="880b77a92d93a9813ce24710be9679a0263954d2"
STARTED=1792971725
NOW=$((STARTED + elapsed * 60))

cat > "$T/bin/curl" <<STUB
#!/bin/sh
# POSIX "last argument" - \${@: -1} is bash-only and fails under dash.
for url in "\$@"; do :; done
case "\$url" in
    *"/api/repos/lookup/"*)
        echo '{"id": 1, "timeout": 60}'
        ;;
    *"pipelines?per_page"*)
        echo '[{"number": 3374, "commit": "$SHA", "status": "running", "event": "push"}]'
        ;;
    *"pipelines/3374"*)
        cat <<'JSON'
{"number": 3374, "status": "running", "started": $STARTED, "workflows": [{"name": "woodpecker", "state": "running", "started": $STARTED, "children": [
    {"name": "shellcheck", "state": "success"},
    {"name": "validate", "state": "running"},
    {"name": "negative-controls", "state": "running"},
    {"name": "mutation-probe", "state": "pending"}
]}]}
JSON
        ;;
    *)
        echo '{}'
        ;;
esac
exit 0
STUB
# The quoted JSON heredoc above cannot expand STARTED; substitute it.
sed -i "s/\"started\": \\\$STARTED/\"started\": $STARTED/g" "$T/bin/curl"
chmod +x "$T/bin/curl"

resolved=$(PATH="$T/bin:$PATH" command -v curl)
if [ "$resolved" != "$T/bin/curl" ]; then
    echo "FLOW_CI_STALLED_CONTROL: cannot-run - curl resolves to '$resolved', not the stub; refusing a real network call"
    exit 3
fi

out=$(env PATH="$T/bin:$PATH" \
          FLOW_CI_CURL="$T/bin/curl" FLOW_CI_NOW="$NOW" \
          FLOW_CI_AWS=/nonexistent/aws FLOW_CI_WPCLI=/nonexistent/woodpecker-cli \
          FLOW_CI_GH=/nonexistent/gh FLOW_CI_SLEEP=/bin/true \
          WOODPECKER_SERVER="https://wp.example.invalid" \
          WOODPECKER_API_TOKEN="control-token-canary" \
          bash "$gate" "$SHA" --repo o/r --event push 2>&1)

statuses=$(printf '%s\n' "$out" | grep -c '^FLOW_CI_STATUS: ' || true)
status=$(printf '%s\n' "$out" | sed -n 's/^FLOW_CI_STATUS: //p' | head -1)
pipeline=$(printf '%s\n' "$out" | sed -n 's/^FLOW_CI_PIPELINE: //p' | head -1)
if [ "$statuses" -ne 1 ] || [ "$pipeline" != "3374" ]; then
    echo "FLOW_CI_STALLED_CONTROL: cannot-run - the gate did not report exactly one verdict for pipeline 3374:"
    printf '%s\n' "$out" | sed 's/^/  /'
    exit 3
fi

case "$status" in
    stalled) echo "FLOW_CI_STALLED_CONTROL: stalled"; exit 1 ;;
    running) echo "FLOW_CI_STALLED_CONTROL: running"; exit 0 ;;
    *)
        echo "FLOW_CI_STALLED_CONTROL: cannot-run - unexpected FLOW_CI_STATUS '$status'"
        exit 3
        ;;
esac
