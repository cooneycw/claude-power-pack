"""`lib/cicd/makefile.py` over the shared declaration reader (issue #1162).

The parser that stood in `parse_makefile` stopped at the first PHYSICAL line of
a rule and took a trailing backslash as a dependency name. These pin the two
things that fixed: the count, and the consumer whose advice it inverted.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from lib.cicd.makefile import _generate_inline, check_makefile, parse_makefile
from lib.cicd.models import Framework, FrameworkInfo, PackageManager

# `unsupported_targets` is imported INSIDE the tests that use it, not here.
# A module-level import of a name the pre-fix code lacks makes the whole file
# fail collection with an ImportError - which is a red, but a red about a
# missing symbol rather than about behaviour. The continuation and consumer
# tests below must be able to RUN against the old parser and fail on what it
# ANSWERS (issue #1162).


def _write(root: Path, text: str) -> Path:
    (root / "Makefile").write_text(text)
    return root


class TestContinuationLines:
    """A rule's prerequisites do not end at its first physical line."""

    def test_a_continued_prerequisite_list_is_read_whole(self, tmp_path):
        """Measured on the old parser: ['build', '\\'] - two wrong answers.

        The backslash became a dependency NAME, and everything after the first
        line was lost. This repository's own `verify` returned 9 of 29 that
        way, the ninth a literal backslash.
        """
        _write(
            tmp_path,
            "test:\n\t@true\nlint:\n\t@true\nbuild:\n\t@true\n"
            "deploy: build \\\n\ttest lint\n\t@echo deploying\n",
        )
        targets = {t.name: t for t in parse_makefile(tmp_path)}
        assert targets["deploy"].dependencies == ["build", "test", "lint"]
        assert "\\" not in targets["deploy"].dependencies

    def test_the_continuation_does_not_leak_into_the_recipe(self, tmp_path):
        """The SECOND wrong answer from the same bug.

        A continued prerequisite line is tab-indented, so the old parser's
        "collect tab-indented lines as commands" loop swallowed it: the recipe
        reader then saw `test lint` as a command that does not exist, and the
        bare-interpreter check ran against it.
        """
        _write(
            tmp_path,
            "test:\n\t@true\nlint:\n\t@true\nbuild:\n\t@true\n"
            "deploy: build \\\n\ttest lint\n\t@echo deploying\n",
        )
        targets = {t.name: t for t in parse_makefile(tmp_path)}
        assert targets["deploy"].commands == ["@echo deploying"]

    def test_a_long_continued_rule_is_read_in_order_and_whole(self, tmp_path):
        """Parser correctness, on a fixture this test OWNS.

        The repository pin below is a tripwire, not this: a legitimate 30th
        gate reds it with a perfectly correct parser, so it cannot tell "the
        parser regressed" from "a neighbour edited the Makefile" (counter-model
        review). This can - the expected sequence is written here, so its red
        means exactly one thing.
        """
        names = [f"check-{i:02d}" for i in range(12)]
        rule = "verify: " + " \\\n\t".join(names) + "\n\t@true\n"
        bodies = "".join(f"{n}:\n\t@true\n" for n in names)
        _write(tmp_path, bodies + rule)
        deps = {t.name: t for t in parse_makefile(tmp_path)}["verify"].dependencies
        assert deps == names, deps

    def test_THIS_repository_verify_rule_is_read_whole(self):
        """A TRIPWIRE on the live Makefile, and it is labelled as one.

        It cannot discriminate, and that is inherent: a legitimate 30th gate
        reds it with an unchanged parser. It is kept anyway because the number
        is load-bearing elsewhere - `verify-coverage-check` and
        `check-ci-coverage` derive their whole population from this reader, and
        9-of-29 is the shape this issue is about. The sibling test above owns
        parser correctness on a fixture nobody else edits.

        IF THIS REDS: check whether the Makefile gained or lost a `verify`
        prerequisite. If it did, update the number - that is not a defect. If
        it did not, the reader changed, and the sibling test should be red too.
        """
        root = Path(__file__).resolve().parent.parent
        targets = {t.name: t for t in parse_makefile(root)}
        deps = targets["verify"].dependencies
        assert len(deps) == 41, (
            f"expected 41 prerequisites, got {len(deps)}: {deps}. If the "
            f"Makefile changed, update the number; if it did not, the "
            f"declaration reader changed and two registered gates derive "
            f"their population from it"
        )
        assert all("\\" not in d for d in deps), deps
        for required in ("lint", "test", "typecheck"):
            assert required in deps


