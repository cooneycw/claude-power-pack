#!/usr/bin/env bash
# flow-helpers-install.sh - Install the flow helper family into ~/.claude/scripts/
# (issue #590).
#
# Problem:
#   Flow commands call ~14 helpers at the stable ~/.claude/scripts/ paths the
#   #581 allowlist matches. This installer puts them there from the CPP checkout.
#   During the #662/#663 migration it also accepts a legacy plugin-cache source,
#   so hosts can keep working until they uninstall the retired flow cache.
#
# Source selection (first match wins):
#   1. A CPP checkout (this script's own dir is <checkout>/scripts) -> SYMLINK,
#      so the helpers follow `git pull` exactly as /cpp:init Tier 2 does today.
#   2. A legacy plugin cache (this script's own dir is <cache>/scripts, no
#      CLAUDE.md one level up) -> COPY. A symlink into a retired cache would
#      dangle when the family is uninstalled; --check detects stale copies.
#
# Usage:
#   flow-helpers-install.sh            # install/refresh, idempotent
#   flow-helpers-install.sh --check    # read-only: report ok/missing/stale, exit 1 if any
#   flow-helpers-install.sh --force    # overwrite even when content already matches
#
# Output ends with a machine-readable verdict line:
#   FLOW_HELPERS: ok | installed | unverifiable | missing | stale | error
#
#   `unverifiable` (issue #927) is NOT a lesser `ok`. It means the helpers are
#   installed and NO SOURCE OF TRUTH was reachable, so this run could not tell
#   "current" from "a version behind". `ok` asserts a comparison happened;
#   `unverifiable` asserts one did not. They were the same word until #927, and
#   the honest sentence ("cannot compare") was printed to a human while the
#   machine-readable verdict said success.
#
#   EXIT STAYS 0 for `unverifiable`, deliberately. This verdict is consumed by a
#   READER deciding whether to repair, not by a gate letting work through - the
#   opposite of shellcheck-gate, whose exit 2 on an absent tool is correct
#   because `make verify` consumes it. A container that genuinely cannot reach a
#   checkout is not a failure, and making it one would fail every container
#   repair.
#
#   REVERSAL TRIGGER (issue #936, pre-committed rather than left to judgement):
#   exit 0 holds only while `unverifiable` is a CONTAINER condition. If it is
#   ever observed on a HOST - where a checkout IS reachable and something else
#   went wrong - exit 0 is hiding a real failure and this becomes non-zero.
#
# Env (test hooks - unset in normal use):
#   FLOW_HELPERS_HOME      override $HOME (install target root)
#   FLOW_HELPERS_SOURCE    override the source dir (skips detection)

set -uo pipefail

# The exit status, on stderr, as the last thing written (issue #1031).
# `helper | tail -3; echo $?` reports TAIL's status, not this script's, and
# `pipefail` is not set in the calling lane. Printing it makes it survive the
# pipe. STDERR and not stdout: stdout is this helper's machine-readable
# contract and is captured with $(...) by sibling helpers, so metadata there
# corrupts them - and stderr bypasses the pipe entirely rather than merely
# landing at the end of it. See docs/agents/evidence-deleting-idioms.md.
trap 'printf "FLOW_HELPERS_EXIT=%d\n" "$?" >&2' EXIT

