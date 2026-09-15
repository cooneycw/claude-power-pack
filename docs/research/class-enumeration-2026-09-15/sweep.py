#!/usr/bin/env python3
"""Invocation-reachability SCREENING for CPP scripts (issue #955, map #950).

WHAT THIS IS. A screening heuristic that asks, per script: does anything in
this repository appear to RUN it, and from where? It applies #591's
discriminator ("no .woodpecker.yml step, no Makefile target, no test in
tests/, referenced only from docs") mechanically.

WHAT THIS IS NOT. A census. Its error rate is not zero and is not estimated.
Known false positives and false negatives are committed as control cases
below, each drawn from a real line in this tree. Counts from this tool are
SCREENING RESULTS, not measurements, and the document that cites it says so.

Its history is the reason for that caution. Four successive versions each
reported a clean, plausible result while blind:

  v1  a MENTION counted as reachability
  v2  same hole via a bare "scripts/<name>" pattern; reported a docstring
      sentence as the evidence that a guard was invoked
  v5  matched "sh" inside a quoted FILENAME as an interpreter, reading a test
      data tuple as an invocation
  v6  matched any line BEGINNING with a script name, so a docstring line and a
      printed advice string both read as invocations; and missed every
      invocation made through a path variable or importlib

v6 was additionally shown, by adversarial mutation, to pass its whole control
battery with its protections disabled. That is the failure this file now
guards against directly: `--self-test` breaks each protection in turn and
requires a control to fail. A battery that survives its own protections being
removed is decoration.

Usage:
  python3 docs/research/class-enumeration-2026-09-15/sweep.py
  python3 docs/research/class-enumeration-2026-09-15/sweep.py --self-test
"""
import ast
import os
import pathlib
import re
import subprocess
import sys

# ---------------------------------------------------------------- text rules

# Interpreter must sit at a token start, so ".sh" inside a quoted filename
# cannot act as one.
_INTERP = r'(?:^|[\s"\'\[(@;&|])(?:bash|sh|zsh|python3?|uv\s+run)\s+[^\s"\',;]*'
# Command position: a Makefile recipe (TAB) or after a shell separator.
# A bare line-start is NOT accepted: that is what let docstring prose through.
_CMDPOS = r'(?:^\t|[;&|]|\$\()\s*\.?/?[\w./$@{}~-]*'


def _in_quoted_string(line: str, idx: int) -> bool:
    """True when offset `idx` sits inside a quoted run on this line.

    A printed suggestion such as  fix "... python3 scripts/mcp-drift.py ..."
    is advice, not an invocation.
    """
    quotes = 0
    for i, ch in enumerate(line):
        if i >= idx:
            break
        if ch in "\"'":
            quotes += 1
    return quotes % 2 == 1


def text_exec(line: str, name: str, allow_bare_line_start: bool = False) -> bool:
    """True when a SHELL/MAKE/YAML line appears to run `name`."""
    if line.strip().startswith("#"):
        return False
    n = re.escape(name)
    for pat in (_INTERP + n, _CMDPOS + n):
        m = re.search(pat, line)
        if m and not _in_quoted_string(line, m.end() - len(name)):
            return True
    if allow_bare_line_start:
        m = re.match(r'\s*\.?/?[\w./$@{}~-]*' + n, line)
        if m and not _in_quoted_string(line, m.end() - len(name)):
            return True
    return False


# ------------------------------------------------------------- python via ast

