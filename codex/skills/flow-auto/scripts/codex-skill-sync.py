#!/usr/bin/env python3
#: HOST-SURFACE: ~/.codex/skills/<skill> owner=cpp write=copy certified=observed mode=--install
#: The mkdir'd parents below are declared `certified=observed`, not
#: `authored`: they were found by running this script against a sandboxed
#: $HOME and diffing what appeared (issue #1150), not by a person reading
#: the code. `authored` means "a person read the code and wrote down what it
#: writes", which would be false here - static reading produced the
#: declaration above and missed these. scripts/host-surface-observe.py
#: re-derives them on every run and reds when they drift.
#: HOST-SURFACE: ~/.codex owner=cpp write=mkdir certified=observed
#: HOST-SURFACE: ~/.codex/skills owner=cpp write=mkdir certified=observed
#: HOST-SURFACE: ~/.codex/.cpp-skill-install.lock owner=cpp write=append certified=observed mode=--install

"""codex-skill-sync.py - single-source -> Codex SKILL.md skill generation.

Issue #555 (companion to codex-power-pack epic cooneycw/codex-power-pack#64,
story B1, ratified hybrid SoT): evolved the flat custom-prompt surface
(scripts/codex-prompt-sync.py, issue #446, retired at the #556 cutover) into
real Codex skills. ADR 0001 section 5 fixes the source of
truth as .claude/commands/<family>/*.md; this script emits checked-in
per-command skill directories under codex/skills/:

    codex/skills/<family>-<command>/
        SKILL.md        # frontmatter (name/description) + harness adaptations
                        # + body inline (progressive disclosure: short bodies)
        reference.md    # full command body (long bodies load on demand)
        scripts/<name>  # helper scripts the body references, bundled byte-identical

Usage:
    codex-skill-sync.py                      # --check (default): exit 1 on drift
    codex-skill-sync.py --check [family...]  # check some or all families
    codex-skill-sync.py --write [family...]  # (re)generate codex/skills/
    codex-skill-sync.py --install            # copy skill dirs -> ~/.codex/skills/

Harness transforms: source frontmatter is replaced by Codex skill frontmatter
(name + description with trigger words front-loaded, JSON-escaped so YAML stays
valid - the retired codex-skill-gen.py's #312 quoting bug); /family:cmd slash
refs are rewritten to the /family-cmd skill names that actually exist in this
surface; Claude-only constructs detected in the body (native worktree tools,
AskUserQuestion, MCP tools, /plugin refs, CLAUDE.md paths) each get a targeted
Codex fallback bullet in a generated adaptations block.

Ownership rule: the script manages ONLY skill dirs whose SKILL.md carries its
GENERATED marker. Hand-curated skill dirs are never overwritten or
orphan-deleted. Generation is deterministic and git-free (byte-for-byte local
diff, no network) so it runs in
the git-less CI validate container. Reconcile drift by editing the SOURCE
(.claude/commands/<family>/) then re-running with --write.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import errno
import hashlib
import json
import os
import re
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = REPO_ROOT / ".claude" / "commands"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
DOCS_ROOT = REPO_ROOT / "docs"
OUTPUT_ROOT = REPO_ROOT / "codex" / "skills"

# Claude command families exposed to Codex, minus `codex`: those commands
# orchestrate the Codex CLI itself, so shipping them INTO Codex as skills would
# be circular.
FAMILIES = [
    "browser", "cicd", "claude-md", "cpp", "documentation", "evaluate",
    "flow", "github", "project", "qa", "second-opinion", "secrets",
    "security", "self-improvement",
]

# Per-family source basenames excluded from generation:
#   cpp: the legacy symlink installer retired in Phase B4.
#   self-improvement/memory.md: Codex ships the hand-curated equivalent
#     codex/cpp-memory.md (issue #433; relocated out of the retired codex/prompts/
#     flat surface at the #556 cutover); a generated variant would duplicate it.
EXCLUDE: dict[str, set[str]] = {
    "cpp": {"init.md", "status.md", "update.md"},
    "self-improvement": {"memory.md"},
}

# Families deliberately not generated as Codex skills (#582 completeness gate):
#   spec: spec-kit is the upstream product; /spec:adopt installs it.
#   codex: orchestrates the Codex CLI itself - circular as a Codex skill.
#   qwen: Claude-supervised local-model orchestration (Qwen Code CLI harness
#     since #745); not a workflow a Codex session drives.
#   gemma: the second Claude-supervised local-model lane (OpenCode harness,
#     #752); same rationale as qwen - Claude is the supervisor, so there is no
#     Codex-side workflow to package.
UNPACKAGED_FAMILIES: set[str] = {"spec", "codex", "qwen", "gemma"}

# Loose *.md files allowed directly under .claude/commands/. Empty by design
# since #582 folded the last six into families: a top-level file is outside
# every family glob, so discovery - and therefore every drift check - is blind
# to it. Adding a name here is an explicit, reviewed exception.
TOP_LEVEL_EXCLUDE: set[str] = set()

MARKER_PREFIX = (
    "<!-- GENERATED by claude-power-pack - scripts/codex-skill-sync.py;"
)

# Codex truncates long skill lists, so descriptions stay short with their
# trigger words up front. CPP's own heuristic for the COMBINED skill-list
# budget (#555, e42b71f) - no specific per-description Codex limit is cited
# anywhere; "front-load trigger words (Codex truncates long skill lists)" is
# the whole rationale.
DESCRIPTION_MAX = 150

#: A NARROW, recorded exception to DESCRIPTION_MAX, not a cap raise - every
#: other skill keeps the 150-char truncation enforced. Each entry's value is
#: the evidence for why spending extra list-budget on THIS skill's full
#: description is worth it, cited rather than silently assumed (#1380).
#: Keyed by the generated skill name (f"{family}-{source_file.stem}").
DESCRIPTION_MAX_EXEMPT: dict[str, str] = {
    "flow-check": (
        "skillc PR #297 (0cbf0fe) / #294 (540d6a3): the full 166-character "
        "description was tested on the CODEX lane, pinned over the complete "
        "cpp-codex skill list, and selected 20/20 when the task called for "
        "it, 0/10 on near-miss tasks - cooneycw/claude-power-pack#1380. The "
        "truncated tail ('...without committing.') was part of what made it "
        "selective, so truncating it here would ship a different, "
        "unevidenced artifact under the evidenced one's name."
    ),
}

# Progressive disclosure: bodies at or under this many lines inline into
# SKILL.md; longer bodies move to reference.md behind a pointer.
INLINE_MAX_LINES = 100

# Claude-only construct classes -> the Codex fallback bullet emitted when any
# of the class's patterns appears in a command body. Only detected classes are
# emitted, so short clean commands carry no adaptations block at all.
ADAPTATIONS: list[tuple[tuple[str, ...], str]] = [
    (
        ("EnterWorktree", "ExitWorktree", ".claude/worktrees"),
        # The location is the visible-sibling convention BOTH harnesses use
        # (claude-power-pack ADR 0003/#627; codex-power-pack#133) - a generic
        # `<path>` here stripped CxPP's sibling guidance on every refresh
        # (issue #586).
        "Native worktrees (`EnterWorktree`/`ExitWorktree` tool calls,"
        " `.claude/worktrees/` paths): use plain git instead, with the"
        " worktree as a VISIBLE SIBLING of the repo -"
        " `git worktree add ../<repo>-<branch> -b <branch>` (or"
        " `$FLOW_WORKTREE_BASE/<repo>-<branch>` when that env var is set),"
        " work inside it, then `git worktree remove ../<repo>-<branch>`"
        " when done.",
    ),
    (
        ("AskUserQuestion",),
        "`AskUserQuestion` tool: ask the user directly in the conversation"
        " and wait for their answer.",
    ),
    (
        ("Skill tool", "Agent tool", "subagent"),
        "Claude subagent/skill dispatch: do the work inline in this session,"
        " or shell out to `codex exec` when isolation is needed.",
    ),
    (
        ("mcp__", "MCP", "playwright"),
        "MCP tools: use the MCP servers configured in `~/.codex/config.toml`,"
        " or fall back to the referenced repo scripts and CLI entry points.",
    ),
    (
        ("CLAUDE.md",),
        # CONDITIONAL, not a substitution (#1071). This line is stamped into 25
        # skills that run in ANY repository, so it must be true in all three
        # shapes a target repo can have: AGENTS.md alone, both files, or
        # CLAUDE.md alone. It previously said "treat them as the target repo's
        # agent-context file" - interchangeable - which is CPP's own shape
        # asserted about every consumer, and which tells a session handed a THIN
        # AGENTS.md to stop there and never follow its pointer.
        "`CLAUDE.md` references: read `AGENTS.md` first - it is the Codex entry"
        " point. Where it defers to `CLAUDE.md`, follow that pointer and"
        " `CLAUDE.md` is the rules; where it does not, `AGENTS.md` is. Where the"
        " repository has no `AGENTS.md`, read `CLAUDE.md`.",
    ),
    (
        ("`! <command>`", "the `!` prefix"),
        "Claude's `! <command>` prompt prefix: run the command in your own"
        " shell instead.",
    ),
]

BUNDLED_SCRIPTS_BULLET = (
    "Helper scripts referenced as `scripts/<name>` are bundled under"
    " `scripts/` in this skill directory (byte-identical copies from the"
    " claude-power-pack checkout); some expect sibling repo resources, so"
    " prefer a full checkout when one is available."
)

BUNDLED_DOCS_BULLET = (
    "Canonical guidance linked as `docs/<path>` is bundled under `docs/` in"
    " this skill directory (byte-identical copies from the claude-power-pack"
    " checkout). The source-relative `../../../docs/...` link in the command"
    " body resolves outside an installed skill, so the generated copy points"
    " at the bundled path instead. docs/ remains the only writable source."
)


NETWORK_BULLET = (
    "Network: this skill's bundled helpers appear to call the network (`gh`,"
    " `git fetch`/`push`, `curl`, `aws`, HTTP). Codex's workspace sandbox has no network,"
    " and an allow rule for `gh` covers only a top-level `gh` command, never one"
    " a helper runs. Run these helpers with escalated permissions. From inside"
    " the sandbox, \"error connecting to api.github.com\" means no network, not a"
    " GitHub outage or a bad login."
)

#: A network INVOCATION in a bundled helper, not a mention (issue #1357). The
#: command body is the wrong place to look: project-next's only `gh` call is in
#: lib/project_next/collect.py, which the command document never names. Each
#: shape is applied only to its own file type:
#:
#:   Python - an argv list opening with the tool, `["gh", ...]`, or with git
#:            whose SUBCOMMAND is a remote verb, `["git", "-C", path, "fetch"]`
#:            (only `-C`/`-c` pairs may precede it, so `["git", "branch",
#:            "fetch"]` is local); or an HTTP client import (`urllib.request`,
#:            `http.client`, `requests`) - the import is the dependency, the
#:            same rule _LIB_IMPORT applies. Comment lines are skipped.
#:   Shell  - the tool at a command position: line start, after `;`, `&`, `|`,
#:            a backtick, `$(`, or `if`/`then`/`do`/`!`, on a non-comment line.
#:            The tool may be literal or a variable named for it, with or
#:            without `_BIN`: `"$GH_BIN" api` (gh-pr-merge.sh,
#:            flow-ci-status.sh), `"$GH" issue view` / `"$GIT" fetch`
#:            (flow-start-resolve.sh).
#:
#: A bare `(` is deliberately NOT a command position: `"... (gh issue create)"`
#: inside a usage string in flow-worktree-claim.sh is prose, and matching it
#: flagged four skills that make no network call.
#:
#: PYTHON IS AST, NOT REGEX (issue #1408, counter-model review, codex LOW,
#: PR #1359). A string or a docstring is ONE `ast.Constant` node to the real
#: parser - it can never contain a nested `ast.List` node, so prose shaped
#: exactly like `run(["gh", "issue", "list"])` inside a docstring simply does
#: not generate the AST shape this detector looks for. No regex tweak closes
#: that gap; the parser already refuses to open it.
#:
#: SHELL KEEPS A COMMAND-POSITION CHECK, because a full shell parser is a
#: much bigger dependency than `ast` for one advisory bullet - but it now
#: tracks quote state per line (the same per-line quote-span tracking
#: `check-test-binary-guards.py` added for heredocs in #1407) and only
#: accepts a match whose START position is OUTSIDE any open quote.
#: `echo "retry; gh issue list"` no longer matches: the `;` that used to open
#: a command position sits inside the double-quoted span. A REAL command
#: position - line start, after `;`, `&`, `|`, a backtick, `$(`, or
#: `if`/`then`/`do`/`!` - still matches outside quotes, with the tool literal
#: or a variable named for it, with or without `_BIN`: `"$GH_BIN" api`
#: (gh-pr-merge.sh, flow-ci-status.sh), `"$GH" issue view` / `"$GIT" fetch`
#: (flow-start-resolve.sh).
_NET_PY_TOOLS = ("gh", "curl", "aws")
_NET_GIT_REMOTE_VERBS = ("fetch", "push", "pull", "ls-remote", "clone")
_NET_PY_IMPORT_MODULES = ("urllib.request", "http.client", "requests")


def _py_list_is_network_argv(node: ast.List) -> bool:
    """True when a list literal's elements open with a network-tool argv shape."""
    if not node.elts:
        return False
    first = node.elts[0]
    if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
        return False
    if first.value in _NET_PY_TOOLS:
        return True
    if first.value != "git":
        return False
    # Only `-C <path>` / `-c <key=val>` PAIRS may precede the subcommand, so
    # `["git", "branch", "fetch"]` (the literal branch name "fetch") is local.
    i = 1
    while i + 1 < len(node.elts):
        flag = node.elts[i]
        if isinstance(flag, ast.Constant) and flag.value in ("-C", "-c"):
            i += 2
            continue
        break
    if i >= len(node.elts):
        return False
    verb = node.elts[i]
    return isinstance(verb, ast.Constant) and verb.value in _NET_GIT_REMOTE_VERBS


