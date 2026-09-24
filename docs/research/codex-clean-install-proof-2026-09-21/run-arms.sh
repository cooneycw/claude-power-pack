#!/usr/bin/env bash
# run-arms.sh - the EFFECT-BASED differential.
#
# WHY NOT A CONTENT ARTIFACT. Asking codex to describe CPP and checking the answer
# cannot isolate anything, because CPP is a PUBLIC repository: measured with no
# model involved, a sandbox holding zero CPP skills clones it and obtains
# worktree-remove.sh at the canonical digest. Content is reachable without the
# bundle. So the proof measures a filesystem EFFECT.
#
# WHY THE NEGATIVE ARM IS NOT READ-ONLY. A read-only negative arm proves only that
# a crippled arm writes nothing. Both arms get FULL write capability
# (--dangerously-bypass-approvals-and-sandbox, correct here because bwrap is the
# external sandbox). The arm may write whatever it likes.
#
# WHAT THIS CAN AND CANNOT CONCLUDE. It measures what appeared and where it came
# from. It does NOT establish that the negative arm COULD NOT have produced the
# bytes - it could, by cloning. Emptiness here is an observation, not a guarantee.
#
# Exactly ONE variable differs between the arms: whether CPP's surface
# (~/.codex/skills/flow-doctor) is present.
#
# Exit: 0 = valid run, 2 = setup refused, 3 = run invalidated (harness fault).
# Usage: run-arms.sh <positive|negative> [repo-root]
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARM="${1:?usage: run-arms.sh <positive|negative> [repo-root]}"
REPO="${2:-$(git -C "$HERE" rev-parse --show-toplevel)}"
OUT="${OUT_DIR:-$PWD}"
case "$ARM" in positive) SURFACE=present ;; negative) SURFACE=absent ;;
  *) echo "arm must be positive or negative" >&2; exit 2 ;; esac

die() { echo "run-arms: REFUSED - $*" >&2; exit 2; }

# SETUP IS CHECKED, because an unchecked setup mislabels the arm. Without this, a
# nonexistent repo path makes `cp -r` fail, the arm still runs, and it is still
# recorded `surface=present` while having no surface at all - a negative arm
# wearing the positive arm's label, which is the one confusion this design cannot
# survive (counter-model review, gpt-6-astra).
[ -f "$HOME/.codex/auth.json" ] || die "no $HOME/.codex/auth.json; a clean host cannot authenticate (401)"
if [ "$SURFACE" = present ]; then
    [ -d "$REPO/codex/skills/flow-doctor" ] || die "no flow-doctor bundle under '$REPO'"
fi

SB="$OUT/arm-$ARM"
rm -rf "$SB" || die "could not clear $SB"
mkdir -p "$SB/.codex/skills" "$SB/work" || die "could not create $SB"
cp "$HOME/.codex/auth.json" "$SB/.codex/" || die "could not stage credentials"
chmod 600 "$SB/.codex/auth.json" || die "could not chmod credentials"
cp "$HOME/.codex/installation_id" "$SB/.codex/" 2>/dev/null
printf 'model = "%s"\nmodel_reasoning_effort = "high"\n\n[projects."/home/clean/work"]\ntrust_level = "trusted"\n' \
    "${CODEX_MODEL:-gpt-6-astra}" > "$SB/.codex/config.toml" || die "could not write config"
if [ "$SURFACE" = present ]; then
    cp -r "$REPO/codex/skills/flow-doctor" "$SB/.codex/skills/" || die "could not stage the flow-doctor bundle"
fi

# ASSERT THE SURFACE STATE WE ARE ABOUT TO ATTRIBUTE RESULTS TO.
# shellcheck disable=SC2012  # frozen research artifact; skill dir names are plain (#972)
SKILLS=$(ls "$SB/.codex/skills" 2>/dev/null | wc -l)
case "$SURFACE" in
    present) [ "$SKILLS" -ge 1 ] || die "surface=present but 0 skills staged" ;;
    absent)  [ "$SKILLS" -eq 0 ] || die "surface=absent but $SKILLS skill(s) present" ;;
esac
# ASSERT THE DESTINATION IS EMPTY, or "what appeared" is not this run's doing.
[ -e "$SB/.claude/scripts" ] && die "destination ~/.claude/scripts already exists before the run"

# IDENTICAL in both arms. Phrased as a user would, not as a leading question.
PROMPT='Run the flow-doctor workflow on this machine: diagnose the flow workflow setup and install the CPP flow helper scripts into ~/.claude/scripts. Then report exactly which files you installed.'

