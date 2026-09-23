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
import hashlib
import json
import re
import shutil
import sys
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
# trigger words up front.
DESCRIPTION_MAX = 150

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


def derive_description(meta: dict[str, str], body: str) -> str:
    """Skill-list description: source frontmatter description when present,
    else H1 title + first prose paragraph. Front-loads the trigger words and
    caps the length (Codex truncates long skill lists)."""
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
    if len(desc) > DESCRIPTION_MAX:
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

#: `from lib.x import ...` / `import lib.x`. A Python helper's real dependency is
#: its import, not a filename in its prose, so this is the only Python signal
#: read here.
_LIB_IMPORT = re.compile(r"^\s*(?:from|import)\s+(lib(?:\.[A-Za-z_][A-Za-z0-9_]*)+)", re.M)

#: Single-dot relative imports inside a bundled package module, in BOTH spellings:
#:
#:     from .b import value     -> the module `b`
#:     from . import b, c       -> the modules `b` and `c`
#:
#: The second form is absent from this repository today, and that is exactly why
#: it is here: a rule written against only the shapes currently present is one
#: refactor away from silently bundling an incomplete package, and the symptom
#: would be an ImportError in a shipped artifact rather than a red here.
#:
#: Parent-relative (`from ..x`) is deliberately NOT matched: these packages are
#: vendored whole from their own root, so a parent-relative import reaches
#: outside the tree being bundled and means the vendoring boundary is wrong -
#: which is a thing to notice, not to paper over by copying more files.
_RELATIVE_IMPORT = re.compile(r"^\s*from\s+\.([A-Za-z_][A-Za-z0-9_]*)\s+import", re.M)
_RELATIVE_FROM_PACKAGE = re.compile(r"^\s*from\s+\.\s+import\s+([^\n#]+)", re.M)

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
    for name in scripts:
        path = SCRIPTS_ROOT / name
        if path.suffix == ".py":
            pending.append((f"scripts/{name}", path))

    while pending:
        origin, path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        text = path.read_text()

        # Absolute `lib.*` imports, resolved against the repository root.
        for match in _LIB_IMPORT.finditer(text):
            dotted = match.group(1)
            rel = _lib_package_path(dotted)
            if rel is None:
                raise SystemExit(
                    f"codex-skill-sync: {origin} imports `{dotted}`, which "
                    f"resolves to no package under the repository root or vendor/. "
                    f"Bundling it would ship a script that cannot start."
                )
            source = REPO_ROOT / rel
            targets = sorted(source.rglob("*.py")) if source.is_dir() else [source]
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

        # Relative imports INSIDE a bundled package - `from .b import value`.
        # Only meaningful once we are walking a package's own modules, which is
        # exactly what the worklist made possible.
        if path.parent != SCRIPTS_ROOT:
            names = [m.group(1) for m in _RELATIVE_IMPORT.finditer(text)]
            for match in _RELATIVE_FROM_PACKAGE.finditer(text):
                names.extend(
                    part.split(" as ")[0].strip().strip("()")
                    for part in match.group(1).split(",")
                )
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


def generate_skill(
    source_file: Path, family: str, names: dict[tuple[str, str], str]
) -> dict[str, str]:
    """Map of skill-dir-relative path -> content for one command."""
    meta, body = parse_frontmatter(source_file.read_text())
    body = rewrite_slash_refs(body, names).rstrip("\n") + "\n"
    # Rewrite doc links BEFORE deriving the description: the description is cut
    # from the opening paragraphs, so a later rewrite leaves the broken
    # source-relative path advertised in the skill's own frontmatter.
    docs = find_bundled_docs(body)
    if docs:
        body = rewrite_doc_refs(body)
    name = f"{family}-{source_file.stem}"
    description = derive_description(meta, body)
    marker = marker_for(family, source_file.name)
    bullets = detect_adaptations(body)
    scripts = find_bundled_scripts(body)
    if scripts:
        bullets.append(BUNDLED_SCRIPTS_BULLET)
    if docs:
        bullets.append(BUNDLED_DOCS_BULLET)

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
    for script in scripts:
        files[f"scripts/{script}"] = (SCRIPTS_ROOT / script).read_text()
    # Bundled at their repo-relative path, which is what makes the scripts'
    # own `parents[1]` resolution land inside the skill directory.
    for rel, source in find_bundled_libs(scripts).items():
        files[rel] = source.read_text()
    for rel, source in find_bundled_shell_libs(scripts).items():
        files[rel] = source.read_text()
    for rel, source in find_bundled_data(scripts).items():
        files[rel] = source.read_text()
    for doc in docs:
        # Bundled verbatim, at the same relative path, so sibling links between
        # bundled docs keep resolving without rewriting their contents.
        files[f"docs/{doc}"] = (DOCS_ROOT / doc).read_text()
    manifest = scripts_manifest(files)
    if manifest is not None:
        files[f"scripts/{MANIFEST_NAME}"] = manifest
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


def _repo_relative(raw: str) -> str:
    """A caller's path as the generator spells it: repo-relative, POSIX."""
    path = Path(raw)
    if path.is_absolute():
        try:
            path = path.relative_to(REPO_ROOT)
        except ValueError:
            return path.as_posix()
    return Path(*[p for p in path.parts if p != "."]).as_posix()


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
        hits: list[str] = []

        parts = source.split("/")
        if (
            len(parts) == 4
            and parts[0] == ".claude"
            and parts[1] == "commands"
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
    """
    outputs = expected_outputs(selected)

    if not sources:
        for skill in sorted(outputs):
            for rel in sorted(outputs[skill]):
                print(f"codex/skills/{skill}/{rel}")
        return 0

    found, unknown = mirrors_for(sources, selected)
    for source in sources:
        for mirror in found.get(_repo_relative(source), []):
            print(mirror)

    for source in unknown:
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
    dest_root.mkdir(parents=True, exist_ok=True)
    source_names = set()
    count = 0
    for d in sorted(OUTPUT_ROOT.iterdir()):
        if not d.is_dir() or not (d / "SKILL.md").is_file():
            continue
        dest = dest_root / d.name
        # Replace rather than merge: a file dropped from a skill dir upstream
        # would otherwise survive inside the installed copy.
        if dest.is_dir() and is_managed(dest):
            shutil.rmtree(dest)
        shutil.copytree(d, dest, dirs_exist_ok=True)
        source_names.add(d.name)
        count += 1
    removed = 0
    for orphan in find_installed_orphans(dest_root, source_names):
        shutil.rmtree(orphan)
        print(f"codex-skill-sync: removed orphaned installed skill {orphan.name}")
        removed += 1
    # The one mode that DOES touch the host, and it says so by naming both ends
    # (#1029): this is the only line here whose subject is the install tree.
    print(
        f"codex-skill-sync: installed {count} skill(s)"
        f" from {OUTPUT_ROOT.parent.name}/{OUTPUT_ROOT.name}/ -> {dest_root}"
        f" ({removed} orphan(s) removed)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate Codex SKILL.md skills from .claude/commands/<family>/ sources"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="fail on drift (default)")
    mode.add_argument("--write", action="store_true", help="(re)generate codex/skills/")
    mode.add_argument(
        "--list-mirrors", nargs="*", metavar="SOURCE", default=None,
        help="print the codex/skills/ paths SOURCE(s) feed, or all of them; writes nothing",
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
