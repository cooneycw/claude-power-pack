#!/bin/sh
# Stage the runner dependency visibly for the CI dependency contract.
set -u
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/cpp-gate-owner-bin.XXXXXX") || exit 2
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/bin"
cat > "$work/bin/uv" <<'STUB'
#!/bin/sh
: > "${CPP_OWNER_STARTED:?owned runner marker missing}"
exec sleep 30
STUB
chmod +x "$work/bin/uv"
PATH="$work/bin:$PATH" python3 "$here/run-case.py" "$1" "$2" "$work/bin"
rc=$?
exit "$rc"