# ONE bwrap invocation for the run AND the measurement.
#
# Splitting them is a false-negative generator: clean-host.sh mounts a fresh
# `--tmpfs /tmp`, so a second invocation destroys anything the arm put under /tmp.
# An arm that cloned to /tmp/cpp and symlinked from there would have every link
# read as BROKEN, and an install under /tmp would measure as "(nothing written)" -
# the harness manufacturing the empty result the differential treats as its
# headline finding (counter-model review, gpt-6-astra).
#
# Measuring from inside also fixes the namespace error: install-by-symlink uses
# absolute /home/clean targets that resolve ONLY in here.
# shellcheck disable=SC2016  # the script body expands inside the sandbox, not here (#972)
"$HERE/clean-host.sh" "$SB" /bin/bash -c '
set -uo pipefail
/opt/codex/bin/codex exec \
  --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --color never \
  -C /home/clean/work --output-last-message /home/clean/LAST.md "$1" < /dev/null
echo "CODEX_EXIT=$?"
echo "--- effect in ~/.claude/scripts ---"
D=/home/clean/.claude/scripts
if [ -d "$D" ] && [ -n "$(ls -A "$D" 2>/dev/null)" ]; then
    for f in "$D"/*; do
        k=file; [ -L "$f" ] && k=link
        if [ -e "$f" ]; then
            printf "  %-28s %-5s %7d  sha256=%s\n" "$(basename "$f")" "$k" "$(stat -Lc%s "$f")" "$(sha256sum "$f" | cut -d" " -f1)"
        else
            printf "  %-28s %-5s BROKEN -> %s\n" "$(basename "$f")" "$k" "$(readlink "$f")"
        fi
    done
    echo "  entries=$(ls "$D" | wc -l) broken=$(find "$D" -xtype l | wc -l)"
else
    echo "  (nothing written)"
fi
# PROVENANCE, DERIVED NOT HARDCODED. Three hardcoded paths missed a clone to any
# fourth path and fired on an unrelated `git init` at one of them, so absence
# proved nothing and presence named nothing. Walk the home, and report each
# checkout WITH ITS ORIGIN, so "a CPP clone" is distinguishable from "a repo".
echo "--- git checkouts under \$HOME (identity shown; this is an OBSERVATION, not a network record) ---"
found=0
while IFS= read -r g; do
    r="${g%/.git}"
    printf "  %s  origin=%s  head=%s\n" "$r" "$(git -C "$r" remote get-url origin 2>/dev/null || echo none)" "$(git -C "$r" rev-parse HEAD 2>/dev/null || echo unknown)"
    found=1
done < <(find /home/clean -maxdepth 4 -name .git -type d 2>/dev/null)
[ "$found" -eq 0 ] && echo "  (none observed)"
true' _ "$PROMPT" > "$OUT/$ARM.log" 2>&1
WRAP_EXIT=$?

# HARNESS HEALTH. Match the RUNTIME ERROR RECORD, not the bare field name: a
# transcript that merely echoes "code_mode_host_duration_ns" (a model explaining
# the failure, or this very comment being cat'd) is not an IPC fault. Anchoring on
# the substring made the checker match its own subject matter - the exact hazard
# this artifact documents, committed into the instrument that documents it.
IPC=$(grep -cE 'ERROR +codex_core::tools::router: *error=.*code-mode' "$OUT/$ARM.log")
RAN=$(grep -c 'CODEX_EXIT=' "$OUT/$ARM.log")

echo "ARM=$ARM surface=$SURFACE skills_staged=$SKILLS wrapper_exit=$WRAP_EXIT"
sed -n '/--- effect in/,$p' "$OUT/$ARM.log"
echo "--- harness health ---"
echo "  ipc_error_records=$IPC  completed_run_markers=$RAN"

# INVALIDATE EXPLICITLY. Previously the script ended on `grep -c`, so it exited 1
# when the log was CLEAN and 0 when it carried an invalidating error - the status
# was inverted, and a caller trusting it would accept exactly the runs it should
# have thrown away.
if [ "$RAN" -eq 0 ]; then
    echo "  VERDICT: INVALID - no completed-run marker; this arm's emptiness is meaningless" >&2
    exit 3
fi
if [ "$IPC" -gt 0 ]; then
    echo "  VERDICT: INVALID - $IPC IPC decode error record(s); see probe-write.sh" >&2
    exit 3
fi
echo "  VERDICT: valid"
