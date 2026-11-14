# Driver parity checker

`make driver-parity-check` builds the real `flow-auto` Codex mirror and checks
its helper membership alongside the Codex, Qwen and Gemma command documents.
The three delegated families intentionally have no generated Codex mirror.

The inventory comes from command positions in `flow/auto.md`, including the
individual plan-record verbs. An empty, short or
unparseable population reports UNKNOWN. This is static membership evidence;
it does not establish flags, ordering, live execution, or semantic equivalence.

`docs/agents/driver-parity.json` records run, owner-approved equivalent and
exempt dispositions. Every entry needs a reason and issue link. Equivalent
citations must still match their exact file and line. Stale entries fail.
Approval and compliance cannot be waived. Issue #1811 stays open to track the
known omissions; the landing closes #1810, not those gaps.

The control in `controls/driver-parity` exercises invented calls, missing driver
coverage and invalid/stale policy. Its constructed fixed-list anchor misses
those defects; it is not historical source. Control mirrors are fixtures;
`tests/test_driver_parity.py` separately builds and reads the actual generator
output. The pre-#1809 source is deliberately red for 15 required verb pairs.

Split mirrors must direct the reader from SKILL.md to reference.md. Every
rendered helper/verb retains an invoked bundled primary address and its helper
file; the generator's explicit CPP-checkout exceptions remain exceptions.
Fallback path/phase behavior is not inferred from this membership check.
