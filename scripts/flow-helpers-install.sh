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
#   FLOW_HELPERS: ok | installed | unverifiable | unverifiable-source
#                 | tampered | missing | stale | error
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
    echo "FLOW_HELPERS_MANIFEST: ${MANIFEST_STATE:-unchecked}"
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
    flow-plan-record.py
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
    # flow-finish-gate.sh SOURCES this and refuses to run without it (#1061).
    # Installing the gate alone would put a script at the stable path that exits 2
    # on every invocation - which is what it did before this line existed.
    gate-lib.sh
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

# --- Source integrity (issue #1185) -----------------------------------------
#: NEGATIVE-CONTROL: controls/flow-helpers-install
# Everything above compares an INSTALLED COPY against its SOURCE. That is drift,
# and it is what those checks are for. It is silent about whether the SOURCE is
# the file we shipped - and on a Codex host, installed from a bundle with no
# checkout attached, there is nothing to look around at. Measured before this
# existed: a tampered worktree-remove.sh (canonical d57ee08d00f1) installed with
# `FLOW_HELPERS: installed`, the injected line reached ~/.claude/scripts, and a
# subsequent `--check` reported `FLOW_HELPERS: ok` - the existing check did not
# merely miss the tampering, it CERTIFIED the tampered install as healthy.
#
# WHAT THIS DOES NOT COVER, stated here and not only in the docs. The manifest
# TRAVELS INSIDE THE BUNDLE IT CERTIFIES. Anyone able to rewrite a bundled
# script can rewrite the manifest, so a match establishes only that these bytes
# are the bytes recorded WHEN THE BUNDLE WAS GENERATED. It detects accidental
# corruption, a partial edit that missed the manifest, and modification after
# generation. It does NOT detect a coherently regenerated bundle and says
# NOTHING ABOUT ARRIVAL: a bundle already tampered with before it reached this
# host carries a manifest that agrees with it perfectly. Covering arrival needs
# a signature checked against a key that is NOT in the bundle. That is a
# different problem and deliberately not this one.
#
# TWO VERDICTS, NEVER COLLAPSED INTO ONE WORD, distinct through to the exit
# code, because they are different facts and a reader acts differently on each:
#   tampered            (exit 5) the source DISAGREES with its manifest
#   unverifiable-source (exit 6) this run COULD NOT ASK the question
# Folding "cannot verify" into "verified" is the failure this whole issue is
# about, one level up; folding it into "tampered" would cry wolf on a host with
# no digest tool. Both refuse: nothing is installed either way.
MANIFEST_NAME="SHA256SUMS"
MANIFEST_PATH="$SOURCE_DIR/$MANIFEST_NAME"
MANIFEST_STATE="absent"

# A BUNDLE is identified by a sibling SKILL.md, not by SOURCE_KIND=plugin. The
# broader test would also catch the CLAUDE_PLUGIN_ROOT legacy cache from the
# #662/#663 migration, which carries no manifest and would then be refused for a
# reason that has nothing to do with it. The narrow test names exactly the
# surface #1185 is about.
IS_BUNDLE=0
if [[ -f "$SOURCE_DIR/../SKILL.md" ]]; then
    IS_BUNDLE=1
fi

DIGEST_CMD=()
if command -v sha256sum >/dev/null 2>&1; then
    DIGEST_CMD=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
    DIGEST_CMD=(shasum -a 256)
fi

# RETURNS NON-ZERO WHEN IT COULD NOT HASH, and the caller must act on that
# (counter-model review, codex, MEDIUM). Swallowing the status made an empty
# result compare unequal to every recorded digest, so an unreadable file or a
# failing digest executable reported `tampered` with exit 5 over an INTACT
# bundle - a false accusation, and precisely the collapse between "the bytes
# disagree" and "I could not ask" that this whole change exists to prevent.
# Reproduced with an `exit 1` stub on PATH before the fix.
_digest_of() {
    local out
    [[ "${#DIGEST_CMD[@]}" -gt 0 ]] || return 1
    out="$("${DIGEST_CMD[@]}" "$1" 2>/dev/null)" || return 1
    out="${out%% *}"
    # A 64-hex-character answer or nothing. A truncated or empty result must not
    # be compared: it would differ from the recorded digest and read as tamper.
    [[ "$out" =~ ^[0-9a-f]{64}$ ]] || return 1
    printf '%s' "$out"
}

