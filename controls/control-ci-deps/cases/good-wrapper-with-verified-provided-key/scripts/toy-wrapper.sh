#!/bin/sh
# Mirrors controls/lane-serveability-check/run-case.sh's own shape exactly:
# stages a throwaway curl stub on PATH, then runs the real gate through it.
# This case carries NO `ci_deps_provided_by_invocation` key, so the real
# gate's own curl requirement must still be reported - this is today's
# make-test failure, reproduced on purpose as the intended red.
set -eu
T=$(mktemp -d "${TMPDIR:-/tmp}/toy-wrapper.XXXXXX")
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
