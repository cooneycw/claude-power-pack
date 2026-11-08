# Wave completion controls (#1658)

The runner drives the actual assign/complete/check CLI through separate
processes and a temporary store. BAD means the reconciler detects a missing
message with a usable receipt, or preserves a terminal failure/cancellation.
Each GOOD case repairs message delivery while keeping the same terminal
receipt, including failed and cancelled outcomes. UNKNOWN has neither message nor receipt and cannot report completion.

The constructed anchor changes only the check's receipt read to require a
message. The dropped-done case then fails to proceed, while its delivered
repair still succeeds. This is an executable model of the old message-only
policy, not vendored historical executable code: the old wave instructions had
no receipt/deadline helper. The baseline tests failed on that missing protocol;
separate store-readback and malformed-null regressions failed on the initial
implementation before repair. Pytest also executes the published shell recipe,
external-adapter round trips/failures/timeouts/empty responses/wrong identities,
and the one-extension deadline policy. These controls do not establish actual
cross-container storage availability or timer wake delivery; setup and deadline
checks are explicit operator actions, with unavailable evidence UNKNOWN.
