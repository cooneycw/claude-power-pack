"""A defect says where it came from (issue #1697, Part 1).

`Origin:` and `Missed because:` are fixed phrases with closed answer lists. The
lists are written ONCE, in `docs/agents/closing-report-contract.md`. Four other
surfaces repeat or point at them - the issue contract, `/github:issue-create`,
this repository's bug form and the project-neutral form `/project:init`
installs - and this file is what keeps the five from drifting apart.

What it cannot say: whether any session fills the lines honestly. That is a
judgement the counter-model review of a fix makes, and the contract says so.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
CONTRACT = REPO / "docs" / "agents" / "closing-report-contract.md"
ISSUE_CONTRACT = REPO / "docs" / "agents" / "issue-contract.md"
ISSUE_CREATE = REPO / ".claude" / "commands" / "github" / "issue-create.md"
INIT = REPO / ".claude" / "commands" / "project" / "init.md"
REPO_FORM = REPO / ".github" / "ISSUE_TEMPLATE" / "bug-report.yml"
NEUTRAL_FORM = REPO / "templates" / "github" / "ISSUE_TEMPLATE" / "bug-report.yml"
ANCHOR = "closing-report-contract.md#a-report-that-closes-a-defect-says-where-it-came-from"

requires_jq = pytest.mark.skipif(shutil.which("jq") is None, reason="requires jq")
requires_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")


def normalized(text: str) -> str:
    return " ".join(text.split())


def answers(contract: str, marker: str) -> list[str]:
    """The backticked answers between one pair of markers, in order."""
    block = contract.split(f"<!-- {marker} -->", 1)[1].split(f"<!-- /{marker} -->", 1)[0]
    found = re.findall(r"^- `([^`]+)`", block, re.MULTILINE)
    assert found, f"the {marker} list has stopped parsing"
    return found


def origin_answers() -> list[str]:
    return answers(CONTRACT.read_text(encoding="utf-8"), "defect-origin-answers")


def missed_answers() -> list[str]:
    return answers(CONTRACT.read_text(encoding="utf-8"), "defect-missed-answers")


# --- the one place the lists are written --------------------------------------


def test_the_contract_states_both_lines_and_the_closed_lists() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "Origin: <one answer from the first list>" in text
    assert "Missed because: <one answer from the second list>" in text
    assert origin_answers() == ["#<number>", "never worked", "not traced - <what was tried>"]
    assert missed_answers() == [
        "lane not exercised",
        "reader not tested against real output",
        "fixture smaller than real use",
        "test could not fail",
        "no test covered it",
        "changed later by another change",
        "not a defect in earlier work",
    ]


def test_the_contract_says_it_is_the_only_copy_and_what_it_cannot_check() -> None:
    text = normalized(CONTRACT.read_text(encoding="utf-8"))
    assert "This section is the only place the lists are written." in text
    assert "Silence is the one answer not allowed." in text
    assert "One defect, one origin." in text
    assert "Nothing checks that conclusion except the counter-model review of the fix" in text


def test_the_heading_the_other_surfaces_link_to_exists() -> None:
    slug = ANCHOR.split("#", 1)[1]
    heading = "## A report that closes a defect says where it came from"
    assert heading in CONTRACT.read_text(encoding="utf-8")
    assert slug == heading[3:].lower().replace(" ", "-")


# --- the copies, compared ------------------------------------------------------


def prose_drift(name: str, text: str) -> list[str]:
    """Problems with a prose surface that repeats the Origin answers."""
    flat = normalized(text)
    problems = []
    if ANCHOR not in text:
        problems.append(f"{name}: no link to the contract's list")
    for answer in origin_answers():
        key = answer.split(" - ")[0].replace("#<number>", "#N")
        if f"`{key}" not in flat and key != "#N":
            problems.append(f"{name}: does not name the answer {key!r}")
    if "`Origin:`" not in flat:
        problems.append(f"{name}: does not spell the `Origin:` line")
    return problems


def origin_fields(form_text: str) -> tuple[dict, dict]:
    form = yaml.safe_load(form_text)
    by_id = {block.get("id"): block for block in form["body"]}
    assert "origin" in by_id and "origin_ref" in by_id, "the form has no origin field"
    return by_id["origin"], by_id["origin_ref"]


def form_drift(name: str, form_text: str) -> list[str]:
    """Problems with a form's Origin field against the contract's list."""
    origin, reference = origin_fields(form_text)
    options = [str(o) for o in origin["attributes"]["options"]]
    problems = []
    if len(options) != len(origin_answers()):
        problems.append(f"{name}: {len(options)} options for {len(origin_answers())} contract answers")
    lowered = [o.lower() for o in options]
    if not any("issue or pull request" in o for o in lowered):
        problems.append(f"{name}: no option for a delivering issue or pull request")
    for key in ("never worked", "not traced"):
        if key not in lowered:
            problems.append(f"{name}: no option spelled {key!r}")
    for block in (origin, reference):
        if block.get("validations", {}).get("required") is not False:
            problems.append(f"{name}: {block['id']} is required, so 'not looked' cannot be left blank")
    return problems


def test_the_issue_contract_points_at_the_list() -> None:
    assert prose_drift("issue-contract", ISSUE_CONTRACT.read_text(encoding="utf-8")) == []
    flat = normalized(ISSUE_CONTRACT.read_text(encoding="utf-8"))
    assert "`Missed because:`" in flat
    assert "Blank is not an answer; `not traced` is." in flat


def test_issue_create_keeps_what_its_removed_example_alone_carried() -> None:
    """The worked example moved out by #1697 was the only full category list and the only pacing rule."""
    text = normalized(ISSUE_CREATE.read_text(encoding="utf-8"))
    assert "## Example Interaction" not in text
    assert "one question at a time" in text
    form = yaml.safe_load((REPO / ".github" / "ISSUE_TEMPLATE" / "best-practice.yml").read_text(encoding="utf-8"))
    categories = next(b for b in form["body"] if b.get("id") == "category")["attributes"]["options"]
    assert len(categories) >= 5
    for category in categories:
        assert category in text, f"/github:issue-create no longer offers the category {category!r}"


