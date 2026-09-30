# Flow run record - issue #1360

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=6973febd668a470780e861fb3359f051 -->
## Run 1

- Run-id:            6973febd668a470780e861fb3359f051
- Run-start:         785d7daadb9d725202b0fe141568ee4bd5cb28cd
- Issue:             #1360
- Base SHA:          785d7daa
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          session user (owner), "approved" in this /flow:auto run
- Recorded at:       2026-09-30T16:00:00Z

### Section B evidence
- `git log origin/main -- uv.lock` since issue creation (2026-09-30T15:25:38Z): none
- Open/merged PRs mentioning urllib3: none
- Related issues inspected: #922, #943, #961 (closed, different packages/advisories) - none supersede
- Audit re-run on pre-bump lock: 3 gating findings (CVE-2026-97687/97688/97689)

### Section C - the approved plan
1. `uv.lock` - `uv lock --upgrade-package urllib3`: urllib3 2.7.0 -> 2.8.0, no other package moves

Scope: trivial. Risks: upgrade drags other packages (diff and stop if so); botocore may cap urllib3 < 2.8 (report, do not force).
