# Lanes demonstrated - issue #1821

<!-- lanes-demonstrated run=daff6dbf76224a8abff25c94f7c98a1d plan=ebdf649e52ca4d600e1a6e11a2410908cdd6d7aed65f9d05b1611dd1721fbb1c -->

| Lane | What was demonstrated |
|---|---|
| Checkout | tests/test_flow_plan_record_lanes.py `test_deleting_the_lane_file_after_approval_does_not_cancel_what_was_owed` and `test_the_clause_is_the_same_from_a_plain_repository_and_a_linked_worktree` run in both a plain repository and a linked worktree (make_checkout); this run itself ran in a linked worktree |
| Driver | The three delegated drivers' close step runs through `controls/delegated-{codex,qwen,gemma}-plan-lanes` (PASS) and tests/test_delegated_plan_lanes.py, against the new helper and the re-rendered drivers, including a foreign GIT_DIR. Limit: the new stale-evidence and deleted-lane-file cases are exercised through the helper directly, not through each driver's shell block; no live delegated run |
| Project state | Lanes adopted at approval vs never adopted, and the lane file absent/present/unusable at close: the approval x close combination test (45 cases), `bad-lane-file-deleted-after-approval`, and `test_a_project_without_lanes_at_approval_stays_silent_when_a_lane_file_appears` |
