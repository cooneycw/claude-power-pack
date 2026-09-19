---
description: Delegate a read-only question to Codex and relay its answer - read-only by default, network opt-in on explicit request
allowed-tools: Bash(codex:*), Bash(mktemp:*), Bash(cat:*), Bash(rm:*), Bash(test:*), Bash(command -v codex), Read
---

# Codex Ask: Delegate a Read-Only Question to Codex

Send a question (or read-only analysis task) to OpenAI Codex through the
`codex` CLI and relay its answer back, clearly attributed. **Which model answers
is host configuration, not a property of this command** - see Options below, and
name the model you actually ran rather than one read from here. Codex runs **read-only**:
it may read files in the current directory to answer questions about the codebase,
but it cannot modify anything.

This is the question / second-opinion counterpart to the code-mutating Codex commands:

- **`/codex:ask`** (this) - ask Codex a question, get an answer. Read-only, no changes.
- **`/codex:exec`** - hand Codex a coding task in the current dir (writes files, `danger-full-access`).
- **`/codex:auto`** - full issue lifecycle delegated to Codex (worktree, PR, quality gates).
- **`/second-opinion:start`** - code review via *other* external LLMs through the MCP server.

## Arguments

- `QUESTION` (required): What to ask Codex. Take it from the slash-command arguments,
  or from whatever question the user phrased when they asked you to delegate to Codex.

## Instructions

When the user invokes `/codex:ask <QUESTION>` (or asks you to delegate/ask Codex):

### Step 1: Preflight

```bash
if ! command -v codex >/dev/null 2>&1; then
    echo "ERROR: Codex CLI not found. Install: npm install -g @openai/codex; then: codex login"
    exit 1
fi
codex --version
```

If the question is empty, ask the user what they want to delegate before running anything.
For a fuller readiness check (login, config, MCP registrations), run `/codex:status`.

### Step 2: Ask Codex

Capture Codex's final answer to a temp file with `--output-last-message`, run read-only,
and disable color for clean text. By default Codex runs in the current working directory
so it can read the project to answer codebase questions.

```bash
ANSWER=$(mktemp /tmp/codex-ask.XXXXXX.txt)

codex exec \
    --sandbox read-only \
    --color never \
    --skip-git-repo-check \
    --output-last-message "$ANSWER" \
    "$QUESTION" < /dev/null   # non-TTY: EOF stdin so codex answers instead of blocking on `Reading additional input from stdin...`

CODEX_EXIT=$?
```

Notes on the flags:
- `--sandbox read-only` - Codex can read files / run read-only commands, never writes. This is
  the guardrail that makes "delegate a question" safe even inside a live repo.
- `--output-last-message "$ANSWER"` - writes ONLY Codex's final answer to the file (the stdout
  stream also includes its reasoning / tool steps; the file is the clean answer to relay).
- `--skip-git-repo-check` - lets it run anywhere, not just inside a git repo.
- `--color never` - avoids ANSI codes in captured text.

While it runs, the stdout stream shows Codex's progress - surface anything notable
(plan, files it read, errors) to the user.

### Step 3: Relay the answer

```bash
echo "===== Codex answer ====="
cat "$ANSWER"
rm -f "$ANSWER"
```

Then present Codex's answer to the user, **attributed to Codex** - do not silently pass it
off as your own. Keep Codex's answer and any take of your own clearly separated. If the
user asked you to compare or sanity-check it, add your own assessment in a labeled section
after relaying Codex's answer verbatim.

If `CODEX_EXIT` is non-zero, report the failure and the tail of the stream; do not fabricate
an answer.

## Options

Adjust the Step 2 command when the user asks for any of these:

