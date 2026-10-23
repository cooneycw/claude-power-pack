# Flow run record - issue #1551

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=13f9e86d214e4d709289e3543622f273 -->
## Run 1

- Run-id:            13f9e86d214e4d709289e3543622f273
- Run-start:         d33fd6a7cb23070870e734ed87dd4945f4f0bef1
- Issue:             #1551
- Base SHA:          d33fd6a7
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          kyle-codex wave orchestrator (GATE: GO-WITH-CONDITIONS, mailbox outbox-worker-D rev 2)
- Recorded at:       2026-10-23T23:25:00Z

### Section B evidence
commits since filing: none touching woodpecker/, templates/woodpecker/, tests/, .gitignore.
PRs merged since filing: none (latest #1545, #1546, #1548, #1549, #1550 predate the issue, none touch woodpecker).
dup/super: none. Server evidence: kyle19 agent ids 114/115/117 (last_work=0); stuck kyle
pipelines 3568/3569 ran on agent 93 (kyleci, persisted id), so persistence does not reclaim
orphaned workflows - the reaper is split into its own issue; #1551 narrows to the drift fix.

### Section C - the approved plan
1. `woodpecker/docker-compose.agent.yml` - add ./agent-config:/etc/woodpecker, WOODPECKER_HOSTNAME and WOODPECKER_AGENT_LABELS via ${VAR:?...} from woodpecker/.env, WOODPECKER_BACKEND=docker
2. `templates/woodpecker/docker-compose.agent.yml.example` - add the agent-config volume and a WOODPECKER_HOSTNAME line
3. `.gitignore` - ignore woodpecker/agent-config/
4. `tests/test_woodpecker_agent_compose.py` - drift test derived from bootstrap-agent-host.sh heredoc; red on today's files committed as a case; synthetic extra-volume control
Scope: 4 files, ~120 lines. Risks: kyle19 needs woodpecker/.env at the live step (compose up refuses without it); first start registers one new id (no seeding).
