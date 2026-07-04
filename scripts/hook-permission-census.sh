#!/usr/bin/env bash
# hook-permission-census.sh - PermissionRequest hook: observe-only permission census.
#
# The grill-me retro (issue #426) treats `permission-prompt` as a first-class
# friction class, but capture for it used to be model-driven and never fired: a
# tool call the user manually approved and one auto-allowed by settings.json are
# indistinguishable to the model AND in the transcript. Claude Code's
# PermissionRequest hook is not - it fires at the exact moment a permission
# dialog is shown. This hook turns that event into one `permission-prompt` record
# in the project's .claude/friction.jsonl (via friction-log.sh), so
# /self-improvement:retro Step 4 finally has real input (issue #482).
#
# Two things per prompt:
#   1. A narrowest candidate allow rule (matching retro Step 4's derivation:
#      `gh issue view 482` -> Bash(gh issue view:*), `git fetch ...` ->
#      Bash(git fetch:*), bare `pwd` -> Bash(pwd), non-Bash tool -> the tool name).
#   2. A RISK TIER for the underlying command (vocabulary mirrors CPP's permission
#      risk taxonomy: READONLY-ADDABLE < WRITE-LOCAL < WRITE-OUTWARD < DUAL-USE-NET
#      < CODE-EXEC < SCRIPT-EXEC < DESTRUCTIVE). The rule candidate is emitted ONLY
#      for the SAFE tiers (read-only + reversible local writes); a risky prompt is
#      recorded with its tier and NO allow candidate, so a command approved once
#      never becomes a blind allowlist rule. Retro maps the tier to allow/ask/deny.
#
# Contract (both non-negotiable):
#   - OBSERVE-ONLY: emits NOTHING on stdout, so it can never return a permission
#     decision and never influences whether the prompt is allowed/denied. It only
#     appends to a local buffer.
#   - FAIL-OPEN: never exits non-zero. No stdin, no python3, no capture helper, or
#     malformed input -> silently skip. A flight recorder must never break a flow.
#
# Input: the PermissionRequest JSON payload on stdin
#        ({tool_name, tool_input, permission_mode, cwd, session_id, ...}).
# Output: none (records land in the project's .claude/friction.jsonl).
#
# Registered (user-confirmed) in ~/.claude/settings.json by /cpp:init and
# /cpp:update:
#   "hooks": { "PermissionRequest": [ { "hooks": [
#     { "type": "command", "command": "~/.claude/scripts/hook-permission-census.sh" }
#   ] } ] }

# Deliberately NO `set -e`: fail-open means we swallow every error and exit 0.
set -u 2>/dev/null || true

# Resolve the sibling friction-log.sh. Both scripts live together: in the repo
# checkout (scripts/) and, once installed, symlinked side by side in
# ~/.claude/scripts/. Honour an override so tests can point at a specific copy.
SELF="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SELF")" 2>/dev/null && pwd || printf '')"
FRICTION_LOG="${CPP_FRICTION_LOG_HELPER:-$SCRIPT_DIR/friction-log.sh}"

# Read the PermissionRequest payload from stdin.
INPUT="$(cat 2>/dev/null || printf '')"

