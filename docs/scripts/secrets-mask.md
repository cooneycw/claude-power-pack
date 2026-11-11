# `secrets-mask` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `secrets-mask`

- secrets-mask - pipe filter that masks common secret patterns with sed, usable standalone or from a hook (it is what `hook-mask-output.sh` filters tool output through). Additional patterns come from `~/.claude/secrets-mask.conf`, one `sed_pattern|replacement` per line
