| Lane | What was demonstrated |
|---|---|
| Toolchain version | Host with uv only in ~/.local/bin: tests/test_runner_target_path.py went 8 failed (on d90712ee and the #1824 branch) to 28 passed; the fallback appends only when the fixed PATH lacks uv, so CI's /usr/local/bin layout keeps the same PATH |
| Gate target | The probes still run the shipped CPP_RUN wrapper against a target venv first on PATH, and the python3 precondition pins the target interpreter; all 28 tests in the file pass, including the target-interpreter and restored-PATH cases |
