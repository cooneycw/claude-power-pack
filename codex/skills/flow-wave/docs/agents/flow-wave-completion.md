# Wave completion receipt-store interface, version 1

`flow-wave-completion.py` owns assignment deadlines and validates receipts.
A receipt adapter supplies storage only. It has no authority to decide that a
role succeeded, to extend a deadline, or to infer completion from a message.
The filesystem implementation is the default. Other services can supply an
executable adapter without changing CPP. CPP has no Kyle substrate dependency.

## Configuration and invocation

- `--state-root /absolute/existing/path` or `FLOW_WAVE_COMPLETION_ROOT` names
  coordinator assignment storage. Explicit CLI wins. The filesystem default
  also stores receipts under this root, requiring shared access by both roles.
- `FLOW_WAVE_RECEIPT_ADAPTER` is an optional JSON array of nonempty argv strings.
  Example: `["/opt/store/bin/adapter", "--profile", "wave"]`. An empty variable
  selects the filesystem default; invalid JSON does not fall back to it.
- `FLOW_WAVE_RECEIPT_TIMEOUT` is a finite number of seconds, inclusive range
  0.05-60, default 10, used per adapter invocation. It is not the assignment
  deadline and does not extend it.

CPP runs the argv with `[VERB, KEY]` appended, with no shell. VERB is `get` or
`put`. Each call is a new process; the adapter may not rely on in-process state.
It inherits the caller's working directory and environment for service configuration, so configure the
same shared service/namespace in both roles. CPP does not print adapter stderr. Stdin/stdout are explicitly UTF-8. Parse
JSON objects; do not compare serialized JSON bytes or depend on whitespace or
field order. The helper emits compact put envelopes, but both escaped and raw
UTF-8 string representations are valid.

`get` receives empty stdin. `put` receives a JSON object on stdin:

```json
{"key":"v1-<64 lowercase SHA256 hex characters>","receipt":{"schema":1,"identity":{"wave":"example","role":"worker","assignment_id":"task-a","generation":1},"outcome":"succeeded","finished_at":"2026-11-08T23:00:00Z","evidence":"log/reference"}}
```

A successful adapter exits 0 and writes exactly one JSON object with exactly
`key` and `receipt` fields to stdout. JSON whitespace is allowed; progress text
is not. KEY must equal the requested key. `get` returns the stored receipt or
`{"key":KEY,"receipt":null}` for **known absence**. A successful `put` returns
the authoritative stored receipt; null is not a successful publication.
An empty response is UNKNOWN, even with exit 0. Any nonzero exit, unavailable
executable, invalid JSON, wrong key, malformed or mismatched receipt is UNKNOWN.
There is no special 'not found' exit code: use the explicit null response.
Duplicate object keys and non-finite JSON numbers (`NaN`, `Infinity`,
`-Infinity`) are rejected anywhere in a response or stored JSON document.

A `complete` operation makes up to three adapter requests: initial get, put,
and readback get. Its request budget is therefore up to 3 times the configured
timeout, plus process startup/teardown; `check` makes one get. An assignment
deadline is independent of this request budget.

A timeout terminates the adapter's process group, including descendants, and
reports UNKNOWN. CPP also terminates remaining descendants when an adapter
request exits. The adapter must not daemonize work or acknowledge a write
before durable publication. Completed stdout longer than 1,048,576 characters
is rejected. This is a validation limit, not a streaming memory limit.

## Identity, key and receipt schema

`identity` is the object with exactly these fields:

| Field | Type | Constraint |
| --- | --- | --- |
| `wave` | string | ASCII letter/digit first, then letters/digits/underscore/dot/dash; 1-128 characters |
| `role` | string | Same token constraint |
| `assignment_id` | string | Same token constraint; a new identifier for each assignment |
| `generation` | integer | 1 through 9007199254740991 (2^53-1); strictly increasing for new assignments; booleans are not integers |

The key is `v1-` plus the lowercase SHA256 hex digest of the UTF-8 identity JSON
with keys sorted lexicographically, **no whitespace**, no trailing newline.
Python reference:

```python
key = 'v1-' + hashlib.sha256(
    json.dumps(identity, sort_keys=True, separators=(',', ':')).encode('utf-8')
).hexdigest()
```

For `{wave:example, role:worker, assignment_id:task-a, generation:1}` the exact
hashed bytes are:

```text
{"assignment_id":"task-a","generation":1,"role":"worker","wave":"example"}
```

