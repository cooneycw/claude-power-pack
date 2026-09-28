# Flow run record - issue #1333

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=2b9e211fddcf4745ada957c5fa2cbcd2 -->
## Run 1

- Run-id:            2b9e211fddcf4745ada957c5fa2cbcd2
- Run-start:         1d8487d99146943dbea3ee780b316a38e6a07f5d
- Issue:             #1333
- Base SHA:          1d8487d99146943dbea3ee780b316a38e6a07f5d
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 2335 in reply to ELI5 message 2334
- Recorded at:       2026-09-28T18:12:34Z

### Section B evidence
- No PR or branch for #1333. tests/test_detector_contracts.py maps count words through two literal dicts
  (index: eighteen..thirty-five; properties: Five..Ten); docs/agents/detector-contracts.md reads
  "The thirty-one instances" and "Seven properties".

### Section C - the approved plan
1. `tests/test_detector_contracts.py` - one stdlib count_word() parser (1-199, hyphenated, case-insensitive, raises on anything unparsed) replacing both literal dicts; heading checks as pure functions over the text; committed cases: off-by-one red per heading, growth-to-fifty pass (red on pre-fix), unparseable word raises, parser spot checks and refusals

Scope: one file, ~90 lines. Risk: weakening the real-document tests - they still run on the real file; a hand bump of the real heading must go red.
