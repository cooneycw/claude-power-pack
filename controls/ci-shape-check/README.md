# CI shape controls (#1917 PR-A)

`make ci-shape-canary` drives the real clone/environment probes and real tiny
pytest subprocesses, followed by the production receipt verifier. It does not
run the repository's complete focused population. The synthetic source contains
small tests for each declared selector and named witness, plus enough
parameterized canaries to clear the committed population floor, allowing the collector and completion check to be
exercised without recursively running the suite. The control's declared `uv run --extra dev --frozen python` runtime supplies pytest even when the global control driver lacks it.

GOOD proves a canary can complete; BAD cases change actual modes, PATH, Git
configuration, shallow boundary, historical object availability, TMP identity
or CI. Other BAD cases erase one real terminal outcome, capture an actual child
that prints INTERNALERROR and exits zero, or mislabel local evidence as root.
UNKNOWN represents an unavailable required tool. The availability-only anchor
must miss every BAD and agree on GOOD/UNKNOWN. This is a constructed anchor,
with its digest in `control.json`, not a claimed historical implementation.

`history/provenance.json` identifies immutable predecessor excerpts and their
digests. `tests/test_ci_shape_check.py` exercises their specific failure paths:
copied mode comparison, missing pinned history, commit-versus-file presence in a
real filtered clone, and expensive pytest byte assertion rendering with CI=true.
The root chmod and exact hardcoded system PATH witnesses run only at real uid 0
in the pinned slim image. Local skips remain unexamined root/image evidence.

The historical byte-diff child is deliberately bounded to four seconds and
captures a traceback after one second. The fixed child must finish successfully
in the same bound. This establishes the known failure input on this run; it is
not a general performance benchmark or a promise about all machine speeds.

The controls do not authenticate a container image, test a container backend,
or prove the complete focused suite ran. Those facts come from separate real
run receipts and the host/image execution record. No fake uid is used.

The fixed selector manifest and floor (200) live in `lib/ci_shape_check.py`.
Every required historical witness is pinned by node id; removing one refuses
collection even if total counts still clear the floor. The committed
missing-witness and below-floor BAD cases distinguish these failures.

Bootstrap carry is a separate one-time qualification command. Its real-Git GOOD
fixture changes a named measurement document; its BAD fixture also changes
executable source. The same availability-only anchor misses the code delta.
The digest-bound local umask profile remains UNKNOWN until the actual root run
supplies image, full identity, mask and receipt digest. Parser tests use plainly
synthetic JSON identity fields; they do not establish a real-root run.
