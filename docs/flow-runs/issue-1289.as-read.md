# Issue #1289 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1289
- Read at:      2026-09-28T11:27:35Z
- updatedAt:    2026-09-27T13:35:49Z   (context only - moves on comments and labels)
- Body digest:  4c6e9a66bab5014af04207d92fd2f38d152478aa9580c1efb320609a108ba1a2   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3274 of 3274 (cap 16384)

## Body as read
## Outcome

CPP identifies supported components in ordinary consumer repositories and selects checks that match those repositories' declared scope. A root manifest must not make a nested stack silently disappear from the result.

Source: owner-requested capability assessment and incremental improvement 3, 2026-09-27. Verified reproduction: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5856177536

## Evidence at `879df15`

Executed `lib.cicd.detector.detect_framework` against temporary marker-file trees:

- Root `package.json` + `package-lock.json`: Node/npm with Node runner defaults (control).
- The same root files plus `backend/pyproject.toml` + `backend/uv.lock`: still Node/npm; the backend is absent from `detected_files`.
- Frontend and backend manifests under sibling directories with no root manifest: Multi is detected, but no runner defaults are supplied.
- `pyproject.toml` + `manage.py`, no lockfile: Django/unknown with an empty runner map, despite an existing Django/pip runner definition.

Subdirectory discovery only runs when no root framework was found. Django promotion occurs before a package-manager fallback that handles only the Python enum. These are verified selection gaps, not proof that every downstream flow skips a backend: explicit Makefile/config recipes may already cover it.

## Bounded acceptance

Use a small executable fixture matrix, not a new testing platform:

- Preserve existing single-stack Python/Node behavior.
- For root Node plus nested Python, enumerate both components with their locations and package-manager evidence. If mixed execution cannot be inferred, say so explicitly; do not claim complete verification after running only the root stack.
- For no-lockfile Django, select the existing appropriate Python-package-manager fallback and Django runners.
- For a Python repository without a Makefile, exercise the shipped runner's command-resolution path and prove declared check scope is honored. Use harmless fixture commands and a deliberately failing declared check to prove it actually runs; do not fetch toolchains or run real deployments.
- Demonstrate that at least the two reproduced detector cases fail on pre-fix code and pass after the change; assert fixture preconditions.
- Wire the fixtures into the existing test/verify path, and report each examined layout and any unsupported layout explicitly.

## Constraints and proposed approach

Depends on: None.

Prefer honoring explicit consumer Makefile/config recipes over inferred defaults. Retain component provenance rather than choosing one global package manager for unrelated components. The exact representation is a proposed implementation choice, not a requirement for a new public schema.

This is a bounded improvement to `lib/cicd` plus integration fixtures. It does not implement a general monorepo scheduler or extend language support. Install/update smoke coverage belongs to the readiness issue from this same assessment, so do not recreate the retired dual-client distribution matrix from #1074. Coordinate with #1271 for reliable test execution; it is not a logical prerequisite for authoring these fixtures.

Value-first sequence and related work: #1292. The sequence does not replace this issue's acceptance.

