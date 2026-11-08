"""Queue HTTP authentication reaches curl without exposing credentials in argv."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from tests.test_gh_pr_merge import _calls, _linked_worktree, _make_stubs, _run

requires_tools = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in ("bash", "jq")), reason="requires bash and jq",
)


@requires_tools
@pytest.mark.parametrize("endpoint", ["lookup", "pipelines"])
def test_queue_header_is_delivered_without_credential_in_argv(tmp_path: Path, endpoint):
    stubs = _make_stubs(tmp_path, head_sha="a" * 40, repo_full="owner/repo")
    records = tmp_path / "http-evidence.jsonl"
    curl = Path(stubs["GH_PR_MERGE_CURL"])
    curl.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
token = os.environ['WOODPECKER_API_TOKEN']
url = args[-1]
headers = sys.stdin.read() if '@-' in args else '\\n'.join(args)
record = {'url': url, 'credential_in_argv': any(token in arg for arg in args),
          'header_received': 'Authorization: Bearer ' + token in headers,
          'accept_json': 'Accept: application/json' in args}
with Path(RECORDS).open('a') as output:
    output.write(json.dumps(record) + '\\n')
if not record['header_received']: raise SystemExit(22)
if '/lookup/' in url: print(json.dumps({'id':42}))
elif '/pipelines?' in url: print(json.dumps([{'commit':'a'*40,'status':'running'}]))
else: raise SystemExit(22)
'''.replace('RECORDS', repr(str(records))))
    canary = "OWNED-MERGE-QUEUE-CANARY-1656"
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-1656",
                  extra_env={"WOODPECKER_API_TOKEN": canary, "WOODPECKER_SERVER": "https://owned.invalid"})
    assert result.returncode == 0, result.stderr
    assert records.exists(), "queue HTTP path must execute"
    evidence = [json.loads(line) for line in records.read_text().splitlines()]
    assert [item["url"] for item in evidence] == [
        "https://owned.invalid/api/repos/lookup/owner/repo",
        "https://owned.invalid/api/repos/42/pipelines?per_page=5",
    ]
    matching = [item for item in evidence if ("/lookup/" if endpoint == "lookup" else "/pipelines?") in item["url"]]
    assert len(matching) == 1, evidence
    assert matching[0]["header_received"] and matching[0]["accept_json"], evidence
    assert not matching[0]["credential_in_argv"], "owned canary was visible in curl argv"
    assert canary not in result.stdout + result.stderr + records.read_text()
    assert any(call.startswith("gh pr merge") for call in _calls(stubs))
