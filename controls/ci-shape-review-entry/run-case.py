"""Exercise the actual review CLI with controlled qualification and reviewer processes."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.test_ci_shape_review_entry import observe  # noqa: E402


def exercise():
    gate, case = map(Path, sys.argv[1:3])
    output = []
    with tempfile.TemporaryDirectory(prefix="cpp-review-entry-control-") as owned:
        observations = []
        for only in (False, True):
            temporary = Path(owned) / str(only)
            temporary.mkdir()
            answer, spec, reviewer, qualification = observe(
                case, temporary, gate, qualification_only=only)
            invoked = "exec" in reviewer
            if spec["project"] != "claude-power-pack" and qualification:
                return 1, "".join(output) + "CI_SHAPE_REVIEW_CONTROL: refused - neighbor ran CPP qualification\n"
            expected_calls = [] if (spec.get("identity_error")
                                   or spec["project"] != "claude-power-pack") else ["ci-shape-check"]
            if answer.returncode == 0 and (only or invoked):
                observations.append("GOOD")
            elif (not invoked and answer.returncode == 1 and qualification == expected_calls
                  and "CODEX_REVIEW: blocked" in answer.stdout + answer.stderr):
                observations.append("BAD")
            else:
                output.append(answer.stdout + answer.stderr + "\n")
                observations.append("UNKNOWN")
        if observations == ["GOOD", "GOOD"]:
            return 0, "".join(output) + "CI_SHAPE_REVIEW_CONTROL: admitted - both entries permit review\n"
        if observations == ["BAD", "BAD"]:
            return 1, "".join(output) + "CI_SHAPE_REVIEW_CONTROL: refused - both entries prevent review\n"
        return 2, "".join(output) + "CI_SHAPE_REVIEW_CONTROL: unavailable - entries disagree or could not be examined\n"


def main():
    code, output = exercise()
    print(output, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
