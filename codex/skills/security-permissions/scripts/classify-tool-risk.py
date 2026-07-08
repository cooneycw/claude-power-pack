#!/usr/bin/env python3
"""Risk-graded classifier for observed Bash/MCP tool calls in Claude Code transcripts.

Complements the native /fewer-permission-prompts skill (which does a binary
read-only/skip split) by sorting every observed command into risk tiers, so you
can tell a safe-reversible local write (git add) from arbitrary code execution
(python3) from a destructive op (rm -rf).

Usage:
    python3 scripts/classify-tool-risk.py [--limit N] [--projects DIR]

Tiers (best -> worst):
    READONLY-AUTO     already auto-allowed by Claude Code; informative
    READONLY-ADDABLE  read-only but not auto-allowed -> safe allowlist candidate
    WRITE-LOCAL       mutates local state, reversible, low blast radius
    WRITE-OUTWARD     creates/publishes to a remote (GitHub, git push); reversible-ish
    DUAL-USE-NET      reads OR writes over the network (curl, gh api); ambiguous
    CODE-EXEC         interpreters / package runners / shells -> arbitrary execution
    SCRIPT-EXEC       opaque local scripts; vet individually
    DESTRUCTIVE       irreversible / data-loss (rm, --force, --hard)
    SHELL-CTL/OTHER   shell keywords and tokenizer noise
"""
# CANONICAL taxonomy: this file is CPP's source of truth for permission risk
# tiers. scripts/hook-permission-census.sh (the #482 real-time census hook)
# carries a vendored inline copy for fail-open self-containment;
# scripts/tool-risk-drift.py guards the safety-critical sets (DESTRUCTIVE_TOKENS,
# CODE_EXEC) between the two so a new dangerous command cannot be missed by one.
import argparse
import glob
import json
import os
import re
from collections import Counter, defaultdict

PREFIX = {"sudo", "command", "nice", "nohup", "time", "env"}
SHELL_KW = {"for", "if", "while", "set", "case", "function", "then", "do", "done",
            "fi", "else", "elif", "{", "}", "(", "[[", "]]", ":", "&&", "||", "#", "\\"}
RO_ANY = {
    "cal", "uptime", "cat", "head", "tail", "wc", "stat", "strings", "hexdump", "od",
    "nl", "id", "uname", "free", "df", "du", "locale", "groups", "nproc", "basename",
    "dirname", "realpath", "cut", "paste", "tr", "column", "tac", "rev", "fold",
    "expand", "unexpand", "fmt", "comm", "cmp", "numfmt", "readlink", "diff", "true",
    "false", "sleep", "which", "type", "expr", "seq", "tsort", "pr", "echo", "ls", "cd",
    "xargs", "file", "sed", "sort", "man", "help", "netstat", "ps", "base64", "grep",
    "egrep", "fgrep", "sha256sum", "sha1sum", "md5sum", "tree", "date", "hostname",
    "lsof", "pgrep", "tput", "ss", "fd", "fdfind", "rg", "jq", "uniq", "history",
    "arch", "ifconfig", "pyright", "find", "printf", "test", "pwd", "whoami",
}
CODE_EXEC = {"python", "python3", "node", "bun", "deno", "ruby", "perl", "php", "lua",
             "npx", "bunx", "uvx", "uv", "pip", "pip3", "eval", "exec", "bash", "sh",
             "zsh", "fish", "ssh", "gcc", "cc"}
TASK_RUNNER = {"make", "just", "rake", "task", "cargo", "go", "npm", "yarn", "pnpm",
               "gradle", "mvn", "tsc"}
DUAL_NET = {"curl", "wget", "http", "https", "aws", "gcloud", "az", "scp", "rsync",
            "nc", "telnet"}
GIT_RO = {"status", "log", "diff", "show", "blame", "tag", "remote", "ls-files",
          "ls-remote", "rev-parse", "describe", "reflog", "shortlog", "cat-file",
          "for-each-ref", "stash", "rev-list", "check-ignore", "symbolic-ref",
          "name-rev", "cherry", "whatchanged", "grep", "count-objects", "merge-base"}
GIT_REMOTE_READ = {"fetch", "clone"}
GIT_REMOTE_WRITE = {"push", "pull"}
GIT_WRITE = {"add", "checkout", "switch", "restore", "mv", "reset", "commit", "branch",
             "worktree", "merge", "rebase", "cherry-pick", "apply", "am", "clean",
             "gc", "init", "config", "update-ref", "update-index", "notes", "revert",
             "filter-branch", "filter-repo", "subtree", "stash-push"}
GH_RO = {"view", "list", "status", "diff", "checks"}
GH_WRITE_ACTS = {"create", "close", "comment", "edit", "delete", "merge", "reopen",
                 "ready", "add", "remove", "rename", "develop"}
DESTRUCTIVE_TOKENS = {"rm", "rmdir", "shred", "mkfs", "dd", "truncate", "fdisk"}


def tokens(cmd):
    seg = re.split(r'\|\||&&|[|;]', cmd, 1)[0].strip()
    t = seg.split()
    while t and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', t[0]):
        t.pop(0)
    while t and t[0] in PREFIX:
        t.pop(0)
        while t and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', t[0]):
            t.pop(0)
    if t and t[0] == "timeout":
        t.pop(0)
        if t:
            t.pop(0)
    return t


