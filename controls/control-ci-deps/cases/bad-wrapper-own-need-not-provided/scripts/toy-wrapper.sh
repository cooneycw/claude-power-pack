#!/bin/sh
# Stages a real, verifiable curl stub (same shape as the other cases in this
# control) - but ALSO hard-requires jq itself, unconditionally, for its own
# bootstrap, independent of anything the gate needs. Removing the ADDITIVE
# wrapper walk (`binaries_in_script(wrapper_path)` in requirements()) would
# leave this case's expected result unchanged by accident, since nothing else
# in this fixture tree would surface jq - which is exactly what this case
# exists to catch (counter-model review, issue #1407 fallout).
set -eu
if ! command -v jq >/dev/null 2>&1; then
    echo "jq is required" >&2
    exit 1
fi
MODE=$(printf '{"mode":"case"}' | jq -r '.mode')
T=$(mktemp -d "${TMPDIR:-/tmp}/toy-wrapper.XXXXXX-$MODE")
mkdir "$T/bin"
cat > "$T/bin/curl" <<'STUB'
#!/bin/sh
exit 0
STUB
chmod +x "$T/bin/curl"
env PATH="$T/bin:$PATH" sh "$(dirname "$0")/toy-gate-curl.sh"
rc=$?
rm -rf "$T"
exit $rc
