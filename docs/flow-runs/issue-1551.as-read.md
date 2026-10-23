<!-- flow-run n=1 id=13f9e86d214e4d709289e3543622f273 -->
## Run 1 - issue #1551 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1551
- Read at:      2026-10-23T23:16:17Z
- updatedAt:    2026-10-23T23:14:48Z   (context only - moves on comments and labels)
- Body digest:  ad5673b3d9114b9d3a6c20183104b57d392798074355036c94081d38e8cd99ee   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3573 of 3573 (cap 16384)

### Body as read
## Problem

The Woodpecker agent on proxVMkyle19 does not persist its agent config. On every start it logs:

```
no agent config found at '/etc/woodpecker/agent.conf', start with defaults
could not persist agent config at '/etc/woodpecker/agent.conf'
```

So every restart registers it on the server as a **new agent id**. The server cannot tie work the old id held to the new one, and a pipeline that was mid-run when the host went down stays `running` forever: service steps `running`, later steps `pending`, the deploy step never runs. On 2026-10-23 this happened twice:
- kyle push 3568 (T013, kyle#1821) after the Proxmox reset at 16:26 EDT;
- kyle PR 3569 (kyle#1817) after kyleci's resize reboot.

Dev stayed on the previous release until each pipeline was stopped by hand. Because the list says `running`, it reads as slow CI rather than dead CI. (Those two pipelines ran on kyleci, so kyleci's agent may orphan them too even with persistence. Persistence is the precondition, not the whole fix: see item 3.)

## Cause

kyle19's agent runs from `woodpecker/docker-compose.agent.yml` in this repo (compose `working_dir` /home/cooneycw/Projects/claude-power-pack/woodpecker). That file mounts only the docker socket:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
environment:
  - WOODPECKER_MAX_WORKFLOWS=2
```

The compose file that `woodpecker/bootstrap-agent-host.sh` generates, which runs on kyleci (proxVMkyleci22), already has the fix:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
  # Persists the server-assigned agent id across restarts; without it
  # every restart registers a brand-new agent on the server.
  - ./agent-config:/etc/woodpecker
environment:
  - WOODPECKER_AGENT_LABELS=host=kyleci
  - WOODPECKER_HOSTNAME=proxVMkyleci22
  - WOODPECKER_FILTER_LABELS=host=kyleci
```

The checked-in agent compose has drifted from the bootstrap script's output. kyle19's agent also sets no `WOODPECKER_HOSTNAME` and no agent labels, so the server lists it under the container id (`233e926e1091`) and it takes any unlabelled workflow. kyle and skillc pin `host: kyleci`, so today it only gets unpinned repos.

## Proposed fix

1. Bring `woodpecker/docker-compose.agent.yml` in line with what `bootstrap-agent-host.sh` generates:
   - `./agent-config:/etc/woodpecker`;
   - `WOODPECKER_HOSTNAME`;
   - an agent label such as `host=kyle19`.
   Or delete the static file and generate it with the bootstrap script, so the two cannot drift again.
2. Recreate kyle19's agent from it while the agent is idle. Delete the orphaned agent ids on the server.
3. Separately, and only after a measurement: does a persisted id actually let the server reclaim or fail the workflows of an agent that restarts mid-run? If not, a post-boot reaper is needed that stops `running` pipelines whose workflow containers are absent on their agent. That is a question, unverified.

## Acceptance (with a negative control)

- Restart kyle19's agent twice. The server shows **one** agent id for kyle19 throughout, and the log no longer says `could not persist`.
- Negative control: with the volume removed, the same restart produces a new id. This shows the check can fail.
- A drift check, if added, fails on today's file (no `/etc/woodpecker` mount) and passes on the fixed one.

Related: kyle#1004 nit-store comment 6376599023; kyle#1819 (closed, kyleci now 16c/32G with `MAX_WORKFLOWS=2`).

Found while orchestrating wave kyle-codex (kyle#1640) and restarting T013's push pipeline.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

