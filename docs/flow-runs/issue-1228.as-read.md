# Issue #1228 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1228
- Read at:      2026-09-24T09:12:00Z
- updatedAt:    2026-09-23T21:43:00Z   (context only - moves on comments and labels)
- Body digest:  c2877ce47c9957680decc2b6cb1a1297252ce26d0003957a6d1977635857b0e0   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4556 of 4556 (cap 16384)

## Body as read
## The defect

`register.md:433-453` (worker step 4) and `wave.md:231-245` (orchestrator) prescribe `flow-wave-mailbox.sh supervise` **instead of** a background `watch` parented to the session. The stated reason: `watch` is one-shot and relies on the agent remembering to re-arm it, while `supervise` "makes 'a listener for this role exists' independent of any agent remembering anything."

The `supervise` daemon detaches and is reparented to `systemd --user`. The harness re-invokes a session only when a process **that session owns** exits, so the daemon's surfacing never wakes the session. #871's 2026-09-13 and 09-20 comments establish this as a matter of mechanism. `register.md:452` concedes it ("does not, and cannot, guarantee the harness tells YOU") and then prescribes the daemon anyway.

## What that costs in the field (three waves, two days, two repos)

- **2026-09-22, `kyle-improvements`** (nit #864 comment 5775255814): a daemon survived its session by 18 h. Two of three sessions were deaf while the roster read `armed` and `route=confirmed`.
- **2026-09-23, `claude-improvements`**: two workers sat idle for 20 to 25 min with approved gate rulings unread, while the roster read `watch=armed, 1 watcher, 0s ago`. The only pollers were systemd-parented daemons.
- **2026-09-23, `kyle-improvements`**: an orchestrator was live and idle (pid 1559193) while its daemon (PPID 1514, up 1 d 1 h) kept `watch=armed`. Three messages sat unread for 35+ min.

**Control case (09-22):** a worker that had armed a plain `watch --peek` as a **background tool call parented to its session** came back correctly dead after the restart and re-armed cleanly.

## Why following the docs cannot repair it

- The daemon's `watch --peek` child holds the role, so the session's own `watch` is refused with exit 4 `duplicate`, and the refusal does not name the holder (nit 5775255814). A worker told to "re-arm" tries, is refused, and stays deaf.
- `.supervise-<role>.pid` records the last writer. A session that correctly stops using `supervise` leaves that file frozen, and a check reading it reports the **compliant** session as dead (measured 2026-09-23 against worker-DD). The instrument is inverted with respect to the behaviour it should encourage.
- `watch=armed` and the fused watcher count (#801) answer "is some process polling". They do not answer "can this session hear". Neither distinguishes a daemon from the session.

## Proposed direction (for argument, not yet agreed)

1. Make a **session-parented background `watch`** (`run_in_background: true`, never a trailing `&`, re-armed after every wake) the prescribed listener in `register.md` and `wave.md`. Demote `supervise` to an explicit legacy/opt-in path, and state its no-wake property at the point where it is offered.
2. **Roster discriminator:** record the arming session's pid and start time with each watcher, and have `watch --status` and `list` render `orphaned` (or `no-wake`) when the poller is not parented to a live registered session, instead of `armed`.
3. `supervise` exits when its arming session is gone (see #1107 comment 5803437076). That is a narrower and more valuable exit than the empty-wave case #1107 adds.
4. The `duplicate` refusal names the holder's pid and start time, and says whether the holder is orphaned.

**What argues against this and has to be answered:** the #814 incident that motivated `supervise` (forgotten re-arms, a 25-minute gap with seven unheard messages). A session-parented watch brings back the need to remember. #871 records `asyncRewake` Stop hooks (09-20) as a measured, session-parented waker that re-arms on every `Stop` without the agent remembering, and that is the candidate to weigh against it. **Separately unmeasured:** whether a background `watch` survives `/compact` (#871 §3c; kyle#997 says a kyle watch does not).

## Negative control for any fix

The roster check has to render the **known-bad** shape, as in the 2026-09-23 incident: a daemon-parented poller for a role whose registering session is idle and reachable only through the daemon. It must render that as not-armed. It must render a session-parented background `watch` for the same role as `armed`. A version that renders both as `armed` is today's instrument.

## Provenance

Found by `/self-improvement:retro` on 2026-09-23 (harness 2.1.280) while augmenting #871. Full evidence and vantage notes: #871 comment 5803431537, section 3a. Filed as its own issue rather than in the nit store because it is a live correctness problem on the path every wave follows.

