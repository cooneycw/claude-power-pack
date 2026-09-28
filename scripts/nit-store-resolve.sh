#!/usr/bin/env bash
# nit-store-resolve.sh - which issue, if any, is this repository's Nit Store
# (issues #1272 item 1, #1273 items 10 and 28).
#
# The map used to be a `case` block copied verbatim into three command
# documents (flow/finish.md, flow/auto.md, codex/code_review.md). The copies
# agreed with each other and not with GitHub: codex-power-pack still mapped to
# #227 after #227 was CLOSED, and nothing checked a mapped number before a
# finding was posted into it. So the map lives here once, and no number is
# answered until GitHub confirms it is an OPEN issue titled exactly "Nit Store".
#
# Usage:
#   nit-store-resolve.sh [--repo OWNER/NAME]
#
# Without --repo the repository is read from `origin` (never the directory
# name: flow runs from per-issue worktrees whose basename is not the repo),
# falling back to `gh repo view`.
#
# Contract (stdout, exit code):
#   NIT_STORE=<n>, NIT_STORE_REPO=, NIT_STORE_SOURCE=map|search,
#   NIT_STORE_STATUS: ok                                     exit 0
#   NIT_STORE_STATUS: none - <reason>; file the finding as a normal issue
#                                                            exit 1
#   NIT_STORE_STATUS: unknown - <reason>                     exit 3
#   usage error                                              exit 2
#
# `none` and `unknown` are different answers and must stay different: `none`
# means GitHub was asked and there is no open Nit Store (file a normal issue);
# `unknown` means GitHub could not be asked, or the answer was ambiguous, so
# NOTHING is established - never post on it, and never read it as `none`.
# A mapped number that is closed or retitled is `none`, never the number: a
# finding posted into a closed issue is read by nobody.
set -u

REPO=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --repo)
            [ "$#" -ge 2 ] || { echo "nit-store-resolve: --repo needs OWNER/NAME" >&2; exit 2; }
            REPO="$2"; shift 2 ;;
        -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
        *) echo "nit-store-resolve: unknown argument: $1" >&2; exit 2 ;;
    esac
done

unknown() { echo "NIT_STORE_STATUS: unknown - $*"; exit 3; }
none() { echo "NIT_STORE_STATUS: none - $*; file the finding as a normal issue"; exit 1; }

if [ -z "$REPO" ]; then
    url=$(git remote get-url origin 2>/dev/null || true)
    REPO=$(printf '%s\n' "$url" | sed -nE 's#^.*github\.com[:/]+([^/]+/[^/]+)$#\1#p' | sed 's/\.git$//')
    [ -n "$REPO" ] || REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)
fi
case "$REPO" in
    */*) ;;
    *) unknown "could not determine the repository (no github origin, and gh repo view failed)" ;;
esac
echo "NIT_STORE_REPO=$REPO"

# THE MAP - the only copy. Add a repository here, not in a command document.
case "${REPO#*/}" in
    kyle)              MAPPED=1004 ;;
    claude-power-pack) MAPPED=864 ;;
    skillc)            MAPPED=20 ;;
    *)                 MAPPED="" ;;
esac

if [ -n "$MAPPED" ]; then
    echo "NIT_STORE_SOURCE=map"
    if ! got=$(gh issue view "$MAPPED" --repo "$REPO" --json state,title \
                 --jq '.state + "\t" + .title' 2>/dev/null); then
        unknown "gh could not read $REPO#$MAPPED"
    fi
    state=${got%%$'\t'*}
    title=${got#*$'\t'}
    [ "$state" = "OPEN" ] || none "$REPO#$MAPPED is $state, not OPEN"
    [ "$title" = "Nit Store" ] || none "$REPO#$MAPPED is titled '$title', not 'Nit Store'"
    echo "NIT_STORE=$MAPPED"
    echo "NIT_STORE_STATUS: ok"
    exit 0
fi

# Unmapped: an EXACT title match among open issues, and exactly one of them.
# (`--search` alone is full text and selects any issue that mentions the phrase.)
echo "NIT_STORE_SOURCE=search"
if ! found=$(gh issue list --repo "$REPO" --state open --search 'in:title "Nit Store"' \
               --json number,title --jq '.[] | select(.title == "Nit Store") | .number' 2>/dev/null); then
    unknown "gh could not list open issues in $REPO"
fi
count=$(printf '%s\n' "$found" | grep -c '^[0-9][0-9]*$' || true)
case "$count" in
    0) none "$REPO has no open issue titled 'Nit Store'" ;;
    1) echo "NIT_STORE=$found"; echo "NIT_STORE_STATUS: ok"; exit 0 ;;
    *) unknown "$REPO has $count open issues titled 'Nit Store'; which one is not decidable here" ;;
esac
