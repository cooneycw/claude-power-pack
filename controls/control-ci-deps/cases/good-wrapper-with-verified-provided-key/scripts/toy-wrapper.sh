#!/bin/sh
# Mirrors controls/lane-serveability-check/run-case.sh's own shape exactly:
# stages a throwaway curl stub on PATH, then runs the real gate through it.
# This control's own control.json DOES declare `ci_deps_provided_by_invocation:
# ["curl"]`, and this wrapper's text genuinely demonstrates the claim - the
# checker must verify it against this file's own text and score the control
# clean (counter-model review: an earlier copy-paste left this comment
# claiming the opposite, the bad-wrapper-without-provided-key case's own
# header, which described this file correctly there and not here).
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
