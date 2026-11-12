# `worktree-remove` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `worktree-remove`

- worktree-remove
- worktree-remove `--steal` + claim owner check (#597) - refuses with exit 4 to remove a worktree claimed by another LIVE session (printing the owning pid/session), releases a self-owned or stale claim and proceeds otherwise, and takes `--steal` as the deliberate override. One change covers `/flow:auto` Step 7, `/flow:merge` and `/flow:cleanup`, since all three route removal through this script
- worktree-remove live-occupancy guard (#888, follow-on to #597) - the #597 claim protects a worktree only where one was STAKED, and `flow-worktree-claim.sh check` has seven states while the removal `case` handled two pairs: `held|foreign` stopped, `self|stale` released, and `free`, `unsupported` and `unknown` fell through it silently. `free` is not evidence of an idle checkout - it is simply what any worktree created outside the /flow lane reports - so an unclaimed worktree was removed like an abandoned one, and the uncommitted-changes backstop could not catch it either because `--force` skips that check and `/flow:auto` Step 7 always passes `--force`. Found on 2026-09-13 on a live worktree reporting `CLAIM=free` while a session sat in `flow-finish-gate` holding a 21KB staged spec file; the only thing between it and deletion was the #503 mtime heuristic, whose 30-minute window that session had already outlived by being in a long test run - so both guards read "clear" on a checkout that was plainly occupied, which is the two-guards-one-signal shape, not defence in depth. When no claim names THIS session, the script now asks a second question no time window can blind: does a live process have its working directory inside the worktree (`/proc/<pid>/cwd`)? Occupied is a hard stop (exit 5), dirty or clean since #1032 (it was occupied AND dirty when #888 landed), that `--force` does NOT suppress, since a guard `--force` silences never fires where the damage happens; `--steal` overrides as it does for a claim. Deliberately NOT the obvious fix of refusing every unclaimed removal - `free` being the normal state of most worktrees, that converts a rare data-loss bug into an everyday blocker, and `test_idle_and_dirty_still_removed_with_force` pins the ordinary Step-7 path against exactly that over-correction. Occupied-but-clean used to remove, on the argument that with nothing unsaved there was nothing unrecoverable to lose; #1032 refuses it too (the reasoning is in `scripts/worktree-remove.sh`'s header). Path matching is boundary-aware (`<wt>` vs `<wt>-2`) rather than a bare prefix, which is not hypothetical - `kyle-issue-1142` is a real prefix of `kyle-issue-1142-container-spec-superseded` - and the scan excludes its own PID and full ancestor chain, since `/flow:auto` invokes the script from a shell whose cwd may still be the worktree. A host with no readable `/proc` prints `WORKTREE_REMOVE_OCCUPANCY: unknown` and falls open: unchecked must never render as clean, which is the failure the guard exists to remove. `WORKTREE_REMOVE_PROC_ROOT` is a test seam that makes that unscannable lane reachable on a host with a working /proc
- worktree-remove branch attribution + the recycled-pid reading (#1032) - a worktree directory is NAMED for the issue it was created for, but the name is a string and nothing keeps it in step with what is checked out inside. Observed on this host: `...-issue-971-...` (CLOSED, PR #1004 merged) holding branch `issue-980-lexicon-quoted-token` (OPEN) - a cleanup trusting the path would have read "closed, merged, safe" about an open lane's checkout, and survived only because #980 had no commits yet. The script now prints `WORKTREE_REMOVE_ATTRIBUTION: branch=<b> issue=<N> [dirname-issue=<M> DISAGREE | agree | dirname-unkeyed]` naming the BRANCH as authoritative, and on a disagreement REFUSES `--delete-branch` with exit 8: removing a directory is local and recoverable, deleting the wrong issue's branch is neither. Confirmed against the pre-fix script, which exited 0 and deleted issue #980's branch when handed the #971 path. Comparison is on the issue NUMBER alone, never the slug - a branch legitimately keeps an older title's slug while the issue is renamed (#793), so matching full names would fire on the ordinary case, and a guard that fires on the normal case is one everybody learns to pass with the override. `--force` does NOT override it (Step 7 passes `--force` every run); `--steal` does. The refusal is deliberately the LAST check reached: every other refusal means "do not remove this at all", while this one means only "do not also delete the branch" and its remedy still removes the directory - reached earlier it would hand that remedy to a caller whose tree the occupancy or claim guard had already refused. It also relays the claim's new `identity` field, so `stale` from a recycled pid is distinguishable from `stale` because the owner exited
- worktree-remove (#1262) the exit-7 unpushed refusal now NAMES its coupling to `gh-pr-merge.sh`: after a squash a branch's commits are on no remote ref by construction, the only evidence this helper accepts that they LANDED is `branch.<name>.cpp-merged-head`, and its only writer is `gh-pr-merge.sh`. A PR merged any other way (web UI, plain `gh pr merge`) has no record and arrived here described as unpushed work with no hint why

## Commentary moved out of the script (#1693)

Everything below was in `scripts/worktree-remove.sh` at `4c8aa79a` and was removed or condensed there by issue #1693. It is kept here verbatim, with the line numbers it had at that commit, so the script reads shorter and nothing is lost.

Lines 71-122:

````text
# POSITIVE OWNERSHIP, NEVER DISCOVERY (issue #1524). A half-deleted worktree
# has no .git file, so the normal path below - which derives the main
# repository FROM the worktree's own .git file - cannot run at all; there is
# nothing left to read. An earlier version of this flag (#1491, reverted
# 20e72086) tried to find the owner by searching sibling and ancestor
# directories for a repo that still lists the path. Three cross-model review
# passes each found a new variant of the same structural gap: a repo that
# TRUTHFULLY does not have the path registered answers "not registered"
# exactly like a repo that was simply never asked, and a proximity search
# cannot tell those apart. There is no global worktree registry to query, so
# "nobody nearby admits to owning this" can never mean "nobody owns this" -
# only "I did not ask the right repo". The redesign removes the search
# entirely: the caller must NAME the owner with --owner-repo, and that repo's
# own registry must say so, in git's own words - a `prunable` attribute on
# the exact matching record - or this script refuses. A read failure (the
# porcelain call itself fails) is also a refusal, never a silent "proceed
# because nothing said no".
#
# VERIFY-AND-PRINT, NOT AUTO-REMOVE (issue #1524, owner decision after a
# third review pass still found a real defect). Across three cross-model
# review passes on this flag's positive-ownership redesign, EACH pass found
# a genuine path-handling defect the previous pass's fix had not closed: a
# newline guard checking the wrong value, a missing dirty/unpushed
# requirement, `readlink -f`'s own trailing-newline loss, and finally a
# normalization step SHARED with the normal removal path below (see its own
# newline guard, right after "Worktree path is required") that could
# silently substitute a different target before any of this branch's checks
# ever ran. Three passes is this repository's ceiling for one change. Rather
# than ship a fourth attempt at automatic `rm -rf` with no further review,
# --finish-partial-removal now VERIFIES every precondition exactly as before
# (positive ownership, occupancy, the undeletable pre-scan, dirty, unpushed)
# and, on a pass, PRINTS the exact command for a human to run - it removes
# nothing itself. Every defect the three passes found was in path handling
# feeding an automatic deletion; none of them survive as a hazard once the
# deletion itself is a human's own typed (or pasted) command.
#
# `worktree prune` is deliberately never run OR printed as a ready command:
# it prunes every eligible stale entry in the owner's WHOLE registry, not
# only the one target this script verified, and could drop an unrelated
# stale worktree's registration that nothing here has checked. A
# `--dry-run --verbose` hint is printed instead, so a human can see exactly
# what pruning would affect before deciding to run it.
#
# A symlink in the PATH ITSELF is never named in the printed `rm -rf`. If the
# caller passes a path whose final component is a symlink pointing at the
# worktree, `rm -rf` on the symlink would remove only the link - the real
# worktree directory would survive untouched, an orphan indistinguishable
# from the outside from "this was never a worktree". This script resolves
# the input ONCE via `realpath`, before any comparison, and uses that
# resolved path for both the registry match and the printed command - never
# the caller's own symlink, which may live anywhere (a different repo, a
# home directory) and is not part of the worktree this script verifies.
````

Lines 225-286:

````text
            echo "Usage: worktree-remove.sh <worktree-path> [--force] [--delete-branch] [--steal] [--allow-dirty] [--allow-unpushed]"
            echo ""
            echo "Safely remove git worktrees. If you're currently inside the worktree"
            echo "being removed, the script automatically changes to the main repository"
            echo "first to prevent breaking your shell session."
            echo ""
            echo "Options:"
            echo "  --force          Pass --force to 'git worktree remove' (the worktree is"
            echo "                   busy). It does NOT override the data-loss refusals below"
            echo "                   - being busy is not the same as being expendable (#899)"
            echo "  --delete-branch  Also delete the associated branch after removal"
            echo "                   (force-deletes a squash-merged branch non-interactively)"
            echo "  --steal          Remove even when another live /flow session claims it"
            echo "                   (issue #597; without it a live claim is a hard stop)"
            echo "  --allow-dirty    Remove even though uncommitted work would be destroyed"
            echo "                   (issue #899; exit 6 without it; implies --force, since"
            echo "                   git worktree remove makes its own separate dirty-tree"
            echo "                   judgment, Nit Store #864)"
            echo "  --allow-unpushed Remove even though commits exist on no remote ref"
            echo "                   (issue #899; exit 7 without it)"
            echo "  --finish-partial-removal"
            echo "                   VERIFY (never remove) a worktree already left half-"
            echo "                   deleted (no .git file). On a pass, PRINTS the rm -rf"
            echo "                   command for a human to run - never runs it. Requires"
            echo "                   --owner-repo AND --allow-dirty - there is no .git left"
            echo "                   to verify the directory is clean. Also needs"
            echo "                   --allow-unpushed, but only if the owner's own refs show"
            echo "                   HEAD is actually unreachable from a remote (#1524)"
            echo "  --owner-repo <path>"
            echo "                   The repo whose own registry must positively list the"
            echo "                   target as prunable. Required by --finish-partial-removal"
            echo ""
            echo "Each refusal has its own override on purpose: one flag that silenced all"
            echo "three would be one flag away from silencing everything."
            echo ""
            echo "Exit codes:"
            echo "  0  removed (or already absent - stale refs pruned); normal path only"
            echo "  1  usage, path, or repository validation error"
            echo "  4  claimed by another live /flow session (#597)"
            echo "  5  in use by a live process (#888, #1032)"
            echo "  6  holds uncommitted work without --allow-dirty (#899)"
            echo "  7  holds commits on no remote ref without --allow-unpushed (#899); for"
            echo "     --finish-partial-removal this is checked via the owner's own refs"
            echo "  8  --delete-branch asked for, but the directory name and the"
            echo "     checked-out branch name different issues (#1032)"
            echo "  9  a path cannot be deleted (parent directory not writable) (#864)"
            echo " 10  --finish-partial-removal/--owner-repo given without the other (#1524)"
            echo " 11  a literal newline in the argument (any invocation), --owner-repo, or"
            echo "     the resolved target (--finish-partial-removal) - refused (#1524)"
            echo " 12  --owner-repo is not a readable git working tree (#1524)"
            echo " 13  --owner-repo's registry does not positively list the path as"
            echo "     prunable (#1524)"
            echo " 14  --finish-partial-removal without --allow-dirty (#1524)"
            echo " 15  --finish-partial-removal: VERIFIED, not removed - printed instead (#1524)."
            echo "     Distinct from 2 on purpose: a failing grep or bash builtin under"
            echo "     set -euo pipefail also exits 2 elsewhere in this script."
            echo ""
            echo "Examples:"
            echo "  worktree-remove.sh /home/user/Projects/nhl-api-issue-42"
            echo "  worktree-remove.sh ../nhl-api-issue-42 --delete-branch"
            echo "  worktree-remove.sh /path/to/half-deleted-wt --finish-partial-removal \\"
            echo "      --owner-repo /path/to/main --allow-dirty --allow-unpushed"
````

Lines 307-319:

````text
# Codex cross-model review (issue #1524, pass 3, HIGH): reject a literal
# newline in the RAW argument for EVERY invocation, before any
# normalization - not only inside --finish-partial-removal. The relative-
# path resolution two blocks below is command substitution wrapped around
# `basename`, and `basename` always appends its OWN trailing newline; when
# the argument's last byte is already a newline, that becomes two
# consecutive trailing newlines, and command substitution strips ALL of
# them. Verified directly: a relative argument "collider" + a literal
# trailing newline normalizes to the newline-free sibling "collider" - the
# SAME hazard --finish-partial-removal's own newline guards exist to close,
# reached through the NORMAL removal path instead, which has no guard of
# its own and would act on whatever that newline-free name happens to name.
# One guard, here, before normalization, closes it for both paths at once.
````

Lines 351-359:

````text
# Resolve to absolute path. REFUSE if the parent cannot be entered, for
# EVERY invocation (pass-4 supplementary review, cnb-orch + Gemini): the old
# single-expression form silently substituted "" for a `cd` failure, so
# WORKTREE_PATH became "/$(basename ...)" - an absolute, filesystem-ROOT
# path unrelated to the argument's actual (missing) parent directory - and
# the script carried on as if that had been the caller's intent all along.
# Splitting the `cd` out and checking its own exit status, rather than
# trusting the combined command substitution's output, is what makes a
# resolution failure visible instead of silently reinterpreted.
````

Lines 362-362:

````text
    WT_REAL_DIR="$(cd -- "$WT_DIR_PART" 2>/dev/null && pwd)" || {
````

Lines 381-388:

````text

# Hoisted here (originally defined just above their own call sites further
# down) so --finish-partial-removal's own branch - which runs much earlier,
# at the "no .git file" check below, before a normal worktree's main
# repository can even be derived - can call them too. Moving a pure function
# definition earlier changes nothing about its later call site; bash just
# needs the definition to have executed before the first call, wherever that
# call is.
````

Lines 579-591:

````text
    # --finish-partial-removal (issue #1524): POSITIVE OWNERSHIP ONLY, never
    # discovery. See the header comment above for why - three cross-model
    # review passes on the earlier discovery-based version each found a new
    # variant of the same structural gap, and it was removed entirely rather
    # than patched again.
    #
    # The raw-argument newline guard that used to live here (red case 2) is
    # now global, applied before normalization, before this branch is even
    # reached - see the check near the top of the script, right after
    # "Worktree path is required". Kept here only as this comment, not as a
    # second (unreachable) check: a naive line-based parse of the registry
    # still cannot survive a newline, which is why the NUL-delimited parser
    # below exists independently of that guard.
````

Lines 604-620:

````text
    # Codex cross-model review (issue #1524, pass 2, HIGH): the shared WT_REAL
    # above is plain command substitution, which strips ALL trailing newlines
    # from its OWN captured output - so a pass-1 fix that checked "$WT_REAL"
    # for an embedded newline could never see one in the trailing position,
    # because bash had already removed it before the check ran. Verified
    # directly: a symlink to a directory named "target\n" resolves through
    # that form to WT_REAL with no trailing \n at all.
    #
    # Resolved AGAIN here, robustly, for THIS branch only (never touching the
    # shared WT_REAL the normal path above already relies on). Capture with a
    # non-newline sentinel appended in the SAME command substitution, so
    # nothing trailing gets stripped; then peel the sentinel and exactly the
    # ONE newline `readlink -f` itself always appends as its own line
    # terminator - whatever newline remains after that is part of the real
    # resolved path, not readlink's formatting. A readlink FAILURE is a hard
    # refusal: never fall back to the raw, unresolved argument the way the
    # shared WT_REAL computation does for the normal path.
````

Lines 718-731:

````text
    # Codex cross-model review (issue #1524, pass 1, HIGH): the ORIGINAL
    # version of this branch ran no dirty-tree check at all, reasoning that
    # `git status` needs the worktree's own .git, which is already gone -
    # "nothing left to check". That reasoning proved too much: removing
    # `.git` does not remove the FILES. A worktree with real uncommitted
    # edits or untracked work sitting in it is still full of exactly that
    # content, and this branch would delete it unconditionally - the state
    # cannot be verified clean, which is the opposite of permission to treat
    # it as clean. --allow-dirty is now REQUIRED for --finish-partial-removal,
    # not merely honoured: there is no `git status` to ask, so the caller
    # must affirmatively accept that whatever is on disk may be destroyed,
    # exactly as the explicit-override convention above requires for every
    # other data-loss path. Checked FIRST, same order as the normal path
    # below (dirty, then unpushed).
````

Lines 819-830:

````text
    # decision after a pass-3 HIGH: three review passes each found a real
    # path-handling defect in this branch - a newline guard that checked the
    # wrong value, a missing dirty/unpushed requirement, a readlink
    # trailing-newline loss, and finally a SHARED normalization step that
    # could silently swap the target before any of this branch's own guards
    # ever ran. That is the three-pass ceiling, so this ships as verification
    # only: everything above (positive ownership, occupancy, the undeletable
    # pre-scan, dirty, unpushed) still runs and still refuses on exactly the
    # same conditions - what changes is that a PASS prints the exact command
    # for a human to run, rather than running it. `printf %q` quotes the path
    # so the printed line is safe to copy-paste even if it contains shell
    # metacharacters this review process has not had cause to think about.
````

Lines 833-838:

````text
    # it prunes every eligible stale entry in the OWNER's whole registry
    # (pass 3, MEDIUM), not just the one target this branch verified - a
    # second, unrelated stale worktree could lose its registration with none
    # of the checks above having looked at it. A `--dry-run --verbose` hint
    # is printed instead, so the human can see exactly what pruning would
    # drop before deciding to run it themselves.
````

Lines 894-899:

````text
# is just a string and nothing keeps it in step with what is checked out inside.
# Observed on this host: a directory named `...-issue-971-...` (CLOSED, PR #1004
# merged) holding the branch `issue-980-lexicon-quoted-token` (OPEN). Anything
# deciding "safe to delete" from the directory name would have read "closed and
# merged, safe" and destroyed an open lane's checkout. It survived only because
# #980 happened to have no commits of its own yet.
````

Lines 1067-1073:

````text
# That is how a LIVE session loses unsaved work. On 2026-09-13 a session sitting
# in `flow-finish-gate` held a 21KB staged file in a worktree reporting
# CLAIM=free; the only thing between it and deletion was the #503 mtime
# heuristic, whose 30-minute window that session had already outlived by being
# in a long test run. Both guards read "clear" on a checkout that was plainly
# occupied.
#
````

Lines 1082-1085:

````text
#
# WT_REAL, occupancy_self_pids, PROC_ROOT and occupancy_scan are all defined
# earlier now (issue #1524), so --finish-partial-removal's own branch can use
# them too - see the comment there.
````

Lines 1354-1357:

````text
#
# undeletable_find (and its sticky-bit-aware sticky_dir_is_safe helper,
# issue #1520) are defined earlier now (issue #1524), so
# --finish-partial-removal's own branch can call them too.
````

Lines 1399-1404:

````text
# The old interactive `read -p` confirmation broke every non-interactive caller
# (/flow:auto, /flow:merge): with stdin not a TTY, `read` hit EOF and returned
# non-zero, tripping `set -e` so the whole script exited non-zero AND left the
# branch undeleted - a false "cleanup failed" even though the worktree removal
# succeeded (issue #566). Branch-delete outcome never fails the script now: the
# worktree removal (above) is the only step whose failure surfaces non-zero.
````
