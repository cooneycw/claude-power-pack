# Lanes demonstrated - issue #1714

What happened in each lane the approved plan answered `will test`.

| Lane | What was demonstrated |
|---|---|
| Checkout | The scope probe, run from the document's own Step 3 block under `set -o pipefail`, in a temporary repository with 8,000 tracked files (a listing several times a pipe buffer): scope reads `full`. On main's document the same test reads `unverified` (`tests/test_code_review_sandbox_scope.py::test_the_probe_survives_pipefail_in_a_large_checkout`). A linked worktree was not exercised separately. |
| Project state | `.claude/lanes.md` present and absent (existing tests), a dangling symlink in its place, and a real file under an unsearchable `.claude`: the last two now hand over the could-not-be-read line and fail on main (`tests/test_lanes_contract.py`). |
| Reader: counter-model-receipt.py, which binds the reviewed patch | NOT demonstrated, and no longer applicable. The plan's test was a receipt written after a repository-route run. That route was built, found to have ten defects by one review pass and an independent read, and withdrawn to #1769 before merge. What ships blocks an oversized patch before any model call, so there is no run to bind; a patch at or under the threshold is piped exactly as before, byte for byte (`test_a_patch_at_or_under_the_threshold_is_piped_at_every_scope`). |
