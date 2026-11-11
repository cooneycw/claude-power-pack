# `check-skill-coverage-map` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `check-skill-coverage-map` (#1370)

Maps changed CPP skills and their dependency closures to current evaluation
coverage (R10, `.specify/specs/per-skill-audit/spec.md`), over two staleness
axes that must not be collapsed into one: axis 1 (content) - has EVERY file
shipped under `codex/skills/<skill>/` moved since the evaluation-bound
reference - and axis 2 (dependency) - does skillc's `profile diagnose`
report the skill's dependency closure broken, independent of whether its own
content changed. `check-skill-coverage-map.py` answers both from the current
checkout and a vendored snapshot; it never imports or invokes skillc, the
same discipline #1369's `check-behavioral-eval.py` states for itself, since
skillc cannot run in CPP's CI.

**Axis 1 covers every file, not only SKILL.md (#1390).** The generator moves
most of a skill's actual instructions into `reference.md` behind a
progressive-disclosure pointer (#864: `codex-skill-sync.py`'s
`INLINE_MAX_LINES` split), so the original design - SKILL.md's
description/body digests only - read a `reference.md`-only change as axis-2
snapshot drift (`unknown`, remedy "re-run the snapshot") rather than
axis-1 content staleness (the correct remedy: re-evaluate). Measured on
#1388's real branch before the fix: `axis1: current; axis2: unknown
(snapshot stale); state: unknown` - one `skill-coverage-snapshot.py` regen
away from a FALSE GREEN, since regenerating would have flipped axis 2 back
to current while axis 1 kept saying current for text that was never
evaluated. The fix compares `digest_tree(closure_root)` (the exact function
axis 2 already used for its own drift check) against a NEW `reference.files`
map vendored from skillc's inventory `skills[].files[]` (sha256 `digest`,
not `git_blob` - same hash family the rest of this gate already uses, zero
new hashing logic), keyed by path relative to `codex/skills/<skill>/` to
match `digest_tree()`'s own keys exactly - a silent key mismatch here would
either mark every file changed or compare nothing at all, so
`skill-coverage-snapshot.py`'s `_reference_files` REFUSES an inventory entry
whose `source` does not carry the expected prefix rather than mis-keying or
skipping it. SKILL.md's description/body digests stay as the finer-grained
sub-check (skillc's evidence model tracks them separately for R14
cross-checking); the per-file check is the coarser one that catches
everything else, including bundled helpers and the `lib/cicd` copy the
generator ships with the skill - a change to one of those is axis-1
content-stale independent of whether it is ALSO axis-2 dependency-relevant.

**Five states, not fewer**, for the same reason `check-behavioral-eval`
distinguishes `absent` from a clean pass: `not evaluated` (the skill is absent
from `SKILL_FAMILY_MAP` - axis work is never attempted, and never inherited
from a mapped sibling) is a membership fact; `unknown` (either axis
undecidable) is a different claim with a different remedy. `current`,
`stale (content)` and `stale (dependency)` are the three substantive
verdicts.

**Axis 2 is always computed, even once axis 1 is already stale** (counter-
model review, 2026-10-06). Content-staleness still dominates the COMBINED
`state` - fixing content is step one regardless of what axis 2 says - but
the `reason` always names both axes, so an auditor who fixes axis 1 is never
surprised by axis 2 on the next run. On today's real data both axes ARE
stale at once: see "the first committed snapshot" below.

**Axis 2's own staleness is the sharper half.** The vendored snapshot records
a digest for every file in the skill's `codex/skills/<skill>/` closure AT
SNAPSHOT TIME. The gate recomputes the same digests against the CURRENT tree
on every run; any mismatch reports `unknown` for axis 2, never a
silently-reused cached `intact`/`broken` verdict (this `unknown` still loses
to an already-stale axis 1 in the combined `state`, exactly as `broken`
would). That is CI's whole answer for axis 2: fresh as of the last manual
regeneration, and able to say whether that regeneration is still valid -
never a live result. Registered control `controls/check-skill-coverage-map`:
a closure that grew a file after the snapshot was recorded, with axis 1 held
current (so the case isolates axis 2's own staleness check rather than
exercising the content-dominance path above), must read `unknown`. Its
anchor is CONSTRUCTED - the real drift comparison replaced with a hardcoded
empty list - and reports `current` over the known-bad input it misses.

**Axis 1's per-file check has its OWN registration, `controls/check-skill-
coverage-map-axis1-files` (#1390)** - a separate control, not a case added
to the one above, because disabling axis 1's per-file comparison does not
make the axis-2 anchor blind and disabling axis 2's drift check does not
make THIS anchor blind (same shape as this repository's `flow-finish-gate`
family). A `reference.md` edit with axis 2 held current must read `stale
(content)` naming the file; its anchor is CONSTRUCTED - the per-file
comparison removed entirely, reverting to the exact pre-#1390 behavior - and
reports `current` over the known-bad input it misses.

**Q1 (no newer evaluation-bound reference exists).** Neither #1369's
`check-behavioral-eval.py::_evaluate_skill_evidence` (whose own docstring
says "Freshness against the CURRENT checkout (R10) is NOT checked here -
that is #1370's job") nor skillc #272's coverage-report assembler expose a
`{revision, skill, digest}` tuple for content freshness, so the reference
stays whichever skillc profile pin `skill-coverage-snapshot.py` was last run
against (its `--profile-dir`, #1370 refresh). NOT NAMED HERE - skillc
re-declares a profile as a new directory when it needs a new pin, so naming
one in this prose would strand it exactly as the original `85e9b03` mention
was stranded by skillc #330. Read the CURRENT pin from the committed
snapshot's own provenance: `docs/measurements/skill-coverage/<skill>.json`'s
`reference.source` and `diagnose.profile_dir` fields say so explicitly,
rather than this document implying a fixed one exists.

**The committed snapshot is the real one, not a fixture - and it has already
been refreshed once.** The first snapshot (CPP `8ff62ca`, skillc `bbd4ed6`,
profile `cpp-codex-flow-check` @ `85e9b03`) showed both axes genuinely stale
at once: axis 1 from #1380's description change, axis 2 from
`execution-evidence-verify.py` having no skillc dependency in that profile.
That profile stayed stale by design (skillc's own stated rule: it is not
edited once it has a citing case contract), so skillc #330 re-declared a
SEPARATE profile directory (`cpp-codex-flow-check-ea6dbfa`) with the
dependency added and the description/body re-pinned at CPP `ea6dbfa` - and
`docs/measurements/skill-coverage/flow-check.json` was regenerated against
it, reporting `current` on both axes.
`test_stale_dependency_real_fixture_shape` keeps the ORIGINAL real problem
shape pinned in an immutable synthetic fixture regardless of which profile
the committed snapshot currently points at - it is a regression test for
the code's behavior on a broken-dependency result, not a live assertion
about today's snapshot.

**v1's map is the degenerate 1:1 case** (`flow-check` only; skillc has only
one CPP profile today). Map-level staleness - a skill's file set outgrowing
what `SKILL_FAMILY_MAP` accounts for - is explicitly deferred (owner ruling
via the cpp-eval orchestrator, 2026-10-06) and routed to the Nit Store (#864)
when this work ships, not fixed here. v1 also declares no equivalence
registry: a cosmetic (whitespace/comment-only) change is `stale (content)`
exactly like any other difference, by the same ruling.
