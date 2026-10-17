# Delegated-lane stream captures (issue #1454)

These files are **real harness output**: each was written by the harness binary
named in its filename, run exactly as `/qwen:exec` and `/gemma:exec` run it.
They were captured **against a stub model endpoint**: a local HTTP server that
answers the harness's own API (OpenAI `/v1/chat/completions` for Qwen Code,
Ollama `/api/chat` for OpenCode) with canned replies. The first reply is a tool
call to the harness's own shell tool (`run_shell_command` / `bash`), and the
second is the text `OK`. **No live-model run is captured here.** The endpoint changes
what the model says, not how the harness frames it, so these pin the FORMAT the
receipt writer reads. They do not pin a real model's behaviour.

Captured on 2026-10-17 in a Kyle session container, where the real Ollama
endpoints (`$QWEN_OLLAMA_URL`, `$GEMMA_OLLAMA_URL`) were unreachable.

| File | Harness | What it is |
|---|---|---|
| `qwen-code-0.15.10.stream.jsonl` | Qwen Code 0.15.10, `--output-format stream-json` | the stream: `system/init` (with `model`, `qwen_code_version`), an assistant `tool_use`, a user `tool_result`, an assistant text, a `result` |
| `qwen-code-0.15.10.transcript.jsonl` | Qwen Code 0.15.10 | the persisted transcript `~/.qwen/projects/<cwd-slug>/chats/<session_id>.jsonl` for that session |
| `opencode-1.18.32.stream.jsonl` | OpenCode 1.18.32, `--format json` | the stream: `step_start`, `tool_use` (bash, completed), `step_finish`, then a text step. It carries **no model**, only `sessionID` |
| `opencode-1.18.32.db-rows.jsonl` | OpenCode 1.18.32 | that session's rows from `~/.local/share/opencode/opencode.db` (`session` and `message`), exported as JSON lines; the tests rebuild a SQLite file from them |

**What the model fields mean (measured).** A second stub reported a DIFFERENT
served model than the one requested. Qwen Code's `init.model`, its assistant
`message.model`, its transcript's assistant `model`, and OpenCode's
`providerID`/`modelID` all still named the **requested** model. That is the
same basis as Codex `turn_context.model`, which the writer already reads.

A live-endpoint capture, to diff against these, is owed. Nit Store #864 holds
the request.
