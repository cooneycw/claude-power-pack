#!/usr/bin/env bash
# run-arms.sh - the EFFECT-BASED differential.
#
# WHY NOT A CONTENT ARTIFACT. Asking codex to describe CPP proves nothing: CPP
# is a public repository and the model demonstrably knows it in detail. Measured
# 2026-09-21, an arm with NO CPP surface named `stash-worktree-guard.sh` - a real
# script in scripts/ that is not in flow-doctor's bundle. It did not invent a
# plausible name; it RECALLED a real one. So the proof measures a filesystem
# EFFECT, not prose.
#
# WHY THE NEGATIVE ARM IS NOT READ-ONLY. A read-only negative arm would prove
# only that a crippled arm writes nothing. Both arms get FULL write capability
# (--dangerously-bypass-approvals-and-sandbox, correct here because bwrap is the
# external sandbox). The arm may write whatever it likes. What it cannot do is
# produce the helper's BYTES: three files totalling 79,496 bytes, byte-identical
# to the checkout. Knowing a filename is cheap; reproducing 79KB exactly is not.
#
# Exactly ONE variable differs between the arms: whether CPP's surface
# (~/.codex/skills/flow-doctor) is present.
#
# Usage: run-arms.sh <positive|negative> [repo-root]
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARM="${1:?usage: run-arms.sh <positive|negative> [repo-root]}"
REPO="${2:-$(git -C "$HERE" rev-parse --show-toplevel)}"
OUT="${OUT_DIR:-$PWD}"
case "$ARM" in positive) SURFACE=present ;; negative) SURFACE=absent ;;
  *) echo "arm must be positive or negative" >&2; exit 2 ;; esac

SB="$OUT/arm-$ARM"; rm -rf "$SB"; mkdir -p "$SB/.codex/skills" "$SB/work"
cp "$HOME/.codex/auth.json" "$SB/.codex/"; chmod 600 "$SB/.codex/auth.json"
cp "$HOME/.codex/installation_id" "$SB/.codex/" 2>/dev/null
printf 'model = "%s"\nmodel_reasoning_effort = "high"\n\n[projects."/home/clean/work"]\ntrust_level = "trusted"\n' \
    "${CODEX_MODEL:-gpt-6-astra}" > "$SB/.codex/config.toml"
[ "$SURFACE" = present ] && cp -r "$REPO/codex/skills/flow-doctor" "$SB/.codex/skills/"

# IDENTICAL in both arms. Phrased as a user would, not as a leading question.
PROMPT='Run the flow-doctor workflow on this machine: diagnose the flow workflow setup and install the CPP flow helper scripts into ~/.claude/scripts. Then report exactly which files you installed.'

# stdin MUST be closed. `codex exec` otherwise blocks on "Reading additional
# input from stdin..." forever, which reads as a slow run, not a hang.
"$HERE/clean-host.sh" "$SB" /opt/codex/bin/codex exec \
  --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --color never \
  -C /home/clean/work --output-last-message /home/clean/LAST.md "$PROMPT" \
  < /dev/null > "$OUT/$ARM.log" 2>&1
echo "ARM=$ARM surface=$SURFACE codex_exit=$?"

# The measurement. Digests, not filenames: a filename is recallable, bytes are not.
#
# MEASURE FROM INSIDE THE NAMESPACE. The installer installs by SYMLINK when its
# source is a checkout (and by copy when it is a plugin bundle), and those links
# are absolute into /home/clean - a path that exists ONLY inside bwrap. Measured
# from the host, all 29 of them stat as broken and hash as nothing, which reads
# exactly like a model that fabricated 29 plausible filenames and wrote no bytes.
# They were real, resolving, canonical-digest links. A measurement taken outside
# the namespace its subject lives in does not return an error; it returns a
# confident wrong answer.
echo "--- effect in ~/.claude/scripts (resolved INSIDE the sandbox) ---"
"$HERE/clean-host.sh" "$SB" /bin/bash -c '
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
# Did the arm leave the clean-host premise by fetching CPP over the network?
for c in /home/clean/.claude-power-pack /home/clean/cpp /home/clean/work/claude-power-pack; do
    [ -d "$c/.git" ] && echo "  NETWORK-ACQUIRED CHECKOUT: $c at $(git -C "$c" rev-parse HEAD)"
done
true'

# A harness that cannot write reports "nothing written" identically to a real
# negative. probe-write.sh is the positive control that separates them.
echo "--- harness health: IPC decode errors (non-zero invalidates this arm) ---"
grep -c 'code_mode_host_duration_ns' "$OUT/$ARM.log"
