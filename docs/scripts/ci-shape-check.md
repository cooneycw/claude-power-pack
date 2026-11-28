# ci-shape-check

Focused qualification for CPP (#1917, #1958), required by its review consumers.
Ordinary consumer repositories do no CPP qualification work.

```sh
make ci-shape-canary
make test-ci-shape
make ci-shape-check CI_SHAPE_RECEIPT=/absolute/path/local.json
make ci-shape-check CI_SHAPE_TIER=image CI_SHAPE_RECEIPT=/absolute/path/image.json
make ci-shape-ci CI_SHAPE_RECEIPT=/absolute/path/ci.json
```

Local runs require non-root Linux, uv and a working bootstrap Python. Image
runs require Docker (or `scripts/ci-shape-check.py run --tier image --backend
podman --receipt PATH`) and execute as actual uid 0 in the digest named by
Woodpecker's validate step. Missing prerequisites or unestablished preconditions
produce UNKNOWN/nonzero. The launcher does not install a container backend.
The image mount must be a standalone Git checkout, not a linked worktree whose
Git directory is outside the mount. See the committed
[host commands](../measurements/ci-shape-check/host-run.sh).

Each tier creates an isolated private Git donor at the exact committed HEAD,
then two real file-transport clones: `--depth=1` and `--depth=1 --filter=tree:0`.
The donor supports filtering. A separate historical witness commit is fetched
without its tree; a present commit with unavailable old file contents proves
that the clone really omitted objects. It is an explicitly synthetic transport
witness, not a substituted historical CPP revision. The actual historical CPP
pin must be absent too. After HEAD is checked out, lazy fetch is disabled and
the clone's origin points to an absent private remote, including for Git 2.39
which predates the no-lazy-fetch environment switch.

Both clones use CI=true, checkout umask 000, verified 0666/0777 tracked inputs, private
0700 HOME, a symlink TMPDIR, external cwd and a small executable PATH with Git
and Make available only through the existing content-pinned stagers. No host
Git configuration or credentials are copied. Test dependencies are synced from
the frozen project lock into an owned environment. Nothing changes the caller's
HOME, PATH, umask or Git configuration. Serial pytest has a per-test timeout and
a bounded whole-lane timeout. The pytest-time umask comes from the digest-bound
validate profile; absent actual image evidence is UNKNOWN and prevents a run.
The 000 mask applies to checkout creation. Owned temporary directories and basetemps are
removed after each run; receipts and logs remain at the requested output path.

`lib/ci_shape_check.py` owns the fixed focused selector population and probes.
`lib/ci_shape_pytest.py` records collection, terminal outcomes, skips and errors.
An exit zero cannot pass without complete terminal results, a population of at least 200 and every named
acceptance witness. Passing tests are required for every
selector, and INTERNALERROR is always BAD (#1923). The two full historical
installer cases (`real-pre-e32-install` at 5204ea06 and `real-v13-install` at
40d25173) are expected omissions in both shallow/filtered shape lanes. The
shape-only collector marks them at collection, before fixtures run. Each lane
declares both exact node IDs and the fixed reason; completion refuses an
unexpected pass, absent skip, changed reason or missing declaration. Ordinary
full-history validation is unchanged. Root-only skips remain explicitly named.
A passing local run has a GOOD local tier
and an UNKNOWN root column: `not examined: needs real uid 0`. It never claims
root success. Image/root evidence has a separate receipt.

The shared source's automatic-GC fix is exercised by the separate required,
executed `test_source_publication_joins_automatic_gc` witness. A historical
installer setup error happens before its old availability check, so reaching
that setup never proved the historical installer executed. Those skip outcomes
prove neither historical installation nor the GC fix. Cite the committed GC
regression's red/green for the fix, separately from the shape receipt.

Receipts bind the exact commit, declared tier, image pin, tool identities,
observed preconditions, identity, selectors, terminal outcomes/counts, named
skips, durations and log hashes. To recheck one for a review checkpoint:

```sh
uv run python scripts/ci-shape-check.py verify /absolute/path/local.json \
  --tier local --commit COMMITTED_CHECKPOINT_SHA
```

Exit codes are 0 GOOD, 1 BAD, 2 UNKNOWN. GOOD is bounded to the named tier and
population; this qualification is not the full finish gate. The image field on a
local receipt identifies the comparison target, not an image that was run.
The image launcher pins the actual runtime argument; the inside-image runner's
private marker is an execution assertion, not a cryptographic attestation.
Keep the host launch command and backend/image identity alongside its receipt.

The CI entry runs directly inside the step, without launching a container.
It requires `CI=woodpecker`, a positive `CI_PIPELINE_NUMBER`, an exact
`CI_COMMIT_SHA` matching the checkout's actual HEAD, actual uid/euid 0, and a
literal `ci-shape` image pin equal to validate's. Missing, malformed or mismatched
context is UNKNOWN before the producer runs; a generic `CI=true` is refused.
This checks declarations and checkout identity, not authenticated pipeline
provenance or independent image attestation. The host reproduction supplies the
same context variables, with a synthetic positive pipeline number and its exact
checkpoint SHA; it cannot establish that a real pipeline ran.
The runner creates its own environment and clones; it does not sync the shared
validate environment. The required step depends on staging and generated Codex
output, and overlaps validate. The pre-wiring image measurement took 475.7s;
actual PR timing must confirm that the new step finishes before validate and
that neither validate nor pipeline wall time rises by more than about 120s
against recent runs of the same event type. Report a breach before merging.

`codex-review-run.sh` qualifies the target checkout after diff collection and
before review. Its `--qualify-only` entry supplies the same admission check for
alternate reviewers, without probing or launching Codex. CPP GOOD admits; BAD,
UNKNOWN, duplicate/missing result markers, nonzero status, or a moved/dirty
checkpoint blocks. No cached success or trusted bypass exists. A non-CPP
project, including one carrying similarly named shape files, invokes no CPP
Make entry, environment sync, tool staging or image launch. Committed neighbor
and lookalike cases exercise both entries and trip on unexpected expensive work.

Changes to runner/consumer code, selected tests, shape configuration or image
require fresh local and actual pinned-image qualification of the committed
checkpoint. Previous PR-A root receipts do not qualify new code. A data-only
carry requires an explicitly bounded comparison; never infer it from filenames.

[Controls](../../controls/ci-shape-check/README.md) and
[acceptance measurements](../measurements/ci-shape-check.md) describe the
negative cases and proof limits. #1924 remains a held proposal; this change
does not relax review caps or classify test-only changes as harmless.

For PR-A's bootstrap only, the approved data/docs carry is checked explicitly:

```sh
make ci-shape-bootstrap-check CI_SHAPE_ROOT_CHECKPOINT=ROOT_CHECKPOINT_SHA
```

It proves the root checkpoint is an ancestor and only the named profile,
receipt and measurement/document paths changed through HEAD. A source-code
change is BAD. This qualification applies to the initial root-profile carry;
routine future local checks validate the profile against the committed root
receipt's image, observed mask, complete identity and digest.

Cancellation owns the active pytest process group through shutdown (#1961).
TERM, HUP and INT stop its leader and descendants before the producer exits;
a descendant that ignores TERM is killed. Prior signal handlers are restored
when the run returns. An interruption exits with `128 + signal`, never GOOD.
The committed cancellation witness runs tiny real pytest inputs, including a
blind old owner, and is part of the focused selector manifest. Its controlled
checkout/probe setup is not physical shape or root qualification; live lease
release is measured separately from the normal test suite.

If cancellation coincides with an unconfirmed group stop, the cleanup failure
is reported as `CI_SHAPE_CANCEL: UNKNOWN` and chained to the interruption.
The signal exit still wins, so the caller cannot start another lane or turn
the interruption into a returned UNKNOWN lane.
