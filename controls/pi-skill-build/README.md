# Pi A1 file snapshot controls

Committed case descriptors materialize a complete canonical topic, a fresh real
build and an independently mutable comparison tree. The actual CLI, bundled
checker and drift reader receive those bytes. Member removal, marker removal,
one-byte reference edit, unsupported source manifest and absent source have
explicit precondition assertions. No install or provider/runtime claim is made.

`pi-skill-build` registers the new builder/fidelity contract. The sibling
`pi-bundled-parity` and `pi-drift-reader` controls register the actual readers,
using the same scenario population and runner. The constructed always-clean
anchor must agree on the healthy case and miss the bad/unknown cases; this
establishes that the controls themselves can fail.

The metadata-history case belongs to the builder's path guard only. Runtime RPC,
transient-write syscall observation, ownership/adoption and locking are A2 work.

Inverse-containment inputs put the agent or selected history root beneath the
output root and must be refused before fidelity descends. A group-writable
source is a GOOD input; a regular executable Markdown source remains BAD.
The pinned generator under `reference/` is exact historical source, not the
constructed blind anchor. Its commit and byte digest are recorded in
codex-baseline.json and verified before same-candidate-input comparisons.
