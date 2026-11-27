"""Real maintained readers and plain-runtime production installations."""
import base64
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest

from lib.host_update.codex import CodexAdapter
from lib.host_update.links import ClaudeLinks
from lib.host_update.scope import Scope
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


def run_maintained(source, home, *, finish=False, between="", deferred="", path=None,
                   migration=None, before_migration=""):
    env = dict(os.environ, HOME=str(home), CPP_DIR=str(source), CPP_DEFER_SURFACES=deferred)
    if path is not None:
        assert shutil.which("git", path=path) and shutil.which("python3", path=path)
        assert shutil.which("codex", path=path) is None, "custom PATH must exclude the native CLI"
        env["PATH"] = path

    def invoke(script):
        return subprocess.run(["bash", "-c", script], cwd=home.parent, env=env.copy(),
                              capture_output=True, text=True, timeout=180)

    # Every tool call has a fresh process. Only printed literals are bound next.
    result = invoke(bind_managed_literals(maintained_block("# CPP_SHARED_REFRESH"), source))
    outputs, errors, code = [result.stdout], [result.stderr], result.returncode
    revision = next((line.removeprefix("Revision: ") for line in result.stdout.splitlines()
                     if re.fullmatch(r"Revision: [0-9a-f]{40,64}", line)), "")
    names = next((line.removeprefix("Codex migration packages: ").split()
                  for line in result.stdout.splitlines() if line.startswith("Codex migration packages: ")), [])
    if before_migration:
        changed = invoke(before_migration)
        assert changed.returncode == 0, changed.stderr
    if names:
        result = invoke(bind_managed_literals(maintained_block("# CPP_CODEX_MIGRATION"),
                        source, revision, names, "no" if migration is None else migration, code))
        outputs.append(result.stdout)
        errors.append(result.stderr)
        code = result.returncode
    if finish:
        if between:
            changed = invoke(between)
            assert changed.returncode == 0, changed.stderr
        result = invoke(bind_managed_literals(maintained_block("# CPP_SHARED_FINISH_GUARD"), source, revision))
        outputs.append(result.stdout)
        errors.append(result.stderr)
        if result.returncode:
            code = result.returncode
    outputs.append(f"\nCPP_REFRESH_EXIT={code}\n")
    return subprocess.CompletedProcess(["bash", "separate maintained tool calls"], code,
                                       "".join(outputs), "".join(errors))


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
    assert result.returncode == 4 and "CPP_REVISION_GUARD: stable" not in result.stdout


