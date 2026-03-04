---
description: Select models and depth for second opinion code review
allowed-tools: mcp__second-opinion__list_available_models, mcp__second-opinion__get_multi_model_second_opinion, mcp__second-opinion__get_code_second_opinion
---

# Second Opinion: Model Selection

Interactive model and depth selection for code review consultations.

ARGUMENTS: $ARGUMENTS

---

## Step 1: List Available Models

Call `list_available_models` to get the current list of configured and available models.

Display the results in a clear table showing:
- Model key (what the user selects)
- Display name
- Provider
- Description
- Whether it's available (API key configured)

---

## Step 2: Two-Part Selection Menu

Use AskUserQuestion to present **two questions simultaneously**:

### Question 1: Select Models (multiSelect=true)

Present available models grouped by provider. Only show models that are available (API key configured).

Options (show up to 4 most relevant, user can type Others):
- `gemini-3-pro + claude-sonnet` — Gemini 3.1 + Claude Sonnet (Recommended, best cross-provider coverage)
- `gemini-3-pro + codex` — Gemini 3.1 + GPT-5.3 Codex (Google + OpenAI)
- `claude-sonnet` — Claude Sonnet 4.6 only (fast, excellent for code)
- `codex + o4-mini` — GPT-5.3 Codex + o4-mini (OpenAI coding + reasoning)

If user types Other, they can specify any model keys: `gemini-2.5-pro`, `claude-haiku`, `claude-opus`, `codex-mini`, `o3`, `o1`, `gpt-5.2`, `gpt-4o`, etc.

### Question 2: Analysis Depth

Options:
- `brief` — Quick feedback, key issues only (~4K tokens output)
- `detailed` — Comprehensive analysis with recommendations (Recommended, ~48K tokens output)
- `in_depth` — Exhaustive 64K analysis, covers edge cases, security, architecture

---

## Step 3: Get Code Context

If the user provided code or a file path in the ARGUMENTS, use that.

Otherwise, ask the user using AskUserQuestion:

- **Paste code** — Provide code directly
- **File path** — Specify a file to read
- **Recent context** — Use code from current conversation

If a file path is given, read it.

---

## Step 4: Ask for Context (Optional)

Ask briefly if they have specific concerns:

```
Any specific concerns about this code? (optional)
```

---

## Step 5: Run Consultation

Based on selections:

- **Single model:** Use `get_code_second_opinion` (Gemini) or `get_multi_model_second_opinion` with one model
- **Multiple models:** Use `get_multi_model_second_opinion` with selected models

Pass: code, language (auto-detect), verbosity (from depth selection), and any context/issue description.

**Important:** Pass the verbosity parameter from the depth selection directly to the tool call. Do not hardcode it.

---

## Step 6: Display Results

For multi-model results, display each model's response clearly separated:

```
=== {display_name} ({depth}) ===
Cost: ${cost}

{response}

---
```

At the end:

```
Total cost: ${total_cost}
Models consulted: {count}
Depth: {verbosity}
```

---

## Notes

- Only models with configured API keys are shown as available
- Cost estimates are approximate (token counting heuristics)
- `in_depth` generates significantly more output and costs more
- Model keys are stable across versions (e.g., `gemini-3-pro` always points to latest Gemini)