class TestTheConsumerThatInvertedItsAdvice:
    """`check_makefile`'s deploy advisory, which the bug turned upside down."""

    def test_a_deploy_with_continued_quality_prerequisites_is_not_flagged(
        self, tmp_path
    ):
        """It declared `test lint`; the old reader said it declared neither.

        The advisory told the author to add prerequisites they already had -
        the worst shape for a lint, because following it is a no-op and
        ignoring it teaches the reader to ignore the next one too.
        """
        _write(
            tmp_path,
            "test:\n\t@true\nlint:\n\t@true\nbuild:\n\t@true\n"
            "deploy: build \\\n\ttest lint\n\t@echo deploying\n",
        )
        flagged = [i for i in check_makefile(tmp_path).issues if "deploy" in i]
        assert flagged == [], flagged

    def test_a_deploy_that_really_lacks_them_is_still_flagged(self, tmp_path):
        """The guard on the fix: it must not have simply stopped reporting.

        A check that went quiet would pass the test above for the wrong
        reason, so the negative membership is asserted beside it.
        """
        _write(tmp_path, "build:\n\t@true\ndeploy: build\n\t@echo deploying\n")
        flagged = [i for i in check_makefile(tmp_path).issues if "deploy" in i]
        assert any("without test/lint dependencies" in i for i in flagged), flagged


class TestWhatItCannotReadIsNamed:
    """The refusal discipline, carried out of the reader to its callers."""

    def test_an_unvalidatable_rule_name_is_reported(self, tmp_path):
        _write(tmp_path, "%.o: %.c\n\t@true\nlint:\n\t@true\n")
        from lib.cicd.makefile import unsupported_targets

        assert unsupported_targets(tmp_path) == [("%.o", 1)]

    def test_check_makefile_says_its_population_was_incomplete(self, tmp_path):
        """Otherwise a clean report means "everything I could parse".

        Every other finding in that report is a claim about a population. One
        that silently dropped a rule supports a narrower claim than it makes,
        which is the detector contract this repository holds its checks to.
        """
        _write(tmp_path, "%.o: %.c\n\t@true\nlint:\n\t@true\n")
        issues = check_makefile(tmp_path).issues
        assert any("not one this reader can validate" in i for i in issues), issues

    def test_an_ordinary_makefile_reports_no_such_caveat(self, tmp_path):
        """The caveat must be earned, not printed on everything."""
        _write(tmp_path, "lint:\n\t@true\ntest:\n\t@true\n")
        from lib.cicd.makefile import unsupported_targets

        assert unsupported_targets(tmp_path) == []
        issues = check_makefile(tmp_path).issues
        assert not any("not one this reader can validate" in i for i in issues)


class TestPhonyAndProvenance:
    """Two counter-model findings against the extraction itself."""

    def test_phony_survives_the_move_to_the_shared_reader(self, tmp_path):
        """Measured: before True, after False, on every target in every Makefile.

        The shared reader drops special targets from the rule loop - correct,
        `.PHONY` is not a target anyone runs - and the adapter read `.PHONY`
        out of `prereqs`, where a special target has no entry. So `is_phony`
        silently became False everywhere, and the first draft of these tests
        compared dependencies only and never saw it.
        """
        _write(tmp_path, ".PHONY: lint test\nlint:\n\t@true\ntest:\n\t@true\n")
        assert {t.name: t.is_phony for t in parse_makefile(tmp_path)} == {
            "lint": True,
            "test": True,
        }

    def test_a_continued_phony_declaration_is_read_whole_too(self, tmp_path):
        """The same continuation bug, one directive over."""
        _write(
            tmp_path,
            ".PHONY: lint test \\\n\tbuild\n"
            "lint:\n\t@true\ntest:\n\t@true\nbuild:\n\t@true\n",
        )
        assert all(t.is_phony for t in parse_makefile(tmp_path))

    def test_a_non_phony_target_is_still_reported_as_such(self, tmp_path):
        """The negative membership: the fix must not make everything phony."""
        _write(tmp_path, ".PHONY: lint\nlint:\n\t@true\nbuild:\n\t@true\n")
        phony = {t.name: t.is_phony for t in parse_makefile(tmp_path)}
        assert phony == {"lint": True, "build": False}


