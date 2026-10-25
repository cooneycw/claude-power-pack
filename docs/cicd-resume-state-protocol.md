# Resume-state evidence v1

CPP owns this additive producer protocol (#1555). It reports bytes the current
runner selected and generated, plus its observed terminal state. It establishes
neither writer ownership nor inherited gate success. The consumer owns stream
validation and reconciliation with its earlier controller-held stage evidence.

A JSON-mode run or explicit resume emits an optional `resume_state_evidence`
object inside its existing single runner-result document:

```json
{
  "version": 1,
  "family": "cpp-run-state",
  "plan": "check",
  "consumed": {
    "status": "loaded",
    "file": "check-ab12cd34.json",
    "sha256": "sha256:<64 lowercase hex>",
    "bytes": 1234,
    "reason": null
  },
  "generated": {
    "status": "written",
    "file": "check-ab12cd34.json",
    "sha256": "sha256:<64 lowercase hex>",
    "bytes": 1456,
    "reason": null
  },
  "final_state": {"status": "present", "reason": null}
}
```

The example's digest placeholders are explanatory, not valid fixture digests.
Every v1 object has exactly these top-level keys. Each identity has exactly
`status`, `file`, `sha256`, `bytes`, and `reason`; final state has `status` and
`reason`. A new reader refuses unknown keys/versions or contradictory fields.
An old reader may ignore the additive object. Missing metadata is unsupported,
never observed empty state or permission to reconstruct historical facts.

## Meaning and bounds

| Field | Allowed values and claim |
|---|---|
| `version` | Integer `1`, never a boolean |
| `family` | Literal `cpp-run-state` |
| `plan` | A logical id of 1-64 ASCII alphanumeric/underscore/hyphen characters, starting with alphanumeric; null when unavailable or unsafe |
| `consumed.status` | `none`, `loaded`, `unreadable` |
| `generated.status` | `none`, `written`, `unreadable` |
| `file` | Logical basename of 1-128 ASCII alphanumeric/dot/underscore/hyphen characters, starting with alphanumeric; no slash, backslash or control character |
| `sha256` | `sha256:` followed by exactly 64 lowercase hex characters |
| `bytes` | Non-boolean integer in 0..67108864 (64 MiB) |
| `final_state.status` | `present`, `absent`, `unreadable` |

A loaded/written identity has all three data fields and null reason. A none or
unreadable identity has null file/hash/bytes and a fixed safe reason. No raw
state, command, exception message or host path is copied into the object.
The original logical run id must derive that exact leaf (`run_id + ".json"`);
checking only a resolved path's basename would hide traversal or redirection.
A rejected requested id cannot publish innocent final presence merely because
the parsed id matches that basename; unnameable selected/write scope keeps final
state unreadable for the invocation. A selected file's parsed run id must agree as well. Absolute filesystem roots
are normal; absolute/separator-bearing logical ids are not supported evidence.
Unsafe logical values or state over the size bound yield unreadable protocol
evidence; they do not change the runner's existing resume choices or I/O.
This bound is on the evidence protocol, not a new cap on persisted state.

Reasons are a closed enum: `no-selected-state`, `no-save`, `not-observed`,
`selection-unreadable`, `input-unreadable`, `parse-failed`,
`serialization-failed`, `write-failed`, `short-write`, `cleanup-failed`,
`presence-unreadable`, `unsafe-logical-id`, and `size-limit`.

`consumed` identifies the exact byte buffer parsed into the selected state,
including automatic `find_latest`. It is not a later read of the file. A
candidate inspected and discarded for a tree-signature mismatch did not supply
this invocation's stage results and is not selected consumed input. A failed
selection scan with no usable selected state is unreadable, not clean none.
None means no input was selected; it does not say the directory was empty or
that another repository/attempt has no state.

`generated` identifies the exact serialized UTF-8 buffer successfully written
by this invocation. A complete write of unchanged bytes is written; no save is
none. A short or failed write cannot claim the submitted buffer was written.
A later failed save invalidates an earlier generated claim. The producer never
rereads the mutable file to manufacture generated identity. Transient evidence
and exception references are excluded from persisted state-file `to_dict`.

Final state observes only the selected/generated leaf, without reading its
contents to infer provenance. A real file is present; an observed missing leaf
is absent; a non-file/symlink or failed observation is unreadable. Successful
cleanup is followed by an observation: another file created meanwhile is
present, not assumed absent. Failed cleanup is unreadable. An absent final
state does not leave an inheritable surviving cache lease.

## Stage facts and errors

Normal success and step failure retain terminal in-memory `step_details` before
cleanup. Run and explicit resume share that result serialization; a post-run
filesystem reload never reconstructs missing stages. A nonfailed explicit
resume is a no-execution result: loaded input, generated none, and all returned
stage rows marked `executed_in_this_run: false`. It earns no fresh stage fact.

Direct state/runner APIs and no-JSON mode preserve the original state-operation
exception. JSON-mode `run_plan`/`resume_run` classify only the exact original
exception privately tracked by the current state I/O/parse/serialization
operation. They emit a single safe failure object and return 1:

```json
{
  "success": false,
  "error": "runner-state-unavailable",
  "state_operation": "save",
  "resume_state_evidence": "<the bounded object above>"
}
```

The explanatory string is an object in real output. `state_operation` is one
of load/select/save/cleanup. Known in-memory stage facts may be included as
structural diagnostics: at most 256 rows, with bounded logical stage ids,
known status values and boolean execution/carry flags only. Arbitrary persisted
tests, coverage, reasons or messages are never copied into this new envelope.
If diagnostics cannot be constructed safely, omit the whole list, without
replacing the minimal failure JSON or presenting a partial/empty population.
Unknown run/population fields are omitted rather than invented.
This error envelope establishes no gate or stage success. The existing
execution-evidence wrapper observes/re-raises first. Untracked same-class step
or configuration errors still propagate, as do errors outside this narrow
classification. Exception text and filesystem locations are never serialized.

## Consumer responsibility and controls

Normative cases are in `tests/fixtures/cicd-resume-state/cases.json`. Real
producer tests exercise its producer inputs; its malformed/missing/duplicate
stream cases are development and follow-up consumer controls. CPP adds no
unused stream validator and does not claim those cases are refused by CPP.

The skillc follow-up must reject missing/unknown/malformed/duplicate/incomplete
output and reconcile actual consumed identity with a prior admitted generated
identity for the same attempt, repository, source, plan and declared family.
It must compare exported surviving bytes with generated identity and reconcile
each carried stage with earlier attributable controller evidence. Seeded state,
before-load/restored swaps, after-save/export swaps, no-op laundering, missing
history and unconfirmed stop cannot become inherited credit merely by matching
hashes. Old pinned profiles remain conservative; no retrospective credit.

Same-UID filesystem writers are not excluded by a witness lock. Exact buffer
accounting exposes swaps; it does not authenticate an OS writer. The existing
single-document output contract rejects an appended forgery, but coordinated
replacement of the whole trusted stream remains an explicit trust limit.
