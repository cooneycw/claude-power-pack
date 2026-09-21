# The clean-install proof

A Codex host reaches CPP's surface from a clean install and runs a workflow end
to end (issue #1074). This file records what was demonstrated, at which SHA, and
how to re-run it - **evidence for an earlier SHA is not release approval**, so
the re-run instruction is the point of this document, not the transcript.

## Re-running against a newer SHA

```bash
make codex-install-proof              # installs into a constructed CODEX_HOME
```

It constructs its own `CODEX_HOME` under a temp dir and never writes to
`$HOME/.codex`. Pass `PROOF_WORK=<dir>` to keep the work tree for inspection.
A newer SHA needs a fresh run: the manifest is derived from the generated tree at
HEAD, so a run's verdict belongs to the SHA it names and to no other.

## Two phases, and the boundary is the proof

```
phase 0   IN the repository: derive the expected set from codex/skills/<skill>
          at a named SHA into a manifest. The manifest TRAVELS AS DATA.
phase 1   Install, then exercise the installed copy with the four absences
          asserted. Every verdict is made against the MANIFEST.
```

#1074's defect class is **inferred from a neighbour**. A harness that reads the
INSTALLED skill to decide what should be installed marks the install complete
because the install says so - the same error as reading a manifest to learn what
the manifest should contain.

**One honest seam, stated rather than hidden:** the install step itself reads the
repository, because that is what installing IS. It decides nothing. Every verdict
after it comes from the manifest, and the exercise runs with cwd outside any
checkout.

## What the run emits

Verbatim from `make codex-install-proof` at `8e8fdb5ff24f24b0de4e21454b41c3dea7287e18`:

```
PROOF_WORK: /tmp/codex-install-proof-sf1wk2
PROOF_EXPECTED_FILES: 11
PROOF_SOURCE_SHA: 8e8fdb5ff24f24b0de4e21454b41c3dea7287e18
PROOF_ABSENCE: empty-codex-home ok
PROOF_ABSENCE: invocation-path-qualified ok
PROOF_ABSENCE: no-ambient-on-path ok
PROOF_ABSENCE: no-repo-reachable ok
PROOF_INSTALLED_AT: /tmp/codex-install-proof-sf1wk2/codex-home/skills/project-next
PROOF_ABSENCE: engine-resolves-inside-codex-home ok (/tmp/codex-install-proof-sf1wk2/codex-home/skills/project-next/lib/project_next/rank.py)
PROOF_INSTALLED_HASH: 2ca9ec7f969a9712
PROOF_COMPARED: 11 file(s) against the manifest
PROOF_WORKFLOW: ok - contract v1.3, next_startable_issue=2
PROOF_KNOWN_BAD: stale-bundled-helper REJECTED - PROOF_FAIL: DRIFT: lib/project_next/rank.py
PROOF_KNOWN_BAD: missing-scripts REJECTED - names a path under CODEX_HOME, no ambient or repo path
PROOF_KNOWN_BAD: payload-drift REJECTED - PROOF_FAIL: DRIFT: SKILL.md
PROOF_NOT_RUN: codex-loader - the Codex CLI's own skill loader was not exercised; this proof drives the installed artifact directly
PROOF_NOT_RUN: other-skills - only 'project-next' was exercised; the other generated skills are not implied by it
PROOF_NOT_RUN: platform - one Linux host; macOS and Windows were not run
PROOF: ok
```

## The cells that were NOT run

Quoted from the harness's own `PROOF_NOT_RUN:` lines above, never hand-written:
a cell not run is recorded as not run and is never inferred from a neighbour that
passed. The harness emits them; this document quotes them. If they are ever
hand-maintained here they will drift from what the run actually skipped, which is
the failure the rule exists to prevent.

## The three known-bad inputs

A proof that only walks the happy path demonstrates the happy path exists. It
says nothing about whether a broken install is noticed.

| input | why it is the one to test | rejection |
|---|---|---|
| stale bundled helper | an engine module edited after install; every path present, bytes wrong | `DRIFT: lib/project_next/rank.py` |
| missing `scripts/` | the case most likely to "pass" by silently finding an ambient or repo copy | names a path under `CODEX_HOME`, and names neither `~/.claude/scripts` nor a repo path |
| payload drift | installed bytes differ from what shipped | `DRIFT: SKILL.md` |

The middle one pins its failure TEXT, not just its exit code: a rejection that
names the repository is a rejection produced by the neighbour this proof asserts
is absent.

## The four constructed absences

Each is ASSERTED before anything relies on it, per the CLAUDE.md rule, and each
was red-proved once - run with the absence violated, to see the assert refuse.

| absence | what it actually measures |
|---|---|
| empty CODEX_HOME | the destination is empty before installing |
| invocation path-qualified | the workflow is invoked by absolute path, not by name |
| no ambient `project-next` on PATH | a name-based invocation could not find a neighbour |
| no repo reachable | the exercise cwd is outside any checkout |
| engine resolves inside CODEX_HOME | *(after install)* the executed engine is the installed one |

**Two of these were wrong when first written**, and the correction is the useful
part: they tested host INVENTORY - "does `~/Projects/codex-power-pack` exist",
"does `~/.claude/scripts/project-next.py` exist" - rather than reachability in
effect. A sibling checkout existing on a box is not the hazard; the installed
skill RESOLVING through one is. The inventory form also made the proof unrunnable
on any developer machine that has either, and a precondition nobody can satisfy
is not a precondition - it is a way of never running the proof while looking
rigorous. The second one was caught only because the assert fired and refused.

## What this proof does not establish

- The Codex CLI's own skill loader: not exercised (`NOT RUN: codex-loader`).
- The other generated skills: not exercised, and not implied by this one.
- Other platforms: one Linux host.
