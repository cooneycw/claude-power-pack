<!-- flow-run n=1 id=b86d11f11c304e4fb15cf5b1fb831cb2 -->
## Run 1 - issue #1341 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1341
- Read at:      2026-09-28T21:41:27Z
- updatedAt:    2026-09-28T21:40:12Z   (context only - moves on comments and labels)
- Body digest:  5a84e0e802c2f4b29dee40e9c5d8450f2b6eb94afaaf8948ccd2086c6173566b   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1078 of 1078 (cap 16384)

### Body as read
Child of #1268 ("the rest", FIX candidates), split so three workers can run in parallel without sharing a branch or a `docs/flow-runs/issue-1268.md` plan record. Items as reproduced on c6b02fa by the run45 wave (see the #1268 wave-close comment); re-reproduce each on current main before planning.

**Files:** `lib/security/modules/secrets.py`, `lib/security/modules/pip_audit.py`, `tests/conftest.py` (plus their tests).

1. **The security scan counts the runner's own state.** `lib/security/modules/secrets.py` scans `.claude/cicd-state/*.json` (`.json` is in `SCAN_EXTENSIONS`; `.claude` is not in `SKIP_DIRS`). Skip exactly `.claude/cicd-state`, not all of `.claude`.
2. **`lib/security/modules/pip_audit.py:112`:** `assert temporary_requirement is not None` is erased under `-O`. Replace it with an explicit raise.
3. **`tests/conftest.py` `_guarded_binaries`** anchors on `Path(__file__).resolve().parents[1]` rather than the module-level `REPO_ROOT` (#1232), which breaks inside a pytester sub-run.

Each fix needs a red case that fails on the pre-fix code. Refs #1268.

