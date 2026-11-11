# `check-eval-enrollment` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `check-eval-enrollment` (#1371)

Reads the CPP evaluation-enrollment decision record,
`docs/measurements/eval-enrollment/flow-check.json`, and reports what it may
claim. The decision is ADR 0011's: flow-check stays ADVISORY, because skillc
#288's evidence (#279 and #529 D3) is single-arm and #1084's flip needs a
DISCRIMINATING and an IMPROVED result on a certified pairing. The record is
data so the decision is CHECKED on every run, not merely written down.

**Every state says advisory or names why the record cannot be read; none is
behavioural assurance.** `current` (0) means only that at least one evidence item FOR THIS
FAMILY (#279's flow:auto result is context, never this family's evidence) was
taken on the shipped closure and has not passed `review_by`.
`stale-content` (3) - the flow-check closure digest no longer matches the
evaluated one, i.e. the CPP pin moved past 652c0118 in a way that touches the
skill. `stale-aged` (4) - past `review_by` (2027-01-21), printed with the
reversal trigger recorded beside it. `failing` (5) - an evidence item records a
failure. `fixture` (6) - a fixture population, never evidence. `unknown` (2) -
absent, unreadable, unsupported schema, a required field missing, a pass-rate
threshold anywhere in the record, a `blocking` decision, a required field present
but not a usable string, an evidence item without integer counts and at least one
evaluable attempt, or no evidence item for the record's own family. Each state has its
own exit code without `--advisory`, so a later gate can tell them apart (the
always-1 shape of `check-skill-coverage-map` without `--advisory` is the
defect this avoids, Nit Store #864); `--advisory` maps every printed verdict
to 0 while a crash still fails. The record's four `limits` print beside every
reading.

**Refusals, not omissions.** A threshold key is refused rather than ignored,
because an ignored threshold is one a reader would assume was enforced. A
`blocking` decision is refused whether or not its flip fields claim to be
filled: the change that lands a real flip must change this consumer too.

The closure digest restates `check-skill-coverage-map.py`'s `digest_tree`
rather than importing it, so the file runs unchanged from its control's anchor
copy; `tests/test_eval_enrollment.py` pins the two definitions equal. No git,
no network, no skillc. Registered control `controls/check-eval-enrollment`:
a closure changed after the evidence was taken must read `STALE (content)`;
its constructed anchor hardcodes the comparison off and misses it.

- `counter-model-receipt` (#1557, #1580): `write` derives both sides of a counter-model review rather than accepting model names. A resumed Codex implementation with multiple complete turn-model identities writes schema 4: `implementers` is a nonempty unique list from the full retained rollout, the reviewer stays scalar, and overlap with any implementer refuses. Unknown implementation turns and mixed reviewer evidence still refuse; schemas 1-3 remain valid. Opt-in `--implementer-flow-run RUN` is the narrower schema-3 path for a genuinely fresh Codex flow whose original harness events prove the bounded run scope; `audit-flow RECEIPT --codex-sessions-dir ROOT` re-derives that captured prefix. Neither route accepts a caller-selected model or arbitrary history window. See ADR 0007 for both evidence boundaries.

- `flow-preflight` - `flow-preflight.sh` bootstraps the stdlib `flow-preflight.py` observer on Python 3.10+. It aggregates local gh capabilities, uv presence, CPP-only Python 3.11 availability, the bash floor (4.4, read from the caller's PATH only), git identity presence, optional reviewer presence and resolved engine ownership. Required gaps and unknowns remain distinct; no install, identity write or authentication is performed. Its installed-Python coverage is PATH and the selected uv install directory, not all possible host runtime directories.