# PROVENANCE, on EVERY verdict (issue #927). An `ok` from a 22-entry allowlist
# and an `ok` from a 24-entry one were the same line, so a verdict could not be
# read against what produced it - the denominator convention (#952) applied to
# this script's own output.
#
# Defined HERE, above every exit, because the first cut defined it below the
# missing-source error path: that verdict fired before the function existed, so
# "provenance on every verdict" was true of the paths I was looking at and false
# of the ones I was not. Codex found it.
#
# EXAMINED is the denominator that matters. FLOW_HELPERS_ALLOWLIST says how many
# names this installer KNOWS; it does not say how many it actually compared. A
# source directory containing none of them skipped all 24 and still reported
# `ok` - scanned nothing, reported clean, inside the change that documents `ok`
# as meaning a comparison happened.
EXAMINED=0
REASON="-"
emit_provenance() {
    echo "FLOW_HELPERS_INSTALLER: ${BASH_SOURCE[0]}"
    echo "FLOW_HELPERS_ALLOWLIST: ${#HELPERS[@]}"
    echo "FLOW_HELPERS_EXAMINED: $EXAMINED"
    echo "FLOW_HELPERS_SOURCE_KIND: ${SOURCE_KIND:-unknown}"
    echo "FLOW_HELPERS_SOURCE_DIR: ${SOURCE_DIR:-unknown}"
    echo "FLOW_HELPERS_REASON: $REASON"
}

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="${FLOW_HELPERS_HOME:-$HOME}"
TARGET_DIR="$HOME_DIR/.claude/scripts"

# The load-bearing family. flow-start-resolve.sh resolves its live-driver
# sibling via $SELF_DIR, so the guard must travel with it. The advisory guards
# fail open when absent, but a legacy-cache user should keep the zero-prompt lane
# whole, not degraded.
#
# Despite the script's name this is NOT a flow-only list - it already carries
# gh-pr-merge.sh, worktree-remove.sh, friction-log.sh, check-ignored-additions.sh
# and this installer itself. The membership rule is simpler than the name
# suggests: THIS IS THE STABLE-PATH INSTALL SET. Anything that
# templates/claude-settings-permissions.json pre-approves at
# `Bash(~/.claude/scripts/<name>:*)` belongs here, whatever family it comes from,
# because that rule matches a command PREFIX - so a helper the rule blesses but
# nothing installs leaves the rule matching a path that does not exist (issue
# #677: cpp-commands-link.sh and install-drift.sh were both missing, so on any
# host provisioned WITHOUT interactive /cpp:init the rule was inert and
# /cpp:update Step 5c fell back to the checkout copy - which the rule does not
# match - and prompted, the exact friction the stable path removes). Do not
# re-litigate a non-flow addition on naming grounds; the template is the
# membership test, and tests/test_permissions_template_link_parity.py enforces it.
HELPERS=(
    flow-start-resolve.sh
    flow-live-driver-guard.sh
    flow-stale-check.sh
    flow-worktree-guard.sh
    flow-worktree-claim.sh
    flow-wave-registry.sh
    flow-wave-mailbox.sh
    flow-wave-lexicon.sh
    flow-wave-plan.py
    speckit-context.py
    flow-driver-capability.sh
    flow-vantage.sh
    flow-finish-gate.sh
    flow-ci-status.sh
    flow-pr-watch.sh
    gh-pr-merge.sh
    worktree-remove.sh
    flow-worktree-sweep.sh
    friction-log.sh
    check-ignored-additions.sh
    delegated-run-check.sh
    lane-serveability-check.sh
    cpp-commands-link.sh
    install-drift.sh
    stash-worktree-guard.sh
    flow-helpers-install.sh
)

MODE="install"
FORCE=0
for arg in "$@"; do
    case "$arg" in
        --check) MODE="check" ;;
        --force) FORCE=1 ;;
        --help|-h)
            # 2,28p: the doc block ends at line 28 (the last `# Env:` entry).
            # It was 2,37p, which spilled `set -uo pipefail`, three variable
            # assignments and two stray comment lines into --help output (#686).
            # tests/test_flow_helpers_install.py pins the boundary so the range
            # cannot silently re-drift when the header grows.
            # DERIVED, not hardcoded (issue #927). The range was `2,28p` and
            # my own header growth pushed the Env block past line 28, so
            # --help stopped printing it - the exact re-drift the comment
            # above predicted and the test below pins. A literal number here
            # is a coverage list of one, and it goes stale on the next edit
            # of the thing it measures. Print from line 2 until the first
            # line that is not a comment instead: the header IS the block.
            awk 'NR>1 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "$0"
            exit 0
            ;;
        *)
            echo "flow-helpers-install: unknown argument: $arg" >&2
            exit 2
            ;;
    esac
