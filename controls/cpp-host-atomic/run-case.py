#!/usr/bin/env python3
"""Observe actual seam writes in an owned sandbox, including defer/failure."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    gate, case = map(Path, sys.argv[1:])
    scenario = (case / 'scenario.txt').read_text().strip()
    with tempfile.TemporaryDirectory(prefix='host-atomic-control-') as directory:
        root = Path(directory)
        target = root / '.claude/cpp-host.json'
        env = {**os.environ, 'HOME': str(root), 'CPP_DEFER_SURFACES': ''}
        old = root / 'previous'
        if scenario == 'bad-symlink':
            target.parent.mkdir()
            old.write_text('previous-record')
            target.symlink_to(old)
            assert target.is_symlink() and old.read_text() == 'previous-record'
        elif scenario == 'bad-deferred':
            env['CPP_DEFER_SURFACES'] = '~/.claude/cpp-host.json'
            assert not target.parent.exists()
        else:
            assert scenario == 'good-written' and not target.exists()
        result = subprocess.run(['bash', str(gate), 'file-write-atomic', str(target)],
                                input='new-record\n', text=True, capture_output=True, env=env)
        if result.returncode in {1, 3}:
            if scenario == 'bad-symlink':
                assert old.read_text() == 'previous-record'
            elif scenario == 'bad-deferred':
                assert not target.parent.exists()
            else:
                raise AssertionError('good input refused')
            print('HOST_ATOMIC: refused')
            return 1
        assert result.returncode == 0 and target.read_text() == 'new-record\n'
        print('HOST_ATOMIC: written')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