#: NEGATIVE-CONTROL: controls/codex-skill-sync-network-detector
def _py_calls_network(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        # A bundled script that cannot parse is a different problem entirely,
        # not this detector's to diagnose; it reports no network call rather
        # than guessing at malformed source.
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for arg in (*node.args, *(kw.value for kw in node.keywords)):
                if isinstance(arg, ast.List) and _py_list_is_network_argv(arg):
                    return True
        elif isinstance(node, ast.Import):
            if any(alias.name in _NET_PY_IMPORT_MODULES for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in _NET_PY_IMPORT_MODULES or module == "urllib" and any(
                alias.name == "request" for alias in node.names
            ):
                return True
    return False


def _sh_quote_free_mask(line: str) -> list[bool]:
    """True at each index of `line` that is outside a quoted span and before
    any unquoted `#` - the only positions a real command can start at.

    `$( ... )` is tracked as a NESTED, FRESH parsing context (a stack, not a
    flag), because real bash still performs command substitution INSIDE a
    double-quoted string - `out="$(gh issue list)"` genuinely runs `gh`, and
    an enclosing double quote does not suppress it the way a single quote
    would. A flat one-level quote tracker that masked everything inside the
    outer `"..."` made this case indistinguishable from the one this
    function exists to mask - `echo "retry; gh issue list"` - which really
    is inert text. The distinguishing fact is `$(`, not quote depth, so each
    `$(...)` gets quote state that starts over, exactly as bash's own parser
    restarts tokenizing inside one.
    """
    mask = [True] * len(line)
    stack = [{"single": False, "double": False}]
    paren_depth: list[int] = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        top = stack[-1]
        if top["single"]:
            mask[i] = False
            if ch == "'":
                top["single"] = False
            i += 1
            continue
        if top["double"]:
            if ch == '"' and line[i - 1] != "\\":
                mask[i] = False
                top["double"] = False
                i += 1
                continue
            if line[i : i + 2] == "$(":
                # A substitution inside a double-quoted string still runs -
                # start a FRESH context for its contents, left unmasked.
                stack.append({"single": False, "double": False})
                paren_depth.append(1)
                i += 2
                continue
            mask[i] = False
            i += 1
            continue
        if ch == "#" and len(stack) == 1:
            for j in range(i, n):
                mask[j] = False
            break
        if ch == "'":
            top["single"] = True
            # The OPENING quote char itself stays free: `"$GH_BIN"` quotes a
            # COMMAND WORD, and the tool pattern below expects to match that
            # leading quote as part of the token - only what comes strictly
            # AFTER it is the string's own inert content.
            i += 1
            continue
        if ch == '"':
            top["double"] = True
            i += 1
            continue
        if line[i : i + 2] == "$(":
            stack.append({"single": False, "double": False})
            paren_depth.append(1)
            i += 2
            continue
        if ch == "(" and paren_depth:
            paren_depth[-1] += 1
            i += 1
            continue
        if ch == ")" and paren_depth:
            paren_depth[-1] -= 1
            if paren_depth[-1] == 0:
                paren_depth.pop()
                stack.pop()
            i += 1
            continue
        i += 1
    return mask


_NET_SH_CORE = re.compile(
    r"(?:^|[;&|`]|\$\(|\b(?:if|then|do|!)\s)\s*"
    r"(?:(?:gh|\"?\$\{?GH(?:_BIN)?\}?\"?)\s+(?:api|issue|pr|repo|run|release|auth|search|label|workflow)\b"
    r"|(?:git|\"?\$\{?GIT(?:_BIN)?\}?\"?)\s+(?:-[Cc]\s+\S+\s+)*(?:fetch|push|pull|ls-remote|clone)\b"
    r"|(?:curl|aws|\"?\$\{?(?:CURL|AWS|WPCLI)(?:_BIN)?\}?\"?)\s)"
)


def _sh_calls_network(text: str) -> bool:
    for line in text.splitlines():
        mask = _sh_quote_free_mask(line)
        for match in _NET_SH_CORE.finditer(line):
            if mask[match.start()]:
                return True
    return False


def calls_network(files: dict[str, str]) -> bool:
    """True when any bundled helper (skill-relative path -> text) invokes the network."""
    for rel, text in files.items():
        if rel.endswith(".py") and _py_calls_network(text):
            return True
        if rel.endswith(".sh") and _sh_calls_network(text):
            return True
    return False


def marker_for(family: str, base: str) -> str:
    return (
        f"{MARKER_PREFIX} edit .claude/commands/{family}/{base} instead -->"
    )


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Split a leading YAML frontmatter block into a flat key map + body.

    Only top-level scalar `key: value` lines are read (that is all the command
    sources use); everything else in the block is ignored.
    """
    if not content.startswith("---"):
        return {}, content
    end = content.find("\n---", 3)
    if end == -1:
        return {}, content
    block = content[3:end]
    body = content[end + len("\n---"):].lstrip("\n")
    meta: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line or line.startswith((" ", "\t", "#")):
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        meta[key.strip()] = value
    return meta, body


def _visible_lines(body: str) -> list[str]:
    """Body lines with HTML comment blocks and fenced code stripped out."""
    lines: list[str] = []
    in_comment = False
    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        if stripped.startswith("<!--"):
            if not stripped.endswith("-->"):
                in_comment = True
            continue
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        lines.append(line)
    return lines


def derive_description(meta: dict[str, str], body: str, *, skill_name: str | None = None) -> str:
    """Skill-list description: source frontmatter description when present,
    else H1 title + first prose paragraph. Front-loads the trigger words and
    caps the length (Codex truncates long skill lists) - unless `skill_name`
    is a recorded DESCRIPTION_MAX_EXEMPT entry (#1380)."""
    desc = " ".join(meta.get("description", "").split())
    if not desc:
        title = ""
        para_lines: list[str] = []
        for line in _visible_lines(body):
            stripped = line.strip()
            if not stripped:
                if para_lines:
                    break
                continue
            if stripped.startswith("#"):
                if para_lines:
                    break
                if not title:
                    title = stripped.lstrip("#").strip()
                continue
            if stripped.startswith(("|", ">", "- ", "* ", "---")):
                if para_lines:
                    break
                continue
            para_lines.append(stripped)
        para = " ".join(para_lines)
        if title and para:
            desc = f"{title} - {para}"
        else:
            desc = title or para
        desc = " ".join(desc.split())
    if len(desc) > DESCRIPTION_MAX and skill_name not in DESCRIPTION_MAX_EXEMPT:
        desc = desc[:DESCRIPTION_MAX].rsplit(" ", 1)[0].rstrip(" ,;:-") + " ..."
    return desc


def derive_title(body: str) -> str:
    for line in _visible_lines(body):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def detect_adaptations(body: str) -> list[str]:
    return [
        bullet
        for patterns, bullet in ADAPTATIONS
        if any(pattern in body for pattern in patterns)
    ]


#: `~/.claude/scripts/<name>` - the convenience-install absolute path a command
#: document invokes a helper by (issue #1408, Nit Store #864). The RELATIVE
#: form `scripts/<name>` already reads correctly unchanged in both the CPP
#: checkout (repo-root-relative) and a generated skill (skill-dir-relative,
#: since the helper is bundled at that same relative path) - which is exactly
#: why `_SCRIPT_REF` needs no rewrite at all for that shape. The absolute form
#: has no such luck: `~/.claude/scripts/` names a path that exists only on a
#: host with the convenience install, never inside a generated skill, so it
#: must become the relative form before anything downstream can see it as a
#: dependency - it previously became nothing, and the Codex entry point hit
#: exit 127.
_ABS_CLAUDE_SCRIPT_REF = re.compile(r"~/\.claude/scripts/([A-Za-z0-9._-]+\.(?:sh|py))\b")


#: NEGATIVE-CONTROL: controls/codex-skill-sync-remap
def rewrite_absolute_script_refs(body: str) -> tuple[str, list[str]]:
    """Rewrite `~/.claude/scripts/<name>` to `scripts/<name>` when `<name>` is
    a real checkout script (so `find_bundled_scripts` bundles it exactly as it
    already does for a relative reference - no second bundling path).

    Returns `(new_body, unremapped)`: `unremapped` names any `<name>` that is
    NOT a real checkout script, left untouched in the body rather than
    rewritten to a relative path that would resolve to nothing bundled - a
    typo'd or genuinely host-only name must be named as a gap, not silently
    pointed at a file this generator never ships.
    """
    unremapped: list[str] = []

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if (SCRIPTS_ROOT / name).is_file():
            return f"scripts/{name}"
        unremapped.append(name)
        return match.group(0)

    new_body = _ABS_CLAUDE_SCRIPT_REF.sub(repl, body)
    return new_body, sorted(set(unremapped))


def unremapped_script_bullet(names: list[str]) -> str:
    joined = ", ".join(f"`~/.claude/scripts/{n}`" for n in names)
    return (
        f"Absolute path(s) {joined}: no matching checkout script was found, so"
        " this skill cannot bundle it and the reference will not resolve in a"
        " Codex-only install (exit 127). Obtain the helper from a"
        " claude-power-pack checkout, or file a Nit Store finding."
    )


_SCRIPT_REF = re.compile(r"scripts/([A-Za-z0-9._-]+\.(?:sh|py))")


#: A shell script running a SIBLING out of its own directory:
#: `"$SELF_DIR/eli5-vendor.py"`, `"$_self_dir/speckit-context.py"`,
#: `"$(dirname "$0")/x.sh"`. THE `$VAR/` PREFIX IS THE WHOLE SIGNAL, and it is
#: what separates a dependency from a mention (issue #1028).
#:
#: `eli5-core-drift.sh` is why the rule is not a `scripts/<name>` grep: its only
#: `scripts/` token is in the header comment, while the line that actually runs
#: is `exec python3 "$SELF_DIR/eli5-vendor.py"`. So the bundler saw no
#: dependency, shipped the shim alone, and every invocation from the Codex
#: surface died on a missing file instead of reporting drift - in a script whose
#: own header says it exists "so there is exactly ONE implementation behind
#: them".
#:
#: The rule is tight in the other direction too. `flow-wave-registry.sh` prints
#: `"... scripts/checkout-readers.sh says when ..."` inside an `echo`, and
#: `speckit-tasks-to-issues.sh` names `scripts/flow-wave-registry.sh` in a
#: comment; neither is a dependency, and neither has a `$VAR/` prefix.
_SIBLING_REF = re.compile(
    r"(?:\$\{?\w+\}?|\$\((?:dirname|readlink)[^)]*\))/([A-Za-z0-9._-]+\.(?:sh|py))"
)

#: `from lib.x import ...` / `import lib.x`, and single-dot relative imports
#: inside a bundled package module (`from .b import value` -> the module `b`;
#: `from . import b, c` -> the modules `b` and `c`) are both resolved by the
#: AST-based `_live_absolute_lib_imports`/`_live_relative_imports` below
#: (issue #1408) rather than by a regex here - see their docstrings for why a
#: line-shape match over-bundled `lib/cicd/` from its own module docstring.
#:
#: The second relative-import spelling (`from . import b, c`) is absent from
#: this repository today, and that is exactly why `_relative_import_names`
#: still handles it: a rule written against only the shapes currently present
#: is one refactor away from silently bundling an incomplete package, and the
#: symptom would be an ImportError in a shipped artifact rather than a red
#: here.
#:
#: Parent-relative (`from ..x`) is deliberately NOT matched (`level == 1`
#: only): these packages are vendored whole from their own root, so a
#: parent-relative import reaches outside the tree being bundled and means
#: the vendoring boundary is wrong - which is a thing to notice, not to paper
#: over by copying more files.


#: NEGATIVE-CONTROL: controls/codex-skill-sync-over-bundle
def _typing_checking_bindings(tree: ast.Module) -> tuple[set[str], set[str]]:
    """Names this file's own imports actually bind to `typing.TYPE_CHECKING`
    (bare, respecting `as`) and to the `typing` module itself (respecting
    `as`) - issue #1408, counter-model review.

    `_is_type_checking_test` used to accept ANY name ending in
    `TYPE_CHECKING`, bare or attribute, regardless of what imported it -
    so `if settings.TYPE_CHECKING:` (an unrelated application flag) or a
    locally assigned `TYPE_CHECKING = True` excluded a live import exactly
    like the real typing sentinel does, with no way to tell them apart. Only
    a name this file imports FROM `typing` is the real guard.
    """
    checking_names: set[str] = set()
    typing_module_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == "typing":
            checking_names.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "TYPE_CHECKING"
            )
        elif isinstance(node, ast.Import):
            typing_module_names.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "typing"
            )
    return checking_names, typing_module_names


def _is_type_checking_test(
    test: ast.expr, checking_names: set[str], typing_module_names: set[str]
) -> bool:
    """True for an `if` test that resolves to `typing.TYPE_CHECKING` through
    an import THIS FILE actually has - bare (`from typing import
    TYPE_CHECKING`, any `as`) or module-qualified (`import typing`, any
    `as`, then `<name>.TYPE_CHECKING`)."""
    if isinstance(test, ast.Name):
        return test.id in checking_names
    if isinstance(test, ast.Attribute):
        return (
            test.attr == "TYPE_CHECKING"
            and isinstance(test.value, ast.Name)
            and test.value.id in typing_module_names
        )
    return False


def _live_import_nodes(text: str) -> list[ast.Import | ast.ImportFrom]:
    """`Import`/`ImportFrom` statements NOT nested inside `if TYPE_CHECKING:`
    (issue #1408, counter-model review).

    A block guard is control flow a regex cannot see - only the parser knows
    a statement sits inside an `if` whose test names TYPE_CHECKING, which
    `importlib`/`__getattr__` never executes. `lib/cicd/__init__.py` lists
    all 29 submodules there for mypy's benefit alone; the old regexes
    (`_RELATIVE_IMPORT`/`_RELATIVE_FROM_PACKAGE` for `from .x import ...`,
    `_LIB_IMPORT` for `from lib.x import ...`) read line shape alone, so a
    USAGE EXAMPLE in that module's own docstring (`from lib.cicd import
    run_health_checks`) matched `_LIB_IMPORT` exactly like a live import and
    bundled the whole package via `rglob` - not even a TYPE_CHECKING case,
    just text that happens to start a line the same way code does.

    Walks into every compound statement (functions, classes, other `if`s)
    so an import nested deeper still counts, with the SAME TYPE_CHECKING
    exclusion propagated into it - not just the module's top level. A
    docstring is a single `Constant` node and never produces an `Import`/
    `ImportFrom` node at all, so this exclusion is structural rather than a
    second pattern to keep in sync with the first.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    live: list[ast.Import | ast.ImportFrom] = []
    checking_names, typing_module_names = _typing_checking_bindings(tree)

    def walk(nodes: list[ast.stmt], skip: bool) -> None:
        for node in nodes:
            if isinstance(node, ast.If) and _is_type_checking_test(
                node.test, checking_names, typing_module_names
            ):
                walk(node.body, True)
                walk(node.orelse, skip)
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if not skip:
                    live.append(node)
                continue
            if isinstance(node, ast.Match):
                # `match_case.body` is a field of the CASE, not of the
                # `Match` node itself, so the generic `body`/`orelse`/
                # `finalbody`/`handlers` walk below never reaches it
                # (counter-model review) - an import inside any case
                # silently never counted as a dependency.
                for case in node.cases:
                    walk(case.body, skip)
                continue
            for field in ("body", "orelse", "finalbody", "handlers"):
                child = getattr(node, field, None)
                if not child:
                    continue
                if field == "handlers":
                    for handler in child:
                        walk(handler.body, skip)
                else:
                    walk(child, skip)

    walk(tree.body, False)
    return live


def _live_relative_imports(text: str) -> list[ast.ImportFrom]:
    """`from .x import ...` / `from . import x, y` statements among the live
    (non-TYPE_CHECKING) imports `_live_import_nodes` returns."""
    return [
        node
        for node in _live_import_nodes(text)
        if isinstance(node, ast.ImportFrom) and node.level == 1
    ]


def _live_absolute_lib_imports(text: str) -> list[str]:
    """Dotted `lib.*` targets of the live (non-TYPE_CHECKING) imports
    `_live_import_nodes` returns - replaces `_LIB_IMPORT`'s regex scan, which
    cannot tell a docstring's `from lib.cicd import ...` usage example from a
    real import (issue #1408: that example is exactly what over-bundled
    `lib/cicd/` for flow-check)."""
    dotted: list[str] = []
    for node in _live_import_nodes(text):
        if isinstance(node, ast.Import):
            dotted.extend(
                alias.name for alias in node.names
                if alias.name == "lib" or alias.name.startswith("lib.")
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
            and (node.module == "lib" or node.module.startswith("lib."))
        ):
            dotted.append(node.module)
    return dotted


def _relative_import_names(node: ast.ImportFrom) -> list[str]:
    """The sibling module name(s) one `from .x import ...` / `from . import
    x, y` AST node names - both spellings `_live_relative_imports` returns."""
    if node.module:
        return [node.module]
    return [alias.name for alias in node.names]


def _lazy_getattr_map(text: str) -> dict[str, str] | None:
    """The `{name: submodule}` dict a lazy `__getattr__` package resolves
    against, read from the package's OWN AST rather than hardcoded here -
    issue #1408's ruling, and the same #1136 lesson this repository has
    already paid for once ("a hardcoded universe again, one entry longer"):
    a SECOND copy of the map drifts from the real one on the package's next
    refactor, silently.

    A module qualifies only when it DEFINES a MODULE-LEVEL `__getattr__`
    (PEP 562) whose own body REFERENCES a MODULE-LEVEL dict literal (by
    name) whose keys and values are all string constants - the shape
    `lib/cicd/__init__.py` uses, not a convention tied to that one package.

    Both restrictions are load-bearing (counter-model review): `ast.walk`
    over the WHOLE tree finds a dict or a function nested inside ANY class
    or other function too, and `__getattr__` existing somewhere says nothing
    about which dict it resolves against. A package with a real PEP 562
    `__getattr__` and an UNRELATED string-to-string dict elsewhere in the
    file (a config table, an error-message map) would otherwise be
    classified as lazy and resolved through the wrong map - silently
    suppressing this function's own whole-directory bundling for a package
    that was never actually lazy in the way this fix assumes.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    getattr_fn = next(
        (
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "__getattr__"
        ),
        None,
    )
    if getattr_fn is None:
        return None
    referenced = {node.id for node in ast.walk(getattr_fn) if isinstance(node, ast.Name)}
    for node in tree.body:
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in referenced
            and isinstance(node.value, ast.Dict)
        ):
            continue
        mapping: dict[str, str] = {}
        for key, value in zip(node.value.keys, node.value.values):
            if not (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                mapping = {}
                break
            mapping[key.value] = value.value
        if mapping:
            return mapping
    return None


def _referenced_lazy_names(text: str, package_dotted: str) -> set[str]:
    """Names this file's own text accesses through `package_dotted`'s lazy
    `__getattr__`: `from <package_dotted> import <name>` (module-absolute,
    `level == 0`), a `<package_dotted>.<name>` attribute chain, or the same
    chain through an explicit `import <package_dotted> as <alias>` (issue
    #1408, counter-model review - `import lib.cicd as c; c.run_health_checks`
    bundled the package's own `__init__.py` fine but never recorded
    `run_health_checks`, since the attribute chain started at `c`, not at
    `pkg_parts`)."""
    names: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return names
    pkg_parts = package_dotted.split(".")
    aliases = {
        alias.asname
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == package_dotted and alias.asname
    }
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module == package_dotted
        ):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Attribute):
            chain: list[str] = []
            cur: ast.expr = node
            while isinstance(cur, ast.Attribute):
                chain.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                chain.append(cur.id)
                chain.reverse()
                via_real_name = chain[:-1] == pkg_parts
                via_alias = len(chain) == 2 and chain[0] in aliases
                if via_real_name or via_alias:
                    names.add(chain[-1])
    return names

