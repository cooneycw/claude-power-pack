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
    local sha dirty
    # THREE PROVENANCE STATES, because there are three and collapsing them is how
    # a label starts lying. git is ABSENT from the CI image (measured on the
    # pinned digest), so requiring it made the proof unrunnable in exactly the
    # place it most nearly means what it says - the cleanest machine available.
    local provenance
    if sha="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null)" && [ -n "$sha" ]; then
        provenance="git"
    elif [ -n "${CI_COMMIT_SHA:-}" ]; then
        # The CI system names the commit authoritatively, and its checkout is a
        # fresh clone - but with no git here that cleanliness cannot be VERIFIED,
        # only relied upon. Said out loud rather than folded into "clean".
        sha="$CI_COMMIT_SHA"
        provenance="ci-declared"
    else
        fail "no SHA from git or CI_COMMIT_SHA; a proof cannot attribute evidence to an unnamed commit"
        return 1
    fi
    # THE LABEL MUST DESCRIBE THE BYTES (#1074 re-review). This read the WORKING
    # TREE and labelled it with HEAD's SHA, so an uncommitted change compared
    # successfully and produced evidence attributed to a commit that never
    # contained it - which is exactly what "evidence for an earlier SHA is not
    # release approval" exists to prevent, inverted.
    if [ "$provenance" = "ci-declared" ]; then
        note "PROOF_PROVENANCE: ci-declared - the commit is $sha, named by CI. Tree cleanliness is NOT verified here: git is absent from this image, so this run relies on the checkout being a fresh clone rather than demonstrating it."
        dirty=""
    else
        dirty="$(git -C "$REPO_ROOT" status --porcelain -- codex/skills "tests/project_next/fixtures" 2>/dev/null)"
    fi
    if [ "$provenance" = "git" ] && [ -n "$dirty" ]; then
        # THE LABEL MUST NOT LIE - it does not have to REFUSE. Refusing outright
        # was the first shape and it made the gate unusable in the one place
        # #1074 wired it: `make verify` runs on a dirty tree by definition during
        # development, so every developer run would have redded on provenance
        # rather than on the install. The property the re-review actually named
        # is that evidence must not be attributed to a commit that never
        # contained the bytes - so the label carries `-dirty` and the contract
        # says so out loud. PROOF_STRICT_PROVENANCE=1 restores the refusal for a
        # release claim, where "runs anyway, honestly labelled" is not enough.
        if [ "${PROOF_STRICT_PROVENANCE:-0}" = "1" ]; then
            fail "the generated tree or fixture corpus has uncommitted changes, so bytes here are not $sha:"
            printf '%s\n' "$dirty" | sed 's/^/    /' >&2
            return 1
        fi
        sha="$sha-dirty"
        note "PROOF_PROVENANCE: DIRTY - the generated tree or fixture corpus has uncommitted changes, so these bytes are NOT $(printf '%s' "$sha" | sed 's/-dirty$//'). This run is evidence about a working tree, not about a commit."
    elif [ "$provenance" = "git" ]; then
        note "PROOF_PROVENANCE: clean - the bytes are $sha"
    fi
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
scenario = scenarios["active_pr_and_safe_issue"]
Path(out).with_name("state.json").write_text(json.dumps(scenario["state"]))
# The EXPECTED RESULT travels as data too (#1074 re-review). Checking only that
# keys exist accepted next_startable_issue=999: a broken recommendation satisfied
# the end-to-end proof. The scenario already declares the answer; phase 0 was
# discarding it.
Path(out).with_name("expected_result.json").write_text(json.dumps(scenario["expected"]))
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

    # An ambient `project-next.py` on PATH was asserted absent here until the
    # #1074 re-review. THIRD instance of the same defect in this file: it is host
    # INVENTORY, and every invocation in this proof is `python3 <absolute path>`,
    # which never consults PATH - so an unrelated neighbour failed the proof while
    # changing nothing it measures. The property is carried by
    # `engine-resolves-inside-codex-home`, observed in the workflow's own process.
    note "PROOF_ABSENCE: path-inventory-check RETIRED - superseded by engine-resolves-inside-codex-home"

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
    # THE ABSENCE THAT BEARS WEIGHT, observed in the workflow's OWN environment
    # (#1074 re-review). The first version inserted the installed directory into
    # sys.path itself and then asserted the import came from there - it supplied
    # the answer it was checking for. It now runs with the SAME scrubbed
    # environment the workflow uses and lets the entry point resolve on its own.
    local resolved
    resolved=$( cd "$EXERCISE_CWD" && env -u PYTHONPATH -u PYTHONSTARTUP \
        CODEX_HOME="$CODEX_ROOT" python3 - "$CODEX_ROOT/skills/$SKILL/scripts/project-next.py" <<'PROBE' 2>/dev/null
import contextlib, io, runpy, sys
entry = sys.argv[1]
sys.argv = [entry, "--help"]
# The entry point's own output is not the answer; where its IMPORTS resolved is.
# Swallow it so the probe prints exactly one line.
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    try:
        runpy.run_path(entry, run_name="__main__")
    except (SystemExit, Exception):
        pass
mod = sys.modules.get("lib.project_next.rank")
sys.stdout.write((mod.__file__ if mod else "") + "\n")
PROBE
)
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
    ( cd "$EXERCISE_CWD" && env -u PYTHONPATH -u PYTHONSTARTUP CODEX_HOME="$CODEX_ROOT" \
        python3 "$CODEX_ROOT/skills/$SKILL/scripts/project-next.py" \
        "$EXERCISE_CWD" --input "$state" --json ) > "$out" 2>"$WORK/workflow.err"
    local rc=$?
    if [ $rc -ne 0 ]; then
        fail "workflow exited $rc"; sed 's/^/    /' "$WORK/workflow.err" >&2; return 1
    fi
    python3 - "$out" "$WORK/expected_result.json" <<'PY'
