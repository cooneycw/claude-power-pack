# ci-shape-check

Opt-in focused pre-CI shape check for CPP (#1917 PR-A). Review and Woodpecker
wiring are a separate PR, after the controls and portability smoke qualify it.

```sh
make ci-shape-canary
make test-ci-shape
make ci-shape-check CI_SHAPE_RECEIPT=/absolute/path/local.json
make ci-shape-check CI_SHAPE_TIER=image CI_SHAPE_RECEIPT=/absolute/path/image.json
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
selector, and INTERNALERROR is always BAD (#1923). Root-only skips and the two
named unavailable/partial historical-installer cases are explicitly permitted;
their reasons remain in the receipt. A passing local run has a GOOD local tier
and an UNKNOWN root column: `not examined: needs real uid 0`. It never claims
root success. Image/root evidence has a separate receipt.

Receipts bind the exact commit, declared tier, image pin, tool identities,
observed preconditions, identity, selectors, terminal outcomes/counts, named
skips, durations and log hashes. To recheck one for a review checkpoint:

```sh
uv run python scripts/ci-shape-check.py verify /absolute/path/local.json \
  --tier local --commit COMMITTED_CHECKPOINT_SHA
```

Exit codes are 0 GOOD, 1 BAD, 2 UNKNOWN. GOOD is bounded to the named tier and
population; this opt-in gate is not the full finish gate. The image field on a
local receipt identifies the comparison target, not an image that was run.
The image launcher pins the actual runtime argument; the inside-image runner's
private marker is an execution assertion, not a cryptographic attestation.
Keep the host launch command and backend/image identity alongside its receipt.

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
