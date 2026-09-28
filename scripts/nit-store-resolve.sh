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
    if [ -n "$url" ]; then
        # EXACT host: github.com and nothing that merely ends in it. An origin that
        # exists but is not a github.com remote is unknown - never a guessed repo,
        # because the number would be verified and posted somewhere unrelated.
        REPO=$(printf '%s\n' "$url" | sed -nE \
            -e 's#^https?://([^/@]+@)?github\.com/([^/]+/[^/]+)$#\2#p' \
            -e 's#^(ssh://)?git@github\.com[:/]([^/]+/[^/]+)$#\2#p' | sed -e 's#/$##' -e 's/\.git$//')
        [ -n "$REPO" ] || unknown "origin ($url) is not a github.com remote"
    else
        REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)
    fi
fi
case "$REPO" in
    */*) ;;
    *) unknown "could not determine the repository (no github origin, and gh repo view failed)" ;;
esac
echo "NIT_STORE_REPO=$REPO"

# THE MAP - the only copy. Add a repository here, not in a command document.
# Keyed on OWNER/NAME: a fork or a same-named repository under another owner is
# a different repository, and must be searched, not handed its namesake's number.
case "$REPO" in
    cooneycw/kyle)              MAPPED=1004 ;;
    cooneycw/claude-power-pack) MAPPED=864 ;;
    cooneycw/skillc)            MAPPED=20 ;;
    *)                          MAPPED="" ;;
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
# The listing is BOUNDED, and the exact-title filter runs after the bound, so a
# listing that fills the bound may have cut off a match: absence and uniqueness
# are then not established, and the answer is unknown rather than a guess.
LIMIT=200
echo "NIT_STORE_SOURCE=search"
if ! listing=$(gh issue list --repo "$REPO" --state open --search 'in:title "Nit Store"' \
                 --limit "$LIMIT" --json number,title \
                 --jq '"TOTAL \(length)", (.[] | select(.title == "Nit Store") | .number)' 2>/dev/null); then
    unknown "gh could not list open issues in $REPO"
fi
total=$(printf '%s\n' "$listing" | sed -n 's/^TOTAL //p')
case "$total" in
    ''|*[!0-9]*) unknown "gh returned no readable listing for $REPO" ;;
esac
[ "$total" -lt "$LIMIT" ] || unknown "$REPO has $total or more open issues mentioning 'Nit Store' in the title; the listing may be cut off"
found=$(printf '%s\n' "$listing" | grep -v '^TOTAL ' || true)
count=$(printf '%s\n' "$found" | grep -c '^[0-9][0-9]*$' || true)
case "$count" in
    0) none "$REPO has no open issue titled 'Nit Store'" ;;
    1) echo "NIT_STORE=$found"; echo "NIT_STORE_STATUS: ok"; exit 0 ;;
    *) unknown "$REPO has $count open issues titled 'Nit Store'; which one is not decidable here" ;;
esac
