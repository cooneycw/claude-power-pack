# Issue #1242 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1242
- Read at:      2026-09-24T10:51:03Z
- updatedAt:    2026-09-24T10:47:20Z   (context only - moves on comments and labels)
- Body digest:  fae40e9b0f7df6c1a0740277a1afc546fafed42f553e91ab7a61d8dcb90dc3a3   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4023 of 4023 (cap 16384)

## Body as read
## Reproduction (deterministic, 0.11s)

```
$ pytest "tests/test_host_surface_observe.py::test_a_parent_set_GIT_CONFIG_cannot_reach_the_child" -q
1 passed in 0.07s

$ pytest -p no:randomly -q \
    "tests/test_host_surface_observe.py::test_the_canary_FIRES_when_the_neutralisation_IS_REMOVED" \
    "tests/test_host_surface_observe.py::test_a_parent_set_GIT_CONFIG_cannot_reach_the_child"
E       AssertionError: assert None == 'false'
E        +  where None = <built-in method get of dict object at 0x...>('core.fsmonitor')
E        +    where <built-in method get of dict object at 0x...> = {}.get
1 failed, 1 passed in 0.11s
```

The victim passes alone and fails when one specific sibling has run before it in
the same process.

## Mechanism

`scripts/host-surface-observe.py`

```python
_OVERRIDES_CACHE: dict[str, list[tuple[str, str]]] = {}      # :497

def git_exec_config_overrides(repo):
    key = str(repo)
    if key in _OVERRIDES_CACHE:
        return list(_OVERRIDES_CACHE[key])                    # :506-507
    overrides = sorted(GIT_EXEC_CONFIG_NEUTRALISED.items())   # :508
    ...
    _OVERRIDES_CACHE[key] = list(overrides)                   # :534
```

`tests/test_host_surface_observe.py:640` does
`monkeypatch.setattr(hso, "GIT_EXEC_CONFIG_NEUTRALISED", {})` and then calls
`hso.verify_git_containment()`. That reaches `git_exec_config_overrides`, computes
`overrides == []` from the emptied table, and **writes `[]` into the module-level
cache under the repo path**.

`monkeypatch` restores the ATTRIBUTE at teardown. It knows nothing about the
cache, so the empty list survives for the rest of the process. Every later
`sandbox_env()` in that worker then gets `GIT_CONFIG_COUNT=0`, and
`test_a_parent_set_GIT_CONFIG_cannot_reach_the_child` reads `None` where it
requires `'false'`.

`tests/test_host_surface_observe.py:735` patches the same table to
`{"core.someNewHook": "false"}` and is a second poisoning candidate with the same
shape.

## Why it is intermittent, and why it reads as someone else's bug

Under `pytest -n 4` xdist decides which tests share a worker process and in what
order, and that grouping varies between runs. The failure needs poisoner and
victim in the same process, poisoner first. So it appears and disappears with no
change to the code, and it lands on whatever PR is in flight.

Observed on PR #1238 (pipeline 2629) whose change touches neither file. That PR
had already passed CI green at pipelines 2619/2620 on its pre-merge SHA.

`@requires_git` gates the poisoner, so a git-less container skips it and the
victim passes - which is part of why this has stayed hidden.

## What this is NOT

Not a production defect, and the distinction matters for triage. The poisoning
requires `GIT_EXEC_CONFIG_NEUTRALISED` to be empty or replaced, which only these
tests do; `host-surface-observe.py` runs as a one-shot process in `make verify` and
in CI, where the table is its real value and the cache is populated once from it.
The sandbox neutralises `core.fsmonitor` in production exactly as #1182 intended.

This is a test-isolation defect that makes CI intermittently red, not a hole in the
containment.

## Directions, none settled

- Clear `_OVERRIDES_CACHE` in an autouse fixture in that test file. Smallest, and
  it leaves the trap for the next module that imports `hso`.
- Key the cache on the table's own contents, not just the repo path, so a patched
  table cannot collide with the real one's entry. Fixes it for every caller.
- Have the two patching tests clear the cache themselves - correct, and it is the
  option that relies on whoever writes the third such test knowing to do it.

The second removes the class; the first two remove the instance.

## Provenance

Found during `/flow:auto #1232` while establishing whether that PR's red CI was
its own fault. It was not. Sibling of #1241, which is the OTHER intermittent CI
failure in the same window (the negative-control battery's 120s timeout) - separate
cause, same symptom for whoever is holding the PR.

