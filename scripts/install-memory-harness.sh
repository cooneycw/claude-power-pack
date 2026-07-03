#!/usr/bin/env bash
# Install the harness-neutral common-memory surfaces so BOTH Claude Code and
# Codex can utilize the store:
#   - ~/.local/bin/cpp-memory        -> <repo>/scripts/cpp-memory   (global CLI)
#   - ~/.codex/prompts/cpp-memory.md <- <repo>/codex/prompts/...     (Codex /cpp-memory)
#
# Claude Code already discovers .claude/commands/self-improvement/memory.md in
# the repo. Idempotent; safe to re-run (e.g. from /cpp:update).
set -euo pipefail

SCRIPTS_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPTS_DIR")"

# 1. Global CLI on PATH (~/.local/bin is already on PATH for uv etc.)
mkdir -p "$HOME/.local/bin"
ln -sfn "$REPO_ROOT/scripts/cpp-memory" "$HOME/.local/bin/cpp-memory"
echo "linked: ~/.local/bin/cpp-memory -> $REPO_ROOT/scripts/cpp-memory"

# 2. Codex user-level slash command
mkdir -p "$HOME/.codex/prompts"
cp -f "$REPO_ROOT/codex/prompts/cpp-memory.md" "$HOME/.codex/prompts/cpp-memory.md"
echo "installed: ~/.codex/prompts/cpp-memory.md  (Codex: /cpp-memory)"

echo "done. Claude Code: /self-improvement:memory   Codex: /cpp-memory   shell: cpp-memory"