def test_issue_create_does_not_contradict_itself_about_a_routine_bug() -> None:
    text = normalized(ISSUE_CREATE.read_text(encoding="utf-8"))
    assert "how to reproduce it and where the behaviour came from has already satisfied the contract" in text
    assert "Ask the user; never guess a number." in text


def test_issue_create_asks_for_the_origin_on_the_bug_path() -> None:
    text = ISSUE_CREATE.read_text(encoding="utf-8")
    bug_path = text[text.index("**For Bug Report:**") : text.index("### Step 3: Create Issue")]
    assert prose_drift("issue-create", bug_path) == []
    assert "Blank is not an answer." in normalized(bug_path)


@pytest.mark.parametrize("form", [REPO_FORM, NEUTRAL_FORM], ids=["repository", "project-neutral"])
def test_a_bug_form_offers_exactly_the_contracts_answers(form: Path) -> None:
    assert form_drift(form.name, form.read_text(encoding="utf-8")) == []


def test_the_two_forms_carry_the_same_origin_field() -> None:
    assert origin_fields(REPO_FORM.read_text(encoding="utf-8")) == origin_fields(
        NEUTRAL_FORM.read_text(encoding="utf-8")
    )


def test_blank_and_not_traced_are_different_answers_on_the_form() -> None:
    """An unanswered optional dropdown renders `_No response_`; `Not traced` is a choice."""
    origin, _ = origin_fields(NEUTRAL_FORM.read_text(encoding="utf-8"))
    assert origin["type"] == "dropdown"
    assert "Not traced" in origin["attributes"]["options"]
    description = origin["attributes"]["description"]
    assert "unanswered only if you have not looked" in description
    assert '"Not traced" means you looked and could not tell' in description


