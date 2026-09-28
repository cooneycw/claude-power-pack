#!/bin/sh
# Runs one cpp-checkout-freshness case (issue #1282).
#
# A case is a git SITUATION - a clone relative to its origin - and a repository
# cannot be committed inside this one (a nested .git is not tracked). So each
# case commits a one-word `scenario`, and this wrapper builds the bare origin and
# the clone from it in a fresh temporary directory on every run:
#
#   current      clone at the origin's tip
#   behind-1     origin advanced one commit after the clone
#   fetch-fails  origin advanced, then the clone's origin URL points nowhere -
#                the stale remote-tracking ref still matches HEAD
#   read-only    origin advanced, then the clone's .git made unwritable in TWO
#                layers, so the case is BAD for every uid (CI runs as ROOT):
#                  - chmod -R a-w .git: what an unprivileged reader of a
#                    read-only checkout meets. ROOT IGNORES MODE BITS, so under
#                    root this layer alone lets the fetch succeed - pipeline
#                    2800 was red on exactly that, and until then the wrapper
#                    reported this case UNAVAILABLE under root, which the
#                    harness rightly refuses beside real verdicts.
#                  - a pre-existing refs/remotes/origin/main.lock: git refuses
#                    to update a ref whose lock exists, for ANY uid, and the
#                    stale origin/main stays readable - the ref a blind count
#                    would read as "current".
#                A real read-only MOUNT refuses root too (EROFS), so the helper's
#                own `-w` test reports "checkout not writable" there; under this
#                fixture root sees "cannot lock ref" instead. Both are `unknown`.
#
# The gate's output is passed through unchanged and its exit status is this
# wrapper's, so the runner reads the gate's own words and code.
set -u
gate="$1"
case_dir="$2"

for tool in bash git; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "CPP_CHECKOUT_FRESHNESS_CONTROL: unavailable - $tool is not installed"
        exit 2
    fi
done
scenario=$(cat "$case_dir/scenario" 2>/dev/null) || scenario=""

work=$(mktemp -d) || exit 2
trap 'chmod -R u+w "$work" 2>/dev/null; rm -rf "$work"' EXIT

# Builds the fixture; any failure here is the harness's, not the gate's.
build() {
    q=--quiet
    git init $q --bare --initial-branch=main "$work/origin.git" &&
    git clone $q "$work/origin.git" "$work/seed" 2>/dev/null &&
    git -C "$work/seed" checkout $q -b main &&
    git -C "$work/seed" -c user.email=c@x.invalid -c user.name=c commit $q --allow-empty -m one &&
    git -C "$work/seed" push $q origin main &&
    git clone $q "$work/origin.git" "$work/checkout" || return 1
    [ "$scenario" = "current" ] && return 0
    git -C "$work/seed" -c user.email=c@x.invalid -c user.name=c commit $q --allow-empty -m two &&
    git -C "$work/seed" push $q origin main || return 1
    case "$scenario" in
        behind-1)    return 0 ;;
        fetch-fails) git -C "$work/checkout" remote set-url origin "$work/gone.git" ;;
        read-only)
            # Precondition: the stale ref must still resolve and still equal
            # HEAD, or this case would not test the stale-count hazard at all.
            [ "$(git -C "$work/checkout" rev-parse refs/remotes/origin/main)" = \
              "$(git -C "$work/checkout" rev-parse HEAD)" ] || return 1
            mkdir -p "$work/checkout/.git/refs/remotes/origin" &&
            : > "$work/checkout/.git/refs/remotes/origin/main.lock" &&
            chmod -R a-w "$work/checkout/.git" ;;
        *)           return 1 ;;
    esac
}
if ! build >/dev/null 2>&1; then
    echo "CPP_CHECKOUT_FRESHNESS_CONTROL: unavailable - could not build scenario '$scenario'"
    exit 2
fi

CPP_FRESHNESS_FETCH_TIMEOUT=20 bash "$gate" --path "$work/checkout"
