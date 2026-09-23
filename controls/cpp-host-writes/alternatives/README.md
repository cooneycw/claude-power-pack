# Alternative implementations - NOT anchors

These are wrong implementations of the unread-seam-verdict check (issue #1198),
kept because each one excuses a committed case and so justifies that case's
existence. They are driven by `tests/test_cpp_host_writes.py`, not by
`scripts/check-negative-controls.py`.

**They are deliberately not in `anchors/`.** That directory has a specific
contract: an anchor must MISS every committed bad case, because it represents
the blind version the gate replaced, and the battery marks the whole control
INERT if an anchor catches one. Measured - registering these as anchors produced
`anchor constructed CAUGHT the known-bad input, so this control would not notice
the gate regressing to it`, which is the battery being right.

Neither of these is blind in that sense:

- `naive-next-line-...` is PARTIALLY blind. It catches the claim-shaped case and
  misses the silent loop and the heredoc-data case. An anchor blind to only some
  of the register is not the artifact the battery models.
- `over-broad-...` is not blind at all - it is the opposite error. It catches
  every bad case AND reds on the fix, so it is what the `good-` cases exist to
  separate the gate from.

The `good-` cases stay sanity cases in the battery's sense, where the anchor is
REQUIRED to agree with the gate. Their discrimination against the over-broad
framing is asserted in the test instead, which is the right place for it: the
property is "this gate is not that gate", not "this control's anchor is blind".
