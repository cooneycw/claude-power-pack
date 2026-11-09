#!/usr/bin/env python3
"""Run the host step and final receipt consumer in separate owned shell processes."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ['commands', 'stash-guard', 'scripts', 'permission-profile', 'uv', 'second-opinion', 'playwright', 'tavily']


def exercise(gate, case):
    spec = json.loads((case / 'case.json').read_text())
    expected_bad = {
        'bad-deferred': (3, 'HOST_CI_RECORD: deferred'),
        'bad-failed-retry': (1, 'HOST_CI_RECORD: failed'),
        'bad-unknown': (3, 'HOST_CI_RECORD: unknown'),
        'bad-no-receipt-zero': (0, ''),
        'bad-contradictory-receipt': (3, 'HOST_CI_RECORD: written'),
        'bad-duplicate-receipt': (0, 'HOST_CI_RECORD: written\nHOST_CI_RECORD: malformed!'),
    }
    if case.name in expected_bad:
        assert (spec['exit'], spec['report']) == expected_bad[case.name], 'known bad input must be present'
    else:
        assert spec['exit'] == 0 and spec['report'] == 'HOST_CI_RECORD: written'

    text = (ROOT / '.claude/commands/cpp/init.md').read_text()
    host = next(block for block in re.findall(r'```bash\n(.*?)```', text, re.S)
                if '\nCPP_HOST_RUNTIME=' in block or block.startswith('CPP_HOST_RUNTIME='))
    final = re.search(r'# CPP_INSTALL_RECEIPT_WRITE_BEGIN\n(.*?)# CPP_INSTALL_RECEIPT_WRITE_END', text, re.S)
    assert final and final[1].strip()
    with tempfile.TemporaryDirectory(prefix='host-install-control-') as directory, \
            tempfile.TemporaryDirectory(prefix='host-install-mcp-state-') as state_directory:
        root = Path(directory)
        cpp = root / 'cpp'
        (cpp / 'scripts').mkdir(parents=True)
        (cpp / 'scripts/cpp-install-receipt.py').symlink_to(gate.resolve())
        bindir = root / 'bin'
        bindir.mkdir()
        uv = bindir / 'uv'
        uv.write_text('#!/bin/bash\nprintf "%s\\n" "$CONTROL_HOST_REPORT"\nexit "$CONTROL_HOST_EXIT"\n')
        uv.chmod(0o755)
        observations = [{'step':step, 'outcome':'installed', 'exit_code':0} for step in BASE]
        if spec.get('old_green'):
            observations.append({'step':'host-ci', 'outcome':'written', 'exit_code':0})
            assert observations[-1]['outcome'] == 'written' and spec['exit'] != 0
        report = 'github-actions: ' + spec.get('provider', 'ready') + ' (private-payload-canary)\n' + spec['report']
        env = {**os.environ, 'PATH':str(bindir) + os.pathsep + os.environ['PATH'],
               'CPP_DIR':str(cpp), 'CPP_CAPABILITIES_JSON':'["cicd"]',
           'CPP_PROJECTS_ROOT':str(root / 'projects'), 'HOME':str(root / 'home'),
               'CONTROL_HOST_REPORT':report, 'CONTROL_HOST_EXIT':str(spec['exit']),
               'STEP_RESULTS_JSON':json.dumps(observations)}
        assert uv.is_file() and os.access(uv, os.X_OK)
        assert shutil.which('uv', path=env['PATH']) == str(uv)
        assert (cpp / 'scripts/cpp-install-receipt.py').is_symlink()
        # EXIT trap observes the general metadata even when the actual host
        # snippet returns failure. Nothing fakes shell-state persistence.
        script = 'trap \'printf "HOST_CONTROL_ROWS: %s\\n" "$STEP_RESULTS_JSON"\' EXIT\n' + host
        observed = subprocess.run(['bash', '-c', script], cwd=root, env=env,
                                  capture_output=True, text=True, timeout=10)
        raw = [line.removeprefix('HOST_CONTROL_ROWS: ') for line in observed.stdout.splitlines()
               if line.startswith('HOST_CONTROL_ROWS: ')]
        assert len(raw) == 1
        rows = json.loads(raw[0])
        assert [row for row in rows if row['step'] != 'host-ci'] == observations[:len(BASE)]
        # The final consumer runs in a fresh harness shell and requires this
        # run's explicit temporary path. Initialize the real state helper, not
        # a synthesized function/array or the host-observation blind anchor.
        initial = re.search(r'# CPP_MCP_RUN_INIT_BEGIN\n(.*?)# CPP_MCP_RUN_INIT_END', text, re.S)
        assert initial and initial[1].strip(), 'must execute the actual MCP run initializer'
        setup = subprocess.run(['bash', '-c', initial[1]], cwd=root,
                               env={**env, 'CPP_DIR':str(ROOT), 'TMPDIR':state_directory},
                               capture_output=True, text=True, timeout=10)
        assert setup.returncode == 0, setup.stdout + setup.stderr
        run_paths = [line.split('=', 1)[1] for line in setup.stdout.splitlines()
                     if line.startswith('CPP_MCP_RUN_DIR=')]
        assert len(run_paths) == 1 and Path(run_paths[0]).is_absolute()
        final_env = {**env, 'CPP_MCP_RUN_DIR':run_paths[0], 'STEP_RESULTS_JSON':json.dumps(rows),
                      'CPP_CAPABILITIES_JSON':'["commands","scripts","mcp","cicd"]' , 'PROFILE_NAME':'not-selected',
                     'OFFERED_STEPS_JSON':json.dumps(BASE + ['host-ci']), 'PERMISSION_REPORT':'{}'}
        consumer = final[1].replace('--cpp-dir "$CPP_DIR"', '--revision "' + 'a' * 40 + '"')
        result = subprocess.run(['bash', '-c', consumer], cwd=root, env=final_env,
                                capture_output=True, text=True, timeout=10)
        receipt = root / '.claude/cpp-install.json'
        assert receipt.is_file(), result.stdout + result.stderr
        assert 'private-payload-canary' not in receipt.read_text()
        print(result.stdout, end='')
        if 'CPP Installation Complete' in result.stdout.splitlines():
            return 0
        assert 'CPP Installation Incomplete' in result.stdout.splitlines()
        return 1


if __name__ == '__main__':
    raise SystemExit(exercise(Path(sys.argv[1]), Path(sys.argv[2])))
