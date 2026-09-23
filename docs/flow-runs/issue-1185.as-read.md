# Issue #1185 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1185
- Read at:      2026-09-22T11:06:45Z
- updatedAt:    2026-09-21T18:49:42Z   (context only - moves on comments and labels)
- Body digest:  a19b306ee51ececcf5376b4d2e6ee7c55143a21e183527b58affa6d42ccb175d   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3088 of 3088 (cap 16384)

## Body as read
Found during #1074's clean-install proof, measured, and routed to the wave orchestrator rather than filed by the worker. Verified independently by the orchestrator before filing.

## Finding

**A tampered bundled helper installs on a clean Codex host and reports success.** Nothing in the install path verifies that the *source* is authentic.

Measured: a tampered `worktree-remove.sh` (canonical `d57ee08d00f1`, tampered `3b9cf001dddec901`) installs with verdict `FLOW_HELPERS: installed`, and the injected line reaches `~/.claude/scripts`.

## Why the existing checks do not catch it

`flow-helpers-install.sh:244` and `:321`, and `install-drift.sh:246`, do compare source against installed — correctly, and that is what they are for:

```
elif ! diff -q "$src" "$dest" >/dev/null 2>&1; then
    echo "STALE $name (installed copy differs from source)"
```

That detects **drift between a source and its installed copy**. It is silent about whether the source itself is what it should be. Independently verified across the whole install path:

| script | `sha256` / `hashlib` / `digest` occurrences |
|---|---|
| `scripts/flow-helpers-install.sh` | **0** |
| `scripts/install-drift.sh` | **0** |
| `scripts/codex-skill-sync.py` | **0** |

There is no integrity verification anywhere in that path.

The two tools that might otherwise help cannot:

- `codex-skill-sync.py --check` is generation-parity against the checkout, so **it cannot run on a clean host by definition** — a clean host has no checkout to compare against.
- `install-drift.sh` is **in no codex bundle at all** (verified: `find codex/skills -name install-drift.sh` returns nothing), so it is not present on a host installed from a bundle.

## Bound — this is deliberately narrow

**This is about detection ON the host. It says nothing about whether a tampered bundle can ARRIVE.** Distribution is outside the clean-install proof that found this, and nothing here should be read as a claim about the likelihood of a tampered bundle existing. The finding is only that if one did, the install path would report `installed` and the host would have no way to notice.

## Related, and why it matters more on a Codex host than a Claude one

A Claude host typically installs from a checkout it can inspect. The Codex surface is installed from a *bundle*, which is the case where "is the source authentic" stops being answerable by looking around.

## Acceptance

- [ ] A bundled helper's integrity is verifiable on a host with no checkout.
- [ ] A tampered helper does not install with a success verdict.
- [ ] A committed negative control per ADR 0008: the known-bad is a helper whose content differs from its recorded digest, and it must be shown to red — the tampered-`worktree-remove.sh` case above is a ready-made candidate, with both digests already measured.
- [ ] Whatever verification is added states what it does **not** cover, since it cannot cover arrival.

Refs #1074. Found by worker-A during the `claude-improvements` wave; digests and the `diff -q` mechanism verified independently by the orchestrator.