done

# --- Source detection -------------------------------------------------------
# Self-source is the degenerate case: the copy at ~/.claude/scripts/ is itself
# one of the installed helpers, so running IT would diff every file against
# itself and always report "ok" - stale legacy-cache copies would be
# invisible, which is the one failure mode a copy-based install can hit. When
# self and target coincide, look for a real upstream first.
SOURCE_DIR="${FLOW_HELPERS_SOURCE:-$SELF_DIR}"
NO_UPSTREAM=0
if [[ -z "${FLOW_HELPERS_SOURCE:-}" && "$SOURCE_DIR" == "$TARGET_DIR" ]]; then
    upstream=""
    # A legacy plugin cache, while the #662/#663 migration is in progress.
    if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" && -f "$CLAUDE_PLUGIN_ROOT/scripts/flow-start-resolve.sh" ]]; then
        upstream="$CLAUDE_PLUGIN_ROOT/scripts"
    else
        for dir in "$HOME_DIR/Projects/claude-power-pack" /opt/claude-power-pack "$HOME_DIR/.claude-power-pack"; do
            if [[ -f "$dir/CLAUDE.md" && -f "$dir/scripts/flow-start-resolve.sh" ]]; then
                upstream="$dir/scripts"
                break
            fi
        done
    fi
    if [[ -n "$upstream" ]]; then
        SOURCE_DIR="$upstream"
    else
        # Nothing to compare against: the helpers are installed and working,
        # there is just no source of truth reachable from here.
        NO_UPSTREAM=1
    fi
fi

SOURCE_KIND="plugin"
if [[ -f "$SOURCE_DIR/../CLAUDE.md" && -d "$SOURCE_DIR/../.claude/commands" ]]; then
    SOURCE_KIND="checkout"
fi

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "flow-helpers-install: source dir not found: $SOURCE_DIR" >&2
    REASON="source-dir-missing"
    emit_provenance
    echo "FLOW_HELPERS: error"
    exit 2
fi

if [[ "$NO_UPSTREAM" -eq 1 ]]; then
    echo "flow-helpers-install: helpers are installed at $TARGET_DIR, but no upstream"
    echo "source (plugin bundle or CPP checkout) is reachable from here - cannot compare."
    echo "flow-helpers-install: this run cannot tell a CURRENT install from a STALE"
    echo "one. Bring a CPP checkout within reach and re-run to get a real verdict."
    REASON="no-upstream"
    emit_provenance
    echo "FLOW_HELPERS: unverifiable"
    exit 0
fi

echo "flow-helpers-install: source $SOURCE_DIR ($SOURCE_KIND), target $TARGET_DIR"

# --- Check mode (read-only) -------------------------------------------------
if [[ "$MODE" == "check" ]]; then
    missing=0
    stale=0
    for name in "${HELPERS[@]}"; do
        src="$SOURCE_DIR/$name"
        dest="$TARGET_DIR/$name"
        if [[ ! -f "$src" ]]; then
            echo "SKIP $name (not present in source)"
            continue
        fi
        EXAMINED=$((EXAMINED + 1))
        if [[ ! -e "$dest" ]]; then
            # A dangling symlink is -L but not -e: report it as missing, which is
            # what it behaves like (exit 127 on invocation).
            if [[ -L "$dest" ]]; then
                echo "MISSING $name (dangling symlink -> $(readlink "$dest"))"
            else
                echo "MISSING $name"
            fi
            missing=$((missing + 1))
        elif ! diff -q "$src" "$dest" >/dev/null 2>&1; then
            echo "STALE $name (installed copy differs from source)"
            stale=$((stale + 1))
        elif [[ ! -x "$dest" ]]; then
            echo "STALE $name (not executable)"
            stale=$((stale + 1))
        else
            echo "OK $name"
        fi
    done
    # SCANNED NOTHING IS NOT CLEAN (#952, and this script's own new promise that
    # `ok` means a comparison happened). A source directory holding none of the
    # helper names skipped all of them and reported ok - the allowlist length
    # said 24 while the examined count was 0, and only one of those was printed.
    if [[ "$EXAMINED" -eq 0 ]]; then
        echo "flow-helpers-install: $SOURCE_DIR holds none of the ${#HELPERS[@]} known" >&2
        echo "helper names, so nothing was compared. This is UNVERIFIABLE, not ok." >&2
        REASON="empty-source"
        emit_provenance
        echo "FLOW_HELPERS: unverifiable"
        exit 0
    fi
    if [[ "$missing" -gt 0 ]]; then
        echo "flow-helpers-install: $missing helper(s) missing - run /flow:repair" >&2
        REASON="missing-helpers"
        emit_provenance
        echo "FLOW_HELPERS: missing"
        exit 1
    fi
    if [[ "$stale" -gt 0 ]]; then
        echo "flow-helpers-install: $stale helper(s) stale - run /flow:repair" >&2
        REASON="stale-helpers"
        emit_provenance
        echo "FLOW_HELPERS: stale"
        exit 1
    fi
    emit_provenance
    echo "FLOW_HELPERS: ok"
    exit 0