# Nothing to do without input, without python3, or without the capture helper.
[ -n "$INPUT" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
[ -f "$FRICTION_LOG" ] || exit 0

# Derive "<signal>\t<fix>\t<risk>" from the payload. All parsing + the narrowest
# rule + the risk tier happen in python (reliable JSON, injection-safe via env).
# Any failure prints nothing -> we skip. python's stdout is captured here and
# never reaches THIS hook's stdout, preserving the observe-only contract.
DERIVED="$(CENSUS_INPUT="$INPUT" python3 <<'PYEOF' 2>/dev/null
import os
import re
import shlex
import sys

raw = os.environ.get("CENSUS_INPUT", "")
try:
    import json
    data = json.loads(raw)
except Exception:
    sys.exit(0)
if not isinstance(data, dict):
    sys.exit(0)

tool = str(data.get("tool_name") or "").strip()
if not tool:
    sys.exit(0)

# --- Risk taxonomy (compact; vocabulary matches CPP's permission risk tiers) ---
# Only READONLY-* and the safe WRITE-LOCAL tier yield an allow candidate; every
# riskier tier is recorded but never allowlisted by the census.
SAFE_TIERS = {"READONLY-AUTO", "READONLY-ADDABLE", "WRITE-LOCAL"}

RO_ANY = {
    "cat", "head", "tail", "wc", "stat", "nl", "id", "uname", "df", "du", "cut",
    "paste", "tr", "column", "tac", "rev", "comm", "cmp", "readlink", "diff",
    "true", "false", "which", "type", "seq", "echo", "ls", "cd", "file", "sed",
    "sort", "base64", "grep", "egrep", "fgrep", "sha256sum", "tree", "date",
    "hostname", "pgrep", "ss", "fd", "rg", "jq", "uniq", "find", "printf",
    "test", "pwd", "whoami", "basename", "dirname", "realpath", "awk", "less",
}
CODE_EXEC = {
    "python", "python3", "node", "bun", "deno", "ruby", "perl", "php", "lua",
    "npx", "bunx", "uvx", "uv", "pip", "pip3", "eval", "exec", "bash", "sh",
    "zsh", "fish", "ssh", "gcc", "cc",
}
TASK_RUNNER = {"make", "just", "rake", "cargo", "go", "npm", "yarn", "pnpm", "gradle", "mvn", "tsc"}
DUAL_NET = {"curl", "wget", "aws", "gcloud", "az", "scp", "rsync", "nc", "telnet"}
DESTRUCTIVE_TOKENS = {"rm", "rmdir", "shred", "mkfs", "dd", "truncate", "fdisk"}
WRITE_LOCAL_TOKENS = {"mkdir", "touch", "tee", "cp", "ln", "chmod", "chown", "mv"}

GIT_RO = {
    "status", "log", "diff", "show", "blame", "tag", "remote", "ls-files",
    "ls-remote", "rev-parse", "describe", "reflog", "shortlog", "cat-file",
    "for-each-ref", "rev-list", "check-ignore", "symbolic-ref", "name-rev",
    "merge-base",
}
GIT_REMOTE_READ = {"fetch", "clone"}
GIT_REMOTE_WRITE = {"push", "pull"}
GIT_WRITE = {
    "add", "mv", "commit", "worktree", "merge", "rebase", "cherry-pick",
    "apply", "am", "gc", "init", "config", "update-ref", "notes", "stash",
}
GH_RO = {"view", "list", "status", "diff", "checks"}
GH_WRITE_ACTS = {"create", "close", "comment", "edit", "delete", "merge", "reopen", "ready"}


def first_segment_tokens(cmd):
    """Tokens of the first simple command, stripping env-assignments/prefixes."""
    seg = re.split(r"\|\||&&|[|;\n><]", cmd, 1)[0].strip()
    if not seg:
        return []
    try:
        t = shlex.split(seg)
    except ValueError:
        t = seg.split()
    while t and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t[0]):
        t.pop(0)
    while t and t[0] in {"sudo", "command", "nice", "nohup", "time", "env"}:
        t.pop(0)
        while t and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t[0]):
            t.pop(0)
    if t and t[0] == "timeout":
        t.pop(0)
        if t:
            t.pop(0)
    return t


def git_sub(t):
    rest, i = t[1:], 0
    while i < len(rest):
        x = rest[i]
        if x in ("-C", "-c"):
            i += 2
            continue
        if x.startswith("-"):
            i += 1
            continue
        return rest[i:]
    return []


def classify(t):
    """Return the risk tier for the tokens of a shell command."""
    if not t:
        return "OTHER"
    c = t[0].split("/")[-1]
    if c in DESTRUCTIVE_TOKENS:
        return "DESTRUCTIVE"
    if c == "git":
        sub = git_sub(t)
        s = sub[0] if sub else ""
        flags = {x for x in sub if x.startswith("-")}
        if s in GIT_REMOTE_WRITE:
            if flags & {"-f", "--force", "--force-with-lease"}:
                return "DESTRUCTIVE"
            return "WRITE-OUTWARD"
        if s in GIT_REMOTE_READ:
            return "READONLY-ADDABLE"
        if s == "reset" and (flags & {"--hard"}):
            return "DESTRUCTIVE"
        if s in ("checkout", "restore", "clean", "reset", "rm"):
            return "DESTRUCTIVE"
        if s == "branch" and (flags & {"-D", "-d", "--delete"}):
            return "DESTRUCTIVE"
        if s == "worktree":
            ss = sub[1] if len(sub) > 1 else ""
            if ss == "list":
                return "READONLY-AUTO"
            if ss == "remove":
                return "DESTRUCTIVE"
            return "WRITE-LOCAL"
        if s in GIT_RO:
            return "READONLY-AUTO"
        if s in GIT_WRITE:
            return "WRITE-LOCAL"
        return "OTHER"
    if c == "gh":
        grp = t[1] if len(t) > 1 else ""
        act = t[2] if len(t) > 2 else ""
        if grp == "api":
            return "DUAL-USE-NET"
        if act in GH_RO or (grp == "auth" and act == "status"):
            return "READONLY-AUTO"
        if act in GH_WRITE_ACTS:
            return "WRITE-OUTWARD"
        return "OTHER"
    if c == "docker":
        sub = t[1] if len(t) > 1 else ""
        if sub in ("ps", "images", "logs", "inspect", "version", "info", "top", "port", "stats"):
            return "READONLY-AUTO"
        return "WRITE-LOCAL"
    if c in CODE_EXEC or c in TASK_RUNNER:
        return "CODE-EXEC"
    if c in DUAL_NET:
        return "DUAL-USE-NET"
    if c in RO_ANY:
        return "READONLY-ADDABLE"
    if c in WRITE_LOCAL_TOKENS:
        return "WRITE-LOCAL"
    if c.endswith(".sh"):
        return "SCRIPT-EXEC"
    return "OTHER"


