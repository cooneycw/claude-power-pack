#!/bin/sh
# run-case.sh <case-dir> <harness> - build a throwaway git repository from one
# case and run the harness over it with --strict --verify-provenance.
#
# A case cannot carry a .git directory, and a historical anchor is a claim
# about a COMMIT, so the history is made here: the first commit holds the gate
# as first written (first-commit-toy-gate.sh), the second the gate as it stands
# now, and the fixture manifest's @FIRST_COMMIT@ is filled with the first
# commit's id. A case with a `shallow-clone` file is then run in a depth-1
# clone, where that first commit does not exist.
set -u
case_dir="$1"; harness="$2"
provenance_flag="${3:---verify-provenance}"
[ "$provenance_flag" = "--verify-provenance" ] || exit 3
command -v git >/dev/null 2>&1 || { echo "PROVENANCE_CONTROL: unavailable - git is not on PATH"; exit 3; }
work="$(mktemp -d)" || { echo "PROVENANCE_CONTROL: unavailable - mktemp failed"; exit 3; }
trap 'rm -rf "$work"' EXIT
repo="$work/repo"
if ! { mkdir "$repo" && cp -R "$case_dir"/. "$repo"/; }; then
  echo "PROVENANCE_CONTROL: unavailable - copy failed"; exit 3
fi
g() { git -C "$repo" -c user.name=control -c user.email=control@example.com -c commit.gpgsign=false "$@"; }
anchor_commit() {
  first="$(g rev-parse HEAD)" || return 1
  if [ -e "$case_dir/off-main-anchor" ]; then
    g checkout -qb side && g commit --allow-empty -qm "anchor retained only by a side branch" &&
      first="$(g rev-parse HEAD)" && g checkout -q main || return 1
    # The negative precondition is topology, not a different blob.
    g merge-base --is-ancestor "$first" main
    [ "$?" -eq 1 ] || return 1
  fi
  return 0
}
{
  git init -q -b main "$repo" &&
  mv "$repo/scripts/toy-gate.sh" "$work/now-toy-gate.sh" &&
  mv "$repo/first-commit-toy-gate.sh" "$repo/scripts/toy-gate.sh" &&
  rm -f "$repo/shallow-clone" &&
  g add -A && g commit -qm "the gate as first written" &&
  anchor_commit &&
  cp "$work/now-toy-gate.sh" "$repo/scripts/toy-gate.sh" &&
  sed "s/@FIRST_COMMIT@/$first/" "$repo/controls/toy/control.json" > "$work/control.json" &&
  cp "$work/control.json" "$repo/controls/toy/control.json" &&
  g add -A && g commit -qm "the gate as it stands now"
} >/dev/null 2>&1 || { echo "PROVENANCE_CONTROL: unavailable - could not build the fixture repository"; exit 3; }
if [ -e "$case_dir/no-main-reference" ] || [ -e "$case_dir/detached-main-reference" ]; then
  if [ -e "$case_dir/detached-main-reference" ]; then
    g update-ref refs/remotes/origin/main HEAD || exit 3
  fi
  g checkout -q --detach && g branch -D main >/dev/null || exit 3
  # A detached HEAD is not permission to guess which branch retains history.
  g show-ref --verify --quiet refs/heads/main
  [ "$?" -eq 1 ] || exit 3
fi
root="$repo"
if [ -e "$case_dir/shallow-clone" ]; then
  git clone -q --depth 1 "file://$repo" "$work/shallow" >/dev/null 2>&1 ||
    { echo "PROVENANCE_CONTROL: unavailable - could not make the depth-1 clone"; exit 3; }
  root="$work/shallow"
fi
python3 "$harness" --root "$root" --strict "$provenance_flag"
