#!/bin/sh
# Case runner for controls/flow-wave-registry-observed (issue #1403).
#
# A SEPARATE registration from controls/flow-wave-registry, same gate AND
# the same "overlapping FILE LANES" text (#986 - several registrations on
# one gate are supported, and a shared signal is fine when nothing widens
# into an alternation to get there). Separate because the FIXTURE SHAPE is:
# that control's cases are a committed registry.json and nothing else,
# generated from declared --files strings alone. This axis is about each
# role's OBSERVED diff - git history that cannot be expressed as one static
# JSON file the way a declared lane can - so each case names a SCENARIO and
# this adapter builds the git fixture fresh, every run, rather than
# committing repository internals that would drift from the gate's own
# git-command assumptions.
set -u
case_dir="$1"
gate="$2"

if [ ! -s "$case_dir/scenario" ]; then
    echo "FLOW_WAVE_REGISTRY_OBSERVED_CONTROL: unavailable - scenario file is missing or empty" >&2
    exit 3
fi
scenario="$(cat "$case_dir/scenario")"

if [ ! -r "$gate" ] || ! command -v bash >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
    echo "FLOW_WAVE_REGISTRY_OBSERVED_CONTROL: unavailable - the gate, bash or git is not present" >&2
    exit 3
fi

T=$(mktemp -d) || { echo "FLOW_WAVE_REGISTRY_OBSERVED_CONTROL: unavailable - no tmpdir" >&2; exit 3; }
trap 'rm -rf "$T"' EXIT INT TERM

origin="$T/origin"
worker_a="$T/worker-a"
worker_b="$T/worker-b"

git init -q -b main "$origin" || { echo "FLOW_WAVE_REGISTRY_OBSERVED_CONTROL: unavailable - git init failed" >&2; exit 3; }
git -C "$origin" config user.email t@example.com
git -C "$origin" config user.name t
mkdir -p "$origin/controls/a-owned" "$origin/controls/b-owned"
echo a > "$origin/controls/a-owned/x.sh"
echo b > "$origin/controls/b-owned/y.sh"
git -C "$origin" add -A
git -C "$origin" commit -qm init >/dev/null
git -C "$origin" update-ref refs/remotes/origin/main HEAD

cp -r "$origin" "$worker_a"
cp -r "$origin" "$worker_b"

case "$scenario" in
  undeclared-write)
    # THE #1403 RED: worker-a never declares controls/b-owned, but its own
    # diff touches it anyway.
    echo a-changed > "$worker_a/controls/a-owned/x.sh"
    echo undeclared > "$worker_a/controls/b-owned/intrusion.sh"
    git -C "$worker_a" add controls >/dev/null
    echo b-changed > "$worker_b/controls/b-owned/y.sh"
    git -C "$worker_b" add controls >/dev/null
    ;;
  disjoint-observed)
    # GOOD: each side's diff stays inside its own declared lane.
    echo a-changed > "$worker_a/controls/a-owned/x.sh"
    git -C "$worker_a" add controls >/dev/null
    echo b-changed > "$worker_b/controls/b-owned/y.sh"
    git -C "$worker_b" add controls >/dev/null
    ;;
  *)
    echo "FLOW_WAVE_REGISTRY_OBSERVED_CONTROL: unavailable - unknown scenario '$scenario'" >&2
    exit 3
    ;;
esac

REG="$T/reg"
mkdir -p "$REG"
out_a=$(env FLOW_WAVE_REGISTRY_DIR="$REG" CLAUDE_PID=4242 CLAUDE_CODE_SESSION_ID=w-4242 \
    bash "$gate" register worker-A --wave cpp --socket uds:/tmp/a.sock \
    --repo "$origin" --cwd "$worker_a" --files controls/a-owned 2>&1)
st_a=$?
out_b=$(env FLOW_WAVE_REGISTRY_DIR="$REG" CLAUDE_PID=9999 CLAUDE_CODE_SESSION_ID=w-9999 \
    bash "$gate" register worker-B --wave cpp --socket uds:/tmp/b.sock \
    --repo "$origin" --cwd "$worker_b" --files controls/b-owned 2>&1)
st_b=$?
if [ "$st_a" -ne 0 ] || [ "$st_b" -ne 0 ]; then
    echo "FLOW_WAVE_REGISTRY_OBSERVED_CONTROL: unavailable - register exited $st_a/$st_b" >&2
    printf '%s\n%s\n' "$out_a" "$out_b" >&2
    exit 3
fi

out=$(env FLOW_WAVE_REGISTRY_DIR="$REG" FLOW_WAVE_LIVE_PIDS="4242:9999" \
    bash "$gate" list --wave cpp 2>&1)
status=$?
if [ "$status" -ne 0 ]; then
    echo "FLOW_WAVE_REGISTRY_OBSERVED_CONTROL: unavailable - list exited $status" >&2
    printf '%s\n' "$out" >&2
    exit 3
fi

if printf '%s\n' "$out" | grep -q 'overlapping FILE LANES'; then
    echo "FLOW_WAVE_REGISTRY_OBSERVED_CONTROL: finding - the roster reported overlapping FILE LANES"
    exit 1
fi
exit 0