def python_exec_names(path: pathlib.Path, names) -> dict:
    """Names this PYTHON file invokes, found via ast rather than text.

    ast sees only real code, so docstrings and comments cannot register as
    invocations. It also resolves the common alias form:

        REGISTRY = ROOT / "scripts" / "flow-wave-registry.sh"
        subprocess.run(["bash", str(REGISTRY), *args])

    which no single-line text rule can follow.
    """
    found = {}
    try:
        tree = ast.parse(path.read_text(errors="ignore"))
    except (SyntaxError, OSError):
        return found

    # alias -> script name, from assignments whose joined string parts name a script
    alias = {}

    def literal_parts(node):
        out = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                out.append(sub.value)
        return out

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name):
                for part in literal_parts(node.value):
                    base = part.rsplit("/", 1)[-1]
                    if base in names:
                        alias[tgt.id] = base

    def record(name, lineno):
        found.setdefault(name, lineno)

    # Only calls that actually RUN or LOAD something count. A script name
    # appearing in a parametrize list, an assertion message, or a data tuple
    # is not an invocation, and an earlier version that accepted any Call
    # reported 57 of 63 scripts as automated, which is the loose-rule failure
    # in the opposite direction from the text rules.
    RUNNERS = {"run", "call", "check_call", "check_output", "Popen", "system",
               "spec_from_file_location", "run_module"}

    def is_runner(call: ast.Call) -> bool:
        f = call.func
        if isinstance(f, ast.Attribute):
            return f.attr in RUNNERS
        if isinstance(f, ast.Name):
            return f.id in RUNNERS
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and is_runner(node):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    base = sub.value.rsplit("/", 1)[-1]
                    if base in names:
                        record(base, getattr(sub, "lineno", 0))
                elif isinstance(sub, ast.Name) and sub.id in alias:
                    record(alias[sub.id], getattr(sub, "lineno", 0))
    return found


# ------------------------------------------------------------------- universe

def derive_universe(root: pathlib.Path) -> dict:
    """Every TRACKED file under scripts/ that is executable or has a shebang.

    Derived from git, never filtered by extension: an extension filter is a
    search term, and an extensionless dormant script is the shape this tool
    exists to find. scripts/cpp-memory is one.
    """
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "scripts/"],
        capture_output=True, text=True, check=True).stdout.split()
    names = {}
    for rel in tracked:
        p = root / rel
        if not p.is_file():
            continue
        try:
            shebang = p.open("rb").read(2) == b"#!"
        except OSError:
            shebang = False
        if os.access(p, os.X_OK) or shebang:
            names[p.name] = p
    return names


class Coverage:
    """Denominator for one root set: what was looked at, and what was not.

    #952: a zero that cannot show it looked in the right place reads UNKNOWN,
    never clean.
    """

    def __init__(self):
        self.discovered = 0
        self.scanned = 0
        self.missing = 0
        self.unreadable = 0

    def ok(self):
        return self.scanned > 0 and self.unreadable == 0

    def __str__(self):
        return (f"discovered={self.discovered} scanned={self.scanned} "
                f"missing={self.missing} unreadable={self.unreadable}")


def closure(roots, names, root, hook_form=False):
    got, evidence, seen = {}, {}, set()
    cov = Coverage()
    frontier, generation = list(roots), 0
    while frontier and generation <= 25:
        generation += 1
        nxt = []
        for f in frontier:
            if f.is_dir():
                continue          # a directory is not an input
            cov.discovered += 1
            if f in seen:
                continue
            seen.add(f)
            if not f.exists():
                cov.missing += 1
                continue
            try:
                text = f.read_text(errors="ignore")
            except OSError:
                cov.unreadable += 1
                continue
            cov.scanned += 1
            hits = {}
            if f.suffix == ".py":
                hits = python_exec_names(f, names)
            else:
                bare_ok = f.suffix in (".sh", "") or f.name == "Makefile"
                for i, line in enumerate(text.splitlines(), 1):
                    for n in names:
                        if n in line and n not in hits and text_exec(line, n, bare_ok):
                            hits[n] = i
            if hook_form and f.name == "hooks.json":
                for i, line in enumerate(text.splitlines(), 1):
                    for n in names:
                        if f"scripts/{n}" in line:
                            hits.setdefault(n, i)
            for n, ln in hits.items():
                if n not in got:
                    got[n] = True
                    evidence[n] = (str(f.relative_to(root)), ln)
                    nxt.append(names[n])
        frontier = nxt
    return set(got), evidence, cov