def derive_rule(t):
    """Narrowest allow-rule candidate for the tokens (retro Step 4 shape)."""
    if not t:
        return ""
    exe = t[0].split("/")[-1]
    # Only genuine multi-verb tools fold a subcommand into the prefix. For every
    # other command the next token is an argument, not a subcommand (`tr a-z A-Z`
    # -> Bash(tr:*), never Bash(tr a-z:*)). gh goes verb+noun+action (depth 2),
    # git/docker one deep.
    max_depth = {"gh": 2, "git": 1, "docker": 1}.get(exe, 0)
    subs = []
    for tok in t[1:]:
        if len(subs) >= max_depth:
            break
        if re.fullmatch(r"[a-z][a-z0-9-]*", tok):
            subs.append(tok)
        else:
            break
    prefix_tokens = [exe] + subs
    prefix = " ".join(prefix_tokens)
    # Bare (exact) form only when the command IS exactly the prefix (no args).
    if len(t) == len(prefix_tokens):
        return "Bash(%s)" % prefix
    return "Bash(%s:*)" % prefix


def truncate(s, n=100):
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 3] + "..."


ti = data.get("tool_input") or {}
if not isinstance(ti, dict):
    ti = {}

if tool == "Bash":
    cmd = str(ti.get("command") or "")
    toks = first_segment_tokens(cmd)
    if not toks:
        sys.exit(0)
    tier = classify(toks)
    summary = truncate(cmd)
    signal = "Bash: %s" % summary
    fix = derive_rule(toks) if tier in SAFE_TIERS else ""
else:
    # Non-Bash tool (Read/Write/WebFetch/MCP/...): the rule is just the tool name.
    tier = "READONLY-ADDABLE" if re.search(r"read|get|list|search|view|fetch|health", tool, re.I) else "OTHER"
    hint = ""
    for key in ("file_path", "path", "url", "pattern", "command", "query"):
        v = ti.get(key)
        if isinstance(v, str) and v.strip():
            hint = truncate(v, 80)
            break
    signal = ("%s: %s" % (tool, hint)).strip().rstrip(":")
    fix = tool if tier in SAFE_TIERS else ""

# One line, tab-separated. Nothing else on stdout.
sys.stdout.write("%s\t%s\t%s\n" % (signal, fix, tier))
PYEOF
)" || DERIVED=""

# No derivation -> fail-open skip.
[ -n "$DERIVED" ] || exit 0

# Split the single "<signal>\t<fix>\t<risk>" line (fields never contain tabs;
# friction-log.sh folds tabs to spaces on write anyway).
SIGNAL="$(printf '%s' "$DERIVED" | cut -f1)"
FIX="$(printf '%s' "$DERIVED" | cut -f2)"
RISK="$(printf '%s' "$DERIVED" | cut -f3)"

[ -n "$SIGNAL" ] || exit 0

# A prompt that was SHOWN (not necessarily approved - the hook cannot observe the
# click). --scope local: census records are per-machine and never pushed to the
# shared store. Everything is silenced so no stray byte reaches stdout.
bash "$FRICTION_LOG" \
  --class permission-prompt \
  --signal "$SIGNAL" \
  --fix "$FIX" \
  --risk "$RISK" \
  --scope local \
  --outcome "shown" \
  --run "permission-census" >/dev/null 2>&1 || true

exit 0
