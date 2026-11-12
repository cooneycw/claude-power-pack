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
command -v git >/dev/null 2>&1 || { echo "PROVENANCE_CONTROL: unavailable - git is not on PATH"; exit 3; }
work="$(mktemp -d)" || { echo "PROVENANCE_CONTROL: unavailable - mktemp failed"; exit 3; }
trap 'rm -rf "$work"' EXIT
repo="$work/repo"
if ! { mkdir "$repo" && cp -R "$case_dir"/. "$repo"/; }; then
  echo "PROVENANCE_CONTROL: unavailable - copy failed"; exit 3
fi
g() { git -C "$repo" -c user.name=control -c user.email=control@example.com -c commit.gpgsign=false "$@"; }
{
  git init -q -b main "$repo" &&
  mv "$repo/scripts/toy-gate.sh" "$work/now-toy-gate.sh" &&
  mv "$repo/first-commit-toy-gate.sh" "$repo/scripts/toy-gate.sh" &&
  rm -f "$repo/shallow-clone" &&
  g add -A && g commit -qm "the gate as first written" &&
  first="$(g rev-parse HEAD)" &&
  cp "$work/now-toy-gate.sh" "$repo/scripts/toy-gate.sh" &&
  sed "s/@FIRST_COMMIT@/$first/" "$repo/controls/toy/control.json" > "$work/control.json" &&
  cp "$work/control.json" "$repo/controls/toy/control.json" &&
  g add -A && g commit -qm "the gate as it stands now"
} >/dev/null 2>&1 || { echo "PROVENANCE_CONTROL: unavailable - could not build the fixture repository"; exit 3; }
root="$repo"
if [ -e "$case_dir/shallow-clone" ]; then
  git clone -q --depth 1 "file://$repo" "$work/shallow" >/dev/null 2>&1 ||
    { echo "PROVENANCE_CONTROL: unavailable - could not make the depth-1 clone"; exit 3; }
  root="$work/shallow"
fi
python3 "$harness" --root "$root" --strict --verify-provenance