# ------------------------------------------------------------------- controls
# Each case is a REAL line from this tree. The `breaks` column names the
# protection the case exists to hold; --self-test disables that protection and
# requires this case to fail. A case no mutation can break is decoration.
CONTROL_CASES = [
    # (source, script, expected, why, protection-it-holds, lang)
    ('Same discipline as scripts/eli5-core-drift.sh (the eli5-gate vendor guard).',
     'eli5-core-drift.sh', False, 'docstring prose (defeated v1, v2)', 'cmdpos', 'sh'),
    ('      - python3 scripts/tool-risk-drift.py --strict',
     'tool-risk-drift.py', True, 'real CI step', None, 'sh'),
    ('        ("install-memory-harness.sh", "cpp-memory would be missing from PATH"),',
     'cpp-memory', False, 'test data tuple (defeated v5)', 'interp', 'sh'),
    ('\t@bash scripts/install-memory-harness.sh',
     'install-memory-harness.sh', True, 'Makefile recipe', None, 'sh'),
    ('    fix "Guided teardown: run /cpp:update, or: python3 scripts/mcp-drift.py --teardown"',
     'mcp-drift.py', False, 'printed ADVICE string, not an invocation (defeated v6)', 'quote', 'sh'),
    ('# bash scripts/flow-finish-gate.sh   (disabled while we debug)',
     'flow-finish-gate.sh', False, 'commented-out real invocation', 'comment', 'sh'),
    # YAML context: bare_ok is False for .yml, so a line that merely BEGINS with
    # a script name is prose. This is the case that makes `cmdpos` load-bearing.
    ('    flow-ci-status.sh reports the pipeline state for a SHA, per the notes above',
     'flow-ci-status.sh', False, 'YAML prose beginning with the name', 'cmdpos', 'yml'),
    # PYTHON path: these exercise ast, which is how .py roots are really read.
    ('"""\nflow-driver-capability.sh takes needs from its caller and never infers them,\n"""\n',
     'flow-driver-capability.sh', False,
     'docstring line STARTING with the name (defeated v6); ast must not see it', 'ast', 'py'),
    ('import subprocess\nREGISTRY = ROOT / "scripts" / "flow-wave-registry.sh"\n'
     'subprocess.run(["bash", str(REGISTRY), "list"])\n',
     'flow-wave-registry.sh', True,
     'invocation through a PATH VARIABLE; missed entirely by every text rule', 'ast', 'py'),
]


def _probe(source, name, lang, mutate):
    """Evaluate a control case the way the real sweep would read that file type."""
    if lang == 'py':
        if mutate == 'ast':
            # the pre-ast behaviour: plain text scan of the whole source
            return any(text_exec(ln, name, True) for ln in source.splitlines())
        import tempfile
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as fh:
            fh.write(source)
            tmp = pathlib.Path(fh.name)
        try:
            return name in python_exec_names(tmp, {name: tmp})
        finally:
            tmp.unlink(missing_ok=True)
    bare_ok = lang != 'yml'
    line = source
    if mutate == 'comment' and line.strip().startswith('#'):
        line = line.lstrip('#').lstrip()
    if mutate == 'quote':
        return bool(re.search(_INTERP + re.escape(name), line)) or text_exec(line, name, bare_ok)
    if mutate == 'interp':
        return bool(re.search(r'(?:bash|sh|zsh|python3?)\s*[^\n]{0,80}?' + re.escape(name), line))
    return text_exec(line, name, bare_ok)


def run_controls(mutate=None, verbose=True):
    """Run the battery. `mutate` disables one protection, for --self-test."""
    global _CMDPOS
    saved = _CMDPOS
    if mutate == 'cmdpos':
        _CMDPOS = r'(?:^)\s*\.?/?[\w./$@{}~-]*'          # v6's permissive rule
    failed = []
    for source, name, expected, why, _breaks, lang in CONTROL_CASES:
        got = _probe(source, name, lang, mutate)
        if got != expected:
            failed.append((name, why, expected, got))
        if verbose:
            print(f"  {'PASS' if got == expected else 'FAIL'}  expect={str(expected):5} "
                  f"got={str(got):5}  {name:30} {why}")
    _CMDPOS = saved
    return failed