Adapters treat the key as opaque and return it unchanged. It is a namespace key,
not authentication. Access control belongs to the configured store. A hash/key
match alone never substitutes for checking the full receipt identity.

Unknown receipt fields are rejected; the identity also permits only its four
named fields. Receipts require exactly the following five fields.

The receipt contains `schema` (integer 1), `identity` as above, `outcome`
(`succeeded`, `failed`, or `cancelled`), `finished_at` (string matching exactly
`YYYY-MM-DDTHH:MM:SS[.ffffff](Z|+00:00)`, with 1-6 fractional digits when
present and a valid calendar date/time. Basic dates, space separators, leap
seconds, `-00:00` and other offsets are rejected), and `evidence` (string, at most 4096 characters, possibly
empty). The coordinator permits up to 5 seconds of positive worker-clock skew. A
timestamp more than 5 seconds ahead is UNKNOWN; retry after checking clock
synchronization before escalating. This does not extend an assignment deadline. Evidence is an
opaque reference, not proof that the work or tests passed; do not store secrets.

## Put semantics and publication acknowledgement

The filesystem store is initialized by `assign`, with a persistent root marker
and receipts directory. A missing/moved directory after initialization is
unavailable, not known absence, and is never recreated by a check. The
coordinator also retains a per-role initialization marker outside its assignment
directory, under `<root>/.assigned-roles/<wave>/<role>.json`. Missing assignment
state after initialization is UNKNOWN; retries cannot reset extension history.
The marker reserves the highest assignment identity before publishing its
state. If publication is interrupted, only a new strictly higher generation
may recover the role; retrying the reserved generation stays UNKNOWN. An old
assignment cannot consume or reset the new generation's extension budget.
Do not delete markers or reuse the interrupted generation. Writes sync
the file and containing directory; new state directories sync their parents.
Reading an existing filesystem receipt also syncs its containing directory
before using it, so a failed writer sync cannot be skipped by a retry or reader.

Filesystem receipt, assignment and marker JSON files use mode 0600. Roles
running as different uids therefore cannot read each other's default store
and receive UNKNOWN unless access is explicitly provisioned; use a shared
adapter when private uid boundaries prevent filesystem sharing. Lock files
follow the caller's umask.

Put must atomically create an immutable terminal receipt. For concurrent calls,
there is one authoritative result. Retries with the same schema, identity,
outcome and evidence return the original receipt, including its first
`finished_at`; a retry's timestamp does not replace it. Different outcomes or
evidence for the same key must not overwrite the result. On a conflict the
adapter may return a nonzero exit (CPP reports UNKNOWN), or the existing receipt
(CPP rejects a differing result). The helper also refuses a known conflicting
receipt before attempting put. This known conflict returns `refused`, exit 1
for either backend. A filesystem conflict detected under its publication lock
also returns `refused`. An adapter put-time conflict/nonzero response is
`unknown`, exit 3, because this protocol does not distinguish an atomic-store
conflict from an unavailable service. Returning a contradictory existing
receipt from put is likewise UNKNOWN. All preserve the original result; no
client may treat exit 1 or 3 as publication success. Reassign with a new identity/generation when
new work is authorized.

After put, CPP performs get and requires the same receipt. A store that
acknowledges without making the receipt readable is UNKNOWN. This immediate
readback is not a proof of crash durability or remote access. The adapter must
provide durable writes; the setup probe in `/flow:wave` must be read from the
coordinator's own service configuration. No CPP local test attests to an
external deployment's storage or permissions.

## Helper results and deadlines

The helper emits a JSON result for normal reconciliation/storage failures.
Successful `assign` (`assigned`) and publication (`recorded`) exit 0. `check`
exits 0 only for a matching succeeded receipt; matching failed/cancelled receipts
have `status:complete` and exit 1. A conflicting mutation is `refused`, exit 1.
Unusable evidence/store or expiry after the single extension is exit 3
(`unknown` or `escalated`). Pending work or the one persisted extension is exit
4 (`waiting` or `extended`). CLI syntax errors use argparse exit 2 and are not
completion evidence. The caller must inspect both status and outcome.

The coordinator schedules deadline checks, including after it resumes from an
interruption. The helper neither sends messages nor installs timers. Fresh
liveness is supplied by the caller using the existing registry/native observation
rules; CPP checks its timestamp age (0-60 seconds) and never probes a remote PID.
A completion message may prompt an earlier check but cannot replace a receipt.