# --- the comparison can fail: alter one copy at a time -------------------------


def test_a_form_that_drops_an_answer_is_reported() -> None:
    altered = NEUTRAL_FORM.read_text(encoding="utf-8").replace("        - Never worked\n", "")
    problems = form_drift("altered", altered)
    assert any("2 options for 3 contract answers" in p for p in problems)
    assert any("'never worked'" in p for p in problems)


def test_a_form_that_respells_an_answer_is_reported() -> None:
    altered = NEUTRAL_FORM.read_text(encoding="utf-8").replace("- Not traced\n", "- Unknown\n")
    assert form_drift("altered", altered) == ["altered: no option spelled 'not traced'"]


def test_a_form_that_makes_the_field_required_is_reported() -> None:
    text = NEUTRAL_FORM.read_text(encoding="utf-8")
    start = text.index("    id: origin\n")
    altered = text[:start] + text[start:].replace("required: false", "required: true", 1)
    assert any("origin is required" in p for p in form_drift("altered", altered))


def test_a_prose_copy_that_loses_its_link_or_an_answer_is_reported() -> None:
    text = ISSUE_CONTRACT.read_text(encoding="utf-8")
    assert prose_drift("altered", text.replace(ANCHOR, "elsewhere.md")) == [
        "altered: no link to the contract's list"
    ]
    assert prose_drift("altered", text.replace("`never worked`", "never did")) == [
        "altered: does not name the answer 'never worked'"
    ]


# --- the project-neutral form and its install ---------------------------------


def test_the_project_neutral_form_names_nothing_from_this_repository() -> None:
    text = NEUTRAL_FORM.read_text(encoding="utf-8")
    repo_form = yaml.safe_load(REPO_FORM.read_text(encoding="utf-8"))
    components = next(b for b in repo_form["body"] if b.get("id") == "component")["attributes"]["options"]
    for word in (*components, "claude-power-pack", "cooneycw", "/home/", "~/.claude", "Claude Code version"):
        assert word not in text, f"the project-neutral form names {word!r}"


def install_block() -> str:
    text = INIT.read_text(encoding="utf-8")
    match = re.search(r"^    # Bug form \(#1697\)\.\n(    F=.*?\n    fi\n)", text, re.DOTALL | re.MULTILINE)
    assert match, "the bug-form install is no longer in /project:init"
    return match.group(1)


def test_project_init_installs_the_form_inside_the_cpp_setup_block() -> None:
    text = INIT.read_text(encoding="utf-8")
    block = text[text.index("### 4b: CPP Init") : text.index("### 4c: Config Scaffold")]
    assert "templates/github/ISSUE_TEMPLATE/bug-report.yml" in block
    assert NEUTRAL_FORM.is_file()


def run_install(project: Path, cpp_dir: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", install_block()],
        cwd=project, capture_output=True, text=True, check=False,
        env={**os.environ, "CPP_DIR": str(cpp_dir)},
    )


@requires_bash
def test_the_install_copies_the_form_into_a_new_project(tmp_path: Path) -> None:
    assert run_install(tmp_path).returncode == 0
    installed = tmp_path / ".github" / "ISSUE_TEMPLATE" / "bug-report.yml"
    assert installed.read_text(encoding="utf-8") == NEUTRAL_FORM.read_text(encoding="utf-8")


@requires_bash
def test_the_install_never_overwrites_an_existing_form(tmp_path: Path) -> None:
    existing = tmp_path / ".github" / "ISSUE_TEMPLATE" / "bug-report.yml"
    existing.parent.mkdir(parents=True)
    existing.write_text("the project's own form\n", encoding="utf-8")
    result = run_install(tmp_path)
    assert result.returncode == 0 and "NOT installed" not in result.stdout
    assert existing.read_text(encoding="utf-8") == "the project's own form\n"


