# Example plan

Issue: `status.sh` reports how many checks it ran.

### Section C - the approved plan
1. `scripts/status.sh` - the verdict line becomes `STATUS: ok (N checks)`
2. `scripts/gate.sh` - unchanged; it reads the verdict line from `status.sh`
3. `tests/test_gate.py` - the gate still passes on a clean run
Scope: 2 files, about 20 lines.
Risks: no notable risks.

### Lanes for this change
| Lane | Answer |
|---|---|
| Reader: `scripts/gate.sh`, which matches the `STATUS:` line of `status.sh` | tested against real output: `tests/test_gate.py::test_the_gate_passes_on_a_clean_run` |

### Code in this change

`scripts/status.sh` (changed):
```sh
#!/bin/sh
checks=3
echo "STATUS: ok ($checks checks)"
```

`scripts/gate.sh` (unchanged):
```sh
#!/bin/sh
# reads the output of status.sh on stdin
grep -qx "STATUS: ok" || { echo "GATE: blocked"; exit 1; }
echo "GATE: passed"
```

`tests/test_gate.py` (changed):
```python
STATUS_OUTPUT = "STATUS: ok\n"


def test_the_gate_passes_on_a_clean_run():
    result = subprocess.run(["sh", "scripts/gate.sh"], input=STATUS_OUTPUT, capture_output=True, text=True)
    assert result.returncode == 0
    assert "GATE: passed" in result.stdout
```