- **Different model / reasoning effort:** add `-m <model>` (e.g.
  `-m gpt-6-astra`) or `-c model_reasoning_effort=high`. With neither flag the
  invocation inherits from the layered configuration described below.

  **The user config file is ONE LAYER, not the resolved model.** A profile
  (`--profile`, layering `$CODEX_HOME/<name>.config.toml`), a `-c model=...`
  override, a trusted repository's own config, and managed defaults all sit
  above or beside it, and `CODEX_HOME` moves the whole tree. So reading the file
  predicts; it does not establish. Measured 2026-09-19 the user file held
  `gpt-5.6-sol` / `high`, and this document named `gpt-5.5` / `xhigh` for long
  enough that nothing noticed - a claim about mutable host state, written where
  no reader could check it. The stamp makes a stale value visible AS stale; it
  is not a promise about today.

  ```bash
  CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
  grep -E '^(model|model_reasoning_effort)' "$CODEX_DIR/config.toml"   # predicts
  ```

  **To establish what actually answered, anchor on the run's own thread.**
  `codex exec --json` names no model anywhere in its stream - it emits
  `thread.started`, `turn.started`, `item.completed`, `turn.completed` and
  nothing else - so a run cannot report its own model directly. The rollout
  record can, and `--json` and `--output-last-message` may be passed together,
  so capturing the thread id costs nothing:

  ```bash
  CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
  THREAD=$(grep -o '"thread_id":"[^"]*"' "$STREAM" | head -1 | cut -d\" -f4)
  # FAIL CLOSED. With THREAD empty the -name pattern degrades to "*.jsonl",
  # which matches EVERY rollout on the host - measured 2026-09-19: 394 files,
  # head -1 returning a confident model name from a session 12 days old and
  # unrelated. An empty THREAD means UNKNOWN and must never become a name.
  if [ -z "$THREAD" ]; then
      MODEL=""
  else
      ROLLOUT=$(find "$CODEX_DIR/sessions" -type f -name "*$THREAD.jsonl" | head -1)
      if [ -n "$ROLLOUT" ]; then
          MODEL=$(grep -o '"model":"[^"]*"' "$ROLLOUT" | head -1 | cut -d\" -f4)
      else
          MODEL=""
      fi
  fi
  ```

  **Never take the NEWEST rollout instead.** It is the obvious shortcut and it
  is wrong twice over: this fleet runs many concurrent sessions, so the newest
  rollout belongs to whoever finished last rather than to you; and when no
  review ran at all, it necessarily names some unrelated run, manufacturing a
  reviewer out of a skip. Anchoring on the thread id is what makes the answer
  about THIS invocation. Verified 2026-09-19 that the field discriminates: it
  read `gpt-6-astra` for a run pinned with `-m gpt-6-astra` and `gpt-5.6-sol`
  for runs that inherited.

  **An unrecognized `-m` value does fail, and the caller does see it.** It warns
  `Model metadata for <name> not found. Defaulting to fallback metadata` and then
  errors; measured 2026-09-19, the process exits **1** where a valid model exits
  0. So check the captured exit status rather than scanning the transcript for
  the warning - and note that no amount of reading the configured default
  validates the spelling of a DIFFERENT model passed with `-m`.

- **Ask about a different directory:** add `-C <DIR>` (alias `--cd`) so Codex reads that
  project instead of the current one.
- **Attach a file or piped context:** pipe it on stdin - it is appended as a `<stdin>` block:
  `cat notes.md | codex exec --sandbox read-only --color never -o "$ANSWER" "Summarize this:"`.
  Attach images with `-i <FILE>`.
- **Attach repo context inline:** include the relevant snippet / path in the QUESTION text;
  the read-only sandbox also lets Codex open files itself.
- **Follow-up on the same thread:** continue the previous session with
  `codex exec resume --last --sandbox read-only --color never -o "$ANSWER" "<follow-up>" < /dev/null`.
- **Let Codex reach the network (fetch repos, browse, curl):** read-only blocks network for
  the commands Codex runs. To allow it, escalate the sandbox - network access is bundled with
  write access in Codex, so there are two opt-in levels. **Only do this when the user explicitly
  asks**, and tell them what you are granting:
  - Network + scratch writes (preferred): `--sandbox workspace-write -c sandbox_workspace_write.network_access=true`
    Codex can `git clone` / `curl` and write under the working dir + `/tmp`, but not elsewhere.
    Point `-C` at a throwaway dir (e.g. `mktemp -d`) so it does not litter a real project.
  - Full access: `--sandbox danger-full-access` - network + writes anywhere. Maximum risk; avoid
    unless the user insists.
  - Safety: with network on, a model-generated command can fetch and run arbitrary code, exfiltrate
    files it can read, or act on a prompt-injection embedded in a file or page. Never enable it
    silently, and prefer the workspace-write level scoped to a scratch dir.
  - Note: Codex always reaches OpenAI to run the model itself; the sandbox only governs the
    network access of the *shell commands* it executes. "No network" means it cannot fetch
    external sources, not that the model is offline.
- **Let Codex actually DO something (write files in your repo):** that is no longer "delegate a
  question" - use `/codex:exec` (one-shot) or `/codex:auto` (full lifecycle) instead, which run
  with write access and JSONL monitoring.

## Long-running delegations

Deep questions at `xhigh` over a real repo can take many minutes and will blow past a normal
foreground command timeout. For anything non-trivial:

- **Run it in the background** so it is not bound by the tool timeout, and stream to a log
  instead of buffering with `tail` (which hides progress until the end):
  ```bash
  ANSWER=$(mktemp /tmp/codex-ask.XXXXXX.txt)
  LOG=$(mktemp /tmp/codex-ask.XXXXXX.log)
  codex exec --sandbox read-only --color never --skip-git-repo-check \
      --output-last-message "$ANSWER" "$QUESTION" < /dev/null > "$LOG" 2>&1   # launch in background (stdin EOF'd so it never blocks on stdin read)
  ```
  Poll `tail -n 20 "$LOG"` for progress; read `$ANSWER` once it exits.
- To keep latency tractable instead, lower effort with `-c model_reasoning_effort=high` (or
  `medium`) - faster, slightly less thorough than the `xhigh` default.
- Scope tightly: target the smallest relevant dir with `-C`, and name the key files / paths in
  the question so Codex does not crawl an entire monorepo.

## Notes

- Uses the user's **Codex account** (real quota / billing on each call). Keep delegated
  questions purposeful; do not loop unattended.
- Read-only by design: safe to run inside any project without risking edits. Network and write
  access are explicit opt-ins (see Options) - never escalate without the user asking.
- The temp answer file lives in `/tmp` and is removed after relaying.
- For code CHANGES, use `/codex:exec` (one-shot) or `/codex:auto` (full issue lifecycle) instead.
