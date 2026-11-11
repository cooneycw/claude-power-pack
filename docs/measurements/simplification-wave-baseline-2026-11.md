# Simplification wave baseline - 2026-11-11

The "before" reading for the flow and cicd simplification wave (issue #1673).
Wave close re-runs the commands below and reports both columns. Measured on
`origin/main` at `15521b1e`.

## What this does and does not establish

- Line counts are counts of tracked lines, comments and blank lines included.
  They measure how much there is to read and maintain, not how much executes.
- A `fix` title is not proof of a defect in earlier work; some are hardening.
  The fix:feat ratio depends on how pull requests are titled, so it is a prompt
  to look and the line counts are the firmer measure (#1673 says the same).
- The areas are defined by the path globs below and by title scope. A change
  that moves code out of a glob without deleting it lowers the count here and
  is not a simplification; wave close names any such move.

## Line counts

| Area | Glob | Files | Lines |
|---|---|---|---|
| flow scripts | `scripts/flow-*` | 22 | 21,763 |
| flow commands | `.claude/commands/flow/*` | 15 | 8,163 |
| cicd library | `lib/cicd/**` | 37 | 18,302 |
| cicd commands | `.claude/commands/cicd/*` | 12 | 1,497 |
| flow tests | `tests/test_flow_*` | 40 | 33,732 |
| cicd tests | `tests/*cicd*` | 21 | 7,424 |
| flow controls | `controls/flow-*/**` | 314 | 42,143 |
| merge and cleanup tail | `scripts/gh-pr-merge.sh`, `scripts/worktree-remove.sh` | 2 | 3,657 |

```bash
for g in 'scripts/flow-*' '.claude/commands/flow/*' 'lib/cicd/**' \
         '.claude/commands/cicd/*' 'tests/test_flow_*' 'tests/*cicd*' 'controls/flow-*/**'; do
    n=$(git ls-files -- "$g" | wc -l)
    l=$(git ls-files -z -- "$g" | xargs -0 -r cat | wc -l)
    echo "$g files=$n lines=$l"
done
wc -l scripts/gh-pr-merge.sh scripts/worktree-remove.sh
```

A glob that matches no file prints `files=0 lines=0`. Read that as "the glob
is wrong or the area moved", never as "the area is now empty".

## Fix commits per file, 2026-09-12 to 2026-11-11

Commits on `origin/main` whose subject starts with `fix`, counted once per file
they touch.

| File | Fix commits | Lines |
|---|---|---|
| `.claude/commands/flow/auto.md` | 36 | owned by #1669 |
| `lib/cicd/runner.py` | 18 | 2,074 |
| `scripts/flow-wave-registry.sh` | 15 | 4,684 |
| `lib/cicd/steps.py` | 14 | 1,869 |
| `scripts/flow-finish-gate.sh` | 13 | 1,796 |
| `scripts/flow-wave-mailbox.sh` | 11 | 3,517 |
| `scripts/worktree-remove.sh` | 11 | 1,422 |
| `scripts/gh-pr-merge.sh` | 10 | 2,235 |
| `.claude/commands/flow/finish.md` | 10 | owned by #1669 |
| `lib/cicd/outcomes.py` | 8 | 637 |
| `scripts/flow-ci-status.sh` | 7 | 1,132 |
| `lib/cicd/manifest.py` | 7 | 603 |

```bash
git log --since=2026-09-12 --no-merges --format='@%s' --name-only origin/main -- \
    'scripts/flow-*' lib/cicd '.claude/commands/flow' '.claude/commands/cicd' \
    scripts/worktree-remove.sh scripts/gh-pr-merge.sh \
  | awk '/^@/{fix=($0 ~ /^@fix/); next} NF&&fix{c[$0]++} END{for(f in c)print c[f],f}' \
  | sort -rn | head -25
```

## Fix:feat ratio

Merged pull requests, 2026-09-12 to 2026-11-11, read on 2026-11-11 late in the
day (#1673 recorded 429 / 244 / 98 earlier the same day, before ten more merges).

| Population | fix | feat | fix per feat |
|---|---|---|---|
| all merged PRs (439) | 251 | 103 | 2.4 |
| title scope starts `flow` | 53 | 22 | 2.4 |
| title scope starts `cicd` | 27 | 5 | 5.4 |

```bash
gh pr list --state merged --search "merged:2026-09-12..2026-11-11" --limit 1000 \
    --json title -q '.[].title' > prs.txt
wc -l < prs.txt                      # must be BELOW the --limit, or the listing was cut off
grep -c '^fix' prs.txt;  grep -c '^feat' prs.txt
grep -cE '^fix\(flow[^)]*\)' prs.txt; grep -cE '^feat\(flow[^)]*\)' prs.txt
grep -cE '^fix\(cicd[^)]*\)' prs.txt; grep -cE '^feat\(cicd[^)]*\)' prs.txt
```

## The follow-up reading

Thirty days after the wave closes, run the fix:feat block with the search window
set to those thirty days and report it beside this table. Two months and thirty
days are different window lengths, so compare the ratios, not the counts. A
window holding fewer than about twenty flow or cicd pull requests is too small
to read a ratio from; say so and do not report one.
