A valid bundle (`bundle-1/`) plus a `skill-evidence` record whose one entry
declares `reconciliation: matched`, citing a usage-record payload with its
`observed.checks[0].population` field deleted - the exact #1373 shape
(`_structure_errors`, `lib/cicd/evidence.py`). skillc's `check-records`
validates only the reference's shape (path/digest), never decodes the bytes
(R14, `.specify/specs/per-skill-audit/spec.md`), so this genuinely malformed
payload is invisible to skillc and is #1369's own job to catch - the owner
explicitly required this committed case (cpp-eval mailbox 5225, 2026-10-06).
Built from `good-bundle-skill-evidence-matched` with the one field removed
and both the manifest entry and the skill-evidence `artifact_ref` digest
updated to match the corrupted file's new hash.
