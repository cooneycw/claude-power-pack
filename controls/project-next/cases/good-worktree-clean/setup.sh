#!/usr/bin/env bash
# The companion GOOD case (issue #1398): the identical unmapped-worktree
# shape, but with its `.git` left intact - a genuinely clean, examinable
# worktree must still get the lighter cleanup action and no false warning.
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
git -C "$FIXTURE/repo" worktree add -q "$FIXTURE/repo-issue-999-ghost" -b issue-999-ghost