#: A module-level constant naming a REPO-RELATIVE DATA FILE:
#: `MANIFEST_PATH = REPO_ROOT / ".claude" / "project-next-vendor.json"`.
#:
#: CODE IS NOT THE WHOLE DEPENDENCY (found by the #1028 counter-model review).
#: Bundling `project-next.py` with its library made the script IMPORT, and
#: `--help` then printed usage - which is what the first test asserted, and it
#: proved less than its name suggested. A real query still died on
#: `[Errno 2] ... codex/skills/project-next/.claude/project-next-vendor.json`,
#: because the entry point reads that manifest at rank time. "It starts" and "it
#: works" are different claims, and only the second one matters to whoever runs it.
_ROOT_DATA_PATH = re.compile(
    r"(?m)^\s*[A-Z][A-Z0-9_]*\s*=\s*([A-Z][A-Z0-9_]*)((?:\s*/\s*\"[^\"]+\")+)\s*$"
)

#: A root constant is only trusted when the module derives it from its OWN
#: location. Without this, any constant divided by a string literal that happens
#: to exist under the repository root would pull a file into the bundle - and a
#: bundle is not the place to find out that a heuristic was loose.
_FILE_ROOTED = r"(?m)^\s*{name}\s*=\s*Path\(__file__\)"


def find_bundled_scripts(body: str) -> list[str]:
    """Helper-script basenames the body references, plus what THOSE scripts run.

    A closure, the same shape `find_bundled_docs` uses for sibling doc links:
    it starts from what the command body actually names and stops when no new
    file is reached. The bundler used to discover only the body's own
    references, so a bundled script's own helper was simply absent and the
    shipped copy could not run at all (issue #1028).
    """
    pending = [
        name for name in {m.group(1) for m in _SCRIPT_REF.finditer(body)}
        if (SCRIPTS_ROOT / name).is_file()
    ]
    found: set[str] = set()
    while pending:
        name = pending.pop()
        if name in found:
            continue
        found.add(name)
        for match in _SIBLING_REF.finditer((SCRIPTS_ROOT / name).read_text()):
            sibling = match.group(1)
            if sibling not in found and (SCRIPTS_ROOT / sibling).is_file():
                pending.append(sibling)
    return sorted(found)


