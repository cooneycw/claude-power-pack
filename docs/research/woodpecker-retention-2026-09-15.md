# Woodpecker retention: pipeline history and step logs

**Established 2026-09-15 for [#957](https://github.com/cooneycw/claude-power-pack/issues/957). Deployment: Woodpecker server `3.13.0` on `proxvmwoodpecker20` (100.78.227.106), measured from `proxVMkyle19` with `woodpecker-cli` 3.17.0.**

## Verdict

**No deletion of pipelines or step logs has been observed, and the oldest records survive.** Step logs are retrievable from the repo's first pipeline that ran steps - **2026-03-06** - through the day of measurement. That is roughly six months and it is the repository's entire life, not a retention horizon.

Stated at the strength the evidence carries: what is established is that **the oldest surviving records are the oldest records that ever existed, and their logs still serve**. What is NOT established is the stronger universal "nothing has ever been deleted" - a selective deletion, or a log-only purge of pipelines other than those sampled, would leave every measurement below unchanged. See "What remains unverified" in section 2.

CI step history is therefore a viable standing record of what actually executed, which is the question [#952](https://github.com/cooneycw/claude-power-pack/issues/952) was blocked on.

## How to read the evidence in this document

Two kinds of claim appear below and they are **not interchangeable**:

| Kind | What it rests on |
|---|---|
| **MEASURED** | Calls made against the running server on 2026-09-15. Holds regardless of what any config file declares. |
| **DOCUMENTATION-DERIVED** | Upstream Woodpecker documentation. Explains *why* the measurements look as they do; is not itself evidence about this server. |

**Bullets 1 and 4 are MEASURED against the running server.** They are properties of the system as it actually behaves, and no configuration file - read or unread - can overturn them. This independence is what makes the partially-verified bullet 3 non-fatal rather than a hole in the finding.

**Bullet 2 is MIXED and is the one to read carefully.** Its first two lines are measurements; its third and fourth are a documented upstream property and an inference from it. The measurements do not become universal by sitting next to the inference, and the section states its own residue explicitly rather than leaving a reader to work out which line is which.

## 1. Oldest surviving pipeline, and oldest retrievable step log - MEASURED

| | Pipeline | Created | Evidence |
|---|---|---|---|
| Oldest surviving **pipeline** | **#1** | 2026-03-06 23:49:15 | literally pipeline number 1, not a sample floor |
| Oldest retrievable **step log** | **#3** | 2026-03-06 | 639 bytes returned for its last step |

Issue #957 expected these two dates to differ, with the second being the one that matters. **On this deployment they do not differ** - both reach back to the repository's first day of CI.

**#1 and #2 return no log because they have ZERO steps** (`status=error` - they failed before any step was created). That is not log expiry and must not be read as the retention boundary. #3 is the first pipeline that ran steps at all.

Full history: **1418 pipelines** present. This is not a page cap - `--limit 1000` returns 1000 while `--limit 5000` returns 1418.

## 2. External purge, pruning, or volume policy - MEASURED (plus one documented reason)

**No purge policy was found, and no purge that would have removed the oldest records has run.** Four lines, no one of which is the inference [#951](https://github.com/cooneycw/claude-power-pack/issues/951) declined. Read the scope on each - they do not sum to a universal:

1. **No age-ordered purge has removed the oldest records** - MEASURED, and location-independent. `pipeline purge` defaults to `--keep-min 10` and removes oldest-first; any such purge at defaults takes pipeline #1 first. **#1 is still there**, and #3's logs still serve. This holds no matter where such a purge might have been scheduled.
   **It does not exclude:** a `--branch`-filtered purge, a `pipeline log purge` targeting specific pipelines, or any selective deletion. Note particularly that **#1 has no steps and therefore no logs**, so its survival is evidence about pipeline RECORDS and says nothing on its own about log deletion; the log-side evidence is #3 serving 639 bytes from the same day.
2. **No scheduled purge on the CLI host** - MEASURED on `proxVMkyle19`: no user crontab, nothing matching in `/etc/cron.d`, `/etc/cron.daily`, `/etc/cron.weekly`, and no systemd timer beyond stock OS maintenance.
3. **Both purge paths are manual** - `woodpecker-cli pipeline purge` and `pipeline log purge` are operator-invoked commands carrying `--dry-run` and `--keep-min`. They are not a server-side policy and nothing runs them on a schedule here.
4. **Upstream has no automatic retention feature at all** - DOCUMENTATION-DERIVED, see below.

### The upstream statement - DOCUMENTATION-DERIVED, not measured

> "Woodpecker does not perform data archival; it considered out-of-scope for the project."

Quoted verbatim, including the missing "is" in the published text [sic]. Source: [Woodpecker CI - Databases](https://woodpecker-ci.org/docs/2.8/administration/database). The same page states you "should expect the database logs to grow the size of your database considerably."

**Citation caveat:** that sentence was verified on the **2.8-versioned** page. The unversioned `/docs/administration/database` path and a `/docs/3.13/...` equivalent both return 404, so no version-matched page exists to cite for our 3.13 server. The statement is consistent with the measured behaviour of 3.13 but is documentation for a different version, and is recorded that way rather than as a measurement of our deployment.

**Consequence, and it inherits the caveat above.** On the documented behaviour of 2.8 there is no upstream retention or purge *setting*, so there would be no knob `docker.env` could set. This is DOCUMENTATION-DERIVED and **not version-matched to our 3.13 server**: it was not confirmed against 3.13 documentation or source, so "3.13 has no such setting" is consistent with everything measured but is not itself established here. It explains the measurements; it does not replace them, and it is not a substitute for reading the deployed file.

### What remains unverified about deletion

Stated so a later reader does not have to reconstruct it:

- **Selective or log-only deletion** anywhere in history. Nothing sampled was missing, but the sample is not the population, and a targeted `pipeline log purge` leaves the pipeline record intact and would be invisible to a record-level check.
- **Whether an absent pipeline number ever existed.** A 404 establishes current absence only. See discriminator B.
- **Policies on hosts not inspected.** Schedules were checked on the CLI host only. A purge scheduled on `proxvmwoodpecker20` is not excluded - though it cannot already have fired in age-ordered form, since #1 survives.
- **Whether 3.13 specifically lacks a retention setting.** See the version caveat above.

## 3. What the deployed `docker.env` sets - PARTIAL: RECIPE verified, ARTIFACT NOT

**This bullet is the one with a real bound on it, and the distinction below must not be collapsed.**

**RECIPE - verified.** `woodpecker/bootstrap-secrets.py` generates `docker.env` from AWS Secrets Manager (secret `essent-ai`) and writes exactly four keys, from a **hardcoded list**:

- `WOODPECKER_GITHUB_CLIENT`
- `WOODPECKER_GITHUB_SECRET`
- `WOODPECKER_AGENT_SECRET`
- `WOODPECKER_HOST`

All four are credentials or host addressing. No retention setting, and because the key list is hardcoded the generator *cannot* emit one.

**ARTIFACT - NOT verified.** The deployed file itself was not read. The server is `proxvmwoodpecker20`; `proxVMkyle19` has no SSH key to it (`Permission denied (publickey,password)`), and `docker.env` is gitignored, so it exists in the tree nowhere.

**What this means for a reader.** The four-key list describes **what the generator writes, not what is on the server**. A hand-edit applied directly on `proxvmwoodpecker20` - at any time, by anyone - would be invisible to this investigation. Do not restate this section as "docker.env sets only credentials": that sentence is about the artifact, and the artifact was not read.

**Why it does not change the verdict.** Bullets 1, 2 and 4 are measurements of the running server. They hold whatever `docker.env` contains, because they observe the behaviour that file would be configuring. To close the bound properly: read `/path/to/woodpecker/docker.env` on `proxvmwoodpecker20`, or run `docker inspect woodpecker-server` there and read the resolved environment.

## 4. Step-level history across the full history, not only recent pipelines - MEASURED (sampled)

**Retrievable at every point sampled across the full range**, which decisively answers the question #957 posed - history is NOT limited to recent pipelines. Non-empty step logs confirmed at:

| Pipeline | Date | Last-step bytes |
|---|---|---|
| #3 | 2026-03-06 | 639 |
| #50 | 2026-03-08 | 2883 |
| #500 | 2026-07-03 | 989 |
| #800 | 2026-07-08 | 105 |
| #1100 | 2026-08-11 | 105 |
| #1400 | 2026-09-11 | 105 |
| #1721 | 2026-09-15 | 105 |

**Coverage bound.** This is a SAMPLE of 7 pipelines out of 1418, each probed at one step. It establishes that retrievable step history spans March to September and is not confined to recent pipelines. It does NOT establish that every step of every pipeline is retrievable - an individual missing log elsewhere would leave all seven of these measurements unchanged. Treat "retrievable for an arbitrary historical commit" as strongly supported and spot-checkable by the commands below, not as exhaustively verified.

## Three discriminators - REUSABLE beyond this ticket

All three exist because a result from this API has more than one cause, and the wrong reading manufactures a retention boundary that does not exist. The first two concern results that look empty; the third concerns a result that looks full.

### A. A zero-byte step log can mean `skipped` rather than expired

**Age and emptiness are independent on this server.** Pipeline **#1600 is two days old** and its last step returns **zero bytes** - because that step's `State` is **`skipped`** (`dockerfile-lint`, skipped after `validate` failed). A step that never ran has no log to serve.

`State` is a positive identifier, not a complete decision procedure: it tells you a `skipped` step explains its own emptiness, but an **executed step that simply printed nothing is also zero bytes**, and that case is not distinguished from expiry by `State` alone. So a zero is never evidence of expiry by itself; it is a prompt to find the cause, and `skipped` is the first cause to rule in.

Anyone sampling last-steps and reading zeros as expiry would infer a retention boundary from step *outcomes*. **The step's `State` field is what separates the two causes** - check it before reading any empty log as evidence of age.

### B. Absent pipeline NUMBERS are not deletions

1418 pipelines exist against a maximum number of 1721 - **303 absent numbers**, which invite reading as purged history. They are not. Absences are **uniform across the whole range**:

| Number block | Absent |
|---|---|
| 1-200 | 37 |
| 201-400 | 30 |
| 401-600 | 35 |
| 601-800 | 35 |
| 801-1000 | 41 |
| 1001-1200 | 37 |
| 1201-1400 | 37 |
| 1401-1600 | 30 |
| 1601-1721 | 21 |

**Age-ordered purging removes the OLD end first**, so a flat rate across every block - including the newest - is not what an `--older-than` / `--keep-min` purge leaves behind. The distribution is strongly consistent with allocated-but-unmaterialized numbering (numbers claimed by pipeline-creation attempts that never materialised).

**Stated as a hypothesis, because the distribution cannot establish the cause.** A selective deletion scattered through history would produce the same flat profile. And a **404 establishes only current absence** - it cannot say whether a record once existed and was removed. What the uniformity does rule out is the age-ordered purge; it does not resolve what the 303 numbers are. Resolving that would need Woodpecker's number-allocation behaviour or an independent historical record, neither of which was consulted.

### C. A NON-ZERO byte count from `log show` may be an error payload, not a log

The two discriminators above concern empty results. This one is their mirror and is the easier mistake: **a byte count that looks like content can be a CLI error string.**

`pipeline log show` for a pipeline with no steps emits a fatal error rather than an empty log:

```
{"level":"fatal","error":"invalid step '2': no step with number or name '2' found", ...}
```

That is **149 bytes** for pipelines #1 and #2. Piped through `2>&1 | wc -c` - the natural way to measure a log's size - it counts as 149 bytes of apparent log content for a pipeline that has **no steps and no logs whatsoever**.

This was found by auditing a corroborating measurement, not by suspecting it: a second session independently reported "#1 present, 151-byte log", which is consistent with the zero-steps finding only by coincidence - the bytes it counted were the error message, not a log. Nobody was careless; the number simply looks exactly like evidence.

**How to tell them apart.** `pipeline ps` is the reliable signal: it returns **nothing** for a pipeline with no steps. And an error payload is JSON beginning `{"level":"fatal"`, on **stderr** - so the byte count is zero unless stderr is merged, which means two people measuring the same thing can honestly get 0 and 149. Check the stream and the shape before reading a byte count as retrieval.

## Method, and why an absence claim is not being made

This ticket asks about retention, which is absence-shaped, and a broken or unauthorised extractor returns empty for a live log and an expired one identically.

**The finding avoids that failure mode structurally rather than merely guarding against it: no absence is claimed.** The result is a **presence at the far end of history** - pipeline #3 from 2026-03-06 *returns content*. A broken extractor cannot manufacture 639 bytes of real log text.

**Positive control**, run first and through the identical call path used for every historical probe (same binary, same stored context, same subcommand): pipeline **1721 step 3** returned **315 bytes** of real `gitleaks` output. So retrieval demonstrably works and an empty result would have been interpretable had one appeared.

**The instrument also demonstrably returns the other verdict** - #1600 yields zero bytes, and #1/#2 yield nothing at all. Having observed both outcomes from the same instrument, "content returned" is a meaningful signal rather than an untested one.

**Independent check.** A second session on this host re-ran the load-bearing claims through its own calls: #1 present with `status=error`; #3 returning 84,952 bytes across all its steps; #1721 returning 15,293; and `--keep-min` defaulting to 10. Recorded as corroboration, with its bound stated - same host and same server, so it is a second observer rather than a fully independent one.

## Commands to re-run this

```bash
# newest→oldest pipeline history (number|status|created)
woodpecker-cli --disable-update-check pipeline ls \
  --output 'go-template={{range .}}{{.Number}}|{{.Status}}|{{.Created}}{{"\n"}}{{end}}' \
  --limit 5000 cooneycw/claude-power-pack

# steps of one pipeline (State is the field that explains an empty log)
woodpecker-cli --disable-update-check pipeline ps cooneycw/claude-power-pack 1600

# a single step's log - run this against a RECENT pipeline first, as a positive
# control, before believing any empty result from an old one
woodpecker-cli --disable-update-check pipeline log show cooneycw/claude-power-pack 1721 3
```

Note `--output json` is silently ignored; `--output go-template=...` is the working form. Flags must precede the positional repo argument.

## What this does NOT establish

- **The deployed `docker.env` contents** - see bullet 3. Recipe verified, artifact unread.
- **That no purge has ever run, or could never run.** No AGE-ORDERED purge has removed the oldest records, and nothing is scheduled on the CLI host. Selective or log-only deletion elsewhere in history is not excluded, and a purge scheduled on `proxvmwoodpecker20` that has not yet fired would be invisible here. See "What remains unverified" in section 2 for the full residue.
- **Any claim about other repositories.** Every measurement is scoped to `cooneycw/claude-power-pack`. The server hosts others and their retention was not examined.
- **A recommendation.** Issue #957 is a task, not a decision. Whether six months of unpurged, database-backed log growth is acceptable - the upstream docs warn logs grow the database "considerably" - is a separate call for the owner.

## Practical consequence recorded for a reader of `flow-ci-status.sh`

`scripts/flow-ci-status.sh:224` queries `?per_page=50` and then filters that page for a matching SHA. This is a **client-side lookup limit in CPP's own helper and says nothing about server retention** - it is the specific wrong turn #957 warned against.

**A note on that line number, because it is the same failure this document is about.** Issue #957 cites this code as `flow-ci-status.sh:217`, and `:217` is a section-header comment (`# -- Woodpecker lookup --`), not the lookup. The file has not changed since 2026-09-05, so the cite did not drift - it was wrong when written, and it propagated from the issue into the assignment brief and into a wave residual ledger before anyone opened the file. A line number is what stops a reader checking: it reads as verification, and it is the cheapest thing in a citation to get wrong. The correct line is **224**, confirmed by `grep -n per_page scripts/flow-ci-status.sh` against the tree this document was written on.

It does have a real effect worth knowing: **a SHA older than the latest 50 pipelines is not found by that helper even though the server still holds both the pipeline and its logs.** No change is proposed here; recorded so the limit is not later rediscovered as a retention finding.