if [[ -f "$MANIFEST_PATH" ]]; then
    if [[ "${#DIGEST_CMD[@]}" -eq 0 ]]; then
        # A manifest's PRESENCE is a declaration that verification is expected.
        # Falling open here would make an absent guard indistinguishable from a
        # guard that passed, which is the #823 shape this repository refuses.
        MANIFEST_STATE="no-digest-tool"
        echo "flow-helpers-install: $MANIFEST_NAME is present but neither sha256sum nor" >&2
        echo "  shasum is installed, so this run CANNOT verify the source. Nothing installed." >&2
        REASON="no-digest-tool"
        emit_provenance
        echo "FLOW_HELPERS: unverifiable-source"
        exit 6
    fi
    listed=0
    bad=0
    declare -A MANIFEST_ROWS=()
    while read -r m_digest m_name; do
        case "$m_digest" in '#'*|'') continue ;; esac
        [[ -n "$m_name" ]] || continue
        MANIFEST_ROWS["$m_name"]=1
        listed=$((listed + 1))
        m_file="$SOURCE_DIR/$m_name"
        if [[ ! -f "$m_file" ]]; then
            echo "TAMPERED $m_name (listed in $MANIFEST_NAME, absent from the source)" >&2
            bad=$((bad + 1))
            continue
        fi
        if ! actual="$(_digest_of "$m_file")"; then
            # COULD NOT ASK, not "the answer is no". Refuse on the unverifiable
            # path rather than accusing an intact file of being tampered.
            echo "flow-helpers-install: could not compute a digest for $m_name, so this" >&2
            echo "  run cannot verify the source. Nothing installed." >&2
            MANIFEST_STATE="digest-failed"
            REASON="digest-failed"
            emit_provenance
            echo "FLOW_HELPERS: unverifiable-source"
            exit 6
        fi
        if [[ "$actual" != "$m_digest" ]]; then
            echo "TAMPERED $m_name (recorded ${m_digest:0:12}, found ${actual:0:12})" >&2
            bad=$((bad + 1))
        fi
    done < "$MANIFEST_PATH"

    # THE OTHER DIRECTION, and it is the one a digest check usually forgets.
    # Verifying only the rows the manifest lists is trivially bypassed by ADDING
    # a file rather than modifying one: an unlisted script named in HELPERS would
    # be installed without ever being compared to anything. A bundle's manifest
    # is complete by construction - the generator writes a row for every script
    # it bundles - so an unlisted file in a bundle is an addition, and refusing
    # it is what makes the listed-row check mean anything. Scoped to bundles:
    # a hand-placed manifest elsewhere may legitimately be partial.
    if [[ "$IS_BUNDLE" -eq 1 ]]; then
        for f in "$SOURCE_DIR"/*; do
            [[ -f "$f" ]] || continue
            b="${f##*/}"
            [[ "$b" == "$MANIFEST_NAME" ]] && continue
            if [[ -z "${MANIFEST_ROWS[$b]:-}" ]]; then
                echo "TAMPERED $b (present in the bundle, listed in no $MANIFEST_NAME row)" >&2
                bad=$((bad + 1))
            fi
        done
    fi

    if [[ "$listed" -eq 0 ]]; then
        MANIFEST_STATE="empty"
        echo "flow-helpers-install: $MANIFEST_NAME carries no digest rows, so it verifies" >&2
        echo "  nothing. An empty manifest is not a clean one. Nothing installed." >&2
        REASON="manifest-empty"
        emit_provenance
        echo "FLOW_HELPERS: unverifiable-source"
        exit 6
    fi
    if [[ "$bad" -gt 0 ]]; then
        MANIFEST_STATE="mismatch"
        echo "flow-helpers-install: $bad of $listed source file(s) disagree with $MANIFEST_NAME." >&2
        echo "  REFUSING to install. This detects a bundle that changed after it was built;" >&2
        echo "  it does NOT prove the bundle was authentic when it arrived - the manifest" >&2
        echo "  ships inside the bundle it certifies." >&2
        REASON="manifest-mismatch"
        emit_provenance
        echo "FLOW_HELPERS: tampered"
        exit 5
    fi
    MANIFEST_STATE="verified"
    echo "flow-helpers-install: $listed source file(s) match $MANIFEST_NAME"
elif [[ "$IS_BUNDLE" -eq 1 ]]; then
    # A bundle always carries a manifest once generated by codex-skill-sync.py,
    # so its ABSENCE on a bundle is either a pre-#1185 bundle or a manifest that
    # was removed - and deleting the manifest must not be the way past the check.
    MANIFEST_STATE="absent-on-bundle"
    echo "flow-helpers-install: this source is a skill bundle but carries no" >&2
    echo "  $MANIFEST_NAME, so its scripts cannot be verified. Nothing installed." >&2
    echo "  A bundle generated before #1185 predates the manifest: re-generate it." >&2
    REASON="manifest-absent-on-bundle"
    emit_provenance
    echo "FLOW_HELPERS: unverifiable-source"
    exit 6
fi

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