import json, sys
payload = json.loads(open(sys.argv[1]).read())
expected = json.loads(open(sys.argv[2]).read())
for key in ("contract_version", "decision_policy", "next_startable_issue"):
    if key not in payload:
        print(f"PROOF_FAIL: workflow output has no {key!r}", file=sys.stderr)
        raise SystemExit(1)
# COMPARE THE VALUE, not merely its presence.
want = expected.get("next_startable")
if payload["next_startable_issue"] != want:
    print(f"PROOF_FAIL: next_startable_issue is {payload['next_startable_issue']!r}, "
          f"the scenario declares {want!r}", file=sys.stderr)
    raise SystemExit(1)
if not payload["contract_version"] or not payload["decision_policy"]:
    print("PROOF_FAIL: contract_version or decision_policy is empty", file=sys.stderr)
    raise SystemExit(1)
print(f"PROOF_WORKFLOW: ok - contract v{payload['contract_version']}, "
      f"next_startable_issue={payload['next_startable_issue']} (matches the scenario)")
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
    cmp -s "$victim" "$WORK/rank.py.orig" && { fail "mutation for 'stale-bundled-helper' did not apply"; return 1; }
    out=$(compare_against_manifest 2>&1); local rc_kb=$?
    # STATUS **AND** DIAGNOSTIC (#1074 re-review). Grepping the text alone
    # accepted a comparator that printed DRIFT and exited 0 - a rejection that
    # rejects nothing.
    if [ "$rc_kb" -ne 0 ] && printf '%s' "$out" | grep -q "DRIFT: lib/project_next/rank.py"; then
        note "PROOF_KNOWN_BAD: stale-bundled-helper REJECTED - $(printf '%s' "$out" | grep -m1 'DRIFT:')"
    else
        fail "known-bad 'stale-bundled-helper' was NOT rejected"; rc=1
    fi
    cp "$WORK/rank.py.orig" "$victim"

    # 2. MISSING scripts/: the case most likely to "pass" by silently finding an
    #    ambient or repo copy. The rejection TEXT is pinned: it must name a path
    #    under $CODEX_HOME and must not name ~/.claude/scripts or a repo path.
    mv "$CODEX_ROOT/skills/$SKILL/scripts" "$WORK/scripts.stash"
    [ -e "$CODEX_ROOT/skills/$SKILL/scripts" ] && { fail "mutation for 'missing-scripts' did not apply"; return 1; }
    out=$( cd "$EXERCISE_CWD" && env -u PYTHONPATH CODEX_HOME="$CODEX_ROOT" \
             python3 "$CODEX_ROOT/skills/$SKILL/scripts/project-next.py" \
             "$EXERCISE_CWD" --input "$WORK/state.json" --json 2>&1 ); local rc_ms=$?
    # The DIAGNOSTIC is the evidence, so it is printed rather than replaced by a
    # canned sentence and then asserted about (#1074 re-review). It must name the
    # exact missing entry point under CODEX_HOME, and no ambient or repo path.
    if [ "$rc_ms" -ne 0 ] \
       && printf '%s' "$out" | grep -q "$CODEX_ROOT/skills/$SKILL/scripts/project-next.py" \
       && ! printf '%s' "$out" | grep -qE "\.claude/scripts|$REPO_ROOT"; then
        note "PROOF_KNOWN_BAD: missing-scripts REJECTED (exit $rc_ms) - $(printf '%s' "$out" | grep -m1 "$CODEX_ROOT" | sed "s|$CODEX_ROOT|\$CODEX_HOME|g")"
    else
        fail "known-bad 'missing-scripts' rejection text is wrong: $(printf '%s' "$out" | head -1)"; rc=1
    fi
    mv "$WORK/scripts.stash" "$CODEX_ROOT/skills/$SKILL/scripts"

    # 3. PAYLOAD DRIFT: an installed file whose bytes differ from what shipped.
    local doc="$CODEX_ROOT/skills/$SKILL/SKILL.md"
    cp "$doc" "$WORK/SKILL.md.orig"
    printf '\ndrifted\n' >> "$doc"
    cmp -s "$doc" "$WORK/SKILL.md.orig" && { fail "mutation for 'payload-drift' did not apply"; return 1; }
    out=$(compare_against_manifest 2>&1); local rc_kb=$?
    if [ "$rc_kb" -ne 0 ] && printf '%s' "$out" | grep -q "DRIFT: SKILL.md"; then
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