def _lib_package_path(dotted: str) -> Path | None:
    """Where `lib.x.y` lives, as a path RELATIVE TO THE REPO ROOT.

    Bundled at that same relative path, the import resolves without any
    rewriting: every one of these scripts derives its own root from
    `Path(__file__).resolve().parents[1]`, which IS the skill directory once the
    script is bundled under `<skill>/scripts/`. `eli5-vendor.py` inserts that
    root and finds `<skill>/lib/vendor.py`; `project-next.py` inserts
    `<root>/vendor/project_next` and finds
    `<skill>/vendor/project_next/lib/project_next/`. One rule, two layouts, no
    per-script knowledge.

    Only the roots this repository actually has are searched, and the search is
    ORDERED rather than globbed-and-hoped: an ambiguous match would silently
    bundle whichever the filesystem returned first.
    """
    rel = Path(*dotted.split("."))
    for base in (REPO_ROOT, *sorted((REPO_ROOT / "vendor").glob("*"))):
        if not base.is_dir():
            continue
        package = base / rel
        if package.is_dir() and (package / "__init__.py").is_file():
            return package.relative_to(REPO_ROOT)
        module = package.with_suffix(".py")
        if module.is_file():
            return module.relative_to(REPO_ROOT)
    return None


def find_bundled_data(scripts: list[str]) -> dict[str, Path]:
    """Repo-relative DATA files the bundled Python scripts read at run time.

    Bundled at the same relative path as the libraries, for the same reason:
    each script resolves it from a root derived from its own `__file__`, which
    is the skill directory once bundled.

    Deliberately narrow, and narrow is the correct answer here rather than a
    limitation to apologise for: it matches a module-level constant assigned
    `<ROOT> / "a" / "b"` where `<ROOT>` is itself derived from `Path(__file__)`
    and the result is an existing FILE. Across all 89 scripts in this repository
    that is exactly two expressions. A rule that tried to chase every runtime
    path a script might open would be guessing, and a bundle assembled by
    guesswork is worse than one whose gaps are visible.
    """
    out: dict[str, Path] = {}
    for name in scripts:
        path = SCRIPTS_ROOT / name
        if path.suffix != ".py":
            continue
        text = path.read_text()
        for match in _ROOT_DATA_PATH.finditer(text):
            root_name = match.group(1)
            if not re.search(_FILE_ROOTED.format(name=re.escape(root_name)), text):
                continue
            rel = Path(*re.findall(r'"([^"]+)"', match.group(2)))
            source = REPO_ROOT / rel
            if source.is_file():
                out[str(rel)] = source
    return out


#: A shell `source` / `.` line, with the sourced filename LITERAL on it. The
#: filename must be visible here or this bundler cannot follow it, which is why
#: every gate-lib consumer spells it `. "$dir/gate-lib.sh"` rather than sourcing a
#: variable that holds the whole path.
_SHELL_SOURCE_RE = re.compile(r"^\s*(?:\.|source)\s+(\S+)", re.MULTILINE)


def find_bundled_shell_libs(scripts: list[str]) -> dict[str, Path]:
    """Map skill-relative path -> source path for the shell libraries `scripts` source.

    WHY THIS EXISTS (issue #1061). `find_bundled_libs` follows PYTHON `lib.*`
    imports and nothing else, so a bundled SHELL script's dependency was invisible
    to the bundler. `scripts/flow-finish-gate.sh` is bundled into four skills and
    now sources `scripts/gate-lib.sh`; without this the four shipped copies would
    carry a gate whose library reaches none of them. Measured before choosing this
    route rather than a reference in a command document: 26 distinct shell scripts
    are bundled into skills and ZERO of them sourced a sibling, so gate-lib is the
    first case and teaching the bundler changes exactly the skills that need it.
    Closing the class also covers the four other gate-lib consumers from #1127, none
    bundled today, each of which would otherwise reopen the identical hole the day
    it is.

    AN UNFOLLOWABLE SOURCE RAISES, and that is the load-bearing half. A `source`
    line whose target this cannot resolve - computed, conditional, or built from a
    variable - is exactly the shape that would ship a silently incomplete bundle,
    which is the defect this function exists to remove. Refusing at generation is
    the only place that failure is cheap: the alternative is discovering it in a
    distributed copy, where nobody runs the suite.
    """
    out: dict[str, Path] = {}
    pending: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for name in scripts:
        path = SCRIPTS_ROOT / name
        if path.suffix == ".sh":
            pending.append((f"scripts/{name}", path))

    while pending:
        origin, path = pending.pop()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        for match in _SHELL_SOURCE_RE.finditer(path.read_text(encoding="utf-8")):
            raw = match.group(1)
            # The sourced word with quoting and any `$dir/` prefix removed. Only a
            # LITERAL basename can be resolved; anything else is refused below.
            candidate = raw.strip('"').strip("'").rsplit("/", 1)[-1]
            if not candidate.endswith(".sh") or "$" in candidate:
                raise SystemExit(
                    f"codex-skill-sync: {origin} sources `{raw}`, whose target this "
                    f"bundler cannot resolve. Spell the filename literally on the "
                    f"source line (`. \"$dir/name.sh\"`), or the bundle would ship a "
                    f"script whose dependency is missing and which cannot start."
                )
            source = SCRIPTS_ROOT / candidate
            if not source.is_file():
                raise SystemExit(
                    f"codex-skill-sync: {origin} sources `{candidate}`, which is not "
                    f"under scripts/. Bundling it would ship a script that cannot start."
                )
            out[f"scripts/{candidate}"] = source
            pending.append((f"scripts/{candidate}", source))
    return out


