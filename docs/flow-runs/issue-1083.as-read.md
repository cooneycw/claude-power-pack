# Issue #1083 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. It does not graduate.

- Issue:        #1083
- Read at:      2026-09-23T15:35:47Z
- updatedAt:    2026-09-20T14:34:40Z   (context only)
- Body digest:  e81bd087ea7a2f83f907c134351b5bc610cb98095a1d0638842526009f40ecfb   (sha256 of the FULL body)
- Stored bytes: 3215 of 3215 (cap 16384)

## Body as read
Parent: #1079.

Status: proposed work, not authorization to implement.

Depends on: #1073, and #1080 for the approval record the hook reads.

## Outcome

The claim that the Step 3 gate cannot be bypassed is true because something enforces it, not because an agent read a document saying so.

## The gap

#775 states that no flag, trailer, marker, environment variable, or governance tier may let Step 3 proceed without a reviewer approving the plan, and that none may be added. It is one of the most forcefully stated rules in this repository.

Verified at `5ceb966`: `.claude/hooks.json` contains one SessionStart notice about being behind `origin/main`, and two PostToolUse output masks. That is the entire file. Nothing enforces #775.

This is precisely the playbook's advisory-versus-deterministic distinction: a skill is an advisory control, a hook is the deterministic layer behind it. It is the one dimension on which the playbook is unambiguously ahead of CPP, and it is worth stating plainly that the strength of the prose is not evidence about the strength of the control. `docs/agents/detector-contracts.md` already makes the general form of that argument.

## Scope

A `PreToolUse` hook that refuses an edit in a flow worktree carrying no approved-plan record, with a block message that explains itself and names the route to approval.

## Why this depends on #1073

#1073 is already scoped to ship pinned plugins from CPP **with safe hook update and rollback**, including preserving the exact hook bytes and roots that active sessions trust. Building a hook-delivery mechanism before #1073 decides how hooks ship means building it twice, and the second build would be the one that has to preserve the first one's trust roots. Wait for it.

## Acceptance

- An edit attempted in a flow worktree with no approval record is refused, and the refusal names what is missing and how to obtain it.
- An edit in a worktree with an approval record proceeds.
- The hook is **opt-in and shipped through `templates/`**, never silently installed into a consumer repository. CPP ships to other people's projects, and a hook that blocks edits is not something to arrive unannounced.
- Refusal is refusal, not a default. A hook that cannot determine the state must refuse and say so, never allow. `docs/decisions/0009-oscillation-control.md` and #1014 both bear on this.
- The advisory layer is unchanged. Step 3's prose contract stays exactly as it is; this adds a floor beneath it rather than replacing it.

## Negative control (ADR 0008)

Committed, both directions, and this child is the clearest case in the wave:

- A run attempting an edit with no approval record must be blocked.
- A run with one must proceed.

A hook that has not been shown to block has not been shown to be a hook. Re-reading its source establishes what it meant, never what it can say.

## Constraint that is not negotiable

**A hook that fails open is worse than no hook**, because the prose it replaces at least made no claim to be deterministic. If the record cannot be read, the hook refuses. Do not add a permissive fallback to keep runs moving; that is the change that would quietly remove the distinction this issue exists to draw.