@pytest.mark.skipif(not shutil.which("bash"), reason="real maintained fences require bash")
def test_skipped_refresh_is_detected_by_actual_installation_oracle(source, tmp_path, monkeypatch):
    original = maintained_block

    def skip_refresh(marker):
        if marker != "# CPP_SHARED_REFRESH":
            return original(marker)
        return '''HOST_REFRESH_REVISION=$(git -C "$CPP_DIR" rev-parse HEAD)
HOST_REFRESH_EXIT=0
HOST_MIGRATION_PACKAGES=()
HOST_MIGRATION_COMMAND=""
HOST_REFRESH_STATUS="Managed refresh: current (coverage=partial)
Revision: $HOST_REFRESH_REVISION
claude-links: current"
printf '%s\\n' "$HOST_REFRESH_STATUS"
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


def historical_legacy(home):
    fixture = CLI.parents[1] / "controls/cpp-update-host-refresh/cases/unknown-stale-legacy/case.json"
    data = json.loads(fixture.read_text())
    assert data["historical_commit"] == "5204ea06fa15efa7fec3e1d86fd489c61b85c708"
    assert data["package"] == "cicd-verify" and data["historical_package_count"] == 80
    hashes = {"SKILL.md": "2b1971591ff29a83459286605a8835c9ee3da071b8116c1da67e4f3b1b3d4f21",
              "reference.md": "c771ef571bc5df750918e86a2006400de3d3564a8448255ac91611ead072ee3c"}
    assert set(data["members"]) == set(hashes)
    root = home / ".codex/skills" / data["package"]
    root.mkdir(parents=True)
    for name, member in data["members"].items():
        content = base64.b64decode(member["base64"], validate=True)
        assert hashlib.sha256(content).hexdigest() == hashes[name] == member["sha256"]
        (root / name).write_bytes(content)
        (root / name).chmod(member["mode"])
    assert not (home / ".codex/skills/.cpp-managed/ownership.json").exists()
    return data["package"], root


@pytest.mark.skipif(not shutil.which("bash"), reason="actual maintained migration fences require bash")
@pytest.mark.parametrize("decision", [None, "no", "yes"])
def test_reviewed_historical_legacy_migration(source, tmp_path, monkeypatch, decision):
    home = tmp_path / "home"
    name, package = historical_legacy(home)
    before = {p.name: p.read_bytes() for p in package.iterdir()}
    ledger = home / ".codex/skills/.cpp-managed/ownership.json"
    adapter = CodexAdapter(home)
    current = request(source)
    expected = next(p for p in adapter.build(current.revision, adapter.preflight(current)).packages if p.name == name)
    assert expected.members["reference.md"].content != before["reference.md"]
    # An inherited yes is not this run's user decision.
    monkeypatch.setenv("CODEX_MIGRATION_CONFIRMED", "yes")
    result = run_maintained(source, home, finish=True, migration=decision)
    assert result.returncode == (0 if decision == "yes" else 4), result.stderr
    assert f"--adopt codex:{name}" in result.stdout and "Codex migration packages: " + name in result.stdout
    backups = list((home / ".codex/skills/.cpp-managed/work").glob(f"transaction-*/backup/{name}"))
    if decision != "yes":
        assert "CPP_REFRESH_EXIT=4" in result.stdout and "Codex refresh frozen: migration declined" in result.stdout
        assert {p.name: p.read_bytes() for p in package.iterdir()} == before
        assert not ledger.exists() and not backups
    else:
        assert "CPP_REFRESH_EXIT=0" in result.stdout and "reviewed adoption backup retained" in result.stdout
        assert ledger.exists() and len(backups) == 1
        assert {p.name: p.read_bytes() for p in backups[0].iterdir()} == before
        assert (package / "reference.md").read_bytes() == expected.members["reference.md"].content
        again = run_maintained(source, home)
        assert "CPP_REFRESH_EXIT=0" in again.stdout and "Codex migration packages:" not in again.stdout


@pytest.mark.skipif(not shutil.which("bash"), reason="actual maintained migration fences require bash")
def test_migration_preserves_unexpected_legacy_without_adopting_it(source, tmp_path):
    home = tmp_path / "home"
    name, package = historical_legacy(home)
    unexpected = package.with_name("retired-legacy-fixture")
    shutil.copytree(package, unexpected)
    before = tree(home / ".codex/skills")
    adapter = CodexAdapter(home)
    current = request(source)
    assert "retired-legacy-fixture" in adapter.legacy(Scope(adapter.preflight(current), owner="codex"))
    assert "retired-legacy-fixture" not in {p.name for p in adapter.build(current.revision,
                                                                 adapter.preflight(current)).packages}
    result = run_maintained(source, home, migration="yes")
    assert "CPP_REFRESH_EXIT=4" in result.stdout and "Unexpected legacy packages preserved" in result.stdout
    assert "retired-legacy-fixture: unmanaged" in result.stdout
    assert "--adopt codex:retired-legacy-fixture" not in result.stdout
    assert f"{name}: unknown" in result.stdout
    after = tree(home / ".codex/skills")
    assert {p: row for p, row in after.items() if not p.startswith(".cpp-managed")} == before
    assert not (home / ".codex/skills/.cpp-managed/ownership.json").exists()


@pytest.mark.skipif(not shutil.which("bash"), reason="actual maintained migration fences require bash")
def test_moved_revision_refuses_reviewed_legacy_migration(source, tmp_path):
    home = tmp_path / "home"
    _, package = historical_legacy(home)
    before = tree(package)
    result = run_maintained(source, home, migration="yes",
                            before_migration='git -C "$CPP_DIR" commit --allow-empty -qm "fixture source moved"')
    assert "CPP_REFRESH_EXIT=4" in result.stdout and "revision changed before migration" in result.stdout
    assert tree(package) == before and not (home / ".codex/skills/.cpp-managed/ownership.json").exists()


@pytest.mark.skipif(not shutil.which("bash"), reason="actual maintained migration fences require bash")
def test_identical_legacy_install_does_not_offer_migration(source, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    legacy = subprocess.run([shutil.which("python3"), str(source / "scripts/codex-skill-sync.py"), "--install"],
                            env=dict(os.environ, HOME=str(home), CPP_DEFER_SURFACES=""),
                            capture_output=True, text=True, timeout=120)
    assert legacy.returncode == 0, legacy.stdout + legacy.stderr
    assert not (home / ".codex/skills/.cpp-managed/ownership.json").exists()
    result = run_maintained(source, home)
    assert "CPP_REFRESH_EXIT=0" in result.stdout and "Codex migration packages:" not in result.stdout
    assert "Codex refresh frozen" not in result.stdout


@pytest.mark.skipif(not shutil.which("bash"), reason="actual displayed migration command requires bash")
def test_displayed_legacy_command_is_usable_after_review(source, tmp_path):
    home = tmp_path / "home"
    name, package = historical_legacy(home)
    before = tree(package)
    declined = run_maintained(source, home)
    command = next(line.removeprefix("Codex migration command: ") for line in declined.stdout.splitlines()
                   if line.startswith("Codex migration command: "))
    argv = shlex.split(command)
    assert str(source / "scripts/cpp-host-update.py") in argv
    assert argv[argv.index("--home") + 1] == str(home)
    assert argv[argv.index("--revision") + 1] == git(source, "rev-parse", "HEAD")
    assert argv[argv.index("--adopt") + 1] == "codex:" + name
    assert tree(package) == before and not (home / ".codex/skills/.cpp-managed/ownership.json").exists()
    result = subprocess.run(argv, cwd=tmp_path, env=dict(os.environ, HOME=str(home), CPP_DEFER_SURFACES=""),
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert next(row for row in report["results"] if row["harness"] == "codex")["after"]["state"] == "current"
    backups = list((home / ".codex/skills/.cpp-managed/work").glob(f"transaction-*/backup/{name}"))
    assert len(backups) == 1 and tree(backups[0]) == before


@pytest.mark.skipif(not shutil.which("bash"), reason="actual historical migration fences require bash")
@pytest.mark.parametrize("revision,v13_baseline", [
    ("5204ea06fa15efa7fec3e1d86fd489c61b85c708", False),
    ("40d25173c8c09987fac851cffa565efdc0f11c72", True),
], ids=["real-pre-e32-install", "real-v13-install"])
def test_real_historical_installer_population(source, tmp_path, revision, v13_baseline):
    from tests.conftest import skip_in_partial_clone

    root = CLI.parents[1]
    skip_in_partial_clone(root)
    available = subprocess.run(["git", "-C", str(root), "cat-file", "-e", revision + "^{commit}"],
                               capture_output=True, text=True)
    if available.returncode:
        pytest.skip(f"historical installer {revision[:8]} unavailable; vendored stale case still runs: "
                    + available.stderr.strip())
    old = tmp_path / "historical-source"
    git(tmp_path, "clone", "-q", "--shared", "--no-checkout", str(root), str(old))
    git(old, "config", "core.hooksPath", "/dev/null")
    git(old, "checkout", "-q", "--detach", revision)
    assert git(old, "rev-parse", "HEAD") == revision
    entry = old / "scripts/codex-skill-sync.py"
    assert entry.read_bytes() == subprocess.check_output(["git", "-C", str(root), "show",
                                                         revision + ":scripts/codex-skill-sync.py"])
    home = tmp_path / "home"
    home.mkdir()
    legacy = subprocess.run([sys.executable, str(entry), "--install"], cwd=old,
                            env=dict(os.environ, HOME=str(home), CPP_DEFER_SURFACES="",
                                     GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1"),
                            capture_output=True, text=True, timeout=120)
    assert legacy.returncode == 0, legacy.stdout + legacy.stderr
    skills = home / ".codex/skills"
    assert not (skills / ".cpp-managed/ownership.json").exists()

    def inventory(root):
        return {p.name: {f.relative_to(p).as_posix(): (hashlib.sha256(f.read_bytes()).hexdigest(),
                                                    f.stat().st_mode & 0o777)
                         for f in p.rglob("*") if f.is_file()}
                for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")}

    before = inventory(skills)
    assert len(before) == 80
    adapter = CodexAdapter(home)
    current = request(source)
    build = adapter.build(current.revision, adapter.preflight(current))
    wanted = {p.name: {name: (m.sha256, m.mode) for name, m in p.members.items()} for p in build.packages}
    if v13_baseline:
        data = json.loads((root / "controls/antigravity-skill-build/codex-baseline.json").read_text())
        old_members = {f"{package}/{name}": list(value)
                       for package, members in before.items() for name, value in members.items()}
        new_members = {f"{package}/{name}": list(value)
                       for package, members in wanted.items() for name, value in members.items()}
        assert old_members == data["members"], "the real v13 install must match the immutable historical inventory"
        changed = {name: new_members.get(name) for name in old_members.keys() | new_members.keys()
                   if old_members.get(name) != new_members.get(name)}
        assert changed == {name: row["candidate"] for name, row in data["attributed_input_delta"].items()}, (
            "only owner-attributed input changes may make the historical v13 install stale")
        assert all(row["baseline"] == old_members[name] for name, row in data["attributed_input_delta"].items())
    if before == wanted:
        result = run_maintained(source, home)
        assert "CPP_REFRESH_EXIT=0" in result.stdout and "Codex migration packages:" not in result.stdout
        assert inventory(skills) == before
        assert not list((skills / ".cpp-managed/work").glob("transaction-*/backup"))
    else:
        stale = {name for name in before.keys() & wanted.keys() if before[name] != wanted[name]}
        assert stale
        if v13_baseline:
            assert stale == {name.split("/")[0] for name in data["attributed_input_delta"]}
        else:
            assert "cicd-verify" in stale
        declined = run_maintained(source, home)
        assert "CPP_REFRESH_EXIT=4" in declined.stdout and "Codex refresh frozen: migration declined" in declined.stdout
        names = next(line.removeprefix("Codex migration packages: ").split()
                     for line in declined.stdout.splitlines() if line.startswith("Codex migration packages: "))
        assert set(names) >= stale and inventory(skills) == before
        if v13_baseline:
            assert set(names) == stale, "the two attributed packages alone need reviewed adoption"
        assert not (skills / ".cpp-managed/ownership.json").exists()
        accepted = run_maintained(source, home, migration="yes", finish=True)
        assert "CPP_REFRESH_EXIT=0" in accepted.stdout, accepted.stdout
        assert "codex: unknown -> current" in accepted.stdout, accepted.stdout
        backups = list((skills / ".cpp-managed/work").glob("transaction-*/backup"))
        assert len(backups) == 1 and inventory(backups[0]) == before
        assert inventory(skills) == wanted
        following = run_maintained(source, home)
        assert "CPP_REFRESH_EXIT=0" in following.stdout and "Codex migration packages:" not in following.stdout


def bind_managed_literals(script, source, revision="", names=(), decision="no", initial_exit=0):
    """Only documented literal inputs cross tool calls; no shell state is copied."""
    replacements = {"REPLACE_WITH_CPP_DIR": shlex.quote(str(source)),
                    "REPLACE_WITH_REFRESH_REVISION": shlex.quote(revision),
                    "REPLACE_WITH_REVIEWED_PACKAGES": shlex.join(names),
                    "REPLACE_WITH_DECISION": shlex.quote(decision),
                    "REPLACE_WITH_INITIAL_EXIT": str(initial_exit)}
    for marker, value in replacements.items():
        script = script.replace(marker, value)
    return script


@pytest.mark.skipif(not shutil.which("bash"), reason="actual separate Bash tool calls require bash")
@pytest.mark.parametrize("scenario", ["current", "accepted-migration"])
def test_actual_fences_survive_separate_bash_tool_calls(source, tmp_path, scenario):
    home = tmp_path / "home"
    if scenario == "current":
        seed(home, source)
    else:
        name, package = historical_legacy(home)
        old = (package / "reference.md").read_bytes()
        adapter = CodexAdapter(home)
        current = request(source)
        expected = next(p for p in adapter.build(current.revision, adapter.preflight(current)).packages
                        if p.name == name)
        assert expected.members["reference.md"].content != old, "negative fixture must actually be stale"
    env = dict(os.environ, HOME=str(home), CPP_DIR=str(source), CPP_DEFER_SURFACES="")

    def invoke(marker, revision="", names=(), decision="no", initial_exit=0):
        script = bind_managed_literals(maintained_block(marker), source, revision, names, decision, initial_exit)
        # A new process and fresh environment for every real tool call.
        return subprocess.run(["bash", "-c", script], cwd=tmp_path,
                              env=dict(env, CODEX_MIGRATION_CONFIRMED=decision),
                              capture_output=True, text=True, timeout=180)

    initial = invoke("# CPP_SHARED_REFRESH")
    revision = next(line.removeprefix("Revision: ") for line in initial.stdout.splitlines()
                    if re.fullmatch(r"Revision: [0-9a-f]{40,64}", line))
    assert revision == git(source, "rev-parse", "HEAD")
    assert initial.returncode == (4 if scenario == "accepted-migration" else 0), initial.stdout + initial.stderr
    if scenario == "accepted-migration":
        names = next(line.removeprefix("Codex migration packages: ").split()
                     for line in initial.stdout.splitlines() if line.startswith("Codex migration packages: "))
        migrated = invoke("# CPP_CODEX_MIGRATION", revision, names, "yes", 4)
        assert (package / "reference.md").read_bytes() != old, migrated.stdout + migrated.stderr
        assert (home / ".codex/skills/.cpp-managed/ownership.json").is_file()
    finished = invoke("# CPP_SHARED_FINISH_GUARD", revision)
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "CPP_REVISION_GUARD: stable" in finished.stdout, finished.stdout + finished.stderr


def cross_fence_dependencies(document):
    """Audit each Bash scope separately, including guarded/defaulted old state."""
    shellcheck = shutil.which("shellcheck")
    assert shellcheck, "UNAVAILABLE: shellcheck is required for the complete fence audit"
    previous, functions, findings = set(), set(), set()
    blocks = re.findall(r"```bash\n(.*?)```", document, re.S)
    assert blocks, "UNAVAILABLE: no Bash population extracted"
    for index, body in enumerate(blocks, 1):
        checked = subprocess.run([shellcheck, "--enable=check-unassigned-uppercase", "-s", "bash", "-f", "json", "-"],
                                 input=body, capture_output=True, text=True)
        comments = json.loads(checked.stdout)
        for row in comments:
            if 1000 <= row["code"] < 1100 and row["level"] == "error":
                findings.add((index, "parse-error", str(row["code"])))
        # Quoted heredoc bodies are data, not shell references or definitions.
        lines, delimiter = [], None
        for line in body.splitlines():
            if delimiter is not None:
                if line.strip() == delimiter:
                    delimiter = None
                continue
            if line.lstrip().startswith("#"):
                continue
            lines.append(line)
            opener = re.search(r"<<-?\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]", line)
            if opener:
                delimiter = opener.group(1)
        shell = "\n".join(lines)
        required = set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*):\?", shell))
        required.update(re.findall(r"\[\[.*declare -p ([A-Za-z_][A-Za-z0-9_]*).*\]\] \|\| exit 4", shell))
        # Collect definitions in this fence; separately check reads outside
        # conditional assignments below.
        local = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)=", shell)) | required
        local.update(re.findall(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b", shell))
        for match in re.finditer(r"\bread\s+-r\s+([^;\n]+)", shell):
            local.update(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", match.group(1)))
        references = set(re.findall(r"(?<!\\)\$(?:\{[#!]?)?([A-Za-z_][A-Za-z0-9_]*)", shell))
        references.update(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\+=", shell))
        # A conditional assignment cannot supply a later top-level read on
        # the branch that skipped it (the old finish-status bug).
        top_lines = "\n".join(line for line in shell.splitlines() if line and not line[0].isspace())
        top_references = set(re.findall(r"(?<!\\)\$(?:\{[#!]?)?([A-Za-z_][A-Za-z0-9_]*)", top_lines))
        top_local = set(re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)=", shell)) | required
        for name in (top_references & previous) - top_local:
            findings.add((index, "variable", name))
        for name in (references & previous) - local:
            findings.add((index, "variable", name))
        for row in comments:
            if row["code"] == 2154:
                name = row["message"].split()[0]
                if name not in required:
                    findings.add((index, "variable", name))
        current_functions = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{", shell))
        for name in functions - current_functions:
            if re.search(r"(?:^|\s|;)" + re.escape(name) + r"(?:\s|$)", shell):
                findings.add((index, "function", name))
        previous.update(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)=", shell))
        functions.update(current_functions)
    return len(blocks), sorted(findings)


@pytest.mark.skipif(not shutil.which("shellcheck"), reason="shellcheck required for actual fence binding audit")
def test_all_update_fences_have_explicit_per_call_inputs():
    document = (CLI.parents[1] / ".claude/commands/cpp/update.md").read_text()
    count, findings = cross_fence_dependencies(document)
    print("Actual Bash scopes:", count, "unresolved per-fence dependencies:", findings)
    assert count == 49, "the complete maintained Bash population must be examined"
    assert not findings, findings


@pytest.mark.skipif(not shutil.which("shellcheck"), reason="shellcheck required for audit negative controls")
def test_cross_fence_audit_detects_lost_variable_and_function():
    bad = '```bash\nCPP_BOUND_INPUT=observed\ncpp_bound_function() { :; }\n```\n'
    bad += '```bash\nprintf "%s\\n" "$CPP_BOUND_INPUT"\ncpp_bound_function\n```\n'
    bad += '```bash\nif false; then\n  CPP_BOUND_INPUT=skipped\nfi\nprintf "%s\\n" "$CPP_BOUND_INPUT"\n```\n'
    count, findings = cross_fence_dependencies(bad)
    assert count == 3
    assert (3, "variable", "CPP_BOUND_INPUT") in findings
    assert (2, "variable", "CPP_BOUND_INPUT") in findings
    assert (2, "function", "cpp_bound_function") in findings
    good = '```bash\n: "${CPP_BOUND_INPUT:?bind literal in this call}"\nprintf "%s\\n" "$CPP_BOUND_INPUT"\n```\n'
    assert cross_fence_dependencies(good) == (1, [])


@pytest.mark.skipif(not shutil.which("bash"), reason="actual literal refusal fences require bash")
@pytest.mark.parametrize("marker,malformation", [
    (marker, problem)
    for marker in ("# CPP_SHARED_REFRESH", "# CPP_CODEX_MIGRATION", "# CPP_SHARED_FINISH_GUARD")
    for problem in ("unbound", "bad-root", "bad-revision", "bad-consent", "bad-package")
    if not (problem in ("bad-consent", "bad-package") and marker != "# CPP_CODEX_MIGRATION"
            or problem == "bad-revision" and marker == "# CPP_SHARED_REFRESH")
])
def test_managed_fences_refuse_unbound_or_malformed_literals(source, tmp_path, marker, malformation):
    script = maintained_block(marker)
    if malformation != "unbound":
        script = bind_managed_literals(script, source if malformation != "bad-root" else "relative-root",
                    "malformed" if malformation == "bad-revision" else git(source, "rev-parse", "HEAD"),
                    ["../foreign" if malformation == "bad-package" else "cicd-verify"],
                    "unreviewed" if malformation == "bad-consent" else "yes", 4)
    home = tmp_path / "refusal-home"
    home.mkdir()
    before = tree(home)
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            env=dict(os.environ, HOME=str(home), CPP_DIR=str(source)),
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 4 and tree(home) == before
    assert "CPP_REVISION_GUARD: stable" not in result.stdout


def assert_shared_executable_population(source):
    """Read the real manifest against an owned on-disk executable population."""
    for name, mode in (("manifest-extensionless", 0o755), ("manifest-python.py", 0o755),
                       ("manifest-not-executable.sh", 0o644), ("manifest-directory/child", 0o755)):
        path = source / "scripts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture source bytes\n")
        path.chmod(mode)
        git(source, "add", "scripts/" + name)
    git(source, "commit", "-qm", "fixture immediate executable membership")
    executable = source / "scripts/manifest-extensionless"
    nonexecutable = source / "scripts/manifest-not-executable.sh"
    assert executable.is_file() and executable.stat().st_mode & 0o111
    assert nonexecutable.is_file() and not nonexecutable.stat().st_mode & 0o111
    assert (source / "scripts/manifest-directory").is_dir()
    members = ClaudeLinks(source.parent / "population-home", source=source).manifest(request(source))["scripts"]
    assert members, "shared executable manifest must have a nonzero population"
    assert {"manifest-extensionless", "manifest-python.py"} <= set(members), (
        "shared executable manifest lost non-shell helper")
    assert "manifest-not-executable.sh" not in members, "shared executable manifest included non-executable"
    assert "manifest-directory" not in members, "shared executable manifest included directory"
    return members


@pytest.mark.skipif(not shutil.which("bash"), reason="shared manifest consumers retain init Bash coupling")
@pytest.mark.parametrize("consumer", ["install-drift", "permissions", "stable-path"])
@pytest.mark.parametrize("fault", ["missing-non-shell", "included-non-executable"])
def test_shared_manifest_readers_reject_wrong_members(source, monkeypatch, consumer, fault):
    original = ClaudeLinks.manifest

    def broken(self, current):
        result = original(self, current)
        members = result["scripts"]
        assert "manifest-extensionless" in members and "manifest-not-executable.sh" not in members
        if fault == "missing-non-shell":
            del members["manifest-extensionless"]
        else:
            members["manifest-not-executable.sh"] = members["manifest-python.py"]
        return result

    monkeypatch.setattr(ClaudeLinks, "manifest", broken)
    with pytest.raises(AssertionError, match="shared executable manifest") as caught:
        if consumer == "install-drift":
            from tests.test_install_drift import test_the_installer_loops_still_read_the_filter_this_axis_assumes
            test_the_installer_loops_still_read_the_filter_this_axis_assumes(source)
        elif consumer == "permissions":
            from tests.test_permissions_template_link_parity import test_link_loop_docs_use_the_widened_executable_gate
            document = CLI.parents[1] / ".claude/commands/cpp/update.md"
            test_link_loop_docs_use_the_widened_executable_gate(document, source)
        else:
            from tests.test_stable_path_scripts_installable import test_the_installer_gate_is_still_executability
            test_the_installer_gate_is_still_executability(source)
    print(consumer, fault, "RED assertion:", str(caught.value).splitlines()[0])