def find_bundled_libs(scripts: list[str]) -> dict[str, Path]:
    """Map skill-relative path -> source path for the libraries `scripts` import.

    An unresolvable `lib.*` import RAISES rather than being skipped. Skipping is
    what the pre-#1028 bundler effectively did, and the artifact it produced was
    indistinguishable from a working one until someone ran it.
    """
    out: dict[str, Path] = {}
    # A WORKLIST, NOT A SINGLE PASS (found by the #1028 counter-model review).
    # The first cut scanned only the entry scripts, so a module it copied was
    # never itself examined: with `scripts/x.py` importing `lib.a`, and `lib/a.py`
    # containing `from .b import value`, the bundle carried `a.py` and no `b.py`.
    # Generation succeeded and the bundled entry point died at import.
    #
    # The real project-next bundle happened to be complete only because the entry
    # point imports all six modules directly - the transitive edges were satisfied
    # by coincidence, which is not a property anything was checking.
    pending: list[tuple[str, Path]] = []
    seen: set[Path] = set()

    def drain() -> None:
        while pending:
            origin, path = pending.pop()
            if path in seen:
                continue
            seen.add(path)
            text = path.read_text()

            # Absolute `lib.*` imports, resolved against the repository root.
            # AST-based and TYPE_CHECKING-aware (issue #1408) - see
            # `_live_absolute_lib_imports` for why the regex this replaced
            # over-bundled `lib/cicd/` from its own module docstring.
            for dotted in _live_absolute_lib_imports(text):
                rel = _lib_package_path(dotted)
                if rel is None:
                    raise SystemExit(
                        f"codex-skill-sync: {origin} imports `{dotted}`, which "
                        f"resolves to no package under the repository root or vendor/. "
                        f"Bundling it would ship a script that cannot start."
                    )
                source = REPO_ROOT / rel
                if source.is_dir():
                    source_init = source / "__init__.py"
                    # A LAZY `__getattr__` package (issue #1408) resolves its
                    # re-exports one name at a time at runtime, so bundling
                    # every module under it eagerly is exactly the over-bundle
                    # this issue exists to remove - `from lib.cicd import
                    # run_health_checks` would otherwise rglob all 29 files
                    # for one. The post-drain lazy-map pass below bundles
                    # only the submodule(s) actually referenced; an ordinary
                    # (non-lazy) package keeps the old whole-directory bundle,
                    # since nothing yet in this repository imports one by its
                    # bare package name while depending on only some of it.
                    if source_init.is_file() and _lazy_getattr_map(source_init.read_text()) is not None:
                        targets = [source_init]
                    else:
                        targets = sorted(source.rglob("*.py"))
                else:
                    targets = [source]
                for child in targets:
                    out[str(child.relative_to(REPO_ROOT))] = child
                    pending.append((str(child.relative_to(REPO_ROOT)), child))
                # EVERY `__init__.py` ON THE WAY DOWN. `from lib.project_next.rank
                # import ...` resolves to one module, so bundling only that module
                # leaves the package's own `__init__.py` behind - and the six
                # modules import each other relatively (`from .models import ...`),
                # which needs the package to BE one. Python would fall back to a
                # namespace package and skip an `__init__.py` that is 488 bytes of
                # real code, so the bundle would import and then behave differently
                # from the checkout: the worst failure shape for a mirror whose
                # whole purpose is being byte-identical.
                for parent in rel.parents:
                    init = REPO_ROOT / parent / "__init__.py"
                    if init.is_file():
                        out[str(init.relative_to(REPO_ROOT))] = init
                        pending.append((str(init.relative_to(REPO_ROOT)), init))

            # Relative imports INSIDE a bundled package - `from .b import value` -
            # AST-based and TYPE_CHECKING-aware (issue #1408): only meaningful once
            # we are walking a package's own modules, which is exactly what the
            # worklist made possible.
            if path.parent != SCRIPTS_ROOT:
                names: list[str] = []
                for node in _live_relative_imports(text):
                    names.extend(_relative_import_names(node))
                for module in names:
                    if not module.isidentifier():
                        continue
                    sibling = path.parent / f"{module}.py"
                    subpackage = path.parent / module / "__init__.py"
                    for candidate in (sibling, subpackage):
                        if candidate.is_file():
                            rel_child = candidate.relative_to(REPO_ROOT)
                            out[str(rel_child)] = candidate
                            pending.append((str(rel_child), candidate))

    for name in scripts:
        path = SCRIPTS_ROOT / name
        if path.suffix == ".py":
            pending.append((f"scripts/{name}", path))
    drain()

    # LAZY `__getattr__` RE-EXPORTS (issue #1408): a TYPE_CHECKING-guarded
    # import is invisible to the worklist above BY DESIGN - it is never
    # executed. But the package's OWN `__getattr__` can still reach that
    # submodule at RUNTIME, on first attribute access, so dropping it
    # unconditionally can ship a mirror that ImportErrors in Codex the
    # moment something touches a re-exported name. The fix is not to trust
    # the TYPE_CHECKING list (undoing the fix above) - it is to ask whether
    # anything actually bundled so far REFERENCES one of those names, and
    # bundle only that submodule, by reading the package's OWN map rather
    # than a second copy of it kept here (the #1136 lesson).
    #
    # TO A FIXED POINT, not one pass (counter-model review). A submodule
    # pulled in by ONE lazy package's map can itself reference a SECOND lazy
    # package - `lib/pkg_a/submodule_a.py` doing `from lib.pkg_b import
    # thing_b` - and that second package's own `__init__.py` only entered
    # `out` partway through this function, after `all_texts` had already been
    # captured. A single pass reads the snapshot from before that arrival and
    # never re-reads it, so `thing_b`'s submodule is silently dropped. Looping
    # until a whole pass adds nothing new closes multi-hop chains of any
    # depth, because each iteration recomputes `lazy_packages` and `all_texts`
    # against the CURRENT `out`, including whatever the previous iteration's
    # `drain()` just pulled in.
    while True:
        before = len(out)
        lazy_packages = [
            child.parent for child in out.values()
            if child.name == "__init__.py" and _lazy_getattr_map(child.read_text())
        ]
        if not lazy_packages:
            break
        entry_texts = [
            (SCRIPTS_ROOT / n).read_text()
            for n in scripts
            if (SCRIPTS_ROOT / n).suffix == ".py"
        ]
        all_texts = entry_texts + [child.read_text() for child in out.values()]
        for package_dir in lazy_packages:
            init_path = package_dir / "__init__.py"
            mapping = _lazy_getattr_map(init_path.read_text())
            if mapping is None:
                continue
            package_dotted = ".".join(package_dir.relative_to(REPO_ROOT).parts)
            referenced: set[str] = set()
            for text in all_texts:
                referenced |= _referenced_lazy_names(text, package_dotted)
            for name in referenced:
                # The map first - that is what `__getattr__` actually
                # resolves against. A name ABSENT from the map but matching a
                # real submodule is `from lib.cicd import evidence`'s shape:
                # Python imports that as a submodule directly, bypassing
                # `__getattr__` entirely (and `evidence` is deliberately not
                # one of the map's keys), so the map alone would under-bundle it.
                submodule = mapping.get(name, name)
                candidate = package_dir / f"{submodule}.py"
                subpackage = package_dir / submodule / "__init__.py"
                for resolved in (candidate, subpackage):
                    if not resolved.is_file():
                        continue
                    rel_child = resolved.relative_to(REPO_ROOT)
                    if str(rel_child) in out:
                        continue
                    out[str(rel_child)] = resolved
                    pending.append((str(rel_child), resolved))
        # The lazy submodules just added may carry their OWN relative or
        # absolute imports (same shape as any other package module) - drain
        # them through the identical worklist logic rather than a second
        # copy. This is what can introduce a brand new lazy `__init__.py`
        # the next iteration's `lazy_packages` scan needs to see.
        drain()
        if len(out) == before:
            break
    return out


# Only SOURCE-RELATIVE markdown links (`](../../../docs/x.md)`) are in scope: those
# resolve against the command's location in this checkout and therefore resolve to
# nothing once the skill is installed elsewhere. A bare `docs/x.md` mentioned in
# prose is not a link, was never resolvable from a skill dir, and is left alone
# rather than silently given a new meaning.
_DOC_REF = re.compile(r"\]\((?:\.\./)+docs/((?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+\.md)\)")
_MD_LINK = re.compile(r"\]\(([A-Za-z0-9._-]+\.md)\)")


def find_bundled_docs(body: str) -> list[str]:
    """Docs-relative paths the body links, plus the docs THOSE docs link.

    The bundler discovers `scripts/<name>` references but not documentation, so
    a command routing to `../../../docs/agents/issue-contract.md` published a
    link that resolves to `<install-parent>/docs/...` once the skill is
    installed anywhere but this checkout - i.e. to nothing (#861).

    Sibling links BETWEEN bundled docs are followed so a bundled document's own
    references resolve too (issue-contract.md -> knowledge-lifecycle.md). That
    expansion is a closure over already-bundled files, not a crawl of docs/: it
    starts from what the command body actually names and stops when no new file
    is reached.
    """
    pending = [
        rel for rel in {m.group(1) for m in _DOC_REF.finditer(body)}
        if (DOCS_ROOT / rel).is_file()
    ]
    found: set[str] = set()
    while pending:
        rel = pending.pop()
        if rel in found:
            continue
        found.add(rel)
        parent = Path(rel).parent
        for match in _MD_LINK.finditer((DOCS_ROOT / rel).read_text()):
            sibling = (parent / match.group(1)).as_posix()
            if sibling not in found and (DOCS_ROOT / sibling).is_file():
                pending.append(sibling)
    return sorted(found)


def rewrite_doc_refs(body: str) -> str:
    """Point source-relative docs links at the copy bundled with the skill.

    Only references that actually resolve in this checkout are rewritten, so a
    typo stays visible rather than being silently repointed at a missing file.
    """
    def sub(match: re.Match[str]) -> str:
        rel = match.group(1)
        return f"](docs/{rel})" if (DOCS_ROOT / rel).is_file() else match.group(0)

    return _DOC_REF.sub(sub, body)


def generated_names(selected: list[str]) -> dict[tuple[str, str], str]:
    """Map (family, stem) -> skill dir name for every command being generated."""
    names: dict[tuple[str, str], str] = {}
    for family in selected:
        src_dir = SOURCE_ROOT / family
        if not src_dir.is_dir():
            raise FileNotFoundError(f"source dir not found: {src_dir}")
        for f in sorted(src_dir.glob("*.md")):
            if f.name in EXCLUDE.get(family, set()):
                continue
            names[(family, f.stem)] = f"{family}-{f.stem}"
    return names


_SLASH_REF = re.compile(r"/([a-z][a-z0-9-]*):([a-z][a-z0-9-]*)")


def rewrite_slash_refs(body: str, names: dict[tuple[str, str], str]) -> str:
    """Rewrite /family:cmd -> /family-cmd, only for refs that resolve to a
    generated skill; unknown targets (e.g. /codex:auto, /cpp:init) are left
    untouched so the adaptations block covers them."""

    def repl(match: re.Match[str]) -> str:
        family, stem = match.group(1), match.group(2)
        if (family, stem) in names:
            return f"/{family}-{stem}"
        return match.group(0)

    return _SLASH_REF.sub(repl, body)


MANIFEST_NAME = "SHA256SUMS"

#: WHAT THIS DOES NOT PROVE, stated where it is generated rather than only where
#: it is consumed (issue #1185). This manifest TRAVELS INSIDE THE BUNDLE IT
#: CERTIFIES. Anyone able to rewrite a bundled script is equally able to rewrite
#: this file, so it establishes only that the scripts in this bundle are the
#: bytes recorded WHEN THE BUNDLE WAS GENERATED. It detects accidental
#: corruption, a partial edit that missed the manifest, and modification after
#: generation. It does NOT detect a coherently regenerated bundle, and it says
#: NOTHING ABOUT ARRIVAL - a bundle that was already tampered with before it
#: reached the host carries a manifest that agrees with it perfectly. Covering
#: arrival needs a signature checked against a key that is NOT in the bundle,
#: which is a different problem and deliberately not this one.
MANIFEST_HEADER = (
    "# GENERATED by claude-power-pack - scripts/codex-skill-sync.py. Do not edit.\n"
    "# sha256 of every script bundled into this skill, recorded at generation.\n"
    "#\n"
    "# SCOPE, because a digest list invites being read as more than it is: this\n"
    "# file ships INSIDE the bundle it certifies, so it proves only that these\n"
    "# scripts are the bytes recorded when the bundle was built. It detects\n"
    "# corruption, a partial edit, and post-build modification. It does NOT\n"
    "# detect a coherently regenerated bundle and says NOTHING about arrival.\n"
    "# Verifying arrival needs a key that is not in this bundle.\n"
)


def scripts_manifest(files: dict[str, str]) -> str | None:
    """`sha256sum -c`-compatible manifest of one bundle's `scripts/` entries.

    Scoped to `scripts/` and nothing else because that directory is exactly what
    `flow-helpers-install.sh` reads as its SOURCE_DIR on a Codex host. Widening
    it to `lib/` and `docs/` would record digests nothing checks, which is the
    decoration this is meant not to be.

    Returns None when the bundle has no scripts, so a skill that bundles none
    carries no empty manifest - an empty manifest and a missing one would
    otherwise look alike to the installer, and they mean different things.
    """
    # NEVER LIST ITSELF, whatever the caller passes (counter-model review,
    # codex, LOW). generate_skill calls this BEFORE adding the manifest, so
    # production was correct - but a caller handing back a dict that already
    # contains one got a self-row, which silently made a test that recomputed
    # the manifest pass without any mutation at all. Correctness that depends
    # on the caller's call order is not correctness.
    names = sorted(
        rel.split("/", 1)[1]
        for rel in files
        if rel.startswith("scripts/")
        and "/" not in rel.split("/", 1)[1]
        and rel.split("/", 1)[1] != MANIFEST_NAME
    )
    if not names:
        return None
    lines = [MANIFEST_HEADER]
    for name in names:
        digest = hashlib.sha256(files[f"scripts/{name}"].encode("utf-8")).hexdigest()
        # Two spaces: the separator GNU coreutils writes and `-c` expects.
        lines.append(f"{digest}  {name}\n")
    return "".join(lines)


#: NEGATIVE-CONTROL: controls/codex-skill-sync-provenance
PROVENANCE_NAME = "PROVENANCE.md"

