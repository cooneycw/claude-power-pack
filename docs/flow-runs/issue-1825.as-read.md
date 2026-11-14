<!-- flow-run n=1 id=7d37e7afc4cf4937b56e7f5c435af7f9 -->
## Run 1 - issue #1825 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1825
- Read at:      2026-11-14T17:02:01Z
- updatedAt:    2026-11-14T16:59:07Z   (context only - moves on comments and labels)
- Body digest:  a364de233b6b295849f6d32334b5fa94a8790bc8f012902599f924e2d73e10a7   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1695 of 1695 (cap 16384)

### Body as read
## Problem

`tests/test_runner_target_path.py:48` builds the probe PATH as

```
target_path = f"{target_venv / 'bin'}:/usr/local/bin:/usr/bin:/bin"
```

and then runs the shipped `CPP_RUN` wrapper (`env ... uv run ...`) under it (line 79). On a host where `uv` is installed only at `~/.local/bin/uv` (the standard uv installer location), `env` cannot find it:

```
AssertionError: env: 'uv': No such file or directory
tests/test_runner_target_path.py:93
```

8 tests fail:
- `test_bare_python_uses_the_target_callers_interpreter[False|True]`
- `test_the_runners_own_interpreter_stays_in_cpp[False|True]`
- `test_wrapper_overwrites_inherited_path_metadata`
- `test_make_queries_and_the_target_step_share_restored_path`
- `test_skip_probe_uses_the_same_target_interpreter_as_the_command`
- `test_target_fixture_finds_python_on_callers_path[run_probe]`

The same 8 fail on `d90712ee` (11.1.1), so this is pre-existing. Presumably CI passes because its image has `uv` under `/usr/local/bin`. This is an undeclared environment fact in the #1718 class.

## Impact

`make test`, and therefore `flow-finish-gate.sh`, fails on this host for every change. Until now it was hidden, because #1824 refused the CPP venv before any test ran. Found while running `/flow:auto #1824`.

## Fix

Put the directory of the resolved `uv` (`shutil.which("uv")`) on `target_path` ahead of the system dirs. The test is about the TARGET python/PATH, not about where uv lives. Alternatively, skip with a stated reason when `uv` is not on the fixed PATH. Assert in the fixture that `shutil.which("uv", path=target_path)` resolves, so a missing launcher reads as a fixture precondition failure rather than a product failure.

<!-- end of body -->
