#!/usr/bin/env bash
# KNOWN-BAD: a defer request the helper must honour, where the caller spells
# the surface `~/.bashrc` and the helper resolves its target from $HOME.
#
# THE SPELLING IS THE WHOLE CASE. A defer spelled "$HOME/.bashrc" matches by
# plain string equality even with normalisation broken, so it cannot tell a
# working helper from the pre-fix one. Only the MIXED spelling discriminates,
# and choosing the input that happens to pass is how a control ends up proving
# nothing. Correct verdict: 3, refused, and ~/.bashrc absent afterwards.
GATE="${1:?gate path required}"
H=$(mktemp -d) || exit 1
trap 'rm -rf "$H"' EXIT
printf 'marker-content\n' > "$H/content.txt"
HOME="$H" bash "$GATE" bashrc-append '# cpp-control-marker' "$H/content.txt" --defer '~/.bashrc'
rc=$?
# A refusal that exits 3 having WRITTEN the file is the pre-fix defect, and it
# is not visible from the exit code alone. Check the surface, not the verdict.
if [ -f "$H/.bashrc" ]; then
    printf 'cpp-host-write: WROTE A DEFERRED SURFACE - ~/.bashrc exists after a refusal\n'
    exit 0
fi
exit "$rc"