class TestOneReaderNotThree:
    """The extraction's own property: the same answer from both entry points."""

    def test_parse_makefile_agrees_with_the_declaration_reader(self):
        """They are the same reader now; a divergence means a second parser.

        This is the test that would red if someone "helpfully" re-implemented
        parsing inside `lib/cicd/makefile.py` again.
        """
        from lib.cicd.makefile_declaration import Makefile as Declaration

        root = Path(__file__).resolve().parent.parent
        declared = Declaration((root / "Makefile").read_text())
        adapted = {t.name: t.dependencies for t in parse_makefile(root)}
        for name in declared.order:
            assert adapted[name] == list(declared.prereqs[name]), name


class TestSharedRecipeSurvivesARedeclaration:
    """A later rule naming ONE target of a multi-target rule (issue #1259).

    `build deploy: test` gives both targets one recipe. A later `build: lint`
    only adds a prerequisite - make keeps the shared recipe - but the reader
    overwrote the group with `["build"]`, so `deploy` resolved to an EMPTY
    recipe and `scripts_invoked("deploy")` reported that it runs nothing.
    """

    TEXT = (
        "build deploy: test\n"
        "\t@bash scripts/shared-step.sh\n"
        "\n"
        "build: lint\n"
    )

    def test_the_sibling_keeps_the_shared_recipe(self):
        from lib.cicd.makefile_declaration import Makefile as Declaration

        mk = Declaration(self.TEXT)
        assert "scripts/shared-step.sh" in mk.recipe_text("deploy")
        assert mk.scripts_invoked("deploy") == {"shared-step.sh"}
        # ...and the redeclared target itself still has it, plus its new prereq.
        assert "scripts/shared-step.sh" in mk.recipe_text("build")
        assert mk.prereqs["build"] == ["test", "lint"]

    def test_a_second_group_led_by_the_same_target_is_kept_too(self):
        from lib.cicd.makefile_declaration import Makefile as Declaration

        mk = Declaration(self.TEXT + "build package:\n\t@bash scripts/pack.sh\n")
        # EXACT sets: a neighbouring rule's recipe must not leak into deploy,
        # which is what GNU make's dry run shows (counter-model review).
        assert mk.scripts_invoked("deploy") == {"shared-step.sh"}
        assert mk.scripts_invoked("package") == {"pack.sh"}

    @pytest.mark.parametrize("sibling", ["build", "deploy"])
    def test_a_later_recipe_REPLACES_the_inherited_one(self, sibling):
        """make runs only the newer recipe (counter-model re-review), for the
        leading target and a non-leading sibling alike."""
        from lib.cicd.makefile_declaration import Makefile as Declaration

        mk = Declaration(self.TEXT + f"{sibling}:\n\t@bash scripts/replacement.sh\n")
        assert mk.scripts_invoked(sibling) == {"replacement.sh"}
        other = "deploy" if sibling == "build" else "build"
        assert mk.scripts_invoked(other) == {"shared-step.sh"}

    def test_a_target_outside_every_group_still_has_no_recipe(self):
        """The negative membership: the fix must not hand recipes to strangers."""
        from lib.cicd.makefile_declaration import Makefile as Declaration

        mk = Declaration(self.TEXT + "other: build\n")
        assert mk.recipe_text("other") == ""


