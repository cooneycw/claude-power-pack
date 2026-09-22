# Issue #1198 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

RE-READ MID-RUN, and the reason is recorded rather than hidden: the body as
first filed carried five U+2014 em dashes, which this repository forbids in
tracked markdown, and a verbatim copy of it therefore failed
`check-unicode-dashes.py`. Rewriting the dashes in THIS file would have made
the evidence copy disagree with its source, so the ISSUE was corrected at
2026-09-22 and re-read. The digest below is of the corrected body.

- Issue:        #1198
- Read at:      2026-09-22T11:33:08Z   (the re-read; the first read was ~10:5x the same day)
- updatedAt:    2026-09-22T11:32:54Z   (context only - moves on comments and labels)
- Body digest:  503d635ccf690e50c4352be29aa924f1fbb2f1d372b4b41a07d3d9e1748e1abb   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 5061 of 5061 (cap 16384)

## Body as read
## What

`/cpp:update` calls `~/.claude/scripts/cpp-host-write.sh` at **six** sites, all
bare, none with a checkout-path fallback. When that symlink is absent the call
exits 127 and **the surrounding step continues and reports success anyway**.

Found while running `/cpp:update` on this host (2026-09-22). The helper was
genuinely absent here, so this is a measured failure, not a hypothetical.

## The six sites

`.claude/commands/cpp/update.md`:

| line | step | call | what it claims on a 127 |
|---|---|---|---|
| 76 | 1 (availability probe) | `probe-writable` | `surface_writable` is empty; report prints `~/.claude/commands writable:     (probed, not inferred from mode bits)` - a blank advertising itself as a probe result |
| 614 | 5b (script refresh) | `link-into` | loop runs N times, links nothing, composes no verdict |
| 1038 | 5d.3 (Gemma profile) | `json-merge-sections` | next line prints `✓ Tier 7 Gemma profile: <status>` |
| 1467 | 7.5 (flow allowlist) | `settings-merge` | next line prints `✓ Flow allowlist merged (N total allow rules)` |
| 1521 | 7.6 (census hook) | `settings-edit` | next line prints `✓ PermissionRequest census hook registered` |
| 1587 | 7.7 (retro hook) | `settings-edit` | next line prints `✓ Session-open pending-retro reminder registered` |

At 1467/1521/1587 the `echo "✓ ..."` is **unconditional** - it is the next
statement, not guarded on the write's exit.

## Control pair (the checkmark cannot fail)

Sandboxed `$HOME`, `settings.json` seeded with exactly 2 allow rules, template
carrying 52. The two Step-7.5 lines run **verbatim**; the only variable is
whether the helper symlink exists.

```
helper ABSENT:
  bash: .../.claude/scripts/cpp-host-write.sh: No such file or directory
  ✓ Flow allowlist merged (2 total allow rules)
  -> file afterwards: ["Bash(ls:*)","Bash(git status:*)"]   # 0 of 52 merged

helper PRESENT:
  cpp-host-write: ok ~/.claude/settings.json (50 new rule(s), 52 total)
  ✓ Flow allowlist merged (52 total allow rules)
  -> file afterwards: 52 rules
```

Both print a `✓ Flow allowlist merged (...)` line. The failing run's number is
the **pre-merge** count, so the false claim carries plausible specificity - it
does not read as a blank or an error, it reads as a smaller install.

## Why it matters

1. **A user who answers "yes" to a write prompt is told the write happened.**
   Steps 7.5/7.6/7.7 are the user-confirmed trust-boundary writes. The whole
   point of routing them through the declaring seam (issue 1132) was that a
   deferred write yields "a stated refusal instead of a silent skip". A 127
   yields neither: it yields a stated *success*.

2. **It is a bootstrap hole that cannot self-heal.** `cpp-host-write.sh` is
   itself one of the files Step 5b links. A host receiving it for the first
   time via `git pull` can never link it, because linking it requires it.
   Step 5b is the step whose job is to install the helpers.

3. **It propagates into a second step's non-measurement.** On this host Step 5b
   left 25 scripts unlinked, including `npm-global-upgrade.sh`. Step 5d then
   correctly reports `unknown (npm-global-upgrade.sh is not installed; upgrade
   NOT attempted)` and its own comment says such a host "must not read like one
   that was measured and found fine" - but the step that *caused* it drew no
   conclusion at all.

4. **Two sibling helpers already have the fallback; the seam does not.**
   `npm-global-upgrade.sh` resolves installed-then-checkout at update.md:850
   and :956, and Step 5c documents the exit-127 fallback for
   `cpp-commands-link.sh` at :716. The helper that owns *every* host write is
   the one without it.

## Suggested shape (not prescriptive)

- Resolve once, early, with the same order the siblings use:
  `HOST_WRITE="$HOME/.claude/scripts/cpp-host-write.sh"; [ -x "$HOST_WRITE" ] || HOST_WRITE="$CPP_DIR/scripts/cpp-host-write.sh"`
  and use `"$HOST_WRITE"` at all six sites. This also fixes the bootstrap case,
  since the checkout copy is what links the symlink.
- Guard each `✓` on the write's exit, and distinguish the helper's three
  documented verdicts (0 wrote / 3 deferred / 1 failed) from 127 "seam absent".
- Step 5b should compose a verdict (linked / already-current / failed) rather
  than emitting nothing.
- Negative control: the case above (helper absent, count unmoved, no `✓`)
  belongs in `controls/` - it is a gate that lets work through, so ADR 0008's
  bound applies.

## Reproduction

```bash
SB=$(mktemp -d); mkdir -p "$SB/.claude/scripts"
echo '{"permissions":{"allow":["Bash(ls:*)","Bash(git status:*)"]}}' > "$SB/.claude/settings.json"
HOME="$SB" bash -c '
TARGET="$HOME/.claude/settings.json"
TEMPLATE="'"$PWD"'/templates/claude-settings-permissions.json"
~/.claude/scripts/cpp-host-write.sh settings-merge "$TEMPLATE"
echo "✓ Flow allowlist merged ($(jq ".permissions.allow | length" "$TARGET") total allow rules)"
'
jq -c '.permissions.allow' "$SB/.claude/settings.json"   # unchanged
```

Found while running `/cpp:update` (v8.0.0, f6f5949 -> 5a4d7fc).


