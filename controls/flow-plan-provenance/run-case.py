"""Exercise the real optional finish entrypoint on an owned fixture repository."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

case, gate = (Path(value).resolve() for value in sys.argv[1:])
root = Path(__file__).resolve().parents[2]
git = shutil.which('git')
if not git:
    print('FLOW_PROVENANCE_CONTROL: unavailable - git is not on PATH')
    raise SystemExit(3)

env = {key: value for key, value in os.environ.items()
       if key not in ('CODEX_THREAD_ID', 'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR')}
env.update(CLAUDE_CODE_SESSION_ID='provenance-control', GIT_AUTHOR_NAME='Fixture',
           GIT_AUTHOR_EMAIL='fixture@example.invalid', GIT_COMMITTER_NAME='Fixture',
           GIT_COMMITTER_EMAIL='fixture@example.invalid', GIT_CONFIG_GLOBAL=os.devnull,
           GIT_CONFIG_NOSYSTEM='1')


def run(argv, repo):
    return subprocess.run(argv, cwd=repo, env=env, capture_output=True, text=True)


def setup(argv, repo):
    done = run(argv, repo)
    if done.returncode:
        print('FLOW_PROVENANCE_CONTROL: unavailable - fixture setup failed')
        print(done.stdout + done.stderr)
        raise SystemExit(3)


with tempfile.TemporaryDirectory(prefix='cpp-flow-provenance-') as temporary:
    owned = Path(temporary).resolve()
    package = owned / 'package'
    staged = package / 'scripts/flow-plan-record.py'
    staged.parent.mkdir(parents=True)
    shutil.copyfile(gate, staged)
    contract = package / 'docs/agents/closing-report-contract.md'
    if not (case / 'missing-contract').exists():
        contract.parent.mkdir(parents=True)
        shutil.copyfile(root / 'docs/agents/closing-report-contract.md', contract)
    else:
        assert not contract.exists(), 'UNKNOWN fixture must not have the canonical contract'
    repo = owned / 'repo'
    repo.mkdir()
    setup([git, 'init', '-q', '-b', 'fixture'], repo)
    (repo / 'README.md').write_text('base\n')
    setup([git, 'add', '-A'], repo)
    setup([git, 'commit', '-qm', 'base'], repo)
    body = owned / 'body.md'
    body.write_text('Fixture issue\n')
    bindir = owned / 'bin'
    bindir.mkdir()
    gh = bindir / 'gh'
    gh.write_text(f'#!{sys.executable}\nfrom pathlib import Path\nprint(Path({str(body)!r}).read_text(), end="")\n')
    gh.chmod(0o755)
    env['PATH'] = str(bindir) + os.pathsep + env.get('PATH', '')
    prefix = [sys.executable, str(staged)]
    setup([*prefix, 'reconcile', '42'], repo)
    setup([*prefix, 'read-issue', '42', '--body-file', str(body)], repo)
    setup([*prefix, 'begin-run', '42'], repo)
    with (repo / 'docs/flow-runs/issue-42.md').open('a') as record:
        record.write('''- Issue: #42
- Approval: granted

### Section C - the approved plan
1. `src/a.py` - fixture change

Scope: 1 file.
''')
    setup([*prefix, 'approve', '42'], repo)
    (repo / 'src').mkdir()
    (repo / 'src/a.py').write_text('x = 1\n')
    setup([git, 'add', '-A'], repo)
    setup([git, 'commit', '-qm', 'fixture change'], repo)
    done = run([*prefix, 'finish', '42', '--base', 'HEAD~1', '--head', 'HEAD',
                '--provenance-file', str(case / 'closing.md')], repo)
sys.stdout.write(done.stdout)
sys.stderr.write(done.stderr)
raise SystemExit(done.returncode)
