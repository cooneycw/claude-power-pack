"""Real maintained readers and plain-runtime production installations."""
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import venv
from pathlib import Path

import pytest

from lib.host_update.codex import CodexAdapter
from lib.host_update.links import ClaudeLinks
from tests.test_host_update_adapters import CLI, cli, git, request
from tests.test_host_update_adapters import source as source_fixture
from tests.test_host_update_adapters import source_template as template_fixture
from tests.test_host_update_links import seed, tree

source_template = template_fixture
source = source_fixture
pytestmark = pytest.mark.skipif(
    not shutil.which("git") or not shutil.which("python3"),
    reason="git and python3 required for real plain-runtime sources",
)


def plain_environment(home):
    git = shutil.which("git")
    assert git is not None
    env = {"HOME": str(home), "PATH": str(Path(git).parent) + os.pathsep + os.defpath,
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    assert shutil.which("git", path=env["PATH"]) == git, "plain runtime must retain the actual Git binary"
    return env


@pytest.fixture(scope="module")
def plain_python(tmp_path_factory):
    root = tmp_path_factory.mktemp("stdlib-runtime")
    venv.EnvBuilder(with_pip=False, system_site_packages=False).create(root)
    executable = root / "bin/python"
    # The parent uses the owner's -I -S setup. The pinned child launches the
    # same executable without those flags: prove its empty venv also has no
    # YAML, so an ambient site installation cannot hide a child import bug.
    for flags in (("-I", "-S"), ("-I",)):
        checked = subprocess.run(
            [str(executable), *flags, "-B", "-c",
             "import json,fcntl,importlib.util; "
             "assert importlib.util.find_spec('yaml') is None; print('stdlib-without-yaml')"],
            env=plain_environment(root), capture_output=True, text=True, check=True,
        )
        assert checked.stdout.strip() == "stdlib-without-yaml"
    return executable


def plain_cli(executable, source, home, operation, *selected):
    args = [str(executable), "-I", "-S", "-B", str(CLI), operation,
            "--source-root", str(source), "--home", str(home), "--json"]
    for harness in selected:
        args += ["--select", harness]
    result = subprocess.run(args, env=plain_environment(home), cwd=home.parent,
                            capture_output=True, text=True, timeout=120)
    assert result.stdout, result.stderr
    return result, json.loads(result.stdout)


@pytest.mark.parametrize("scenario", ["claude-links", "codex", "mixed-unavailable"])
def test_plain_runtime_production_without_yaml(source, tmp_path, plain_python, scenario):
    home = tmp_path / "home"
    if scenario != "codex":
        seed(home, source)
        setup, report = cli(source, home)
        assert setup.returncode == 0, report
    if scenario == "claude-links":
        result, report = plain_cli(plain_python, source, home, "verify", "claude-links")
    elif scenario == "codex":
        result, report = plain_cli(plain_python, source, home, "refresh", "codex")
    else:
        result, report = plain_cli(plain_python, source, home, "refresh",
                                   "codex", "claude-topics", "antigravity")
    rows = {r["harness"]: r for r in report["results"]}
    if scenario == "mixed-unavailable":
        assert result.returncode == 4, report
        for name in ("claude-topics", "antigravity"):
            row = rows[name]
            assert row["exit_code"] == 4 and row["after"]["state"] == "unknown", row
            assert "UNAVAILABLE" in row["reason"] and name in row["reason"] and "yaml" in row["reason"], row
        successful = ("codex", "claude-links")
    else:
        assert result.returncode == 0, report
        successful = (scenario,)
    for name in successful:
        row = rows[name]
        assert row["exit_code"] == 0 and row["after"]["state"] == "current", row
        assert row["after"]["examined_members"] == row["after"]["expected_members"] > 0
    if scenario != "claude-links":
        assert (home / ".codex/skills/flow-auto/SKILL.md").is_file()


# Exact executable Step 5b fences at 8e6efc03; retained for shallow-CI comparison.
LEGACY_STEP5B = (r"""if [ -d ~/.claude/scripts ]; then
  SEAM_OK=0; SEAM_DEFERRED=0; SEAM_FAILED=0
  for script in "$CPP_DIR"/scripts/*; do
    [ -f "$script" ] && [ -x "$script" ] || continue
    name=$(basename "$script")
    # Through the declaring seam (#1132). The helper carries the already-linked
    # skip this block had, and honours --defer ~/.claude/scripts by name.
    "$CPP_DIR/scripts/cpp-host-write.sh" link-into "$script" ~/.claude/scripts "$name"
    #: COMPOSE A VERDICT, do not just run (issue #1198). This loop made ninety
    #: calls and drew no conclusion, so a seam that was absent linked nothing and
    #: the step said so nowhere - measured on 2026-09-22, 25 scripts unlinked
    #: while the run reported success. The tally is what makes the next step's
    #: "npm-global-upgrade.sh is not installed" traceable to a cause here.
    case $? in
      0) SEAM_OK=$((SEAM_OK + 1)) ;;
      3) SEAM_DEFERRED=$((SEAM_DEFERRED + 1)) ;;
      *) SEAM_FAILED=$((SEAM_FAILED + 1)) ;;
    esac
  done
  echo "→ Script refresh: $SEAM_OK linked/skipped, $SEAM_DEFERRED deferred, $SEAM_FAILED failed/preserved conflicts"
"""
    '  [ "$SEAM_FAILED" -gt 0 ] && echo "  WARNING: $SEAM_FAILED script(s) failed '
    'or were preserved as conflicts; see diagnostics. Do not treat these paths as CPP helpers."'
    r"""
else
  echo "→ Script refresh skipped (no ~/.claude/scripts - Tier 0/1 install)"
fi

if [ -d ~/.claude/scripts ]; then
  HELPER_ORPHANS=""
  ORPHAN_SCAN=unavailable
  if DRIFT_JSON=$(CPP_INSTALL_DRIFT_CHECKOUT="$CPP_DIR" "$CPP_DIR/scripts/install-drift.sh" --json) \
     && printf '%s' "$DRIFT_JSON" | jq -e '.orphaned_helpers | type == "array"' >/dev/null 2>&1; then
    ORPHAN_SCAN=read
    HELPER_ORPHANS=$(printf '%s' "$DRIFT_JSON" | jq -r '.orphaned_helpers[]')
  fi
  if [ "$ORPHAN_SCAN" != "read" ]; then
    echo "→ Orphan scan NOT run (install-drift.sh --json gave no orphaned_helpers array) - unchecked, not clean"
  elif [ -n "$HELPER_ORPHANS" ]; then
    echo "Orphaned helper links (installed, their checkout source was deleted upstream):"
    printf '  %s\n' $HELPER_ORPHANS
  else
    echo "→ No orphaned helper links"
  fi
fi

if [ "${PRUNE_CONFIRMED:-no}" = "yes" ]; then
  PRUNED=0; PRUNE_GONE=0; PRUNE_REFUSED=0
  for name in <the listed names>; do
    # The seam RE-PROVES ownership per entry (dangling, install-shaped, into a
    # CPP checkout) and refuses anything else - a name is a string, and the
    # entry can change between the listing and this call.
    #: Exit 0 covers BOTH "removed" and "already absent" (another session got
    #: there first), so the tally reads the seam's own words: counting every 0
    #: as a removal claims work this run did not do (counter-model review).
    if OUT=$("$CPP_DIR/scripts/cpp-host-write.sh" unlink-orphan ~/.claude/scripts "$name"); then
      case "$OUT" in
        *"orphan removed"*) PRUNED=$((PRUNED + 1)) ;;
        *) PRUNE_GONE=$((PRUNE_GONE + 1)) ;;
      esac
    else
      PRUNE_REFUSED=$((PRUNE_REFUSED + 1))
    fi
    echo "$OUT"
  done
  echo "→ Orphan prune: $PRUNED removed, $PRUNE_GONE already absent, $PRUNE_REFUSED refused or deferred"
else
  echo "→ Orphan prune: not run (no orphans, or the user declined)"
fi
""")
LEGACY_STEP5B_SHA256 = '0f39635bd567f38f6ed0733dee988bb8509aad0bdc2877bd19405af26ee693e1'


@pytest.mark.skipif(not shutil.which("bash") or not shutil.which("jq"), reason="real legacy fences need bash and jq")
def test_shared_deletion_is_subset_of_confirmed_legacy_population(source, tmp_path):
    assert hashlib.sha256(LEGACY_STEP5B.encode()).hexdigest() == LEGACY_STEP5B_SHA256
    for name in ("retired-fixture.sh", "nonexec-fixture.sh"):
        member = source / "scripts" / name
        member.write_text("#!/bin/sh\nexit 0\n")
        member.chmod(0o755)
    git(source, "add", "scripts")
    git(source, "commit", "-qm", "fixture executable history")
    git(source, "rm", "scripts/retired-fixture.sh")
    live_nonexec = source / "scripts/nonexec-fixture.sh"
    live_nonexec.chmod(0o644)
    git(source, "add", "scripts/nonexec-fixture.sh")
    git(source, "commit", "-qm", "retired executable kinds")
    assert git(source, "ls-tree", "HEAD", "scripts/nonexec-fixture.sh").startswith("100644 blob ")
    assert live_nonexec.exists() and not os.access(live_nonexec, os.X_OK)
    assert not (source / "scripts/retired-fixture.sh").exists()
    assert git(source, "log", "--oneline", "--", "scripts/retired-fixture.sh")
    assert not git(source, "log", "--oneline", "--", "scripts/never-recorded-b2b-fixture.sh")
    assert git(source, "status", "--porcelain") == ""
    foreign = tmp_path / "foreign"
    (foreign / "scripts").mkdir(parents=True)
    (foreign / ".claude/commands").mkdir(parents=True)
    (foreign / "CLAUDE.md").write_text("owned fixture CPP neighbour")
    shutil.copy2(source / "scripts/cpp-host-write.sh", foreign / "scripts/cpp-host-write.sh")
    (foreign / "live.sh").write_bytes(b"foreign exact bytes")
    roots = {}
    for label in ("legacy", "shared"):
        home = tmp_path / label
        farm = home / ".claude/scripts"
        farm.mkdir(parents=True)
        for name in ("cpp-host-write.sh", "retired-fixture.sh", "nonexec-fixture.sh",
                     "never-recorded-b2b-fixture.sh"):
            (farm / name).symlink_to(source / "scripts" / name)
        (farm / "cpp-commands-link.sh").write_bytes(b"personal exact bytes")
        (farm / "cpp-checkout-freshness.sh").mkdir()
        (farm / "cpp-checkout-freshness.sh/personal").write_bytes(b"personal directory bytes")
        (farm / "foreign-live.sh").symlink_to(foreign / "live.sh")
        (farm / "foreign-dangling.sh").symlink_to(foreign / "scripts/foreign-dangling.sh")
        (farm / "renamed.sh").symlink_to(source / "scripts/retired-fixture.sh")
        (farm / "relative.sh").symlink_to(os.path.relpath(source / "scripts/relative.sh", farm))
        roots[label] = farm
    population = set(p.name for p in roots["legacy"].iterdir())
    assert len(population) == 10
    assert set(p.name for p in roots["shared"].iterdir()) == population
    assert all((farm / name).exists() or (farm / name).is_symlink()
               for farm in roots.values() for name in population)
    env = dict(os.environ, HOME=str(tmp_path / "legacy"), CPP_DIR=str(source),
               CPP_DEFER_SURFACES="", PRUNE_CONFIRMED="yes")
    old = subprocess.run(["bash", "-c", LEGACY_STEP5B.replace("<the listed names>", "$HELPER_ORPHANS")],
                         env=env, cwd=tmp_path, capture_output=True, text=True, timeout=90)
    assert old.returncode == 0, old.stderr
    new = ClaudeLinks(tmp_path / "shared", source=source).operate(request(source), verify_only=False)
    assert new.action == "refreshed" and new.after.expected_packages > 0, new
    deleted = {label: {name for name in population
                        if not (farm / name).exists() and not (farm / name).is_symlink()}
               for label, farm in roots.items()}
    assert "retired-fixture.sh" in deleted["legacy"] & deleted["shared"], deleted
    for farm in roots.values():
        assert (farm / "cpp-commands-link.sh").read_bytes() == b"personal exact bytes"
        assert (farm / "cpp-checkout-freshness.sh/personal").read_bytes() == b"personal directory bytes"
    assert (foreign / "live.sh").read_bytes() == b"foreign exact bytes"
    evidence = {"population_per_farm": len(population), "physical_initial_entries": len(population) * 2,
                "legacy_confirmation": "yes", "legacy_deleted": sorted(deleted["legacy"]),
                "shared_deleted": sorted(deleted["shared"]),
                "legacy_deleted_shared_kept": sorted(deleted["legacy"] - deleted["shared"]),
                "shared_deleted_legacy_kept": sorted(deleted["shared"] - deleted["legacy"])}
    print(json.dumps(evidence, sort_keys=True))
    assert deleted["legacy"] - deleted["shared"] == {
        "foreign-dangling.sh", "never-recorded-b2b-fixture.sh", "relative.sh"}, evidence
    assert deleted["shared"] <= deleted["legacy"], evidence


def test_retired_live_target_preserved_and_dangling_target_pruned(source, tmp_path):
    for name in ("retired-live.sh", "retired-gone.sh"):
        path = source / "scripts" / name
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
    git(source, "add", "scripts")
    git(source, "commit", "-qm", "fixture prior executable members")
    home = tmp_path / "home"
    adapter = seed(home, source, ("scripts",))
    assert adapter.operate(request(source), verify_only=False).exit_code == 0
    live = home / ".claude/scripts/retired-live.sh"
    gone = home / ".claude/scripts/retired-gone.sh"
    assert live.is_symlink() and gone.is_symlink()
    git(source, "rm", "scripts/retired-gone.sh")
    target = source / "scripts/retired-live.sh"
    target.chmod(0o644)
    git(source, "add", "scripts")
    git(source, "commit", "-qm", "fixture retire kinds but retain one target")
    assert target.is_file() and not os.access(target, os.X_OK)
    assert live.exists() and gone.is_symlink() and not gone.exists()
    assert git(source, "status", "--porcelain") == ""
    result = adapter.operate(request(source), verify_only=False)
    assert live.is_symlink() and live.exists(), result
    assert not gone.is_symlink()
    assert result.exit_code == 1 and result.after.state == "unmanaged", result
    assert any(c.package == "scripts/retired-live.sh" and c.state == "unmanaged"
               and c.reason == "retired CPP link target still present; preserved for review"
               for c in result.after.conflicts), result
    # The sole remaining conflict is still non-current on an idempotent run.
    again = adapter.operate(request(source), verify_only=False)
    assert again.exit_code == 1 and again.after.state == "unmanaged", again
    assert len(again.after.conflicts) == 1 and live.is_symlink()


def maintained_block(marker):
    document = (CLI.parents[1] / ".claude/commands/cpp/update.md").read_text()
    blocks = [b for b in re.findall(r"```bash\n(.*?)```", document, re.S) if marker in b]
    assert len(blocks) == 1, f"expected one actual maintained block for {marker}"
    return blocks[0]


def run_maintained(source, home, *, finish=False, between="", deferred="", path=None):
    script = maintained_block("# CPP_SHARED_REFRESH")
    if finish:
        script += "\n" + between + "\n" + maintained_block("# CPP_SHARED_FINISH_GUARD")
    script += '\nprintf "\\nCPP_REFRESH_EXIT=%s\\n" "$HOST_REFRESH_EXIT"\n'
    env = dict(os.environ, HOME=str(home), CPP_DIR=str(source), CPP_DEFER_SURFACES=deferred)
    if path is not None:
        assert shutil.which("git", path=path) and shutil.which("python3", path=path)
        assert shutil.which("codex", path=path) is None, "custom PATH must exclude the native CLI"
        env["PATH"] = path
    return subprocess.run(["bash", "-c", script], cwd=home.parent, env=env,
                          capture_output=True, text=True, timeout=180)


@pytest.mark.skipif(not shutil.which("bash"), reason="real maintained fences require bash")
def test_maintained_refresh_repairs_stale_install_without_a_source_pull(source, tmp_path):
    retired_target = source / "scripts/maintained-retired.sh"
    retired_target.write_text("#!/bin/sh\nexit 0\n")
    retired_target.chmod(0o755)
    git(source, "add", "scripts/maintained-retired.sh")
    git(source, "commit", "-qm", "fixture prior managed helper")
    home = tmp_path / "home"
    adapter = seed(home, source)
    assert adapter.operate(request(source), verify_only=False).exit_code == 0
    retired = home / ".claude/scripts/maintained-retired.sh"
    git(source, "rm", "scripts/maintained-retired.sh")
    git(source, "commit", "-qm", "fixture current source retired helper")
    assert retired.is_symlink() and not retired.exists()
    missing = home / ".claude/scripts/cpp-host-write.sh"
    missing.unlink()
    assert not missing.exists() and not missing.is_symlink()
    old = git(source, "rev-parse", "HEAD")
    result = run_maintained(source, home, finish=True)
    assert result.returncode == 0, result.stderr
    assert "CPP_REFRESH_EXIT=0" in result.stdout and "Managed refresh: current" in result.stdout, result.stdout
    assert missing.is_symlink() and missing.readlink() == source / "scripts/cpp-host-write.sh", (
        "shared refresh did not repair missing helper")
    assert not retired.is_symlink()
    assert git(source, "rev-parse", "HEAD") == old
    assert f"Revision: {old}" in result.stdout and "coverage=partial" in result.stdout
    assert "claude-links: current" in result.stdout


@pytest.mark.skipif(not shutil.which("bash"), reason="real maintained fences require bash")
@pytest.mark.parametrize("scenario", ["foreign-only", "personal-seam", "unavailable", "unwritable", "deferred"])
def test_maintained_refresh_reports_actual_preserved_and_unavailable_states(source, tmp_path, scenario):
    home = tmp_path / "home"
    if scenario == "foreign-only":
        personal = home / ".codex/skills/personal/SKILL.md"
        personal.parent.mkdir(parents=True)
        personal.write_bytes(b"personal skill")
        before = tree(home)
        result = run_maintained(source, home)
        assert tree(home) == before
        assert "CPP_REFRESH_EXIT=5" in result.stdout and "not-applicable" in result.stdout, result.stdout
        return
    seed(home, source)
    scripts = home / ".claude/scripts"
    personal = scripts / "cpp-host-write.sh"
    if scenario == "personal-seam":
        personal.unlink()
        personal.write_text('#!/bin/sh\nprintf executed > "$HOME/PERSONAL_SEAM_EXECUTED"\n')
        personal.chmod(0o755)
        assert personal.is_file() and not personal.is_symlink()
        expected = personal.read_bytes()
    elif scenario == "unavailable":
        entry = source / "scripts/cpp-host-update.py"
        git(source, "rm", str(entry.relative_to(source)))
        git(source, "commit", "-qm", "fixture unavailable production entry")
        assert not entry.exists()
    elif scenario == "unwritable":
        scripts.chmod(0o555)
        if os.access(scripts, os.W_OK):
            scripts.chmod(0o755)
            pytest.skip("executing identity can write through mode restriction; no unwritable claim")
        assert not os.access(scripts, os.W_OK), "fixture must be unwritable to the actual executing identity"
    before = tree(home)
    try:
        result = run_maintained(source, home, deferred="~/.claude/scripts" if scenario == "deferred" else "")
    finally:
        scripts.chmod(0o755)
    assert "Managed refresh: current" not in result.stdout, result.stdout
    assert "CPP_REFRESH_EXIT=1" in result.stdout or "CPP_REFRESH_EXIT=4" in result.stdout, result.stdout
    if scenario == "personal-seam":
        assert personal.read_bytes() == expected and not personal.is_symlink()
        assert not (home / "PERSONAL_SEAM_EXECUTED").exists()
        assert "unmanaged" in result.stdout
    elif scenario == "unavailable":
        assert "UNAVAILABLE" in result.stdout
        assert tree(home) == before
    elif scenario == "deferred":
        assert "Managed refresh: failure" in result.stdout
        assert "Claude links deferred to declared owner" in result.stdout
        assert "CPP_REFRESH_EXIT=1" in result.stdout and tree(home) == before
    else:
        assert not (scripts / "stash-worktree-guard.sh").exists()


@pytest.mark.skipif(not shutil.which("bash"), reason="real maintained fences require bash")
def test_maintained_finish_guard_invalidates_a_moved_source(source, tmp_path):
    home = tmp_path / "home"
    seed(home, source)
    old = git(source, "rev-parse", "HEAD")
    between = 'git -C "$CPP_DIR" commit --allow-empty -qm "fixture concurrent source movement"'
    result = run_maintained(source, home, finish=True, between=between)
    assert git(source, "rev-parse", "HEAD") != old
    assert "CPP_REFRESH_EXIT=4" in result.stdout and "revision changed after refresh" in result.stdout, result.stdout
    assert f"Revision: {old}" in result.stdout


@pytest.mark.skipif(not shutil.which("bash"), reason="real maintained fences require bash")
def test_skipped_refresh_is_detected_by_actual_installation_oracle(source, tmp_path, monkeypatch):
    original = maintained_block

    def skip_refresh(marker):
        if marker != "# CPP_SHARED_REFRESH":
            return original(marker)
        return '''HOST_REFRESH_REVISION=$(git -C "$CPP_DIR" rev-parse HEAD)
HOST_REFRESH_EXIT=0
HOST_REFRESH_STATUS="Managed refresh: current (coverage=partial)
Revision: $HOST_REFRESH_REVISION
claude-links: current"
'''

    monkeypatch.setitem(run_maintained.__globals__, "maintained_block", skip_refresh)
    with pytest.raises(AssertionError, match="shared refresh did not repair missing helper"):
        test_maintained_refresh_repairs_stale_install_without_a_source_pull(source, tmp_path)


@pytest.mark.skipif(not shutil.which("bash"), reason="real maintained fences require bash")
@pytest.mark.parametrize("yaml_installs", [False, True])
def test_maintained_codex_refresh_without_codex_cli_or_yaml(source, tmp_path, plain_python, yaml_installs):
    home = tmp_path / "home"
    home.mkdir()
    selected = ["--select", "codex"]
    if yaml_installs:
        selected += ["--select", "claude-topics", "--select", "antigravity"]
    seeded, payload = cli(source, home, "refresh", *selected)
    assert seeded.returncode == 0, payload
    installed = home / ".codex/skills/flow-auto/reference.md"
    old = installed.read_bytes()
    command = source / ".claude/commands/flow/auto.md"
    with command.open("a") as stream:
        stream.write("\nFixture current-source refresh requirement.\n")
    git(source, "add", str(command.relative_to(source)))
    git(source, "commit", "-qm", "fixture changed canonical command")
    revision = git(source, "rev-parse", "HEAD")
    assert b"Fixture current-source refresh requirement." not in old
    adapter = CodexAdapter(home)
    current = request(source)
    build = adapter.build(current.revision, adapter.preflight(current))
    expected = next(p for p in build.packages if p.name == "flow-auto").members["reference.md"].content
    assert expected != old and b"Fixture current-source refresh requirement." in expected
    tools = tmp_path / "tools"
    tools.mkdir()
    for name in ("git", "bash"):
        binary = shutil.which(name)
        assert binary is not None
        (tools / name).symlink_to(binary)
    (tools / "python3").write_text("#!/bin/sh\nexec " + shlex.quote(str(plain_python)) + ' "$@"\n')
    (tools / "python3").chmod(0o755)
    path = str(tools)
    assert shutil.which("git", path=path) == str(tools / "git")
    assert shutil.which("bash", path=path) == str(tools / "bash")
    assert shutil.which("python3", path=path) == str(tools / "python3")
    assert shutil.which("codex", path=path) is None, "fixture must exclude the native CLI"
    result = run_maintained(source, home, finish=True, path=path)
    assert "codex: current" in result.stdout, result.stdout + result.stderr
    if yaml_installs:
        assert "CPP_REFRESH_EXIT=4" in result.stdout and "Managed refresh: UNAVAILABLE" in result.stdout
        for harness in ("claude-topics", "antigravity"):
            assert f"{harness}: unknown" in result.stdout and f"UNAVAILABLE: {harness}:" in result.stdout
        assert "missing module yaml" in result.stdout
    else:
        assert "CPP_REFRESH_EXIT=0" in result.stdout, result.stdout + result.stderr
    assert installed.read_bytes() == expected
    assert git(source, "rev-parse", "HEAD") == revision
