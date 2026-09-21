#!/usr/bin/env bash
# codex-install-proof.sh - a Codex host reaches CPP's surface from a clean
# install and runs a workflow end to end (issue #1074).
#
# TWO PHASES, AND THE BOUNDARY IS THE PROOF.
#
#   phase 0  IN the repository: derive the expected set from the generated tree
#            at a named SHA and write it to a manifest. The manifest TRAVELS AS
#            DATA; it is the only thing that crosses.
#   phase 1  Install, then exercise the installed copy with the four absences
#            asserted. Every decision is made against the MANIFEST.
#
# WHY THE BOUNDARY MATTERS. #1074's defect class is "inferred from a neighbour".
# A harness that reads the INSTALLED skill to decide what should be installed
# marks the install complete because the install says it is complete - the same
# error as reading a manifest to learn what the manifest should contain.
#
# ONE HONEST SEAM, stated rather than hidden: the INSTALL step itself reads the
# repository, because that is what installing IS - it copies from the generated
# tree. It DECIDES nothing. Every verdict after it comes from the manifest, and
# the exercise runs with cwd outside any checkout and the repo path asserted
# unreachable from the proof's environment.
#
#: NEGATIVE-CONTROL: controls/codex-install-proof
#:     Registered per issue #1074. This proof's green is read as "the shipped
#:     Codex surface works on a clean host" by people who will not re-derive it,
#:     and nothing else in the tree examines an INSTALLED copy at all. A blind
#:     version - one that installs, runs the happy path and reports success -
#:     prints the same PROOF: ok line over an install missing its scripts.
set -uo pipefail

SKILL="${PROOF_SKILL:-project-next}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${PROOF_WORK:-$(mktemp -d /tmp/codex-install-proof-XXXXXX)}"
MANIFEST="$WORK/expected.json"
CODEX_ROOT="$WORK/codex-home"
FAILURES=0

note() { printf '%s\n' "$*"; }
fail() { printf 'PROOF_FAIL: %s\n' "$*" >&2; FAILURES=$((FAILURES + 1)); }