#: WHY NOT STAMP EACH FILE, AND WHY NOT WIDEN THE MANIFEST (issue #1408 bullet
#: 1, Nit Store #864 comment 5685525565). `SKILL.md` and `reference.md` already
#: name their canonical source from inside themselves (`marker_for`), because
#: the generator REWRITES both (slash refs, doc links, the absolute-path remap)
#: - an in-file stamp costs them nothing they were not already paying.
#: `scripts/`, `lib/` and bundled `docs/`/data files are different: every test
#: pinning them (`test_real_repo_bundled_scripts_byte_identical`,
#: `test_real_repo_bundled_libraries_byte_identical`) exists because a Codex
#: session runs them as the SAME bytes the checkout runs, so a stamp inside one
#: would make it a different file than its source - the opposite of what makes
#: it trustworthy. `scripts_manifest` above also will not carry this duty: it
#: is SCOPED to `scripts/` because `flow-helpers-install.sh` reads it as a
#: verification input, and recording digests nothing checks is "the decoration
#: this is meant not to be" by that function's own docstring.
#:
#: So this is the NEAREST HONEST alternative, not the same claim relocated: a
#: file naming every OTHER bundled path, each of which already EQUALS its own
#: checkout-relative source path (scripts/<name>, lib/<pkg>/<mod>.py,
#: docs/<rel> all preserve the repo-relative path on both sides - measured
#: across the real bundle set, never flattened except `scripts/`, which is
#: flattened to the SAME name). It gives a sign from beside the file rather
#: than from inside it, and says so, rather than pretending otherwise.
PROVENANCE_HEADER = (
    "<!-- GENERATED by claude-power-pack - scripts/codex-skill-sync.py;"
    " do not edit. -->\n"
    "\n"
    "# Mirror provenance\n"
    "\n"
    "Every file below is a byte-identical copy of its canonical source in the"
    " claude-power-pack checkout, at the SAME path shown here relative to the"
    " repository root - editing a copy here has no effect once the mirror is"
    " regenerated, and the next `make codex-skills` overwrites it silently."
    " Edit the canonical source and run `make codex-skills`.\n"
    "\n"
)


def provenance_note(files: dict[str, str]) -> str | None:
    """List every bundled path that cannot carry its own in-file stamp.

    Excludes `SKILL.md`/`reference.md` (already self-naming via `marker_for`),
    `scripts/<MANIFEST_NAME>` (itself generated, not a copy of anything), and
    this note's own name - never listing itself, for the same reason
    `scripts_manifest` does not (counter-model review, #1185).

    Returns None when nothing qualifies, so a skill bundling no code, docs or
    data carries no empty note - mirroring `scripts_manifest`'s reason: an
    empty note and a missing one would look alike without meaning the same
    thing.
    """
    named = sorted(
        rel for rel in files
        if rel not in ("SKILL.md", "reference.md", f"scripts/{MANIFEST_NAME}", PROVENANCE_NAME)
    )
    if not named:
        return None
    lines = [PROVENANCE_HEADER]
    lines += [f"- `{rel}`\n" for rel in named]
    return "".join(lines)


def generate_skill(
    source_file: Path, family: str, names: dict[tuple[str, str], str]
) -> dict[str, str]:
    """Map of skill-dir-relative path -> content for one command."""
    meta, body = parse_frontmatter(source_file.read_text())
    body = rewrite_slash_refs(body, names).rstrip("\n") + "\n"
    # Rewrite the absolute convenience-install path BEFORE find_bundled_scripts
    # runs: a rewritten `~/.claude/scripts/<name>` becomes a plain
    # `scripts/<name>` reference, which is the ONLY shape that detector reads -
    # one bundling path, not two.
    body, unremapped_scripts = rewrite_absolute_script_refs(body)
    # Rewrite doc links BEFORE deriving the description: the description is cut
    # from the opening paragraphs, so a later rewrite leaves the broken
    # source-relative path advertised in the skill's own frontmatter.
    docs = find_bundled_docs(body)
    if docs:
        body = rewrite_doc_refs(body)
    name = f"{family}-{source_file.stem}"
    description = derive_description(meta, body, skill_name=name)
    marker = marker_for(family, source_file.name)
    bullets = detect_adaptations(body)
    scripts = find_bundled_scripts(body)
    if scripts:
        bullets.append(BUNDLED_SCRIPTS_BULLET)
    if docs:
        bullets.append(BUNDLED_DOCS_BULLET)
    if unremapped_scripts:
        bullets.append(unremapped_script_bullet(unremapped_scripts))
    # Every bundled code file, gathered before the bullets are rendered because
    # the network bullet is decided by what the helpers DO (issue #1357).
    bundled: dict[str, str] = {
        f"scripts/{script}": (SCRIPTS_ROOT / script).read_text() for script in scripts
    }
    for rel, source in find_bundled_libs(scripts).items():
        bundled[rel] = source.read_text()
    for rel, source in find_bundled_shell_libs(scripts).items():
        bundled[rel] = source.read_text()
    if calls_network(bundled):
        bullets.append(NETWORK_BULLET)

    parts: list[str] = [
        "---",
        f"name: {json.dumps(name, ensure_ascii=False)}",
        f"description: {json.dumps(description, ensure_ascii=False)}",
        "---",
        marker,
        "",
    ]
    if bullets:
        parts += [
            "## Codex harness adaptations",
            "",
            "Generated from a Claude Code command. Where the procedure"
            " references these Claude-only surfaces, adapt as follows:",
            "",
        ]
        parts += [f"- {bullet}" for bullet in bullets]
        parts.append("")

    files: dict[str, str] = {}
    if body.count("\n") <= INLINE_MAX_LINES:
        parts.append(body.rstrip("\n"))
        files["SKILL.md"] = "\n".join(parts) + "\n"
    else:
        title = derive_title(body) or name
        summary = description
        if title and summary.startswith(title):
            summary = summary[len(title):].lstrip(" -") or description
        parts += [
            f"# {title}",
            "",
            summary,
            "",
            "## Full procedure",
            "",
            "Read `reference.md` in this skill directory for the complete,"
            " authoritative procedure before acting on this skill.",
        ]
        files["SKILL.md"] = "\n".join(parts) + "\n"
        files["reference.md"] = f"{marker}\n\n{body.rstrip(chr(10))}\n"
    # Libs are bundled at their repo-relative path, which is what makes the
    # scripts' own `parents[1]` resolution land inside the skill directory.
    files.update(bundled)
    for rel, source in find_bundled_data(scripts).items():
        files[rel] = source.read_text()
    for doc in docs:
        # Bundled verbatim, at the same relative path, so sibling links between
        # bundled docs keep resolving without rewriting their contents.
        files[f"docs/{doc}"] = (DOCS_ROOT / doc).read_text()
    manifest = scripts_manifest(files)
    if manifest is not None:
        files[f"scripts/{MANIFEST_NAME}"] = manifest
    note = provenance_note(files)
    if note is not None:
        files[PROVENANCE_NAME] = note
    return files


def expected_outputs(selected: list[str]) -> dict[str, dict[str, str]]:
    """Map skill dir name -> {relative path -> content} for selected families.

    The rewrite map always spans ALL families so cross-family refs resolve
    identically no matter which subset is being synced.
    """
    all_names = generated_names(FAMILIES)
    outputs: dict[str, dict[str, str]] = {}
    for family in selected:
        src_dir = SOURCE_ROOT / family
        for f in sorted(src_dir.glob("*.md")):
            if f.name in EXCLUDE.get(family, set()):
                continue
            outputs[f"{family}-{f.stem}"] = generate_skill(f, family, all_names)
    return outputs


def is_managed(skill_dir: Path) -> bool:
    """A skill dir is managed when its SKILL.md carries the GENERATED marker
    as the first content line after the frontmatter block."""
    try:
        content = (skill_dir / "SKILL.md").read_text()
    except OSError:
        return False
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            content = content[end + len("\n---"):]
    for line in content.splitlines():
        if line.strip():
            return line.startswith(MARKER_PREFIX)
    return False


#: Interpreter output, not skill content. Bundling real Python PACKAGES (#1028)
#: made this necessary: running a bundled script anywhere - a Codex session, a
#: developer trying the drift check, this repository's own tests - writes
#: `__pycache__/*.pyc` beside the module, inside the bundle. Without this the
#: next `--check` reports each one `STALE: ... (no longer generated)` and CI
#: goes red over a file no commit created and the generator never wrote. Before
#: #1028 no bundled file was ever imported, so the case could not arise.
_GENERATED_BYTECODE = ("__pycache__",)


def skill_files(skill_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in skill_dir.rglob("*")
        if p.is_file() and not any(part in _GENERATED_BYTECODE for part in p.parts)
    )


def find_orphans(outputs: dict[str, dict[str, str]], selected: list[str]) -> list[Path]:
    """Marker-bearing skill dirs under codex/skills/ with no matching source.

    Only families in `selected` are considered so a partial-family run never
    misreads other families' outputs as orphans.
    """
    if not OUTPUT_ROOT.is_dir():
        return []
    prefixes = tuple(f"{family}-" for family in selected)
    orphans = []
    for d in sorted(OUTPUT_ROOT.iterdir()):
        if not d.is_dir() or d.name in outputs or not d.name.startswith(prefixes):
            continue
        if is_managed(d):
            orphans.append(d)
    return orphans


def completeness_errors() -> list[str]:
    """Discovery-completeness gate (#582): every source under .claude/commands/
    must map to a generated family or an explicit exclusion. Discovery globs
    only .claude/commands/<family>/*.md, so a file outside every family is not
    excluded by drift - it is invisible to it; this is the check that sees it."""
    errors: list[str] = []
    for f in sorted(SOURCE_ROOT.glob("*.md")):
        if f.name not in TOP_LEVEL_EXCLUDE:
            errors.append(
                f"UNPACKAGED top-level command: .claude/commands/{f.name}"
                " (move it into a family dir, or list it in TOP_LEVEL_EXCLUDE)"
            )
    for d in sorted(p for p in SOURCE_ROOT.iterdir() if p.is_dir()):
        if d.name not in FAMILIES and d.name not in UNPACKAGED_FAMILIES:
            errors.append(
                f"UNPACKAGED family: .claude/commands/{d.name}/"
                " (add it to FAMILIES, or list it in UNPACKAGED_FAMILIES)"
            )
    return errors


def run_check(selected: list[str]) -> int:
    outputs = expected_outputs(selected)
    drift = 0
    for error in completeness_errors():
        print(error)
        drift = 1
    for skill, files in outputs.items():
        skill_dir = OUTPUT_ROOT / skill
        for rel, content in files.items():
            dest = skill_dir / rel
            if not dest.is_file():
                print(f"MISSING: codex/skills/{skill}/{rel}")
                drift = 1
            elif dest.read_text() != content:
                print(f"DRIFT: codex/skills/{skill}/{rel} differs from generated source")
                drift = 1
        if skill_dir.is_dir() and is_managed(skill_dir):
            for actual in skill_files(skill_dir):
                rel = actual.relative_to(skill_dir).as_posix()
                if rel not in files:
                    print(f"STALE: codex/skills/{skill}/{rel} (no longer generated)")
                    drift = 1
    for orphan in find_orphans(outputs, selected):
        print(f"ORPHAN skill: codex/skills/{orphan.name} (no matching source command)")
        drift = 1
    if drift:
        print(
            "\ncodex-skill-sync: DRIFT detected. Edit the SOURCE"
            " (.claude/commands/<family>/), then run:"
            " scripts/codex-skill-sync.py --write",
            file=sys.stderr,
        )
        return 1
    # NAME THE COMPARED TREES, and name the one this did NOT look at (issue
    # #1029, specimen 4). "N skill(s) in sync" is the line a session reaches for
    # when it wants to know whether its INSTALLED skills are current, and it
    # answers a different question: both sides of this comparison live inside
    # the checkout, so it is a GENERATION-parity check. `--check` is the DEFAULT
    # mode, which is exactly why the wrong reading is the easy one.
    #
    # The failure was measured, twice, four days apart on two hosts: in the same
    # session this printed its green, `install-drift.sh` reported `65 current, 10
    # stale`, and the staleness was real - the installed
    # `flow-check/scripts/flow-finish-gate.sh` still carried pre-#939 wording.
    # `SKILL.md` was byte-identical in all ten, so the whole drift lived in the
    # bundled payload scripts - the part this comparison structurally cannot see.
    #
    # No negative control is owed for a string change. The pairing test is that
    # these two instruments' success lines can no longer be read as answering the
    # same question, and tests/test_codex_skill_sync.py pins it.
    print(
        f"codex-skill-sync: {len(outputs)} skill(s) in sync"
        f" ({SOURCE_ROOT.name}/<family>/ -> {OUTPUT_ROOT.parent.name}/{OUTPUT_ROOT.name}/,"
        f" both IN-CHECKOUT; families: {', '.join(selected)})"
    )
    print(
        "codex-skill-sync: this says NOTHING about the installed copies under"
        f" {install_dest_root()} - run install-drift.sh for those"
    )
    return 0


