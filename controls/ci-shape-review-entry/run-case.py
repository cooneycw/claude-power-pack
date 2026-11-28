"""Exercise the actual review CLI with controlled qualification and reviewer processes."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.test_ci_shape_review_entry import observe  # noqa: E402


def main():
    gate, case = map(Path, sys.argv[1:3])
    with tempfile.TemporaryDirectory(prefix="cpp-review-entry-control-") as owned:
        observations = []
        for only in (False, True):
            temporary = Path(owned) / str(only)
            temporary.mkdir()
            answer, spec, reviewer, qualification = observe(
                case, temporary, gate, qualification_only=only)
            invoked = "exec" in reviewer
            if spec["project"] != "claude-power-pack" and qualification:
                print("CI_SHAPE_REVIEW_CONTROL: refused - neighbor ran CPP qualification")
                return 1
            expected_calls = [] if (spec.get("identity_error")
                                   or spec["project"] != "claude-power-pack") else ["ci-shape-check"]
            if answer.returncode == 0 and (only or invoked):
                observations.append("GOOD")
            elif (not invoked and answer.returncode == 1 and qualification == expected_calls
                  and "CODEX_REVIEW: blocked" in answer.stdout + answer.stderr):
                observations.append("BAD")
            else:
                print(answer.stdout + answer.stderr)
                observations.append("UNKNOWN")
        if observations == ["GOOD", "GOOD"]:
            print("CI_SHAPE_REVIEW_CONTROL: admitted - both entries permit review")
            return 0
        if observations == ["BAD", "BAD"]:
            print("CI_SHAPE_REVIEW_CONTROL: refused - both entries prevent review")
            return 1
        print("CI_SHAPE_REVIEW_CONTROL: unavailable - entries disagree or could not be examined")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