_THREE_RULES = "lint:\n\t@true\ntest:\n\t@true\nbuild:\n\t@true\n"


class TestCheckReadsPhonyThroughTheReader:
    """`check_makefile` reports `.PHONY` from the declaration reader (#1692).

    It used to re-read the file with a one-line regex beside the reader, and
    the regex answer was the one printed.
    """

    def test_a_continued_declaration_is_read_whole(self, tmp_path):
        _write(tmp_path, ".PHONY: lint test \\\n\tbuild\n" + _THREE_RULES)
        result = check_makefile(tmp_path)
        assert result.phony_declared == ["build", "lint", "test"]
        assert result.phony_missing == []

    def test_a_space_before_the_colon_still_declares(self, tmp_path):
        _write(tmp_path, ".PHONY : lint test build\n" + _THREE_RULES)
        result = check_makefile(tmp_path)
        assert result.phony_declared == ["build", "lint", "test"]
        assert result.phony_missing == []

    def test_a_trailing_comment_is_not_a_declared_name(self, tmp_path):
        _write(tmp_path, ".PHONY: lint test build # all three\n" + _THREE_RULES)
        assert check_makefile(tmp_path).phony_declared == ["build", "lint", "test"]

    def test_an_undeclared_target_is_still_reported_missing(self, tmp_path):
        """The other verdict: the fix must not pass by reporting nothing."""
        _write(tmp_path, ".PHONY: lint test\n" + _THREE_RULES)
        result = check_makefile(tmp_path)
        assert result.phony_declared == ["lint", "test"]
        assert result.phony_missing == ["build"]

    def test_known_limit_a_variable_in_phony_is_not_expanded(self, tmp_path):
        """KNOWN LIMIT, not a bug to rediscover: no reader here expands make
        variables, so targets declared through one read as missing."""
        _write(tmp_path, "T = lint test build\n.PHONY: $(T)\n" + _THREE_RULES)
        result = check_makefile(tmp_path)
        assert result.phony_declared == ["$(T)"]
        assert result.phony_missing == ["lint", "test", "build"]


# --- a scaffold cannot report a deployment that deployed nothing (#1712) -----
#
# Every template, the example Makefile and the inline generator used to ship a
# live `deploy` target whose recipe only printed a TODO. It exited 0, and
# /flow:deploy and /flow:auto Step 9 read exit 0 as "deployed". The block is
# now commented out, so there is no target to succeed.

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = sorted((REPO / "templates" / "makefiles").glob("*.mk")) + [REPO / "templates" / "Makefile.example"]
requires_make = pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")

#: /flow:auto Step 9's own test for "a deploy target exists", read from the document.
STEP9_TEST = 'grep -q "^deploy:" Makefile'


def _scaffolds() -> list[tuple[str, str]]:
    found = [(path.name, path.read_text(encoding="utf-8")) for path in TEMPLATES]
    # As detection fills it: `deploy` among the recommended targets, which is
    # what puts it on the generator's .PHONY line.
    detected = FrameworkInfo(
        Framework.PYTHON, PackageManager.UV,
        recommended_targets=["lint", "test", "typecheck", "format", "build", "deploy", "clean", "verify"],
    )
    found.append(("inline-generator", _generate_inline(detected)))
    bare = FrameworkInfo(Framework.UNKNOWN, PackageManager.UNKNOWN)
    found.append(("inline-generator-unknown", _generate_inline(bare)))
    return found


def test_the_step9_test_is_still_the_one_the_document_uses() -> None:
    document = (REPO / ".claude" / "commands" / "flow" / "auto.md").read_text(encoding="utf-8")
    assert STEP9_TEST in document, "auto.md no longer tests for a deploy target this way; update STEP9_TEST"


def test_every_scaffold_was_found() -> None:
    assert len(TEMPLATES) == 10, [path.name for path in TEMPLATES]