fi

# --- Install mode -----------------------------------------------------------
if ! mkdir -p "$TARGET_DIR"; then
    echo "flow-helpers-install: cannot create $TARGET_DIR" >&2
    REASON="target-dir-uncreatable"
    emit_provenance
    echo "FLOW_HELPERS: error"
    exit 2
fi

changed=0
for name in "${HELPERS[@]}"; do
    src="$SOURCE_DIR/$name"
    dest="$TARGET_DIR/$name"
    if [[ ! -f "$src" ]]; then
        echo "skip $name (not present in source)"
        continue
    fi
    EXAMINED=$((EXAMINED + 1))
    if [[ "$SOURCE_KIND" == "checkout" ]]; then
        # Symlink: follows `git pull`, same as /cpp:init Tier 2.
        if [[ "$FORCE" -eq 0 && "$(readlink "$dest" 2>/dev/null)" == "$src" ]]; then
            echo "ok   $name (already linked)"
            continue
        fi
        if ln -sfn "$src" "$dest"; then
            echo "link $name"
            changed=$((changed + 1))
        else
            echo "flow-helpers-install: failed to link $name" >&2
            REASON="link-failed"
            emit_provenance
            echo "FLOW_HELPERS: error"
            exit 2
        fi
    else
        # Copy: a version-stamped legacy cache must not become a dangling symlink.
        if [[ "$FORCE" -eq 0 && -f "$dest" && ! -L "$dest" ]] && diff -q "$src" "$dest" >/dev/null 2>&1; then
            chmod +x "$dest" 2>/dev/null || true
            echo "ok   $name (already current)"
            continue
        fi
        # Replace rather than write through: $dest may be a symlink into an old
        # cached version, and `cp` would follow it and write into the cache.
        rm -f "$dest"
        if cp "$src" "$dest" && chmod +x "$dest"; then
            echo "copy $name"
            changed=$((changed + 1))
        else
            echo "flow-helpers-install: failed to copy $name" >&2
            REASON="copy-failed"
            emit_provenance
            echo "FLOW_HELPERS: error"
            exit 2
        fi
    fi
done

if [[ "$EXAMINED" -eq 0 ]]; then
    echo "flow-helpers-install: $SOURCE_DIR holds none of the ${#HELPERS[@]} known" >&2
    echo "helper names, so nothing was installed or compared. UNVERIFIABLE, not ok." >&2
    REASON="empty-source"
    emit_provenance
    echo "FLOW_HELPERS: unverifiable"
    exit 0
fi
emit_provenance
if [[ "$changed" -eq 0 ]]; then
    echo "flow-helpers-install: all helpers already current ($TARGET_DIR)"
    echo "FLOW_HELPERS: ok"
else
    echo "flow-helpers-install: $changed helper(s) installed to $TARGET_DIR"
    echo "FLOW_HELPERS: installed"
fi
exit 0