def run_write(selected: list[str]) -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    outputs = expected_outputs(selected)
    written = 0
    pruned = 0
    for skill, files in outputs.items():
        skill_dir = OUTPUT_ROOT / skill
        for rel, content in files.items():
            dest = skill_dir / rel
            if not dest.is_file() or dest.read_text() != content:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content)
                # The manifest is GENERATED, not copied, so it has no
                # repo-side source to take a mode from - and it is data, not an
                # executable. Copying its mode raised FileNotFoundError and
                # aborted the whole write part-way through (issue #1185).
                if rel.startswith("scripts/") and Path(rel).name != MANIFEST_NAME:
                    shutil.copymode(SCRIPTS_ROOT / Path(rel).name, dest)
                written += 1
        if is_managed(skill_dir):
            for actual in skill_files(skill_dir):
                rel = actual.relative_to(skill_dir).as_posix()
                if rel not in files:
                    actual.unlink()
                    print(f"codex-skill-sync: pruned stale {skill}/{rel}")
                    pruned += 1
            for sub in sorted(skill_dir.rglob("*"), reverse=True):
                if sub.is_dir() and not any(sub.iterdir()):
                    sub.rmdir()
    removed = 0
    for orphan in find_orphans(outputs, selected):
        shutil.rmtree(orphan)
        print(f"codex-skill-sync: removed orphan skill {orphan.name}")
        removed += 1
    # Same boundary as run_check's line above (#1029): --write regenerates the
    # IN-CHECKOUT mirror and touches no install tree, so "current" here must not
    # be readable as a statement about the host.
    print(
        f"codex-skill-sync: {len(outputs)} skill(s) current in"
        f" {OUTPUT_ROOT.parent.name}/{OUTPUT_ROOT.name}/"
        f" ({written} file(s) written, {pruned} stale file(s) pruned,"
        f" {removed} orphan(s) removed)"
    )
    print(
        "codex-skill-sync: the installed copies under"
        f" {install_dest_root()} are UNCHANGED - run --install to update those"
    )
    return 0


def _repo_relative(raw: str) -> str | None:
    """A caller's path as the generator spells it, or None if it is not one.

    RESOLVED, never string-trimmed (counter-model review). A lexical prefix
    strip called `scripts/../scripts/gh-pr-merge.sh` unbundled while the plain
    spelling of the same file enumerated fine, and an absolute alias failed the
    same way. Resolution also answers CONTAINMENT: a path outside the repository
    is not a source here at all, and saying so is the honest answer rather than
    searching for it and finding nothing.
    """
    try:
        candidate = Path(raw)
        resolved = (candidate if candidate.is_absolute() else REPO_ROOT / candidate).resolve()
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return None


