#!/usr/bin/env bash
# Builds the fixture at $1: a real git repo plus a worktree whose OWN `.git`
# file is removed after `git worktree add`, so `git status --short` run
# inside it fails with "not a git repository" - a genuine, portable failure,
# not a fiction (issue #1398). Sourced by the control's invocation, which
# also arranges a fake `gh` on PATH so the real `scripts/project-next.py` CLI
# needs no network or token.
set -eu
FIXTURE="$1"
mkdir -p "$FIXTURE/bin"
cat > "$FIXTURE/bin/gh" <<'SH'
#!/usr/bin/env bash
case "$1 $2" in
  "repo view") echo '{"nameWithOwner":"example/control","defaultBranchRef":{"name":"main"},"url":"https://example.invalid/control"}' ;;
  "issue list") echo '[]' ;;
  "pr list") echo '[]' ;;
  *) echo '[]' ;;
esac
SH
chmod +x "$FIXTURE/bin/gh"
export PATH="$FIXTURE/bin:$PATH"

git init -q -b main "$FIXTURE/repo"
git -C "$FIXTURE/repo" config user.email c@c
git -C "$FIXTURE/repo" config user.name c
git -C "$FIXTURE/repo" config commit.gpgsign false
echo base > "$FIXTURE/repo/base.txt"
git -C "$FIXTURE/repo" add -A
git -C "$FIXTURE/repo" commit -qm base
git -C "$FIXTURE/repo" remote add origin "$FIXTURE/repo"
# Unmapped (issue #999 does not exist in the fake `gh issue list` above), so
# this worktree is a CLEANUP CANDIDATE - the exact shape whose action text
# and off-open-issue warning differ between the anchor and the fix.
git -C "$FIXTURE/repo" worktree add -q "$FIXTURE/repo-issue-999-ghost" -b issue-999-ghost
rm -f "$FIXTURE/repo-issue-999-ghost/.git"
