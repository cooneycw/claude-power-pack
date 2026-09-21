"""`lib/cicd/makefile.py` over the shared declaration reader (issue #1162).

The parser that stood in `parse_makefile` stopped at the first PHYSICAL line of
a rule and took a trailing backslash as a dependency name. These pin the two
things that fixed: the count, and the consumer whose advice it inverted.
"""

from __future__ import annotations

from pathlib import Path

from lib.cicd.makefile import check_makefile, parse_makefile

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
        assert len(deps) == 31, (
            f"expected 31 prerequisites, got {len(deps)}: {deps}. If the "
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
