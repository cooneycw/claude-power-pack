# `classify-tool-risk` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `classify-tool-risk`

- classify-tool-risk - CANONICAL taxonomy: this file is CPP's source of truth for permission risk tiers. It sorts observed Bash/MCP tool calls from Claude Code transcripts into graded tiers rather than the binary read-only/skip split the native `/fewer-permission-prompts` skill makes, so a safe reversible local write (`git add`) is distinguishable from arbitrary code execution (`python3`) and from a destructive op (`rm -rf`). Tiers run READONLY-AUTO, READONLY-ADDABLE, WRITE-LOCAL, WRITE-OUTWARD, DUAL-USE-NET, CODE-EXEC, SCRIPT-EXEC, DESTRUCTIVE, SHELL-CTL/OTHER. `hook-permission-census.sh` carries a vendored inline copy for fail-open self-containment and `tool-risk-drift.py` guards the safety-critical sets (`DESTRUCTIVE_TOKENS`, `CODE_EXEC`) between the two, so a newly dangerous command cannot be known to one and missed by the other
