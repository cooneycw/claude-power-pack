"""A fixture bandit MUST report at this gate's severity (issue #962).

`--selftest` audits this tree live and refuses to issue any verdict unless the
scan reported something here and nothing in `../good-clean`. That is the half a
replayed capture cannot cover: a capture proves the adjudication logic, never
that bandit was invoked, or invoked against the file we meant.

THE RULE IS CHOSEN, NOT INCIDENTAL. `eval()` is B307, MEDIUM severity, HIGH
confidence. Two properties matter and both are asserted by
tests/test_bandit_audit.py rather than left to this comment:

  * B307 is NOT on codex-power-pack's inherited `--skip B104,B108,B310,B602`.
    Issue #962 names this as the way this control gets built blind - "pick a
    fixture triggering a skipped check and it goes green while the gate is
    doing nothing, which is indistinguishable from a working gate".
  * B307 appears on NO line of `.bandit-audit-allow`, so the accepted residual
    cannot account for it either. The allowlist is the skip list's replacement,
    so it is the second list this fixture has to be outside of.

MEDIUM rather than HIGH deliberately: the gate's threshold IS medium, so a
HIGH-severity fixture would pass even if the threshold had drifted upward.
"""


def evaluate(expression: str) -> object:
    return eval(expression)  # B307 - the point of this fixture
