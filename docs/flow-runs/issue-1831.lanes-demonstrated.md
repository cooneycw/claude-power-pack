<!-- lanes-demonstrated run=0825157b7c3c49e7b362993a0a0e3394 plan=b7941f02ebf153953c5a4e745c1a2f4cd4253b54de9a3989cfc42a936112d9fe -->

# Lanes demonstrated - issue #1831 run 1

| Lane | Result | Evidence |
|---|---|---|
| Checkout | passed | main checkout: `tests/test_flow_finish_gate.py::test_coordination_lease_says_what_it_is_for` builds a plain repository for every layout (18 layouts). Linked worktree: not run; the lookup reads only the branch name and origin URL |
| Harness | passed | Claude install: the tests run `scripts/flow-finish-gate.sh`, which is the file a Claude install links into `~/.claude/scripts` (counter-model review asked for an installed copy; the link means there is no separate copy to diverge). Codex install (a copied bundle): not run |
| Coordination | passed | with Kyle: every layout runs with `CPP_KYLE_COORDINATION_ADMISSION=1` against the test's recording authority, which records the lease argv the gate hands `kyle-lock`. Without Kyle: the lookup is not reached; covered by the gate's existing admission-off tests. A live `kyle-lock` is not run |

Readers (counter-model review): `kyle-lock run` receives `--pr` as an argument; the test reads exactly that argv from the recording authority, not a live client, and the only change is that `--pr` is left out more often. The operator reading `kyle-lock status full-suite` sees that field; unchanged in shape.
