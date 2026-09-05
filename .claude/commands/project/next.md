---
description: Prioritized next-step report from GitHub issues and worktrees (compact default; --full deep analysis, --brief single pick)
allowed-tools: Bash(git:*), Bash(python3:*), Read, Glob, Grep
---

# Project Next Steps Recommendation

Run CPP's always-present vendored project-next engine and return its read-only,
deterministic recommendation. This command never modifies issues, branches,
worktrees, specifications, or lifecycle ledgers. Do not enter plan mode - this
is a report, not a change.

## Arguments

`$ARGUMENTS` may contain a project name and one mode flag, in any order:

- `<project>` (optional): a directory under `~/Projects`. Resolution order is
  positional argument, `CLAUDE_PROJECT`, then the current git repository.
- no flag: compact report with the top three safe candidates plus active,
  blocked, uncertain, lifecycle, and Wayfinder state.
- `--brief`: top action, next safe issue, confidence, and lifecycle counts.
- `--full`: the complete operational, specification, lifecycle, relationship,
  worktree, and cleanup report.

## Step 0: Resolve the pinned vendored contract

CPP vendors codex-power-pack's engine, contract, and fixture corpus under
`vendor/project_next/`. The executable CPP entry point is
`scripts/project-next.py`; normal installations expose it as
`~/.claude/scripts/project-next.py`. It is always present with this command, so
there is no sibling-checkout probe and no prompt-policy fallback.

Read `.claude/project-next-vendor.json` from the CPP checkout and use its
`contract_version` as the runtime pin. The wrapper performs the same check and
fails loudly if the vendored engine speaks a different version. Never fetch a
contract at runtime. Upstream movement is maintenance evidence surfaced by
`make project-next-drift`, not an invitation to silently change behavior.

The decision policy - classification, ranking, `top_action`,
`next_startable_issue`, and candidates - comes VERBATIM from the vendored
engine. CPP's adapter normalizes collector evidence before that decision and
adds `cpp_extensions` afterward; it never re-ranks, filters, or corrects the
engine result. Label every report:

`decision policy: contract v<manifest contract_version> (vendored engine)`

## Step 1: Resolve the project

Resolve the first non-flag token in `$ARGUMENTS`:

```bash
TARGET="<first non-flag token of $ARGUMENTS>"
if [ -n "$TARGET" ]; then
  TARGET="$HOME/Projects/$TARGET"
elif [ -n "$CLAUDE_PROJECT" ] && ! git rev-parse --git-dir >/dev/null 2>&1; then
  TARGET="$HOME/Projects/$CLAUDE_PROJECT"
else
  TARGET="$(git rev-parse --show-toplevel 2>/dev/null)"
fi
```

- If a named directory does not exist, stop and say which path is missing.
- If no git repository resolves, stop and ask for a project name or repository.
- A linked worktree has a `.git` file. Say that its issues belong to the parent
  repository and run against the parent instead of double-reporting it.

## Step 2: Run the engine once

Map the requested mode to exactly one of `--brief`, `--compact`, or `--full`,
then run:

```bash
python3 ~/.claude/scripts/project-next.py "$TARGET" <mode>
```

Return that report without independently collecting issues or rebuilding its
decision. If diagnosis needs the complete structured result, run the same
entry point once with `--json`; the JSON result is authoritative.

The collector uses batched GitHub and git reads. It collects issue assignees
and GitHub's native `blockedBy`, `blocking`, `parent`, and `subIssues` fields.
Native blocker relationships are confirmed edges. A dependency found only in
documented text is retained as evidence but explicitly classified `uncertain`;
it is never presented with native-edge confidence. Parent/sub-issue links are
hierarchy evidence and do not silently become blocker edges.

Collection, authentication, rate-limit, parse, and inventory failures remain
visible. An incomplete inventory produces no globally safe
`next_startable_issue`.

## CPP extension contract

The `cpp_extensions` JSON object contains four annotation sets computed once
and consumed by brief, compact, and full rendering:

- `relationships`: native relationship edges plus documented-text fallback
  edges with `confirmed` or `uncertain` confidence.
