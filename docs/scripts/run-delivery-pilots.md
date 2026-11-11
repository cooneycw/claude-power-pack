# `run-delivery-pilots` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `run-delivery-pilots`

- run-delivery-pilots - runs the bounded delivery pilots for #861 and records what was observed. CHECKED IN deliberately: the #859 and #860 evidence bundles were runnable only from the author's machine, their runners pointing at a worktree path that no longer existed, so a reviewer could read the transcripts but re-run nothing and the claims rested on a path nobody else had. The guidance handed to the model and the scripts building the input are read from a REVIEWED COMMIT with `git show`, never the working tree (`--commit` pins one, default HEAD), so the prompt a result came from can be reconstructed from the commit recorded beside it rather than from whatever the tree held that afternoon. It records mechanical facts only - process status, output size, and a regex match for the issue reference the model appears to have selected - and that regex is PHRASE DETECTION, a pointer into the transcript, not a finding about what the closing step would publish
