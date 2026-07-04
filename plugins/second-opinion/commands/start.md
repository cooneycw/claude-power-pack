---
description: Quick second opinion with sensible defaults
allowed-tools: mcp__second-opinion__get_code_second_opinion, mcp__second-opinion__get_multi_model_second_opinion, mcp__second-opinion__list_available_models
---

# Second Opinion: Quick Start

Get a fast second opinion with sensible defaults. No menus - just review.

ARGUMENTS: $ARGUMENTS

---

## How It Works

This command provides quick shortcuts for common review patterns. Parse the ARGUMENTS to determine what the user wants:

### Pattern 1: File path provided
```
/second-opinion:start src/auth.py
```
Read the file, auto-detect language, run default models (gemini-3-pro) at `detailed` depth.

### Pattern 2: File path + depth
```
/second-opinion:start src/auth.py brief
/second-opinion:start src/auth.py in_depth
```
Read the file, use specified depth.

### Pattern 3: File path + model(s)
```
/second-opinion:start src/auth.py codex
/second-opinion:start src/auth.py gemini-3-pro,codex
```
Read the file, use specified model(s) at `detailed` depth.

### Pattern 4: File path + model(s) + depth
```
/second-opinion:start src/auth.py codex,o4-mini in_depth
```
Read the file, use specified models at specified depth.

### Pattern 5: Description only
```
/second-opinion:start "review my recent changes"
```
Look at recent conversation context for code, or ask user to provide it.

### Pattern 6: No arguments
```
/second-opinion:start
```
Ask the user what they want reviewed (file path or paste code).

---

## Argument Parsing Rules

1. **File paths** end in common extensions: `.py`, `.js`, `.ts`, `.tsx`, `.rs`, `.go`, `.java`, `.rb`, `.c`, `.cpp`, `.h`, `.cs`, `.swift`, `.kt`, `.sh`, `.yml`, `.yaml`, `.json`, `.toml`, `.sql`, `.md`
2. **Depth keywords**: `brief`, `detailed`, `in_depth`, `in-depth`, `comprehensive`, `thorough`, `exhaustive`
3. **Model keys**: `gemini-3-pro`, `gemini-2.5-pro`, `claude-sonnet`, `claude-haiku`, `claude-opus`, `codex`, `codex-max`, `codex-mini`, `o4-mini`, `o3`, `o1`, `gpt-5.2`, `gpt-4o` (comma-separated for multiple)
4. **Everything else** is treated as context/issue description

---

## Defaults

| Setting | Default |
|---------|---------|
| Model | `gemini-3-pro` (single model, fastest) |
| Depth | `detailed` |
| Language | Auto-detected from file extension |

---

## Execution

1. Parse arguments per rules above
2. If file path given, read the file
3. If no code found, ask user
4. Auto-detect language from file extension or content
5. If single model AND model is `gemini-3-pro` (default): use `get_code_second_opinion` with verbosity parameter
6. If single model AND model is NOT `gemini-3-pro`: use `get_multi_model_second_opinion` with `models: ["<model_key>"]` and verbosity parameter
7. If multiple models: use `get_multi_model_second_opinion` with verbosity parameter
7. Display results with cost

---

## Examples

```bash
# Quick Gemini review of a file
/second-opinion:start src/server.py

# Brief review (just key issues)
/second-opinion:start src/server.py brief

# Claude Sonnet review
/second-opinion:start src/auth.py claude-sonnet

# Multi-model deep dive (3 providers)
/second-opinion:start src/server.py gemini-3-pro,claude-sonnet,codex in_depth

# Fast reasoning check
/second-opinion:start src/config.py o4-mini brief

# Cross-provider comparison
/second-opinion:start src/api.py gemini-3-pro,claude-opus
```

---

## Related Commands

- `/second-opinion:models` - Full interactive model/depth selection with menus
- `/second-opinion:help` - Overview of all commands
