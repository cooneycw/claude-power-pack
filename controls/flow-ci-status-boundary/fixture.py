"""Owned public/worker boundary observations, with no real CI or credentials."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHA = "2b308175a757e0b17c30caead6aabbe9356b43cc"
STARTED = 1_000_000


def stage(gate, root):
    """Isolate dispatcher and shell together; anchors cannot import current code."""
    if gate.suffix == ".json":
        bundle = json.loads(gate.read_text())
        parts = {}
        for name, entry in bundle["files"].items():
            source = gate.parent / entry["path"]
            assert hashlib.sha256(source.read_bytes()).hexdigest() == entry["sha256"]
            parts[name] = source
    else:
        parts = {"scripts/flow-ci-status.sh": gate,
                 "lib/cicd/flow.py": ROOT / "lib/cicd/flow.py",
                 "lib/cicd/providers.py": ROOT / "lib/cicd/providers.py"}
    for name, source in parts.items():
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    for path in (root / "lib/__init__.py", root / "lib/cicd/__init__.py"):
        path.write_text("")
    return root / "scripts/flow-ci-status.sh"


def exercise(gate, case, root):
    runtime = root / "runtime"
    script = stage(gate, runtime)
    project, binaries = root / "project", root / "bin"
    project.mkdir()
    binaries.mkdir()
    calls = root / "wp-calls"
    gh_calls = root / "gh-calls"
    if case.get("record"):
        (project / ".claude").mkdir()
        (project / ".claude/cicd.yml").write_text(json.dumps({"pipeline": {"providers": [case["record"]]}}))
    curl = binaries / "curl"
    curl.write_text("#!" + sys.executable + "\n" + '''import json,sys,os
from pathlib import Path
sys.stdin.read()
url=sys.argv[-1]
with Path(os.environ['OWNED_WP_CALLS']).open('a') as f:f.write(url+'\\n')
state=os.environ['OWNED_WP_STATUS']
sha=os.environ['OWNED_SHA']
if '/lookup/' in url:value={'id':17,'timeout':60}
elif 'pipelines?' in url:value=[] if state=='not-found' else [{'number':42,'commit':sha,'event':'push','status':state}]
else:value={'number':42,'status':state,'workflows':[{'name':'ci','state':state,'started':1000000,'children':[{'name':'test','state':state}]}]}
print(json.dumps(value))
''')
    curl.chmod(0o755)
    gh = binaries / "gh"
    gh.write_text("#!" + sys.executable + "\n" + '''import json,sys,os
from pathlib import Path
with Path(os.environ['OWNED_GH_CALLS']).open('a') as f:f.write(' '.join(sys.argv[1:])+'\\n')
if sys.argv[1:3]==['run','list']:
 print(json.dumps([{'databaseId':19,'event':'push','status':'completed','conclusion':'success','workflowName':'ci','startedAt':'2020-01-01T00:00:00Z','url':'https://example.invalid/run/19'}]))
else:sys.exit(1)
''')
    gh.chmod(0o755)
    env = {key: value for key, value in os.environ.items()
           if key not in {"CPP_FLOW_CI_BACKEND", "CPP_FLOW_CI_WORKER", "BASH_ENV",
                          "WOODPECKER_API_TOKEN", "WOODPECKER_SERVER", "WOODPECKER_HOST"}}
    env.update(GIT_CEILING_DIRECTORIES=str(root), GH_TOKEN="", HOME=str(project),
               FLOW_CI_CURL=str(curl), FLOW_CI_GH=str(gh), FLOW_CI_AWS="/nonexistent/aws",
               FLOW_CI_WPCLI="/nonexistent/woodpecker-cli", FLOW_CI_SLEEP="/bin/true",
               FLOW_CI_NOW=str(STARTED + 71 * 60), WOODPECKER_API_TOKEN="boundary-fixture-only",
               WOODPECKER_SERVER="https://provider.example.invalid", OWNED_SHA=SHA,
               OWNED_WP_STATUS=case.get("wp", "running"), OWNED_WP_CALLS=str(calls), OWNED_GH_CALLS=str(gh_calls))
    if case.get("missing_tools"):
        env.update(FLOW_CI_CURL="/nonexistent/curl", FLOW_CI_GH="/nonexistent/gh",
                   WOODPECKER_API_TOKEN="", WOODPECKER_SERVER="")
        assert not Path(env["FLOW_CI_CURL"]).exists() and not Path(env["FLOW_CI_GH"]).exists()
    if "backend" in case:
        env["CPP_FLOW_CI_BACKEND"] = case["backend"]
    if case.get("worker"):
        env["CPP_FLOW_CI_WORKER"] = "1"
    ref = case.get("ref", SHA)
    if ref != SHA:
        assert ref == "fixture-ref-does-not-exist" and not (project / ".git").exists()
    args = ["bash", str(script), ref, "--path", str(project), "--repo", "o/r", "--event", "push"]
    if case.get("fallback"):
        args.append("--fallback-provider-probes")
    result = subprocess.run([*args, *case.get("args", [])], cwd=project, env=env,
                            capture_output=True, text=True, timeout=15)
    markers = {}
    for line in result.stdout.splitlines():
        if line.startswith("FLOW_CI_") and ": " in line:
            key, value = line.split(": ", 1)
            markers.setdefault(key, []).append(value)
    return dict(exit=result.returncode, markers=markers,
                wp_calls=len(calls.read_text().splitlines()) if calls.exists() else 0,
                gh_calls=len(gh_calls.read_text().splitlines()) if gh_calls.exists() else 0,
                stdout=result.stdout, stderr=result.stderr)


def satisfies(observed, case):
    expected = case["expected"]
    if observed["exit"] != expected["exit"]:
        return False
    marks = observed["markers"]
    if any(marks.get("FLOW_CI_" + key) != [expected[key]] for key in ("STATUS", "PROVIDER")):
        return False
    selections = marks.get("FLOW_CI_SELECTION", [])
    if len(selections) != 1 or not selections[0].startswith(expected["SELECTION"]):
        return False
    if expected.get("no_wp") and observed["wp_calls"]:
        return False
    if expected.get("no_requests") and (observed["wp_calls"] or observed["gh_calls"]):
        return False
    return True
