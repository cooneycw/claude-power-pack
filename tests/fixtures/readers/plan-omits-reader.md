# Example plan

Issue: `status.sh` reports how many checks it ran.

### Section C - the approved plan
1. `scripts/status.sh` - the verdict line becomes `STATUS: ok (N checks)`
2. `scripts/gate.sh` - matches the new verdict line from `status.sh`
3. `tests/test_gate.py` - the gate still passes on a clean run
Scope: 2 files, about 20 lines.
Risks: no notable risks.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | not applicable: nothing here depends on where the repository is checked out |

### Code in this change

`scripts/status.sh` (changed):
```sh
#!/bin/sh
checks=3
echo "STATUS: ok ($checks checks)"
```

`scripts/gate.sh` (changed):
```sh
#!/bin/sh
# reads the output of status.sh on stdin
grep -Eqx "STATUS: ok \([0-9]+ checks\)" || { echo "GATE: blocked"; exit 1; }
echo "GATE: passed"
```

`tests/test_gate.py` (changed):
```python
def test_the_gate_passes_on_a_clean_run():
    status = subprocess.run(["sh", "scripts/status.sh"], capture_output=True, text=True, check=True)
    result = subprocess.run(["sh", "scripts/gate.sh"], input=status.stdout, capture_output=True, text=True)
    assert result.returncode == 0
    assert "GATE: passed" in result.stdout
```