def mirrors_for(sources: list[str], selected: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """`(source -> its mirror paths, sources that feed no mirror)`.

    TWO RULES, BOTH DERIVED FROM `expected_outputs` rather than from a path
    table. A table would be a second population to keep in step with the
    generator - the defect this repository has already paid for twice in the
    neighbouring re-sync trigger (#1136).

      - A COMMAND DOCUMENT maps to its whole skill: it generates `SKILL.md` and
        `reference.md`, and it is what pulls in everything else the skill
        bundles.
      - ANY OTHER bundled file maps to THE SAME relative path under every skill
        that bundles it. Measured across all 271 mirror files: the generator
        preserves the repo-relative path for `docs/`, `lib/` and `.claude/`
        sources, and `scripts/<name>` is already `scripts/<name>` on both sides,
        so one rule covers every shape rather than four.
    """
    outputs = expected_outputs(selected)
    found: dict[str, list[str]] = {}
    unknown: list[str] = []

    for raw in sources:
        source = _repo_relative(raw)

        #: A SOURCE IS A FILE THAT EXISTS IN THE REPOSITORY, and checking that
        #: first is what stops the generator's OWN OUTPUT being accepted as
        #: input (counter-model review). `SKILL.md`, `reference.md` and
        #: `scripts/<MANIFEST_NAME>` are synthesised names that appear as keys in
        #: every skill's outputs, so a bare name-match answered
        #: `--list-mirrors SKILL.md` with 74 paths and exit 0 - a confident
        #: answer to a question nobody can ask, which is this issue's own defect
        #: wearing the other hat. None of the three exists as a repository file,
        #: so existence separates them without a list of synthesised names to
        #: keep in step.
        if source is None or not (REPO_ROOT / source).is_file():
            unknown.append(raw)
            continue

        hits: list[str] = []

        parts = source.split("/")
        if (
            len(parts) == 4
            and parts[0] == ".claude"
            and parts[1] == "commands"
            #: THE FAMILY IS VALIDATED, not just the concatenation. `<family>` and
            #: `<stem>` are joined by a hyphen to name the skill, which loses the
            #: boundary: the nonexistent `.claude/commands/second/opinion-help.md`
            #: composes to `second-opinion-help`, a REAL skill generated from
            #: `.claude/commands/second-opinion/help.md`. Checking only the
            #: composed name handed an unknown source a neighbour's mirrors and
            #: called it success.
            and parts[2] in FAMILIES
            and source.endswith(".md")
        ):
            skill = f"{parts[2]}-{parts[3][: -len('.md')]}"
            if skill in outputs:
                hits = [f"codex/skills/{skill}/{rel}" for rel in sorted(outputs[skill])]

        if not hits:
            #: THE MANIFEST TRAVELS WITH THE SCRIPT. A skill that bundles any
            #: script also carries `scripts/<MANIFEST_NAME>` over those scripts,
            #: so changing one bundled script changes TWO files in that skill.
            #: Measured on this change itself: editing `codex-skill-sync.py`
            #: drifted 2 script copies AND their 2 manifests - and the manifests
            #: are exactly the paths that showed up as unexplained lane-check
            #: extras twice on 2026-09-23.
            #:
            #: It is derived, not listed: the manifest is emitted only for
            #: skills whose outputs actually contain it, so a generator that
            #: stops writing one, or renames it, cannot leave this naming a path
            #: that no longer exists.
            found_in = [
                skill for skill, files in outputs.items() if source in files
            ]
            hits = sorted(
                f"codex/skills/{skill}/{source}" for skill in found_in
            )
            if source.startswith("scripts/"):
                hits += sorted(
                    f"codex/skills/{skill}/scripts/{MANIFEST_NAME}"
                    for skill in found_in
                    if f"scripts/{MANIFEST_NAME}" in outputs[skill]
                )
                hits = sorted(hits)

        if hits:
            found[source] = hits
        else:
            unknown.append(source)

    return found, unknown


def run_list_mirrors(sources: list[str], selected: list[str]) -> int:
    """Print the mirror set WITHOUT touching the tree (issue #1151).

    `--check` answers "are the mirrors in sync". It was being read for "what IS
    the mirror set", which is the question a lane declaration asks - and those
    agree only on a DIRTY tree. On a clean one `--check` names nothing, and the
    only way to learn the set was `--write`, which answers by changing the tree.

    THIS IS THE LANE QUESTION, NOT THE DRIFT QUESTION, and the two are not the
    same set. For a bundled SCRIPT they coincide - the script and its manifest
    are exactly what goes stale - which is why they are easy to confuse. For a
    COMMAND DOCUMENT they diverge sharply: the document produces its whole skill,
    so editing one puts every file of that skill in the lane while only the
    generated `SKILL.md` / `reference.md` actually drift. Measured: editing
    `flow/auto.md` and `flow/finish.md` listed 50 paths and drifted 2.

    So DO NOT use this to decide whether a re-sync is needed. `--check` answers
    that, in 0.14s, by comparing the generated output against the tree; this
    answers what a lane must DECLARE. Building a re-sync trigger on an enumerated
    path set would also be the hazard #1136 removed - "a hardcoded universe
    again, one entry longer" - but it would be wrong on its own terms first.
    """
    outputs = expected_outputs(selected)

    if not sources:
        for skill in sorted(outputs):
            for rel in sorted(outputs[skill]):
                print(f"codex/skills/{skill}/{rel}")
        return 0

    found, unknown = mirrors_for(sources, selected)
    #: A UNION, not a concatenation (counter-model review). Passing one source
    #: twice printed it twice, and two scripts sharing a skill repeated that
    #: skill's manifest - so the output was not a mirror SET, which is what a
    #: caller declaring a lane needs.
    for mirror in sorted({m for mirrors in found.values() for m in mirrors}):
        print(mirror)

    for source in dict.fromkeys(unknown):
        #: NAMED, AND NON-ZERO. A tool built to answer "what IS the mirror set"
        #: that returned SILENCE for a source it does not know would reproduce
        #: the exact defect it exists to remove - the caller cannot tell "this
        #: feeds nothing" from "I did not understand your path".
        print(
            f"NOT BUNDLED: {source} feeds no Codex skill mirror", file=sys.stderr
        )
    if unknown:
        print(
            "codex-skill-sync: a BUNDLED source always has at least one mirror, so zero"
            " lines above means the path is not bundled - never a bundled source with an"
            " empty mirror set, which cannot occur.",
            file=sys.stderr,
        )
        return 1
    return 0


def install_dest_root() -> Path:
    return Path.home() / ".codex" / "skills"


#: The environment names a destination this script must never write to. It names
#: a PATH, never a mode: a boolean "we are testing" would disable the one mode
#: this script exists to perform for anyone who ever exported it, while a path
#: can only ever block the single destination it names.
REFUSE_INSTALL_DEST_ENV = "CPP_REFUSE_INSTALL_DEST"


def refuse_forbidden_install_dest(dest_root: Path) -> None:
    """Refuse an install into a destination the environment declared off limits.

    THE DEFECT THIS EXISTS FOR (issue #1232). `run_install()` writes outside the
    repository, and its prune half deletes every managed skill the SOURCE no
    longer carries. Handed a two-entry test fixture as its source it is not
    misbehaving - it is correctly pruning the 72 skills the fixture does not
    contain. One test in `tests/test_codex_skill_sync.py` reached this function
    without the `tmp_home` fixture and did exactly that to the developer's own
    `~/.codex/skills`, on every `make test` and every `make verify`, in every
    checkout, while PASSING - nothing it asserted had anything to do with the
    host.

    REFUSED AT THE WRITE, NOT AT `install_dest_root()`. Three tests resolve that
    function read-only to assert which tree a success line names; refusing to
    RESOLVE the path would break them, and a guard that breaks correct callers
    is one the next person routes around.

    IT RAISES RATHER THAN RETURNING A CODE, and that is the whole of its
    reliability. `main(["--install"])`'s return value is discarded at several
    existing call sites, so a guard reporting by exit code would be ignored by
    exactly the kind of test that needs stopping.

    WHAT IT DOES NOT COVER, stated so its silence is not read as coverage: it
    protects this one install destination. It says nothing about any other write
    under the real `$HOME`, by this script or by any other test.
    """
    forbidden = os.environ.get(REFUSE_INSTALL_DEST_ENV)
    if not forbidden:
        return
    try:
        same = dest_root.expanduser().resolve() == Path(forbidden).expanduser().resolve()
    except OSError:
        # A path that cannot be resolved is compared as written rather than
        # silently treated as "not the forbidden one".
        same = str(dest_root) == forbidden
    if not same:
        return
    raise RuntimeError(
        f"codex-skill-sync: REFUSING to install into {dest_root} - "
        f"{REFUSE_INSTALL_DEST_ENV} names it as off limits.\n"
        "  That is the host's real Codex skill directory. Installing a test "
        "fixture over it deletes every skill the fixture does not carry, which "
        "is what issue #1232 measured: 74 skills to 2, from one passing test.\n"
        "  A test that needs --install must redirect the destination first - "
        "request the `tmp_home` fixture in tests/test_codex_skill_sync.py."
    )


def find_installed_orphans(dest_root: Path, source_names: set[str]) -> list[Path]:
    """MANAGED skill dirs at the install destination with no source dir left.

    `copytree(dirs_exist_ok=True)` only ever adds or overwrites, so a skill
    removed from `codex/skills/` used to linger in ~/.codex/skills forever -
    Codex kept loading a skill CPP no longer ships (issue #575). Ownership is
    decided by the GENERATED marker, never by a name list: a hand-curated skill
    dir, a skill the user wrote themselves, and dotted runtime state such as
    `.system` all lack the marker and are never touched.
    """
    if not dest_root.is_dir():
        return []
    orphans = []
    for d in sorted(dest_root.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in source_names:
            continue
        if is_managed(d):
            orphans.append(d)
    return orphans


def run_install() -> int:
    if not OUTPUT_ROOT.is_dir():
        print(f"codex-skill-sync: nothing to install ({OUTPUT_ROOT} missing)", file=sys.stderr)
        return 2
    dest_root = install_dest_root()
    # BEFORE the mkdir, so a refused install leaves no trace of itself either.
    refuse_forbidden_install_dest(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    staging = install_staging_root(dest_root)
    source_names = set()
    count = 0
    removed = 0
    #: skill name -> why it could not be published atomically
    non_atomic: dict[str, str] = {}
    #: orphan name -> why it was deleted in place rather than renamed out
    removed_in_place: dict[str, str] = {}
    #: Held for the WHOLE install, stale cleanup included (counter-model review,
    #: #1235): every installer shares one staging dir, so without it a second
    #: install would read a live run's scratch as a crashed run's and delete it.
    with _install_lock(dest_root):
        # Under the lock no live installer owns this, so what is here is a
        # leftover from a run that died mid-install. It sits OUTSIDE dest_root,
        # so Codex never saw it.
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        #: A cheap first answer to "can staging rename into dest_root". Equal
        #: devices are NOT proof (a same-filesystem bind mount still refuses
        #: with EXDEV), so every rename below also handles EXDEV itself.
        can_rename = staging.stat().st_dev == dest_root.stat().st_dev
        try:
            for d in sorted(OUTPUT_ROOT.iterdir()):
                if not d.is_dir() or not (d / "SKILL.md").is_file():
                    continue
                why = _install_one(d, dest_root / d.name, staging, can_rename)
                if why:
                    non_atomic[d.name] = why
                source_names.add(d.name)
                count += 1
            for orphan in find_installed_orphans(dest_root, source_names):
                # One rename takes it out of the listing; the slow rmtree then
                # runs where no reader looks. A reader that listed it BEFORE the
                # rename still finds it gone - inherent to removing a skill, and
                # not something any swap of this tree can hide from a reader
                # that re-resolves the path (#1235).
                gone = staging / f"orphan-{orphan.name}"
                if can_rename and _try_rename(orphan, gone):
                    shutil.rmtree(gone)
                else:
                    shutil.rmtree(orphan)
                    removed_in_place[orphan.name] = _WHY_EXDEV if can_rename else _WHY_DEVICE
                print(f"codex-skill-sync: removed orphaned installed skill {orphan.name}")
                removed += 1
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    # The one mode that DOES touch the host, and it says so by naming both ends
    # (#1029): this is the only line here whose subject is the install tree.
    print(
        f"codex-skill-sync: installed {count} skill(s)"
        f" from {OUTPUT_ROOT.parent.name}/{OUTPUT_ROOT.name}/ -> {dest_root}"
        f" ({removed} orphan(s) removed)"
    )
    #: The degraded paths are REPORTED, never silent (#1235): a reader can see a
    #: half-written skill during these, which is the exact symptom this replaced.
    if non_atomic:
        reasons = "; ".join(sorted(set(non_atomic.values())))
        names = ", ".join(sorted(non_atomic)[:5]) + (", ..." if len(non_atomic) > 5 else "")
        print(
            f"codex-skill-sync: NOTE {len(non_atomic)} skill(s) written NON-atomically"
            f" ({reasons}): {names}; a concurrent Codex start may warn about a missing"
            " or partial SKILL.md"
        )
    #: Reported separately (counter-model review): an orphan-only install must
    #: not borrow its warning from an unrelated skill write.
    if removed_in_place:
        reasons = "; ".join(sorted(set(removed_in_place.values())))
        print(
            f"codex-skill-sync: NOTE {len(removed_in_place)} orphan(s) deleted IN PLACE"
            f" ({reasons}): {', '.join(sorted(removed_in_place))}; a concurrent Codex"
            " start may list one mid-delete"
        )
    return 0


def install_staging_root(dest_root: Path) -> Path:
    """Scratch space for building replacement skill dirs (#1235).

    A SIBLING of the destination, not a child: Codex enumerates dest_root, so
    anything staged inside it - dotted or not - is something a reader may list.
    """
    return dest_root.parent / ".cpp-skill-staging"


def install_lock_path(dest_root: Path) -> Path:
    return dest_root.parent / ".cpp-skill-install.lock"


@contextlib.contextmanager
def _install_lock(dest_root: Path) -> Iterator[None]:
    """Serialize installers into one destination (blocks until free)."""
    try:
        import fcntl
    except ImportError:  # no flock on this platform: unserialized, as before #1235
        yield
        return
    with open(install_lock_path(dest_root), "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _try_rename(src: Path, dst: Path) -> bool:
    """os.rename, but False (not an exception) when it would cross a mount."""
    try:
        os.rename(src, dst)
    except OSError as exc:
        if exc.errno == errno.EXDEV:
            return False
        raise
    return True


_AT_FDCWD = -100
_RENAME_EXCHANGE = 2
#: errnos meaning "this kernel/filesystem cannot exchange", as opposed to a real
#: failure (permissions, a vanished path), which must still raise.
_EXCHANGE_UNSUPPORTED = {errno.EINVAL, errno.ENOSYS, errno.EXDEV, errno.EOPNOTSUPP, errno.ENOTSUP}


def _renameat2_exchange(a: Path, b: Path) -> int | None:
    """Call renameat2(a, b, RENAME_EXCHANGE). 0 on success, the errno on
    failure, None when this platform/libc has no binding at all - three
    answers, so a caller can tell "unsupported here" from "binding missing"."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        fn = libc.renameat2
    except (OSError, AttributeError):
        return None
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    if fn(_AT_FDCWD, os.fsencode(a), _AT_FDCWD, os.fsencode(b), _RENAME_EXCHANGE) == 0:
        return 0
    return ctypes.get_errno()


def _exchange_dirs(a: Path, b: Path) -> bool:
    """Atomically swap two existing paths. False when the platform or
    filesystem cannot, so the caller falls back - and reports it. There is no
    portable Python API for this; on Linux glibc >= 2.28 exposes renameat2."""
    err = _renameat2_exchange(a, b)
    if err == 0:
        return True
    if err is None or err in _EXCHANGE_UNSUPPORTED:
        return False
    raise OSError(err, os.strerror(err), str(a), None, str(b))


_WHY_MERGE = "merged into an existing dir without the CPP marker"
_WHY_DEVICE = "staging is on another device"
_WHY_EXDEV = "rename refused across a mount boundary (EXDEV)"
_WHY_NO_EXCHANGE = "atomic directory exchange is unavailable here"


def _replace_in_place(src: Path, dest: Path) -> None:
    if dest.is_dir():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


def _install_one(src: Path, dest: Path, staging: Path, can_rename: bool) -> str | None:
    """Install one skill dir so a concurrent reader sees the old copy or the new
    one, never a hole or a half-copied dir (#1235). Returns None when it did,
    else the reason it had to write non-atomically.

    Replace rather than merge: a file dropped from a skill dir upstream would
    otherwise survive inside the installed copy.
    """
    if dest.exists() and not (dest.is_dir() and is_managed(dest)):
        # Not ours (no marker): the pre-#1235 merge, deliberately unchanged in
        # WHAT it does - but it overwrites files in place, so it is reported.
        shutil.copytree(src, dest, dirs_exist_ok=True)
        return _WHY_MERGE
    if not can_rename:
        _replace_in_place(src, dest)
        return _WHY_DEVICE
    new = staging / f"new-{src.name}"
    shutil.copytree(src, new)
    if not dest.exists():
        if _try_rename(new, dest):
            return None
        _replace_in_place(new, dest)
        return _WHY_EXDEV
    if _exchange_dirs(new, dest):
        shutil.rmtree(new)  # now holds the OLD copy
        return None
    old = staging / f"old-{src.name}"
    if not _try_rename(dest, old):
        _replace_in_place(new, dest)
        return _WHY_EXDEV
    if not _try_rename(new, dest):
        shutil.copytree(new, dest)
        shutil.rmtree(old)
        return _WHY_EXDEV
    shutil.rmtree(old)
    return _WHY_NO_EXCHANGE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate Codex SKILL.md skills from .claude/commands/<family>/ sources"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="fail on drift (default)")
    mode.add_argument("--write", action="store_true", help="(re)generate codex/skills/")
    mode.add_argument(
        "--list-mirrors", nargs="*", metavar="SOURCE", default=None,
        help=(
            "print the codex/skills/ paths SOURCE(s) feed, or all of them; writes"
            " nothing. This is what a LANE must declare, NOT what will drift - use"
            " --check for that"
        ),
    )
    parser.add_argument(
        "--install", action="store_true",
        help="copy codex/skills/ dirs (generated + curated) to ~/.codex/skills/",
    )
    parser.add_argument("families", nargs="*", help="subset of families (default: all)")
    args = parser.parse_args(argv)

    selected = args.families or FAMILIES
    for family in selected:
        if family not in FAMILIES:
            print(
                f"codex-skill-sync: unknown family '{family}'"
                f" (known: {' '.join(FAMILIES)})",
                file=sys.stderr,
            )
            return 2

    if args.list_mirrors is not None:
        #: Returns directly: this mode writes nothing, so `--install` after it
        #: would install a tree this invocation never generated.
        return run_list_mirrors(args.list_mirrors, selected)

    if args.write:
        rc = run_write(selected)
    elif args.install and not args.check:
        rc = 0  # install-only invocation
    else:
        rc = run_check(selected)

    if rc == 0 and args.install:
        rc = run_install()
    return rc


if __name__ == "__main__":
    sys.exit(main())
