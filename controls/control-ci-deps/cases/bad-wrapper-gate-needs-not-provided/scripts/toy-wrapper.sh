#!/bin/sh
# Stages only a curl stub - never jq - mirroring
# controls/lane-serveability-check/run-case.sh's own shape.
set -eu
T=$(mktemp -d "${TMPDIR:-/tmp}/toy-wrapper.XXXXXX")
mkdir "$T/bin"
cat > "$T/bin/curl" <<'STUB'
#!/bin/sh
exit 0
STUB
chmod +x "$T/bin/curl"
env PATH="$T/bin:$PATH" sh "$(dirname "$0")/toy-gate-curl-jq.sh"
rc=$?
rm -rf "$T"
exit $rc
