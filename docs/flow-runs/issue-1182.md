# Flow run record - issue #1182

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1182
- Base SHA:          d3f474b
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          wave `claude-improvements` orchestrator, session
                     `claude-improvements-new` (uds:/run/user/1000/cc-socks/1751946.sock),
                     succeeding `CPP-improvements-orch` on an owner ruling of 2026-09-23.
                     Ruling delivered to the durable mailbox as rev 2 and acked by this
                     session after the content was held; the orchestrator's identity was
                     confirmed against the wave registry, not against the message.
- Recorded at:       2026-09-23T12:20:00Z

## Section B evidence

- Commits touching the relevant paths since the issue was filed (2026-09-21T17:51:10Z):
  exactly one, `71ff297` "feat(host-surface): certify declarations by observation, not by
  reading (Closes #1150) (#1183)". That commit SHIPPED the instrument this issue bounds; it
  is the premise, not the resolution. #1150 is CLOSED and shipped explicitly stating that
  its own acceptance item 5 ("the real $HOME is never a target") was NOT met.
- Merged PRs since 2026-09-21: #1183 through #1209. None except #1183 touches
  `scripts/host-surface-observe.py`, `tests/test_host_surface_observe.py`,
  `controls/host-surface-observe` or `scripts/host-surface-check.py`.
- Duplicate / superseding issues: searched "fsmonitor" -> only #1182. Searched
  "containment host-surface" -> #1182, plus #864 (Nit Store) and #821 (closed, mailbox
  watcher identity), both unrelated. None supersedes this issue.
- The premise was RE-MEASURED rather than taken from the issue's table. git 2.43.0, a
  scratch repo with `core.fsmonitor` set to a canary: `git status`, `git diff` and
  `git ls-files --others` FIRE it; `git rev-parse`, `git branch --show-current`,
  `git config --get` and `git stash list` do not. That reproduces the issue's table
  including its own correction - the live route is `scripts/cpp-commands-link.sh:345-346`,
  while `:342` (`git rev-parse --is-inside-work-tree`), the line the original report cited,
  is the one invocation in that file that does NOT fire.
- The proposed fix was measured before being proposed:
  `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.fsmonitor GIT_CONFIG_VALUE_0=false` neutralises
  the route and reads back as `false` while the repository config still holds the canary.

## Section C - the approved plan

1. `scripts/host-surface-observe.py` - add a derived table of git config keys that cause git
   to EXECUTE a command, each with its neutralising value; inject them into `sandbox_env()`
   AFTER the ENV_ALLOWLIST filter via GIT_CONFIG_COUNT/KEY_n/VALUE_n; add
   `verify_git_containment()`, which proves the neutralisation IN THE CHILD by planting a
   canary `core.fsmonitor` in a scratch repo, running a firing git command under the sandbox
   env, and REFUSING if the canary fired; make that refusal block `certified=observed`
   rather than print a caveat; rewrite the "not contained" bound so it names exactly the
   channels the enforcement covers and those it still does not.
2. `tests/test_host_surface_observe.py` - the committed cases. The load-bearing one is the
   POSITIVE CONTROL: the canary FIRES with the neutralisation removed, so "it did not fire"
   cannot be satisfied by a canary that could never fire. Plus the neutralised case, the
   REFUSED path, the R3 case pinning that the GIT_CONFIG_* keys are never added to
   ENV_ALLOWLIST and a parent-set value cannot reach the child, the enumerator's positive
   control and its clean case, and a test that the printed bound and the enforced key list
   cannot drift apart.
3. `controls/host-surface-observe/control.json` - record the route enumeration and its
   result in `limits`, and state the new containment bound there, following this control's
   existing precedent that sandbox-shaped properties are pinned by
   `tests/test_host_surface_observe.py` rather than by `--root` cases.
4. `controls/host-surface-observe/anchors/constructed-blind-covered-by.py` - REGENERATE the
   blinded anchor from the hardened source, and update its `sha256` in `control.json`. The
   battery EXECUTES the anchor, so an anchor left at the pre-fix source carries the live
   fsmonitor escape this change closes - the same failure its own `why` field records from
   the previous regeneration.
5. `scripts/host-surface-check.py` - retire the stale forward reference at lines 341-342
   ("Filesystem containment is issue #1182; until it lands, `observed` is the stronger of
   two claims, not an absolute one") so the `certified=observed` vocabulary matches the
   containment this change actually delivers. Granted by orchestrator ruling 5 for that
   purpose only; a substantive behaviour change in this file returns to the orchestrator.
6. `docs/flow-runs/issue-1182.md` - this record.
7. `docs/flow-runs/issue-1182.as-read.md` - the as-read snapshot of the issue body.

Scope: 7 files, approximately 400-450 lines net.

Risks: R1 (principal, orchestrator-AFFIRMED) the neutralisation is an ENUMERATION and is only
as strong as its candidate list; closing `core.fsmonitor` and its siblings establishes nothing
about a seventh key, so the verdict wording must NOT be upgraded - `observed` stays explicitly
not `confined`. R2 a helper setting its own `GIT_CONFIG_COUNT` would clobber the injection;
covered by a test. R3 (sharpest, orchestrator-AFFIRMED) the neutralising keys must never be
added to ENV_ALLOWLIST, because that would let a parent-set `GIT_CONFIG_*` through into the
child and re-open the exact escape shape #1150 closed; encoded as a test that goes red, not as
a comment. R4 resolved by the lane extension in ruling 5.
