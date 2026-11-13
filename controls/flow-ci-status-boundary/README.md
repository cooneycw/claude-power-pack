# Flow CI public/worker boundary (#1758)

The owned cases cover approved rows (a)-(e): stalled automation exit,
single-shot unknown/not-found, invalid refs without requests, a legacy backend
preset versus recorded selection, and explicit worker provenance/output.
Three GOOD cases preserve fallback success, recorded success and advisory stall.

The fixture isolates the real shell, dispatcher and canonical provider reader
in one temporary package and uses JSON-subset provider records. Stub HTTP and
Actions responses are owned, request counts are observed, and a Git ceiling
prevents an ancestor checkout from rescuing an invalid or uppercase ref.
There is no real CI service, network, credential, or provider authentication.

The constructed anchor is an isolated bundle of exact pre-change main
`35c51d81424999849f496f325a51ecc7b7ea9367` sources, with a SHA256 for each
member and the bundle descriptor. Freezing only the shell would accidentally
import a fixed current dispatcher and could hide the ref defect. The source
package is staged for the candidate too, so both run through the same fixture.

Before product edits, both current code and the frozen anchor miss all 13 BAD
contracts while passing all three GOOD contracts. A BAD here is unsafe boundary
behavior; a successful runtime unknown/2 refusal is scored as detected BAD, not
as control unavailability. An unsupported fixture/dependency is separate.
Existing provider-marker equality is preserved independently by the constructed
blind-comparison unit case; it already rejects a mismatch on main.

The invalid-ref BAD cases deliberately hide Python from PATH while keeping
Bash, jq, Git and the other shell tools available. This exercises the explicit
compatibility fallback: removing its shell ref-refusal guard alone must expose
requests. The public Python pin resolver is covered separately by unit cases,
so the two validating layers cannot mask each other in this control. An added
GOOD valid-ref not-found wait requires expiry 5 and is shared by the old bundle.

| BAD cases | Decisive guard |
| --- | --- |
| `bad-a-stalled-*` | `emit` applies `--exit-code` to stalled as well as failure |
| `bad-b-not-found-*`, `bad-b-unknown-*` | `emit` returns 2 after checking wait expiry |
| `bad-c-invalid-ref-*` | Shell compatibility path refuses unresolved/non-commit refs before credentials or requests |
| `bad-d-preset-*` | Public dispatch depends on worker context, not a nonempty backend preset |
| `bad-e-worker-no-tool-*` | Worker provider starts `none`; explicit worker selection is emitted once |

Each of these single-guard mutations was executed against its own BAD population
and caught. The two worker-case populations separately catch restoring the
requested provider seed and deleting the worker-selection line. The attribution
unit test remains a preservation case, not a claimed new regression.
