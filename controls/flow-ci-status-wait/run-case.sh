#!/bin/sh
# Offline --wait control (issue #1684); curl stub mirrors flow-ci-status.
# The stub's pipeline LISTING answers the case's `first_status` on the first
# call and `success` on every later one. A gate that polls a found pipeline
# whose status it cannot read makes a second call and ends green; a gate that
# ends its wait on the first look makes one. FLOW_CI_SLEEP=/bin/true makes the
# poll interval instant, so neither gate waits on a clock.
set -u
case_dir="$1"
gate="$2"
case "$gate" in /*) ;; *) gate="$PWD/$gate" ;; esac
case "$case_dir" in /*) ;; *) case_dir="$PWD/$case_dir" ;; esac

command -v bash >/dev/null 2>&1 || { echo "FLOW_CI_WAIT_CONTROL: unavailable - bash is not installed"; exit 3; }
command -v jq >/dev/null 2>&1 || { echo "FLOW_CI_WAIT_CONTROL: unavailable - jq is not installed"; exit 3; }

if ! first=$(jq -er '.first_status | select(type == "string" and test("^[a-z]*$"))' "$case_dir/case.json"); then
    echo "FLOW_CI_WAIT_CONTROL: cannot-run - invalid case fixture"
    exit 3
fi

T=$(mktemp -d "${TMPDIR:-/tmp}/flow-ci-wait-control.XXXXXX") || { echo "FLOW_CI_WAIT_CONTROL: cannot-run - no tmpdir"; exit 3; }
trap 'rm -rf "$T"' EXIT INT TERM
mkdir "$T/bin"

SHA="880b77a92d93a9813ce24710be9679a0263954d2"

cat > "$T/bin/curl" <<STUB
#!/bin/sh
# Read the header the gate pipes in. A stub that exits without reading it can
# close the pipe before the writer runs; under pipefail that fails the whole
# call and the gate reports it could not look (issue #1718).
cat >/dev/null 2>&1 || true
# POSIX "last argument" - \${@: -1} is bash-only and fails under dash.
for url in "\$@"; do :; done
case "\$url" in
    *"/api/repos/lookup/"*)
        echo '{"id": 1, "timeout": 60}'
        ;;
    *"pipelines?per_page"*)
        n=0
        [ -f "$T/calls" ] && n=\$(cat "$T/calls")
        echo \$((n + 1)) > "$T/calls"
        if [ "\$n" -eq 0 ]; then state="$first"; else state="success"; fi
        echo '[{"number": 4726, "commit": "$SHA", "status": "'"\$state"'", "event": "push"}]'
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
    echo "FLOW_CI_WAIT_CONTROL: cannot-run - curl resolves to '$resolved', not the stub; refusing a real network call"
    exit 3
fi

out=$(env CPP_FLOW_CI_WORKER=1 CPP_FLOW_CI_BACKEND=probe PATH="$T/bin:$PATH" \
          FLOW_CI_CURL="$T/bin/curl" \
          FLOW_CI_AWS=/nonexistent/aws FLOW_CI_WPCLI=/nonexistent/woodpecker-cli \
          FLOW_CI_GH=/nonexistent/gh FLOW_CI_SLEEP=/bin/true \
          WOODPECKER_SERVER="https://wp.example.invalid" \
          WOODPECKER_API_TOKEN="control-token-canary" \
          bash "$gate" "$SHA" --repo o/r --event push --wait 30 2>&1)

statuses=$(printf '%s\n' "$out" | grep -c '^FLOW_CI_STATUS: ' || true)
status=$(printf '%s\n' "$out" | sed -n 's/^FLOW_CI_STATUS: //p' | head -1)
pipeline=$(printf '%s\n' "$out" | sed -n 's/^FLOW_CI_PIPELINE: //p' | head -1)
calls=0
[ -f "$T/calls" ] && calls=$(cat "$T/calls")
if [ "$statuses" -ne 1 ] || [ "$pipeline" != "4726" ] || [ "$calls" -lt 1 ]; then
    echo "FLOW_CI_WAIT_CONTROL: cannot-run - the gate did not report exactly one verdict for pipeline 4726 from the stub:"
    printf '%s\n' "$out" | sed 's/^/  /'
    exit 3
fi

if [ "$calls" -eq 1 ]; then
    # The wait ended on the first look, whatever that look said.
    echo "FLOW_CI_WAIT_CONTROL: first-look (status $status)"
    exit 0
fi
if [ "$status" = "success" ]; then
    echo "FLOW_CI_WAIT_CONTROL: polled"
    exit 1
fi
echo "FLOW_CI_WAIT_CONTROL: cannot-run - $calls listing calls ended on unexpected FLOW_CI_STATUS '$status'"
exit 3