@requires_bash
def test_the_install_leaves_a_dangling_symlink_alone(tmp_path: Path) -> None:
    link = tmp_path / ".github" / "ISSUE_TEMPLATE" / "bug-report.yml"
    link.parent.mkdir(parents=True)
    link.symlink_to(tmp_path / "gone.yml")
    assert link.is_symlink() and not link.exists()  # the negative precondition: dangling
    result = run_install(tmp_path)
    assert link.is_symlink() and not link.exists()
    assert "NOT installed" not in result.stdout, "an existing entry is not a failed install"


@requires_bash
def test_a_missing_source_form_is_said_not_swallowed(tmp_path: Path) -> None:
    """A CPP checkout older than this change has no form to copy."""
    old_checkout = tmp_path / "old-cpp"
    old_checkout.mkdir()
    assert not (old_checkout / "templates").exists()  # the negative precondition
    project = tmp_path / "project"
    project.mkdir()
    result = run_install(project, cpp_dir=old_checkout)
    assert "Bug form NOT installed" in result.stdout
    assert not (project / ".github" / "ISSUE_TEMPLATE" / "bug-report.yml").exists()


@requires_bash
def test_an_uncreatable_directory_is_said_not_swallowed(tmp_path: Path) -> None:
    (tmp_path / ".github").write_text("a file where the directory should be\n", encoding="utf-8")
    result = run_install(tmp_path)
    assert "Bug form NOT installed" in result.stdout


# --- reading the lines back ----------------------------------------------------


def search_filter() -> str:
    text = CONTRACT.read_text(encoding="utf-8")
    block = re.search(r"```bash\n(gh pr list --state merged.*?)```", text, re.DOTALL)
    assert block, "the read-back command is no longer in the contract"
    assert "--search '\"Missed because:\" in:body'" in block.group(1)
    jq_filter = re.search(r"--jq '(.*)'", block.group(1), re.DOTALL)
    assert jq_filter
    return jq_filter.group(1)


@requires_jq
def test_the_read_back_filter_keeps_exact_lines_and_drops_loose_matches() -> None:
    """GitHub's phrase search is loose, so the filter is what makes the result exact."""
    bodies = [
        {"number": 1, "title": "a fix", "body": "Summary\n\nOrigin: #1696\nMissed because: no test covered it\n"},
        {"number": 2, "title": "a loose match", "body": "we missed because: of rain"},
        {"number": 3, "title": "half a record", "body": "Missed because: lane not exercised\n"},
        {"number": 4, "title": "mid-line mention", "body": "see the Missed because: line in the contract"},
    ]
    result = subprocess.run(
        ["jq", "-r", search_filter()], input=json.dumps(bodies), capture_output=True, text=True, check=True
    )
    assert result.stdout.splitlines() == [
        "#1 Origin: #1696 | Missed because: no test covered it",
        "#3 Missed because: lane not exercised",
    ]


def test_the_contract_says_an_empty_or_full_result_proves_little() -> None:
    text = normalized(CONTRACT.read_text(encoding="utf-8"))
    assert "A result of exactly 200 pull requests is a truncated list" in text
    assert "it does not show that fixes had no origin" in text


# --- the Harness lane: the generated Codex skills ------------------------------


@pytest.fixture(scope="module")
def codex_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("codex-skills")
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "codex-skill-sync.py"), "--write", "--output-root", str(out)],
        capture_output=True, text=True, cwd=REPO, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return out


def skill_text(tree: Path, skill: str) -> str:
    return "".join(
        (tree / skill / name).read_text(encoding="utf-8")
        for name in ("SKILL.md", "reference.md")
        if (tree / skill / name).is_file()
    )


def test_the_generated_issue_create_skill_asks_for_the_origin(codex_tree: Path) -> None:
    text = normalized(skill_text(codex_tree, "github-issue-create"))
    assert "`Origin:` line" in text
    assert "Blank is not an answer." in text


def test_the_generated_project_init_skill_installs_the_form(codex_tree: Path) -> None:
    assert "templates/github/ISSUE_TEMPLATE/bug-report.yml" in skill_text(codex_tree, "project-init")
