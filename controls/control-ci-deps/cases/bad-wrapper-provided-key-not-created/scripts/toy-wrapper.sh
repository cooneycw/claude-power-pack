#!/bin/sh
# Stages a stub named `wget`, NOT `curl` - unlike the other fixtures in this
# control, this wrapper never writes anything named `curl` anywhere, nor
# prepends anything to PATH naming it. The control's own control.json claims
# curl is provided anyway: a stale claim the checker must refuse rather than
# trust as free text.
set -eu
T=$(mktemp -d "${TMPDIR:-/tmp}/toy-wrapper.XXXXXX")
mkdir "$T/bin"
cat > "$T/bin/wget" <<'STUB'
#!/bin/sh
exit 0
STUB
chmod +x "$T/bin/wget"
env PATH="$T/bin:$PATH" sh "$(dirname "$0")/toy-gate-curl.sh"
rc=$?
rm -rf "$T"
exit $rc