# --- phase 0: derive the expected set from the REPOSITORY -------------------
phase0_derive() {
    local sha
    sha="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
    python3 - "$REPO_ROOT" "$SKILL" "$sha" "$MANIFEST" <<'PY'
import hashlib, json, sys
from pathlib import Path
repo, skill, sha, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
src = Path(repo) / "codex" / "skills" / skill
if not src.is_dir():
    print(f"PROOF_FAIL: no generated skill at {src}", file=sys.stderr)
    raise SystemExit(1)
files = {}
for p in sorted(src.rglob("*")):
    if p.is_file() and "__pycache__" not in p.parts:
        files[p.relative_to(src).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
if not files:
    print("PROOF_FAIL: the generated skill is empty; an empty expected set proves nothing", file=sys.stderr)
    raise SystemExit(1)
Path(out).write_text(json.dumps({"skill": skill, "source_sha": sha, "files": files}, indent=2))
scenarios = json.loads((src / "tests" / "project_next" / "fixtures" / "scenarios.json").read_text()) \
    if (src / "tests" / "project_next" / "fixtures" / "scenarios.json").is_file() else None
if scenarios is None:
    scenarios = json.loads((Path(repo) / "tests" / "project_next" / "fixtures" / "scenarios.json").read_text())
state = scenarios["active_pr_and_safe_issue"]["state"]
Path(out).with_name("state.json").write_text(json.dumps(state))
print(f"PROOF_EXPECTED_FILES: {len(files)}")
print(f"PROOF_SOURCE_SHA: {sha}")
PY
}

# --- the four constructed absences, each ASSERTED before anything relies on it
assert_absences() {
    local ok=0
    if [ -e "$CODEX_ROOT/skills" ] && [ -n "$(ls -A "$CODEX_ROOT/skills" 2>/dev/null)" ]; then
        fail "absence 'empty CODEX_HOME' is NOT real: $CODEX_ROOT/skills is populated"; ok=1
    else note "PROOF_ABSENCE: empty-codex-home ok"; fi

    # REACHABILITY IN EFFECT, not host inventory. An ambient helper EXISTING at
    # ~/.claude/scripts is not the hazard: this proof invokes the skill by
    # ABSOLUTE PATH into $CODEX_HOME, and that script resolves its engine from
    # its own __file__, so the ambient copy is never consulted. The hazard is
    # invoking by NAME and getting whatever PATH supplies - covered by the next
    # assert - and resolving the engine outside CODEX_HOME, asserted after
    # install.
    #
    # I wrote the host-inventory form here and one assert below, and the
    # inventory form fired on this very host (the ambient helper is installed),
    # which is how it was caught. A precondition nobody can satisfy is not a
    # precondition - it is a way of never running the proof.
    if [ "${PROOF_INVOKE_BY_NAME:-0}" = "1" ]; then
        fail "absence 'invocation is path-qualified' is NOT real: the proof was told to invoke by name"; ok=1
    else note "PROOF_ABSENCE: invocation-path-qualified ok"; fi

    if command -v project-next.py >/dev/null 2>&1; then
        fail "absence 'no ambient project-next on PATH' is NOT real"; ok=1
    else note "PROOF_ABSENCE: no-ambient-on-path ok"; fi

    if git -C "$EXERCISE_CWD" rev-parse --show-toplevel >/dev/null 2>&1; then
        fail "absence 'no repo reachable' is NOT real: $EXERCISE_CWD is inside a checkout"; ok=1
    else note "PROOF_ABSENCE: no-repo-reachable ok"; fi
    return $ok
}

# --- phase 1: install, then exercise the COPY against the MANIFEST ----------
phase1_install() {
    CODEX_HOME="$CODEX_ROOT" python3 "$REPO_ROOT/scripts/codex-skill-sync.py" --install >/dev/null 2>&1 \
        || { fail "install failed"; return 1; }
    note "PROOF_INSTALLED_AT: $CODEX_ROOT/skills/$SKILL"
    # THE ABSENCE THAT BEARS WEIGHT: the engine the installed skill executes must
    # resolve inside $CODEX_HOME. A sibling checkout existing on the box is not
    # the hazard - the skill reaching one is, and that is what this measures.
    local resolved
    resolved=$( cd "$EXERCISE_CWD" && CODEX_HOME="$CODEX_ROOT" python3 -c "
import sys
sys.path.insert(0, '$CODEX_ROOT/skills/$SKILL')
import lib.project_next.rank as r
print(r.__file__)" 2>/dev/null )
    case "$resolved" in
        "$CODEX_ROOT"/*) note "PROOF_ABSENCE: engine-resolves-inside-codex-home ok ($resolved)" ;;
        "")              fail "the installed skill's engine could not be imported at all" ;;
        *)               fail "the installed skill resolved its engine OUTSIDE CODEX_HOME: $resolved" ;;
    esac
}

compare_against_manifest() {
    python3 - "$MANIFEST" "$CODEX_ROOT/skills/$SKILL" <<'PY'
import hashlib, json, sys
from pathlib import Path
manifest, installed = json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2])
expected, findings = manifest["files"], []
# AN EMPTY EXPECTED SET IS NOT A PASS (#1074). Zero files compared and zero
# findings is "there was nothing to look at", which must not render as "I looked
# and found nothing" - the same distinction this proof exists to draw about an
# install. Caught by tests/test_codex_install_proof.py on the first run, which is
# the third time in one day I wrote this shape: a check whose success message
# outruns its input population.
if not expected:
    print("PROOF_FAIL: the manifest names no files; a comparison over an empty "
          "expected set proves nothing about the install", file=sys.stderr)
    raise SystemExit(1)
for rel, want in sorted(expected.items()):
    p = installed / rel
    if not p.is_file():
        findings.append(f"MISSING: {rel}")
    elif hashlib.sha256(p.read_bytes()).hexdigest() != want:
        findings.append(f"DRIFT: {rel}")
for line in findings:
    print(f"PROOF_FAIL: {line}", file=sys.stderr)
h = hashlib.sha256()
for rel in sorted(expected):
    p = installed / rel
    h.update(rel.encode())
    h.update(p.read_bytes() if p.is_file() else b"<absent>")
print(f"PROOF_INSTALLED_HASH: {h.hexdigest()[:16]}")
print(f"PROOF_COMPARED: {len(expected)} file(s) against the manifest")
raise SystemExit(1 if findings else 0)
PY
}

run_workflow() {
    local state="$1" out="$WORK/workflow.json"
    ( cd "$EXERCISE_CWD" && python3 "$CODEX_ROOT/skills/$SKILL/scripts/project-next.py" \
        "$EXERCISE_CWD" --input "$state" --json ) > "$out" 2>"$WORK/workflow.err"
    local rc=$?
    if [ $rc -ne 0 ]; then
        fail "workflow exited $rc"; sed 's/^/    /' "$WORK/workflow.err" >&2; return 1
    fi
    python3 - "$out" <<'PY'
import json, sys
payload = json.loads(open(sys.argv[1]).read())
for key in ("contract_version", "decision_policy", "next_startable_issue"):
    if key not in payload:
        print(f"PROOF_FAIL: workflow output has no {key!r}", file=sys.stderr)
        raise SystemExit(1)
print(f"PROOF_WORKFLOW: ok - contract v{payload['contract_version']}, "
      f"next_startable_issue={payload['next_startable_issue']}")
PY
}

# --- the three known-bad inputs: each REJECTED, and the rejection SHOWN -------
#
# A proof that only walks the happy path demonstrates the happy path exists. It
# says nothing about whether a broken install is noticed, which is the whole
# question. Each case mutates the INSTALLED copy and requires a refusal.
known_bad_cases() {
    local rc=0 out

    # 1. STALE BUNDLED HELPER: an engine module edited after install. The skill
    #    carries its own ownership manifest, so the gate travels with it.
    local victim="$CODEX_ROOT/skills/$SKILL/lib/project_next/rank.py"
    cp "$victim" "$WORK/rank.py.orig"
    printf '# stale\n' >> "$victim"
    out=$(compare_against_manifest 2>&1)
    if printf '%s' "$out" | grep -q "DRIFT: lib/project_next/rank.py"; then
        note "PROOF_KNOWN_BAD: stale-bundled-helper REJECTED - $(printf '%s' "$out" | grep -m1 'DRIFT:')"
    else
        fail "known-bad 'stale-bundled-helper' was NOT rejected"; rc=1
    fi
    cp "$WORK/rank.py.orig" "$victim"

    # 2. MISSING scripts/: the case most likely to "pass" by silently finding an
    #    ambient or repo copy. The rejection TEXT is pinned: it must name a path
    #    under $CODEX_HOME and must not name ~/.claude/scripts or a repo path.
    mv "$CODEX_ROOT/skills/$SKILL/scripts" "$WORK/scripts.stash"
    out=$( cd "$EXERCISE_CWD" && python3 "$CODEX_ROOT/skills/$SKILL/scripts/project-next.py" \
             "$EXERCISE_CWD" --input "$WORK/state.json" --json 2>&1 )
    if printf '%s' "$out" | grep -q "$CODEX_ROOT" \
       && ! printf '%s' "$out" | grep -qE "\.claude/scripts|$REPO_ROOT"; then
        note "PROOF_KNOWN_BAD: missing-scripts REJECTED - names a path under CODEX_HOME, no ambient or repo path"
    else
        fail "known-bad 'missing-scripts' rejection text is wrong: $(printf '%s' "$out" | head -1)"; rc=1
    fi
    mv "$WORK/scripts.stash" "$CODEX_ROOT/skills/$SKILL/scripts"

    # 3. PAYLOAD DRIFT: an installed file whose bytes differ from what shipped.
    local doc="$CODEX_ROOT/skills/$SKILL/SKILL.md"
    cp "$doc" "$WORK/SKILL.md.orig"
    printf '\ndrifted\n' >> "$doc"
    out=$(compare_against_manifest 2>&1)
    if printf '%s' "$out" | grep -q "DRIFT: SKILL.md"; then
        note "PROOF_KNOWN_BAD: payload-drift REJECTED - $(printf '%s' "$out" | grep -m1 'DRIFT: SKILL.md')"
    else
        fail "known-bad 'payload-drift' was NOT rejected"; rc=1
    fi
    cp "$WORK/SKILL.md.orig" "$doc"

    return $rc
}

main() {
    EXERCISE_CWD="$WORK/elsewhere"; mkdir -p "$EXERCISE_CWD"
    note "PROOF_WORK: $WORK"
    phase0_derive || return 1
    assert_absences || return 1
    phase1_install || return 1
    compare_against_manifest || FAILURES=$((FAILURES + 1))
    run_workflow "${1:-$WORK/state.json}" || FAILURES=$((FAILURES + 1))
    known_bad_cases || FAILURES=$((FAILURES + 1))
    # NOT RUN cells are EMITTED, never inferred from a neighbour that passed.
    note "PROOF_NOT_RUN: codex-loader - the Codex CLI's own skill loader was not exercised; this proof drives the installed artifact directly"
    note "PROOF_NOT_RUN: other-skills - only '$SKILL' was exercised; the other generated skills are not implied by it"
    note "PROOF_NOT_RUN: platform - one Linux host; macOS and Windows were not run"
    if [ "$FAILURES" -eq 0 ]; then note "PROOF: ok"; return 0; fi
    note "PROOF: fail ($FAILURES finding(s))"; return 1
}

# --root MODE: compare a committed case tree against its manifest, which is what
# makes a committed negative control possible at all. The full proof installs,
# and a case cannot carry an install; this is the comparison half, aimed at a
# fixture instead of at this host.
if [ "${1:-}" = "--root" ]; then
    CASE="${2:?--root needs a case directory}"
    MANIFEST="$CASE/expected.json"
    CODEX_ROOT="$CASE/codex-home"
    [ -f "$MANIFEST" ] || { printf 'PROOF_FAIL: no manifest at %s\n' "$MANIFEST" >&2; exit 1; }
    SKILL="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['skill'])" "$MANIFEST")"
    compare_against_manifest || exit 1
    printf 'PROOF: ok\n'
    exit 0
fi

main "${1:-}"
