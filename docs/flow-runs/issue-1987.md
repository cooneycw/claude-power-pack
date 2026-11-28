# Flow run record - issue #1987

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=72a3ec8df50344c1becf88bb16facf70 -->
## Run 1

- Run-id:            72a3ec8df50344c1becf88bb16facf70
- Run-start:         db63a7ec4e659b083230ca7327248f6ca983f1bb
- Issue:             #1987
- Base SHA:          db63a7ec4e659b083230ca7327248f6ca983f1bb
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run140:ch-orch mailbox44548, exact labels/test/qualification/review/gate/PR assignment
- Recorded at:       2026-11-28T12:09:05.193211+00:00

### Section A - What this issue wants
CPP pipelines must select the owner's dedicated pool=cpp agent rather than sharing other kyleci agents with Kyle. Keep host=kyleci and add the narrower pool label; the actual PR pipeline must identify agent93. No scheduler/runner behavior is otherwise changed.

### Section B evidence
Owner ruling is recorded in issue1987 and relayed in mailbox44548. Main db63a7ec has only labels.host=kyleci. PR1979/issue1977 added that host guard but did not constrain a pool. The existing test at tests/test_ci_trigger.py:152 scans every discovered workflow/YAML document and only asserts host. No Mac commit is fetched. Sibling worker #1973 edits workflow steps; this run owns only the labels block plus its existing test. Release work remains separately held and takes priority if the ruling arrives.

### Section C - the approved plan
1. `tests/test_ci_trigger.py` - extend the existing all-workflows host-label test to require pool=cpp; demonstrate failure against the unchanged main workflow before changing product YAML.
2. `.woodpecker.yml` - add only pool: cpp beneath host: kyleci in the top-level labels map; preserve all other bytes.
Normal flow-run/as-read and counter-model receipt metadata accompany these two source paths. No Makefile target, runtime helper, installer, provider, template or attribution-baseline edit is planned. Use the existing make test entry with PYTEST_ADDOPTS selecting the one file; label its verdict focused rather than full-suite.
Risks: scheduling on the wrong shared agent, loss of the host label, unexpected generated bundle drift, or a conflict with #1973. Verify a real pre-fix red and corrected green, lint/YAML parsing, generated member/hash/mode identity, required maintained pre-review qualification, ch-rev pass1 and fresh receipt, ONE direct finish gate with proven3600 verify budget, then actual PR CI agent_id93. Do not retry a failed gate or CI blindly. Record queue/wait evidence for the PR pipeline; later pipelines are follow-up observations. No material concern found with the narrow assignment.

Lanes: CI provider - CPP Woodpecker; required output reader is the actual scheduler, observed through the PR pipeline agent_id. Local source test verifies the real YAML but cannot prove placement. The canonical gate and local qualifier run in this managed non-root container; image/root CI evidence is distinct and not inferred from local GOOD.
Reader: test_ci_trigger reads actual discovered YAML files/documents and checks both labels; no stand-in pipeline YAML.
Reader: Woodpecker scheduler consumes the changed top-level labels; actual PR pipeline metadata must report agent93.
Reader: Codex generated skills - build and compare every actual member/hash/mode; root workflow labels should not alter bundled output. Stop on unexpected changes rather than refreshing attribution rows.

### Lanes for this change
| Lane | Disposition | Evidence or boundary |
|---|---|---|
| Checkout | will test | linked worktree from db63a7ec; main checkout is not covered by local execution. |
| Harness | not applicable | No claude install or codex install is changed or executed; generated member comparison is not installation proof. |
| Driver | not applicable | No driver orchestration or child payload contract changes. |
| Coordination | will test | with kyle via canonical admission and renewing gate lease; without kyle is not covered in this run. |
| CI provider | will test | Woodpecker PR pipeline must identify agent93; GitHub Actions is not applicable to this CPP workflow. |
| Project state | not applicable | No change to a repository that has adopted a feature's file or record versus one that has not; this edits existing CPP workflow labels. |
| Toolchain version | will test | CI's pinned uv and Python plus the host or container's installed versions; no wider version matrix claimed. |
| Clone shape | will test | a full clone with all refs for source; maintained qualifier uses depth-1 and depth-1 with filter=tree:0; local GOOD is separate from root. |
| Run location | will test | invoked from the CPP root for local gates and from another directory in the maintained qualifier. |
| Gate target | will test | CPP itself; a consumer with its own interpreter and PATH is not covered by this labels change. |
| Wave role state | not applicable | No wave lifecycle or role registry code changes. |