- `planning_routes`: an awaiting-decisions `.claude/wayfinder-map.json` and
  issues linked to one of its `DNNN` decision IDs route to `/project:init` for
  planning/resolution. They never route to `/flow:auto`.
- `spec_lifecycle`: one decision per known spec slug: `active`, `graduated`,
  `stale`, or `retained`.
- `premise_flags`: open spec-derived issues whose parent specification predates
  a live architecture decision covering the same domain.

Lifecycle defaults to `active` when `spec.md` has no `lifecycle` frontmatter,
preserving compatibility with pre-Wayfinder specs. An active spec becomes
`stale` only when its spec-sync issue state conflicts with the engine's current
open-issue evidence. The engine's own `spec_features` remains the separate
`spec-sync:v1` completeness axis.

Graduated and retained decisions come from the optional human-approved
`.specify/graduation-ledger.json`:

```json
{
  "version": 1,
  "specs": [
    {
      "spec_slug": "completed-feature",
      "state": "graduated",
      "evidence_url": "https://github.com/owner/repo/pull/123",
      "recorded_at": "2026-08-16"
    },
    {
      "spec_slug": "public-protocol",
      "state": "retained",
      "owner": "platform-team",
      "evidence_url": "https://github.com/owner/repo/issues/456",
      "recorded_at": "2026-08-16"
    }
  ]
}
```

A graduated spec is normally absent after verified knowledge transfer, so its
ledger evidence prevents a false missing-file warning. Active missing specs are
warned. Retained specs require an owner because they remain maintained
contractual, regulatory, compliance, public-protocol, or cross-team material.
This command only reads the ledger; a future graduation gate owns writing it.

## Premise staleness

Ranking inputs - value, effort, unblocking - are all properties of the issue
itself. None of them can see that a decision merged after the issue's parent
specification retired the premise that specification was written under, so a
dead issue still reads as small, well-formed, and safe.

Architecture decision records are read from `docs/decisions/`, `docs/adr/`, and
`docs/adrs/`, matching `NNNN-*.md` with `- Status:` and `- Date:` header fields.
An unparsable header is reported in the CPP extension warnings, never skipped
silently.

- Only a record whose status still reads `Accepted` can retire a premise. A
  superseded or rejected record states no live decision, and the record that
  replaced a superseded one carries its own date, so the successor raises the
  flag its predecessor cannot.
- A specification's as-of date is the later of its `Created` and `Amended`
  headers (`> **Created:** YYYY-MM-DD`, or YAML frontmatter `created:`/`date:`).
  An amended specification has already been revisited, so it is never accused of
  predating a decision it absorbed.
- Domain evidence is declared domains on both documents first (`- Domains:` on
  the record, `> **Domains:**` on the specification), then shared significant
  terms between the specification slug/title and the record title/filename.
  Every flag names the matched term and which of the two produced it, so a
  heuristic match is never presented with declared-evidence confidence.
- Issues are reached through the specification's task mapping, so only
  spec-derived open issues are ever flagged.

The flag is advisory and additive: it carries a reason naming both the
specification and the decision, and it never changes a score, an order, or a
partition. `/flow:eli5` remains the necessity decision point, and closing an
issue on premise grounds stays a reviewer decision.

## Output invariants

- Every open issue is in exactly one engine partition: `in_flight`, `blocked`,
  `uncertain`, or `available`.
- `next_startable_issue` and start candidates never name an issue outside
  `available` when inventory is complete.
- Critical non-startable work remains visible but is not recommended as safe.
- All modes use the same engine result, lifecycle decisions, relationship
  evidence, and Wayfinder routes. Renderers do not reclassify them.
- Planning-only Wayfinder artifacts never display a `/flow:auto` route.
- A premise flag annotates a ranked issue; it never re-ranks, filters, or hides
  one.
- A malformed vendored package, fixture corpus, manifest hash, import, or
  contract-version pin is a hard failure, never a skipped optional dogfood.

## Notes

- Use `/flow:auto N` only for an implementation candidate that the report
  leaves on that route.
- Use `/project:init` for a Wayfinder planning/resolution route.
- Use `/project:lite` for orientation without issue analysis.
- Optional ranking configuration remains in `.project-next.json`, per the
  vendored contract.
