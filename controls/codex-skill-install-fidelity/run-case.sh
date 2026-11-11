#!/bin/sh
# Case runner for controls/codex-skill-install-fidelity (issue #1670).
#
# THE QUESTION: can a generated mirror that DIFFERS FROM ITS SOURCE be
# published to the Codex install tree?
#
# Since #1670 `codex/skills/` is build output, not a tracked tree, so no CI
# check vouches for whatever tree an install is handed. The fidelity gate is
# the install itself: it must compare the tree against what the sources
# generate and refuse on a difference, BEFORE publishing anything.
#
# The adapter builds a real tree with the gate's own `--write`, from a tiny
# fixture repo copied to a tmp dir. A `corrupt.txt` in the case directory
# (absent for the good case) marks the bad case: one bundled script in the
# built tree is altered AND its SHA256SUMS line is RECOMPUTED. Recomputing is
# the point - a tampered file under a stale manifest only exercises the
# checksum reader (`flow-helpers-install.sh`); a file that is internally
# consistent and still differs from its source is the case only a comparison
# against the SOURCE can see.
#
# Then it asks the gate to install that tree into a tmp destination.
#
# "finding" = the install exited non-zero, PRINTED ITS OWN REFUSAL, and left
# the destination with no file in it. "no finding" = exit 0 with the WHOLE
# tree published byte for byte. Anything in between - a partial publish, an
# exit 0 that copied nothing, a failure for an unrelated reason - is
# `unavailable`: it is not evidence about fidelity in either direction.
#
# THE ANCHOR has no `--output-root`. It is handed the same tree the only way
# it accepts one - as its OUTPUT_ROOT - and its `--install` copies it without
# looking. That is the blindness: the altered bytes land in the destination.
set -u
case_dir="$1"
gate="$2"
TAG="CODEX_SKILL_INSTALL_FIDELITY_CONTROL"

if [ ! -d "$case_dir/repo" ]; then
    echo "$TAG: unavailable - no repo/ fixture in $case_dir" >&2
    exit 3
fi
if [ ! -r "$gate" ] || ! command -v python3 >/dev/null 2>&1; then
    echo "$TAG: unavailable - the gate or python3 is not present" >&2
    exit 3
fi

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT INT TERM
cp -R "$case_dir/repo" "$T/repo"
mkdir -p "$T/repo/codex/skills" "$T/home"

corrupt=""
[ -f "$case_dir/corrupt.txt" ] && corrupt="$(cat "$case_dir/corrupt.txt")"

# The conftest guard (#1232) names the HOST's real skill dir as off limits and
# is inherited here under pytest. This run installs into $T/home only, so the
# guard has nothing to say about it; unset so a stale value cannot be read as
# this gate's refusal.
unset CPP_REFUSE_INSTALL_DEST

checkout="$(cd "$(dirname "$0")/../.." && pwd)"

python3 - "$gate" "$T/repo" "$T/home" "$corrupt" "$TAG" "$checkout" <<'PYEOF'
import contextlib
import hashlib
import io
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

gate_path, repo_dir, home_dir, corrupt, tag, checkout = sys.argv[1:7]


def unavailable(why: str) -> None:
    print(f"{tag}: unavailable - {why}", file=sys.stderr)
    sys.exit(3)


spec = spec_from_file_location("codex_skill_sync_install_control", gate_path)
if spec is None or spec.loader is None:
    unavailable("could not load gate module")
mod = module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception as exc:
    unavailable(f"gate import failed: {exc}")

