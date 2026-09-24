# Issue #921 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #921
- Read at:      2026-09-23T21:40:32Z
- updatedAt:    2026-09-20T14:34:30Z   (context only - moves on comments and labels)
- Body digest:  879b437bae322a93a5d74da200365e3cdb8021eef02bc05b6ad6951062727d89   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 5780 of 5780 (cap 16384)

## Body as read
## Gap

The delegated-lane preflight established by #895 and shipped in #903 correctly separates **registration** from **service**: it probes `/api/generate` with a real generate rather than asking `/api/tags` whether a model is in the catalogue. That was the right correction and it holds.

What it does not establish is **how long a passing probe may be trusted for**. A `/qwen:auto`-shaped invocation is a long agentic run. The evidence below is six readings of one serving host over a few hours in which service went from healthy to connection-reset and back, with the closest healthy-to-broken transition on the order of **minutes**. Nothing in the current practice bounds the validity of a pass, and a run can span well past it.

The host's specific cause was diagnosed and fixed by the owner (memory exhaustion during model load; more memory given) and row 6 confirms it serves now. **The gap is not about this host.** Any capacity-constrained serving host presents to a delegated caller in the same shape: a probe that passed minutes ago, and a run that fails partway with no preflight signal that would have predicted it.

This is #895's own argument one level on. Registration is not service; and serveability is itself **a reading with a timestamp, whose validity expires**.

There is a second edge to it, and it is the one that generalises furthest. **On a host that is failing *during model load*, a preflight that loads a model is not a passive observation — it is the operation that was crashing.** The probe is instrument and trigger at once. Row 6 below spent 13.78s of 14.17s in `load_duration` and none of it in inference, so a probe's own latency reports whether the model happened to be resident — something the caller cannot know in advance, and which the probe itself then changes for the next caller. A measurement that alters the condition it measures, on the exact resource that was exhausted, is not a neutral safety check.

*(This paragraph is the filer's inference, not something the readings establish.)*

## Evidence

Six readings of `100.110.209.34:11434`, 2026-09-13. Sourcing is kept explicit because four were taken directly and two were reported by other sessions.

| # | source | elapsed | result |
|---|---|---|---|
| 1 | observed | ~19s | HTTP 500, body `{"error":"llama-server process has terminated: signal: killed"}` |
| 2 | **cited** (not independently confirmed) | 0.76s | HTTP 200, model RESIDENT 17GB before and after |
| 3 | **cited** (endpoint match not confirmed) | 0.412s | reported SERVING, real token |
| 4 | observed | 30.78s (`-w TIME_TOTAL`) | curl exit 52, empty reply, no body; `/api/ps` sampled 8x at 2s intervals, **all** `{"models":[]}` |
| 5 | observed | 15.0s | curl exit 56, connection reset by peer; `/api/ps` also reset |
| 6 | observed, directly timestamped | 14.17s | HTTP 200 `"OK."`; `load_duration` **13.78s**, `eval_duration` 0.133s; resident after, `size_vram` ~16.6GB |

Rows 1, 4, 5 and 6 were measured directly with raw `curl` output retained. Rows 2 and 3 are cited from other sessions and are marked as reported rather than observed — in particular the endpoint and container of row 3 could not be confirmed to match. Clock times on rows 1–5 are bounds derived from session boundaries and message ordering, not direct measurements; row 6 was timestamped with `date -u` either side.

**Row 1 carried the diagnosis and it was correctly not asserted.** `signal: killed` is genuinely ambiguous between an OOM kill, a supervisor action and a person; naming OOM from the HTTP surface alone would have been a guess dressed as a finding. The owner's later one sentence settled it. The record survived contact with the real cause instead of needing retraction, which is the point of reporting only what the evidence supports.

**Rows 2 and 3 are consistent with the cause without being independent evidence for it.** A resident model does not re-trigger the loader that was failing, so a fast success is a cache hit rather than a health measurement.

## Open questions

Raised, not answered. **No remedy is proposed here on purpose:** six issue-supplied remedies were tested by this group today and every one was wrong when run. An issue that says *"here is the gap, here is the evidence, here are the questions"* is more useful than one that says *"do X"* when nobody has run X.

- Should a passing preflight carry an explicit **freshness window** rather than being treated as valid for a run's full duration?
- Should a long delegated invocation **re-probe mid-flight** — and on what trigger: elapsed time, the first tool-call failure, a fixed interval?
- Should a lane that has shown **any** failure inside some recent window be refused for new dispatch rather than dispatched and degraded?
- **Does the probe perturb the reading it is taking, enough to matter?** The mechanism is described in the Gap section above; whether it changes practice is not established here.

A related consequence, also unresolved: **a fast pass and a slow pass do not mean the same thing.** Fast means resident; slow means a load that succeeded. A probe that *times out* may be a load that would have succeeded given longer — which is a third state, distinct from both pass and fail, and the current practice has nowhere to put it.

## Provenance

Measured and written by `ml-qwen` (rows 1, 4, 5, 6 and Parts 1–3 of the finding), which took the readings from its own container, stopped on a clean negative without looping or falling back to another lane, and kept observed and cited evidence separate throughout. Filed by `ml-orch`. The perturbation and third-state observations in the last two paragraphs are the filer's, not measured.

Related: #895 (registration versus serveability), #903 (the shipped probe).

