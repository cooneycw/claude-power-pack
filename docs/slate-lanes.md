# Slate lanes

[slate-lanes.json](slate-lanes.json) declares which issues are accounted for.
`lanes` maps worker/session names to issue numbers they own. `buckets` maps
off-lane reasons to issue numbers: `backlog` means open and seen, with nobody
assigned yet. Backlog is an explicit assignment, never a default for missing
issues. `notes` is informational text and never affects the verdict. An empty
list records a verified "nothing here" for that named lane or bucket; an absent
name makes no such declaration. Both top-level maps are required.

This file is **hand-maintained: a declaration, not a measurement**. Nothing
keeps it accurate except a human updating it. The reconciler checks it against
an independently measured open-issue set; it never fills in claims. See
`python3 scripts/slate-reconcile.py --help` for the mechanics. The default uses
GitHub through `gh`; `--open-set-capture PATH` reads a JSON list of issue numbers
offline. Controls use synthetic captures, not evidence of today's live slate.
The initial `backlog` is intentionally empty; the orchestrator must populate it
from a live open-issue listing outside the offline implementation session.

**Limitation: the reconciler will not catch the defect that motivated building
it.** #1033's remaining item 3 and the separately filed #1094 describe the same
underlying unit of work, but they are different issue numbers. #1033 in
`owner-decision` and #1094 in `cpp-w2` are legitimate distinct memberships at
this granularity. DUPLICATE fires only when the same number appears twice
(including repeated entries within one list). The tool catches whole-issue
double-listing; it does not catch sub-item re-homing across two different issue
numbers. Finding that kind of duplicate still requires a person reading scope
items against each other. A possible follow-up is explicit partial-claim and
sibling-issue metadata; it is not implemented here, and notes remain unchecked.

Every reconciliation reports open and distinct claimed counts, plus separate
UNACCOUNTED, PHANTOM, and DUPLICATE counts. Exit 0 is clean, 1 means findings,
and 2 means UNKNOWN because an input is missing or unusable. Unknown counts are
printed as `unknown`, not zero; readable claims still allow a duplicate check
when the open set is unavailable. A fully readable empty population is clean.