repo_root = Path(repo_dir).resolve()
tree = repo_root / "codex" / "skills"
dest = Path(home_dir).resolve() / ".codex" / "skills"
mod.REPO_ROOT = repo_root
mod.SOURCE_ROOT = repo_root / ".claude" / "commands"
mod.SCRIPTS_ROOT = repo_root / "scripts"
mod.OUTPUT_ROOT = tree
mod.DOCS_ROOT = repo_root / "docs"
mod.FAMILIES = ["flow"]
mod.EXCLUDE = {}
mod.install_dest_root = lambda: dest
# The gate finds a sibling checker by `Path(__file__)` at CALL time. A vendored
# anchor would look for it in controls/<name>/anchors/ and could not render at
# all, so both gates are pointed at the checkout's scripts/ for that lookup.
mod.__file__ = str(Path(checkout) / "scripts" / "codex-skill-sync.py")

sink = io.StringIO()
try:
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        write_rc = mod.main(["--write"])
except Exception as exc:
    unavailable(f"--write raised: {exc}")
if write_rc != 0:
    unavailable(f"--write exited {write_rc}")

script = tree / "flow-auto" / "scripts" / "helper.sh"
manifest = script.parent / "SHA256SUMS"
if not script.is_file():
    unavailable("the fixture skill bundles no scripts/helper.sh to alter")

MARK = "# altered-after-generation\n"
if corrupt == "tamper-recompute":
    script.write_text(script.read_text() + MARK)
    digest = hashlib.sha256(script.read_bytes()).hexdigest()
    if manifest.is_file():
        lines = []
        for line in manifest.read_text().splitlines(keepends=True):
            if line.rstrip("\n").endswith("  helper.sh"):
                line = f"{digest}  helper.sh\n"
            lines.append(line)
        manifest.write_text("".join(lines))
        # PRECONDITION of the negative case: the altered tree must be
        # INTERNALLY consistent, or this measures the checksum reader instead.
        recorded = [ln.split()[0] for ln in manifest.read_text().splitlines()
                    if ln.endswith("  helper.sh")]
        if recorded != [digest]:
            unavailable("could not make the altered tree's manifest agree with its script")
    if script.read_bytes() == (repo_root / "scripts" / "helper.sh").read_bytes():
        unavailable("the altered mirror does not differ from its source")
elif corrupt:
    unavailable(f"unknown corrupt.txt value {corrupt!r}")

out = io.StringIO()
argv = ["--install", "--output-root", str(tree)]
try:
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            rc = mod.main(argv)
        except SystemExit as exc:
            if exc.code != 2:
                raise
            # A gate with no --output-root: hand it the tree the only way it
            # takes one. OUTPUT_ROOT already names it.
            argv = ["--install"]
            rc = mod.main(argv)
except Exception as exc:
    unavailable(f"{' '.join(argv)} raised: {exc}")

# WHAT WAS PUBLISHED is read from the whole destination, not from one file
# (counter-model review, #1670): an install that wrote SKILL.md and then failed
# has not "published nothing", and one that exited 0 having copied nothing has
# not installed anything.
text = out.getvalue()
published_files = (
    sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    if dest.is_dir() else []
)
tree_files = sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*") if p.is_file())
complete = bool(tree_files) and published_files == tree_files and all(
    (dest / rel).read_bytes() == (tree / rel).read_bytes() for rel in tree_files
)
altered_reached = any(MARK.encode() in (dest / rel).read_bytes() for rel in published_files)
refused = "REFUSING to install" in text
detail = (
    f"argv={argv} rc={rc} refusal-diagnostic={refused} published-files={len(published_files)}"
    f" of {len(tree_files)} complete={complete} altered-bytes-published={altered_reached}"
)

if rc != 0 and refused and not published_files:
    print(f"{tag}: finding - the install REFUSED the tree and the destination is unchanged ({detail})")
    print(text)
    sys.exit(1)
if rc == 0 and complete:
    print(f"{tag}: no finding - the install published the whole tree ({detail})")
    sys.exit(0)
# Neither a clean refusal nor a clean install: a partial publish, an exit 0
# that copied nothing, or a failure for some other reason. None of those is
# evidence about fidelity, so none may score as either verdict.
unavailable(f"the install neither refused cleanly nor published the whole tree ({detail})\n{text}")
PYEOF