def _git_sub(t):
    rest = t[1:]
    i = 0
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


def classify(cmd):
    """Return (tier, label) for a shell command string."""
    t = tokens(cmd)
    if not t:
        return ("OTHER", "?")
    c = t[0].split('/')[-1]
    if c in SHELL_KW:
        return ("SHELL-CTL", c)
    if c in DESTRUCTIVE_TOKENS:
        return ("DESTRUCTIVE", c)
    if c == "git":
        sub = _git_sub(t)
        s = sub[0] if sub else ""
        flags = {x for x in sub if x.startswith("-")}
        if s in GIT_REMOTE_WRITE:
            if flags & {"-f", "--force", "--force-with-lease"}:
                return ("DESTRUCTIVE", f"git {s} --force")
            return ("WRITE-OUTWARD", f"git {s}")
        if s in GIT_REMOTE_READ:
            return ("READONLY-ADDABLE", f"git {s}")
        if s == "reset" and (flags & {"--hard"}):
            return ("DESTRUCTIVE", "git reset --hard")
        if s in ("checkout", "restore", "clean"):
            return ("DESTRUCTIVE", f"git {s} (can discard changes)")
        if s == "rm":
            return ("DESTRUCTIVE", "git rm")
        if s == "branch" and (flags & {"-D", "-d", "--delete"}):
            return ("DESTRUCTIVE", "git branch -D")
        if s == "worktree":
            ss = sub[1] if len(sub) > 1 else ""
            if ss == "list":
                return ("READONLY-AUTO", "git worktree list")
            if ss == "remove":
                return ("DESTRUCTIVE", "git worktree remove")
            return ("WRITE-LOCAL", f"git worktree {ss}")
        if s in GIT_RO:
            return ("READONLY-AUTO", f"git {s}")
        if s in GIT_WRITE:
            return ("WRITE-LOCAL", f"git {s}")
        return ("OTHER", f"git {s}")
    if c == "gh":
        grp = t[1] if len(t) > 1 else ""
        act = t[2] if len(t) > 2 else ""
        if grp == "api":
            return ("DUAL-USE-NET", "gh api")
        if act in GH_RO or (grp == "auth" and act == "status"):
            return ("READONLY-AUTO", f"gh {grp} {act}")
        if act in GH_WRITE_ACTS:
            return ("WRITE-OUTWARD", f"gh {grp} {act}")
        return ("OTHER", f"gh {grp} {act}".strip())
    if c == "docker":
        sub = t[1] if len(t) > 1 else ""
        if sub in ("ps", "images", "logs", "inspect", "version", "info", "top", "port", "stats"):
            return ("READONLY-AUTO", f"docker {sub}")
        return ("WRITE-LOCAL", f"docker {sub}")
    if c in CODE_EXEC:
        return ("CODE-EXEC", c)
    if c in TASK_RUNNER:
        return ("CODE-EXEC", f"{c} (task-runner)")
    if c in DUAL_NET:
        return ("DUAL-USE-NET", c)
    if c in RO_ANY:
        return ("READONLY-AUTO", c)
    if c in ("mkdir", "touch", "tee", "cp", "ln", "chmod", "chown"):
        return ("WRITE-LOCAL", c)
    if c.endswith(".sh"):
        return ("SCRIPT-EXEC", c)
    return ("OTHER", c)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=50,
                    help="scan the N most-recently-modified transcripts (default 50)")
    ap.add_argument("--projects", default=os.path.expanduser("~/.claude/projects"),
                    help="Claude Code projects dir")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.projects, "**", "*.jsonl"), recursive=True),
                   key=os.path.getmtime, reverse=True)[:args.limit]

    tier = defaultdict(Counter)
    mcp = Counter()
    for fp in files:
        try:
            for line in open(fp, errors="ignore"):
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                content = (obj.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for it in content:
                    if not isinstance(it, dict) or it.get("type") != "tool_use":
                        continue
                    name = it.get("name", "")
                    if name == "Bash":
                        t, label = classify((it.get("input") or {}).get("command", ""))
                        tier[t][label] += 1
                    elif name.startswith("mcp__"):
                        mcp[name] += 1
        except OSError:
            continue

    order = ["READONLY-AUTO", "READONLY-ADDABLE", "WRITE-LOCAL", "WRITE-OUTWARD",
             "DUAL-USE-NET", "CODE-EXEC", "SCRIPT-EXEC", "DESTRUCTIVE", "SHELL-CTL", "OTHER"]
    print(f"scanned {len(files)} transcripts under {args.projects}\n")
    for t in order:
        if t not in tier:
            continue
        print(f"### {t}  (total {sum(tier[t].values())})")
        for label, cnt in tier[t].most_common(15):
            print(f"  {cnt:5d}  {label}")
        print()
    if mcp:
        print("### MCP")
        for name, cnt in mcp.most_common():
            ro = any(k in name for k in ("read", "get", "list", "search", "view", "health"))
            print(f"  {cnt:5d}  {name}  {'[read-only]' if ro else '[check: may mutate]'}")


if __name__ == "__main__":
    main()
