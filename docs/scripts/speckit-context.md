# `speckit-context` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `speckit-context`

- speckit-context - resolves, renders and refreshes the task-context cache in a generated issue (#858). A generated issue used to carry its provenance and dependencies and nothing about the behaviour it was meant to produce, so a receiving agent could not tell which words were the goal and which were somebody's suggested mechanism. The rendered block is a CACHE, not a second authority: the spec it names stays authoritative, every part traces to a source section and carries a digest, so drift is visible instead of silent. `check` emits `SPECKIT_CONTEXT_STATE`, whose values separate facts a consumer must act on differently - `changed-in-scope`/`changed-outside-scope` are a byte difference and NOT a ruling that acceptance changed, `changed-task` means the task line or its story tag moved so the cached mapping no longer holds, `block-edited`/`block-damaged` mean the block is unreliable, and `absent` is an ordinary issue whose body is the contract. A failed `gh` leaves an empty body and an empty body reports `absent`, which is why `/flow:auto` Step 2 checks the fetch succeeded before believing the verdict