def self_test():
    """Break each protection; a control MUST fail. Otherwise it is decoration."""
    print("=== self-test: each protection disabled in turn ===")
    bad = 0
    for mutation in ('cmdpos', 'quote', 'interp', 'comment', 'ast'):
        failures = run_controls(mutate=mutation, verbose=False)
        caught = [f for f in failures if True]
        status = "caught" if caught else "NOT CAUGHT"
        print(f"  disable {mutation:8} -> {len(caught)} control(s) fail  [{status}]")
        if not caught:
            bad += 1
    if bad:
        print(f"\n{bad} mutation(s) produced NO control failure. The battery does not "
              f"guard what it claims.", file=sys.stderr)
        return 1
    print("  every disabled protection is caught by at least one control.")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()

    print("=== control battery ===")
    if run_controls():
        print("\nCONTROL FAILED. Output is not evidence. Refusing to report.", file=sys.stderr)
        return 1
    print(f"  {len(CONTROL_CASES)}/{len(CONTROL_CASES)} cases pass")
    if self_test():
        return 1

    root = pathlib.Path(subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True).stdout.strip())
    names = derive_universe(root)

    r_auto = ([root / ".woodpecker.yml", root / "Makefile"]
              + sorted((root / "tests").rglob("*.py")) + sorted((root / "lib").rglob("*.py")))
    r_hook = [root / ".claude/hooks.json"] + sorted((root / "templates").rglob("*"))
    r_doc = (sorted((root / ".claude").rglob("*.md")) + sorted((root / "codex").rglob("*.md"))
             + sorted((root / "plugins").rglob("*.md")))

    auto, ev_auto, cov_a = closure(r_auto, names, root)
    hook, _, cov_h = closure(r_hook, names, root, hook_form=True)
    doc, _, cov_d = closure(r_doc, names, root)

    print("\n=== coverage (denominator per root set) ===")
    for label, cov in (("automated", cov_a), ("hook", cov_h), ("doc", cov_d)):
        flag = "" if cov.ok() else "   <- UNKNOWN, not clean"
        print(f"  {label:10} {cov}{flag}")
    if not all(c.ok() for c in (cov_a, cov_h, cov_d)):
        print("\nA root set could not be fully examined. Its zero means 'did not look', "
              "not 'nothing there'. Refusing to report buckets.", file=sys.stderr)
        return 1

    buckets = {"AUTOMATED": [], "HOOK-ONLY": [], "AGENT-DOC-ONLY": [], "UNREFERENCED": []}
    for n in sorted(names):
        key = ("AUTOMATED" if n in auto else "HOOK-ONLY" if n in hook
               else "AGENT-DOC-ONLY" if n in doc else "UNREFERENCED")
        buckets[key].append(n)

    print(f"\n=== SCREENING RESULT (not a census) universe={len(names)} ===")
    for key in ("AUTOMATED", "HOOK-ONLY", "AGENT-DOC-ONLY", "UNREFERENCED"):
        print(f"  {key:16} {len(buckets[key]):3}")
    for key in ("AGENT-DOC-ONLY", "UNREFERENCED"):
        print(f"\n{key}:")
        for n in buckets[key]:
            print(f"    {n}")

    # Bucket controls. The specimen must EXIST in the universe: otherwise a
    # typo or a deleted file satisfies "not in AUTOMATED" vacuously.
    red, green = "eli5-core-drift.sh", "tool-risk-drift.py"
    checks = [
        (f"{red} present in universe", red in names),
        (f"RED   {red} NOT AUTOMATED (#591's claim)", red not in auto),
        (f"{green} present in universe", green in names),
        (f"GREEN {green} AUTOMATED (#576 item 1, since fixed)", green in auto),
    ]
    print("\n=== bucket controls ===")
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if not all(ok for _, ok in checks):
        print("\nBUCKET CONTROL FAILED.", file=sys.stderr)
        return 1
    print(f"  GREEN evidence: {ev_auto.get(green)}")

    print("\nBounds this tool does NOT overcome:")
    print("  - host hook wiring (~/.claude/settings.json) is outside the repo and invisible")
    print("  - superseded leftovers are indistinguishable from dormant guards")
    print("  - AGENT-DOC-ONLY and UNREFERENCED both admit guards; neither bucket alone")
    print("    bounds dormancy, and these are screening counts rather than measurements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
