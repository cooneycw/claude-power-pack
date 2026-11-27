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
        answer, spec, reviewer, qualification = observe(case, Path(owned), gate)
        invoked = "exec" in reviewer
        if spec["project"] != "claude-power-pack" and qualification:
            print("CI_SHAPE_REVIEW_CONTROL: refused - neighbor ran CPP qualification")
            return 1
        if invoked and answer.returncode == 0:
            print("CI_SHAPE_REVIEW_CONTROL: admitted - reviewer invoked")
            return 0
        expected_calls = [] if spec.get("identity_error") else ["ci-shape-check"]
        if (not invoked and answer.returncode == 1 and qualification == expected_calls
                and "CODEX_REVIEW: blocked" in answer.stdout + answer.stderr):
            print("CI_SHAPE_REVIEW_CONTROL: refused - no reviewer invocation")
            return 1
        print(answer.stdout + answer.stderr)
        print("CI_SHAPE_REVIEW_CONTROL: unavailable - entry did not establish admission/refusal")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
