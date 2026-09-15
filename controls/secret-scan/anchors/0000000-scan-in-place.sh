#!/bin/sh
# BLIND ANCHOR for the secret-scan control (issue #935).
#
# SYNTHETIC, and deliberately so: no HISTORICAL blind version of this gate
# exists. `.gitleaks.toml` has two commits in its life, both `useDefault = true`,
# and both detect the fixture - so there is no ancestor to vendor. Recording that
# as a decision rather than leaving `kind` to imply an artifact that was never
# found.
#
# What it is: the design that was PROPOSED and REFUTED for #935 - scan the case
# WHERE IT LIVES, without relocating. Because the fixture sits at an allowlisted
# path, this misses the known-bad input, which is exactly the property an anchor
# must have. It is the near-miss preserved, not an invented cripple.
set -u
ROOT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --root)
            [ $# -ge 2 ] || { echo "anchor: --root requires a value" >&2; exit 2; }
            ROOT="$2"; shift 2 ;;
        *) echo "anchor: unknown argument: $1" >&2; exit 2 ;;
    esac
done
[ -n "$ROOT" ] || { echo "anchor: --root is required" >&2; exit 2; }
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CONFIG="$HERE/../../../.gitleaks.toml"
command -v gitleaks >/dev/null 2>&1 || { echo "anchor: gitleaks absent" >&2; exit 3; }
gitleaks detect --source "$ROOT" --config "$CONFIG" --no-git --verbose
