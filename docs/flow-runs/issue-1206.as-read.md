# Issue #1206 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. It does not graduate.

- Issue:        #1206
- Read at:      2026-09-22T14:59:09Z
- updatedAt:    2026-09-22T14:58:38Z   (context only)
- Body digest:  2985f41554fb03b384e2ff11de37fc2701b3aec9d940c7d2a30a345c187bbed4   (sha256 of the FULL body)
- Stored bytes: 3820 of 3820 (cap 16384)

## Body as read
Filed as a live **security** finding rather than routed to the Nit Store, per the standing rule that a live correctness/security/data-loss problem gets its own ticket. Found by worker-B during #1083 (it flagged the matcher shape from a counter-model review of its own hook template) and verified independently here with both controls.

## The claim being made today

- `README.md:20` — *"a PostToolUse hook in `.claude/hooks.json` masks secrets (connection strings, API keys, env vars) in Bash/Read output"*
- `CLAUDE.md` Security — *"The PostToolUse hook masks tool output but does not authorize reading credentials."*

Both describe an active protection.

## Measured: the masker works

`scripts/hook-mask-output.sh` is sound. Its own documented example:

```
$ echo '{"tool_output": "password=secret123"}' | bash scripts/hook-mask-output.sh
password=****
```

**That is the positive control** — the instrument can mask, so a later absence of masking means something.

## Measured: the hook does not fire

The identical string emitted through a normal Bash tool call in a live session came back **verbatim and unmasked**:

```
SYNTHETIC-NOT-REAL password=secret123
```

Same string. Masker demonstrably catches it. Live path does not.

## Two candidate causes, neither yet isolated

1. **Matcher shape.** `.claude/hooks.json` declares PostToolUse entries with an **object** matcher — `{"tool_name": "Bash"}` and `{"tool_name": "Read"}` — where Claude Code's documented form is a **string** matcher.
2. **Config location.** PostToolUse appears in **no** `settings.json` that Claude Code reads. Checked: `.claude/settings.json` (absent), `.claude/settings.local.json` (no hooks key), `~/.claude/settings.json` (has `PermissionRequest` and `SessionStart`, **no PostToolUse**). `.claude/hooks.json` is not a documented Claude Code config path.

Note that `SessionStart` and `PermissionRequest` hooks **do** fire — both are declared in `~/.claude/settings.json`. So hooks work on this host; the masking one specifically is not wired.

I have not isolated which of the two causes it is, and the fix differs: (1) is a shape correction, (2) means `/cpp:init` / `/cpp:update` must install the block into `settings.json`. **Whoever takes this should establish which before changing anything** — fixing the shape in a file nothing reads would look like a fix and change nothing.

## Why this is security rather than a nit

A documented protection that does not run is worse than no protection, because people calibrate to it. Two files in this repository tell a reader that Bash and Read output is masked. Every secret that has passed through tool output in any session on this configuration was unmasked.

This is not a claim that secrets *were* leaked — it is that the stated control could not have prevented it, and nothing would have shown that.

## Acceptance

- Establish which cause is live, by measurement, before changing anything.
- The fix ships with a **negative control**: a synthetic secret emitted through a real tool call, observed masked; and the same with the hook removed, observed unmasked. The positive control above already exists and should be committed alongside it — the masker's own capability and the hook's wiring are two different facts and both need proving.
- `README.md` and `CLAUDE.md` state what is actually true once it is.

## Secondary, same file, not the subject of this issue

`scripts/hook-mask-output.sh` interpolates stdin into a Python heredoc as `input_json = '''$INPUT'''`. Tool output containing `'''` (or a `$`) breaks the parse; the handler then prints to **stderr** and exits 0, so a parse failure is silent and reads as "nothing to mask". My first two probes hit exactly this and returned empty, which is how I nearly mis-read a working masker as a broken one.
