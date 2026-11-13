"""Owned offline shell fixture shared by unit and committed control cases."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

PIN = "a" * 40

def exercise(tmp_path: Path, pin=PIN, *, scenario="ok", fork=False, provider="github-actions",
             gate=None, metadata=None, shell_flags=None, stdin=None, receipt_schema=None):
    source = Path(gate) if gate else Path(__file__).resolve().parents[2] / "lib/cicd/enrolment.py"
    spec = importlib.util.spec_from_file_location("pinned_enrolment_under_test", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bootstrap_script = module.bootstrap_script
    if receipt_schema is not None:
        receipt = tmp_path / ".claude/cpp-install.json"
        receipt.parent.mkdir()
        receipt.write_text(json.dumps({"schema": receipt_schema, "cpp_revision": PIN}))
        pin = module.installed_revision(tmp_path)

    binaries = tmp_path / "bin"
    binaries.mkdir()
    calls = tmp_path / "calls"
    git = binaries / "git"
    git.write_text("""#!/bin/bash
printf '%s\\n' "$*" >> "$OWNED_CALLS"
if [[ "$1" == -C ]]; then
  target="$2"; shift 2
  if [[ "$1" == init ]]; then exit 0; fi
  if [[ "$1" == fetch ]]; then
    [[ "$OWNED_SCENARIO" == fetch-failure ]] && exit 22
    case "$*" in
      'fetch --quiet --no-tags https://github.com/cooneycw/claude-power-pack.git '\
'refs/heads/main:refs/remotes/cpp-enrolment/main') exit 0 ;;
      "fetch --quiet --no-tags --depth=1 https://github.com/cooneycw/claude-power-pack.git $OWNED_PIN") exit 0 ;;
      *) exit 90 ;;
    esac
  fi
  if [[ "$1 $2" == 'rev-parse --is-shallow-repository' ]]; then echo false; exit 0; fi
  if [[ "$*" == 'rev-parse --verify refs/remotes/cpp-enrolment/main^{commit}' ]]; then
    echo "$OWNED_MAIN"; exit 0
  fi
  if [[ "$1 $2" == "rev-list $OWNED_MAIN" ]]; then
    printf '%s\\n' "$OWNED_MAIN" "$OWNED_PIN"; exit 0
  fi
  if [[ "$1" == checkout ]]; then
    mkdir -p "$target/scripts"
    touch "$target/scripts/counter-model-receipt.py"
    cat > "$target/scripts/flow-finish-gate.sh" <<'GATE'
#!/bin/bash
[[ "$PWD" == "$OWNED_PROJECT" ]] || exit 96
[[ "$*" == '--enrolment-only --branch owned-branch' ]] || exit 97
case "$OWNED_SCENARIO" in
 missing-receipt) echo 'FLOW_FINISH_GATE: fail (counter-model line missing)'; exit 1 ;;
 broken-bootstrap) exit 127 ;;
 old-checker) exit 2 ;;
 reads-stdin) if read -r value; then exit 98; else echo 'FLOW_FINISH_GATE: ok'; exit 0; fi ;;
 conflicting-verdict) printf 'FLOW_FINISH_GATE: ok\\nFLOW_FINISH_GATE: fail\\n'; exit 0 ;;
 *) echo 'FLOW_FINISH_GATE: ok'; exit 0 ;;
esac
GATE
    exit 0
  fi
  if [[ "$1 $2" == 'rev-parse HEAD' ]]; then
    [[ "$OWNED_SCENARIO" == mismatch ]] && printf '%040d\\n' 0 || echo "$OWNED_PIN"
    exit 0
  fi
fi
case "$*" in
 'rev-parse --is-shallow-repository')
    [[ "$OWNED_SCENARIO" == shallow-fetch-failure ]] && echo true || echo false ;;
 'rev-parse HEAD') echo "$OWNED_PIN" ;;
 *) exit 1 ;;
esac
""")
    git.chmod(0o755)
    curl = binaries / "curl"
    curl.write_text("""#!/bin/bash
[[ "$OWNED_SCENARIO" == metadata-error ]] && exit 22
printf '{"base":{"repo":{"full_name":"o/r"}},"head":{"ref":"owned-branch","sha":"%s",' "$OWNED_PIN"
printf '"repo":{"full_name":"%s"}}}\\n' "$OWNED_API_HEAD_REPO"
""")
    curl.chmod(0o755)
    # Owned metadata never inherits a live authentication branch.
    env = {**os.environ, "GH_TOKEN": "", "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
           "CPP_PR_EVENT": "pull_request", "CPP_PR_BRANCH": "owned-branch",
           "CPP_PR_HEAD_REPO": "fork/r" if fork else "o/r", "CPP_PR_BASE_REPO": "o/r",
           "CI_PIPELINE_EVENT": "pull_request", "CI_COMMIT_SOURCE_BRANCH": "owned-branch",
           "CI_COMMIT_PULL_REQUEST": "12", "CI_REPO": "o/r", "CI_FORGE_TYPE": "github",
           "CI_FORGE_URL": "https://github.com", "OWNED_CALLS": str(calls), "OWNED_PIN": PIN, "OWNED_MAIN": "b" * 40,
           "OWNED_PROJECT": str(tmp_path), "OWNED_SCENARIO": scenario,
           "OWNED_API_HEAD_REPO": "fork/r" if fork else "o/r"}
    if provider == "woodpecker":
        for key in list(env):
            if key.startswith("CPP_PR_"):
                env.pop(key)
    if metadata:
        assert set(metadata) <= {
            "CPP_PR_EVENT", "CPP_PR_BRANCH", "CPP_PR_HEAD_REPO", "CPP_PR_BASE_REPO", "CI_FORGE_TYPE",
        }
        env.update(metadata)
    if shell_flags is None:
        shell_flags = ("-eo", "pipefail") if provider == "github-actions" else ()
    result = subprocess.run(["bash", *shell_flags, "-c", bootstrap_script(pin, provider)], cwd=tmp_path,
                            env=env, input=stdin, capture_output=True, text=True, timeout=15)
    return result, calls.read_text() if calls.exists() else ""
