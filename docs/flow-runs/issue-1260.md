# Flow run record - issue #1260

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1260
- Base SHA:          bdd2d14d5a4ffc8994d54d3b354a599674d97877
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          cooneycw (repository owner, interactive "approved")
- Recorded at:       2026-09-27T10:50:00Z

## Section B evidence
- commits: none touching scripts/flow-wave-mailbox.sh, scripts/flow-wave-registry.sh or their tests since 2026-09-26T14:12Z
- PRs merged since filing: #1283, #1280, #1279, #1275, #1274, #1270, #1255 (none touch these files)
- duplicate/superseding issues: none
- reproduced on bdd2d14: send --body - stores "-"; mailbox list and registry list recreate a deleted wave dir
- re-dispositioned, not coded: S2 watch_state_of unknown-lineage headline (two-sided ADR 0009 call); S2 stand-down report prose half (worker prose, not these scripts)

## Section C - the approved plan
1. `scripts/flow-wave-mailbox.sh` - --body - reads stdin; only writing verbs create the wave dir; list reports absent; supervise daemon exits wave-gone and its inner watch cannot create; inner watch backgrounded + wait so TERM/INT act at once; armed watch exits owner-gone when its arming session dies
2. `scripts/flow-wave-registry.sh` - orchestrator overlap exemption only when it declared no issue/branch/files; unreadable registry is error/undeterminable, never {}
3. `tests/test_flow_wave_mailbox.py` - red cases for --body -, list/supervise on deleted wave, prompt signal, watch owner-gone
4. `tests/test_flow_wave_registry.py` - red cases for orchestrator-with-files overlap and unreadable registry
5. `codex/skills/**` - regenerated mirrors if the scripts are bundled
6. `docs/flow-runs/issue-1260.md` - this record
7. `docs/measurements/counter-model/*.json` - counter-model receipt

Scope: ~4 code/test files, ~250-400 lines.
Risks: tests relying on read/watch --status creating the dir; unreadable-registry guard turns a silent {} into an error for callers; owner-gone test needs #1228 fake-ancestry scaffolding.