@requires_make
@pytest.mark.parametrize(("name", "text"), _scaffolds(), ids=[name for name, _ in _scaffolds()])
def test_a_fresh_scaffold_has_no_deploy_target_and_cannot_report_one(tmp_path: Path, name: str, text: str) -> None:
    (tmp_path / "Makefile").write_text(text, encoding="utf-8")
    assert "deploy" not in {target.name for target in parse_makefile(tmp_path)}
    step9 = subprocess.run(["sh", "-c", STEP9_TEST], cwd=tmp_path, check=False)
    assert step9.returncode != 0, f"{name}: /flow:auto Step 9 would find a deploy target and run it"
    ran = subprocess.run(["make", "deploy"], cwd=tmp_path, capture_output=True, text=True, check=False)
    # A `deploy` left in .PHONY with no rule makes this exit 0 with "Nothing to
    # be done for 'deploy'": the first version of this change did exactly that.
    assert ran.returncode != 0, f"{name}: `make deploy` exited 0 with no deploy steps: {ran.stdout}"
    missing = check_makefile(tmp_path).missing_recommended
    assert "deploy" in missing, f"{name}: the checker does not say deploy is missing"


def _deploy_md_step3() -> str:
    """`/flow:deploy` Step 3, the document's own "does the target exist" block."""
    import re

    text = (REPO / ".claude" / "commands" / "flow" / "deploy.md").read_text(encoding="utf-8")
    section = text[text.index("### Step 3: Verify Target Exists") :]
    block = re.search(r"```bash\n(.*?)```", section, re.DOTALL)
    assert block and 'grep -q "^${TARGET}:" Makefile' in block.group(1), "Step 3 no longer tests for the rule"
    return block.group(1)


@requires_make
@pytest.mark.parametrize("kind", ["directory", "file"])
def test_a_project_that_has_something_named_deploy_is_still_not_deployed_by_the_flows(
    tmp_path: Path, kind: str
) -> None:
    """Counter-model review: with a `deploy` file or directory, bare `make deploy` exits 0.

    That is make's own answer ("'deploy' is up to date"), and removing the rule
    cannot change it. What must hold is that neither flow reaches `make deploy`:
    both test for a deploy RULE first, and a scaffold has none.
    """
    text = (REPO / "templates" / "makefiles" / "python-uv.mk").read_text(encoding="utf-8")
    (tmp_path / "Makefile").write_text(text, encoding="utf-8")
    if kind == "directory":
        (tmp_path / "deploy").mkdir()
    else:
        (tmp_path / "deploy").write_text("notes\n", encoding="utf-8")
    bare = subprocess.run(["make", "deploy"], cwd=tmp_path, capture_output=True, text=True, check=False)
    assert bare.returncode == 0, "precondition: this is the state where bare make reports success"
    assert subprocess.run(["sh", "-c", STEP9_TEST], cwd=tmp_path, check=False).returncode != 0
    step3 = subprocess.run(
        ["bash", "-c", _deploy_md_step3()], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert step3.returncode == 1 and "No 'deploy' target in Makefile" in step3.stdout


@requires_make
def test_a_project_with_a_real_deploy_target_is_found_and_run(tmp_path: Path) -> None:
    """Project state, the other value: the owner has written real deploy steps."""
    text = (REPO / "templates" / "makefiles" / "python-uv.mk").read_text(encoding="utf-8")
    (tmp_path / "Makefile").write_text(text + "\ndeploy:\n\t@echo deployed-for-real\n", encoding="utf-8")
    assert subprocess.run(["sh", "-c", STEP9_TEST], cwd=tmp_path, check=False).returncode == 0
    ran = subprocess.run(["make", "deploy"], cwd=tmp_path, capture_output=True, text=True, check=False)
    assert ran.returncode == 0 and "deployed-for-real" in ran.stdout


def test_the_commented_block_can_be_uncommented_into_a_working_target() -> None:
    """The instructions left in the scaffold are a real target once the `# ` is removed."""
    for name, text in _scaffolds():
        assert "\n# deploy:" in text, f"{name}: no commented deploy block to uncomment"
        assert "<your deploy command>" in text, name
