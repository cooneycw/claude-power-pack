#!/bin/sh
# Case runner for controls/lane-serveability-check (issue #1281, ADR 0008 row 14).
#
# NO MODEL HOST, AND NO NETWORK. The gate's one outside dependency is `curl`, and
# it finds it on PATH. This runner puts stub-curl.py first on PATH as `curl`, so
# the gate's real request is answered from the case's files. The stub models
# WHAT CAME BACK - a status and a body, or curl's own exit code for a transport
# failure - and nothing about the socket, so what this control proves is the
# gate's CLASSIFICATION of responses, which is the part #895 got wrong.
#
# REFUSES A REAL curl. If `curl` on the constructed PATH resolves anywhere but
# the stub directory, a case would silently become a network probe of
# 127.0.0.1 - so the runner checks the resolution and refuses instead.
#
# /api/version and /api/tags are answered IDENTICALLY in every case (the daemon
# is up and the model is in the catalogue). That is deliberate: those two
# answers are what the pre-#895 gate - this control's anchor - trusted, so
# holding them fixed makes /api/generate the only variable.
#
# Markers:
#   unavailable - python3 is not installed    the only declared unavailable
#                                              signal: the stub is python (#1117)
#   cannot-run - ...                           anything else; matches no declared
#                                              signal, so the harness reports it
#                                              loudly, never as clean or detected
set -u
case_dir="$1"
gate="$2"
case "$gate" in /*) ;; *) gate="$PWD/$gate" ;; esac
case "$case_dir" in /*) ;; *) case_dir="$PWD/$case_dir" ;; esac
here=$(cd "$(dirname "$0")" && pwd -P)

command -v python3 >/dev/null 2>&1 || { echo "LANE_SERVE_CONTROL: unavailable - python3 is not installed"; exit 3; }

T=$(mktemp -d "${TMPDIR:-/tmp}/lane-serve-control.XXXXXX") || { echo "LANE_SERVE_CONTROL: cannot-run - no tmpdir"; exit 3; }
trap 'rm -rf "$T"' EXIT INT TERM
mkdir "$T/bin" "$T/responses"
: > "$T/calls"; : > "$T/errors"

MODEL="control-model:latest"
printf '200\n' > "$T/responses/version.status"
printf '{"version":"0.0.0-fixture"}\n' > "$T/responses/version.body"
printf '200\n' > "$T/responses/tags.status"
printf '{"models":[{"name":"%s","model":"%s"}]}\n' "$MODEL" "$MODEL" > "$T/responses/tags.body"

n=0
for f in generate.status generate.body generate.curl_exit; do
    if [ -f "$case_dir/$f" ]; then cp "$case_dir/$f" "$T/responses/$f"; n=$((n + 1)); fi
done
[ "$n" -gt 0 ] || { echo "LANE_SERVE_CONTROL: cannot-run - case supplies no generate.* response"; exit 3; }

cat > "$T/bin/curl" <<STUB
#!/bin/sh
exec python3 "$here/stub-curl.py" "\$@"
STUB
chmod +x "$T/bin/curl"

resolved=$(PATH="$T/bin:$PATH" command -v curl)
if [ "$resolved" != "$T/bin/curl" ]; then
    echo "LANE_SERVE_CONTROL: cannot-run - curl resolves to '$resolved', not the stub; refusing a real network probe"
    exit 3
fi

out=$(env PATH="$T/bin:$PATH" \
          LANE_STUB_RESPONSES="$T/responses" LANE_STUB_CALLS="$T/calls" LANE_STUB_ERRORS="$T/errors" \
          bash "$gate" --endpoint http://127.0.0.1:1/ --model "$MODEL" --timeout 5 --quiet 2>&1)
status=$?

# A stub that refused a request produced no response at all, and the gate would
# classify that as `unreachable` - which is the detect signal. So the gate's
# output is WITHHELD here: a verdict formed from a stub that fell over must not
# reach the harness looking like a detection.
if [ -s "$T/errors" ]; then
    echo "LANE_SERVE_CONTROL: cannot-run - the stub curl refused a request the gate made:"
    sed 's/^/  /' "$T/errors"
    exit 3
fi
if [ ! -s "$T/calls" ]; then
    echo "LANE_SERVE_CONTROL: cannot-run - the gate never reached the stub; no response was classified"
    exit 3
fi

# The exit code and the printed verdict must be ONE answer (counter-model
# review, #1281). The gate's contract pairs them: 0 serving, 1 dead,
# 3 unreachable, 4 unknown. A run printing no verdict, several, or one that
# disagrees with its exit code has not classified anything, and scoring its exit
# code alone would let "exited 0" stand in for "reported serving".
verdicts=$(printf '%s\n' "$out" | grep -c '^LANE_SERVE_STATUS: ' || true)
verdict=$(printf '%s\n' "$out" | sed -n 's/^LANE_SERVE_STATUS: //p' | head -1)
case "$status:$verdict" in
    0:serving|1:dead|3:unreachable|4:unknown) consistent=1 ;;
    *) consistent=0 ;;
esac
if [ "$verdicts" -ne 1 ] || [ "$consistent" -ne 1 ]; then
    echo "LANE_SERVE_CONTROL: cannot-run - the gate's verdict is not one answer:"
    echo "  exit $status, $verdicts LANE_SERVE_STATUS line(s), first '${verdict:-none}'"
    exit 3
fi

printf '%s\n' "$out"
exit "$status"
