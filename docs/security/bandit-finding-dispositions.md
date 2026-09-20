# Bandit Finding Dispositions

**What this file is for.** `bandit` reports that a line of Python matches a risky
pattern. It says nothing about whether this repository can be hurt by it - that is an
assessment, and it costs real work to reach. This file is where those assessments are
recorded, keyed by `(file, rule)`, so the next person holding a scan result can look
the pair up instead of re-deriving the answer from scratch.

Without it, `.bandit-audit-allow` is a list of eleven lines that somebody once decided
not to act on, with no way to tell a considered acceptance from a line nobody has read
since it was written. That is the state #962 created deliberately and #1113 is the
bill for.

**How to use it.** Take a `(file, rule)` pair from a scan report or from
`.bandit-audit-allow` and search this file for it. A hit is a disposition with its
evidence and the date it was reached. A miss means nobody has assessed it yet: the
register covers only what is listed here, and **a miss is "unknown", never "clean"**.

**What a disposition is not.** It is a judgement about this repository at a point in
time, on stated evidence. It is not a claim about the rule, not a claim about other
projects, and not permanent. Re-read the evidence before relying on an old row: if the
facts it rests on have changed, so has the disposition. Each row below names the
assumption that would expire it.

## Scope

| In scope | Out of scope | Where the rest lives |
|---|---|---|
| MEDIUM-or-worse findings over `lib/` and `scripts/` | The LOW-severity band | #1114, [ADR 0010](../decisions/0010-bandit-low-band-disposition.md) - dispositioned by RULE CLASS rather than by `(file, rule)`, and a `reviewed-low` record in `.bandit-audit-allow` marks each class as read |
| | Shell scripts | issue #972 (shellcheck) |
| | Dependency advisories | `dependency-advisory-dispositions.md` |

## Method, and the control on it

Measured with `bandit 1.9.4` at `-ll` (MEDIUM and above) over `lib` and `scripts`, the
same invocation `make bandit-audit` runs:

```
uv run --extra dev bandit -r lib scripts -ll
```

**The extraction carries its own control.** A count is only evidence once the thing
producing it has been shown able to produce a different one. Before the dispositions
below were written, the scanner was run against constructed inputs that must report -
a `urlopen` behind a scheme check, a hardcoded `/tmp` literal, a `defusedxml` parse -
and the three known-good/known-bad answers came back distinct. That probe is what
established the fact the B310 and B314 rows below rest on: **a guard in front of a
blacklisted call does not clear the finding.** Bandit's B310, B314 and B602 are call
blacklists with no dataflow analysis, so they report the call wherever it appears,
whatever guards it.

That is why fixing a hazard and clearing a finding are separate columns in the table
below, and why the residual falls by one while four of the five groups were changed.

## Register

As of **2026-09-20**, `lib` + `scripts`, 0 scan errors, 0 inline suppressions of
either form (`nosec` 0, `skipped_tests` 0): **8 MEDIUM+ findings remain, all
dispositioned below**, down from the 11 #962 recorded.

| file | rule | sev | disposition | date |
|---|---|---|---|---|
| `lib/cicd/bootstrap.py` | B602 | HIGH | **Accepted** - repository-committed config | 2026-09-20 |
| `lib/cicd/deploy/docker_compose.py` | B602 | HIGH | **Accepted** - repository-committed config | 2026-09-20 |
| `lib/cicd/deploy/guardrails.py` | B602 | HIGH | **Accepted** - repository-committed config | 2026-09-20 |
| `lib/cicd/smoke.py` | B602 | HIGH | **Accepted** - repository-committed config | 2026-09-20 |
| `lib/cicd/steps.py` | B602 ×2 | HIGH | **Accepted** - repository-committed config | 2026-09-20 |
| `lib/cicd/deploy/guardrails.py` | B108 | MEDIUM | **Hazard fixed, finding accepted** - shared path is load-bearing; the open is hardened | 2026-09-20 |
| `scripts/pytest-parallel-differential.py` | B314 | MEDIUM | **Accepted** - self-produced XML | 2026-09-20 |

Both `B310` findings were **closed**, not accepted - see the Closed section.

---

### B602 - `subprocess` with `shell=True` (6 sites, HIGH)

`lib/cicd/bootstrap.py:check_dependency`, `lib/cicd/deploy/docker_compose.py:_run_shell`,
`lib/cicd/deploy/guardrails.py:CapabilityCheck.run`, `lib/cicd/smoke.py:run_single_test`,
`lib/cicd/steps.py:ShellStep.should_skip`, `lib/cicd/steps.py:ShellStep.execute`.

**Disposition: accepted.** The shell is the feature. These fields exist so a project
can write `make test | tee log` in its config and have it mean what it says; removing
`shell=True` removes the capability, not a bug.

The question bandit cannot answer is **whose string reaches it**, and the answer is
recorded as a trust model in `lib/cicd/config.py`'s module docstring: every command
string executed by `lib/cicd` originates either in a file committed to the project
checkout, or in a constant in CPP's own source - both at the same trust level as the
code itself. Anyone who can write those files can already write `Makefile` or
`conftest.py`.

**The sources, named exactly.** The first draft of this row said "`.claude/cicd.yml` or
`.claude/deploy.yaml`" and was wrong about five of the six; a source map that sends a
reader to the wrong file is worse than none, because it answers confidently.

| executed by | field | comes from |
|---|---|---|
| `bootstrap.py:check_dependency` | `BootstrapDependency.check_command` | `.claude/bootstrap.yaml`, else built-ins in `bootstrap.py` |
| `smoke.py:run_single_test` | `SmokeTest.command` | `.claude/cicd.yml` `health.smoke_tests[]` |
| `steps.py:should_skip` | `StepDef.skip_if` | `.claude/cicd_tasks.yml`, else `BUILTIN_PLANS` |
| `steps.py:execute` | `StepDef.command` | `.claude/cicd_tasks.yml`, else `BUILTIN_PLANS` |
| `docker_compose.py:_run_shell` | `DeployConfig.deploy_command` / `.rollback_command` | `.claude/cicd_tasks.yml` `config:`, else a caller-supplied dict |
| `guardrails.py:CapabilityCheck.run` | `ReadinessPolicy.capability_checks[].command` | `.claude/cicd_tasks.yml` readiness config |

`.claude/deploy.yaml` is deliberately absent from that table: it is read by the
`/flow:*` command documents in shell, never by `lib/cicd`.

**Built-in commands are not nothing.** A project with no config files still runs the
`BUILTIN_PLANS` steps - `make deploy`, `python3 -m lib.security gate flow_deploy`. They
are constants in CPP's source, which is the strongest end of this trust model rather
than an exception to it, but "no config means no strings" is false and is not claimed.

**Evidence.** `CICDConfig.load()` reads `<project_root>/.claude/cicd.yml` and nothing
else, and contains no `os.environ` or `getenv` call.

**What keeps it true.** `tests/test_bandit_dispositions.py`:
- `TestShellTrueEnumeration` walks the AST of `lib/` and fails if the `shell=True` call
  sites are not exactly the six in `SHELL_TRUE_SITES` **with their per-function call
  counts** - so a second call added inside an already-registered function fails too,
  which key-set comparison missed. It resolves the `subprocess` import binding, so a
  neighbouring library's `renderer.run(..., shell=True)` is not reported as ours, and
  an aliased `import subprocess as sp` is not missed.
- `TestCommandTrustBoundary` pins that this module declares no smoke commands by
  default, that the built-in commands are a known committed set, that
  `.claude/cicd_tasks.yml` is the override path, that a hostile environment cannot
  inject a command, and that the loader reads the root it was given rather than the
  process cwd.

**Not covered, stated so the boundary is usable.** A value a CI *event* can influence -
a branch name, a PR title, a tag - is a different trust level and must never be
interpolated into one of these strings. `_SAFE_SHELL_TOKEN` in `config.py` constrains
such values where they reach *generated pipeline* commands; that guard covers the
generation path, not this execution path.

**Expires if:** a command string ever arrives from anywhere but a file in the project
checkout. The enumeration test is what forces that question to be asked.

---

### B108 - hardcoded `/tmp` (2 sites, MEDIUM) - resolved in OPPOSITE directions

These two look like the same finding and are not, which is why they are written up
together: read apart, the resolution below looks like an inconsistency someone should
tidy up.

#### `lib/cicd/runner.py` - the uv cache. **FIXED; line removed from the ledger.**

`/tmp/uv-cache` is a fixed, guessable name in a world-writable directory, so any other
local user can create it first and own it - and a package cache is executable content:
whoever owns the directory decides what `uv` unpacks on the next run. Now
`tempfile.gettempdir() / f"uv-cache-{os.getuid()}"`.

A cache has no cross-process contract, so scoping it costs nothing and **the finding
genuinely goes away.** It stays under the temp dir rather than `~/.cache` because the
reason the default exists at all is that a sandboxed `~/.cache` is read-only (#534).

**The uid suffix alone was not the fix, and the first draft of this row claimed it
was** (counter-model review). `/tmp/uv-cache-1000` is exactly as predictable as
`/tmp/uv-cache`: a uid in the name says who *should* own the directory, not who does,
and another local user can still create it first. So `_ensure_private_dir` creates it
`0700` and refuses a path that is a symlink, is not a directory, or is owned by another
uid - raising rather than silently relocating, because a cache somebody else supplied is
executable content and a mystery slow run is a worse outcome than a stated refusal. The
residual race (the directory swapped between the check and `uv` opening it) is not
closable from here and is named rather than implied.

`tests/test_runner.py` pins two properties, because the obvious alternative fix -
`tempfile.mkdtemp()` - would also clear the finding and would silently turn every run
into a cold download with nothing going red: the path is uid-scoped, and it is stable
across calls.

#### `lib/cicd/deploy/guardrails.py` - the deploy lock. **Hazard fixed, finding accepted.**

`DEPLOY_LOCK_PATH` stays `/tmp/claude-power-pack-deploy.lock`: fixed, shared, and
hardcoded, deliberately. Both obvious ways to clear the finding delete the property the
lock exists for:

- **per-uid** stops excluding the other users it is there to exclude on a shared
  Docker host - which is the entire purpose named in the module docstring;
- **`tempfile.gettempdir()`** reads `$TMPDIR`, so a user with a custom one silently
  stops participating in the lock. That is the worse of the two, because nothing would
  look wrong.

A lock in a shared directory is shared on purpose. What is not acceptable is opening
whatever happens to be sitting at the path, and that is what changed. `_open_lock_file`
replaces `open(path, "w")` with `os.open(..., O_RDWR|O_CREAT|O_NOFOLLOW|O_NONBLOCK)`
plus an `fstat` regular-file check, closing two distinct hazards:

| flag | hazard | measured on the pre-fix code |
|---|---|---|
| `O_NOFOLLOW` | a symlink at the path is followed and the target **truncated** | a victim file holding `precious` came back holding `pid=1 time=0` |
| `O_NONBLOCK` + `S_ISREG` | a FIFO at the path **blocks forever** - a hung deploy, not a failed one | a 120s `pytest-timeout` kill inside `open()` |

Checking the fd we actually got (`fstat`) rather than the path before opening it
(`lstat`) is what makes this free of a swap-in-between race. No `O_EXCL`: a leftover
regular lock file is the normal state on any host that has deployed once.

**The creation mode stays `0o666`, and the first draft's `0o644` was a regression
dressed as hardening** (counter-model review). `open(path, "w")` requests `0o666` and
lets umask decide, so on a shared-group host at `umask 002` the lock was created `0664`
and a *second* deploying user could open it `O_RDWR`. At `0o644` that user gets `EACCES`
and cannot take the lock at all - destroying the cross-user exclusion this whole
disposition exists to preserve, in the name of securing it. The hardening is the flags,
not the mode; `tests/test_deploy_guardrails.py` asserts mode parity with the code this
replaced, under `umask 002` specifically, because the default `022` makes both `0644`
and hides the difference.

`tests/test_deploy_guardrails.py` covers both refusals, both "must not fire" halves (a
plain leftover lock still works; an ordinary acquire still works), and pins the shared
path itself so a future tidy-up fails there rather than in production.

**Expires if:** the lock stops needing to exclude other users, or moves out of a
world-writable directory - at which point the shared path is no longer load-bearing and
the finding can be fixed rather than accepted.

---

### B310 - `urlopen` with an unchecked scheme (2 sites, MEDIUM) - CLOSED

`lib/vendor.py:Fetcher.bytes_at`, `scripts/ci-stage-jq.py:main`.

**Disposition: FIXED. Both lines removed from the ledger.**

This section is kept in full because the route to closing it was not the obvious
one, and the obvious one does not work.

Both sites already carried `# noqa: S310` and a comment asserting a fixed `https` host.
A comment is an assertion about every present and future caller, enforced by nobody -
and `urllib.request.urlopen` handles `file:`, `ftp:` and `data:` as happily as `https:`.
Measured on the pre-#1113 code: a `file://` URL passed to `Fetcher.bytes_at` **returned
the file's bytes.** Both sites now call a `_require_https` helper first.

**Checking the initial URL is only half of it** (counter-model review). urllib's default
redirect handler permits a redirect to `http`, `https`, `ftp` or a relative target - the
stdlib says so in a comment beginning "For security reasons" in
`HTTPRedirectHandler.http_error_302` - so a server answering an `https` request with
`302 Location: http://...` was followed, and the fetch the check had just guaranteed was
`https` silently was not. Both sites now go through an opener carrying an
`_HttpsOnlyRedirectHandler` that re-checks every redirect target. Enforcing it there
rather than post-hoc on `response.url` is the point: by the time a downgraded response
exists, the request has already crossed the network in the clear.

For `ci-stage-jq.py` the redirect half is not hypothetical - it is the only path. `JQ_URL`
is a GitHub release link and GitHub answers it with a 302 to its object store, so the
initial URL is the one URL that never serves the payload. The `JQ_URL` check still earns
its place for a different reason: the constant can be edited, and the sha256 pin
guarantees *what* bytes are accepted while saying nothing about *how* they arrived, so an
edit to `file:///...` would keep the pin satisfied and turn a pinned download into a local
file read.

**Why the finding went away, and why that is not a dodge.** A scheme check in front of
`urllib.request.urlopen` does NOT clear B310 - it is a call blacklist with no dataflow
analysis, and that was measured (see *Method*). What cleared it is that the code no
longer calls `urlopen`: both sites now go through a purpose-built
`OpenerDirector` that registers only the https, error, redirect and unknown handlers.

That distinction is worth stating because the two look identical in a count. The opener
is not merely unblacklisted, it is **structurally incapable of the thing B310 warns
about**: `urllib.request.build_opener()` installs `FileHandler`, `FTPHandler`,
`DataHandler` and `HTTPHandler` alongside the https one, and an opener built that way
returns the bytes of a `file://` URL - measured, and asserted as a red case in
`tests/test_vendor_module.py`. The replacement raises
`URLError("unknown url type: file")`. So a future caller who forgets `_require_https`
still cannot read a local file, which matters precisely because bandit no longer warns
about these lines.

The options NOT taken, recorded so they are not re-proposed:

| option | effect | why not |
|---|---|---|
| purpose-built https-only opener + scheme check + redirect check | hazard gone, finding gone | **chosen** |
| scheme check alone, in front of `urlopen` | fixes the initial-URL hazard; finding remains; redirect downgrade still open | the first cut, and insufficient on both counts |
| inline `# nosec` | clears the finding only | less visible than a ledger line; the repository's stated policy is that suppressions are visible or they do not happen |
| hand-rolled `http.client.HTTPSConnection` | clears the finding | replaces stdlib redirect handling wholesale to satisfy a linter - a remedy fitted to the framing rather than the harm |

**Re-opens if:** a caller ever needs a non-https source, or the opener is rebuilt with
`build_opener()`, which would silently restore `file:` and `ftp:` support.

---

### B314 - `ElementTree.parse` on untrusted XML (1 site, MEDIUM)

`scripts/pytest-parallel-differential.py:load`.

**Disposition: accepted, with provenance stated.**

The XXE and billion-laughs attacks B314 warns about need an attacker who controls the
document. The documents here are the two JUnit reports `pytest --junitxml` wrote minutes
earlier in the same run, plus the committed control cases under
`controls/pytest-parallel-differential/cases/`. There is no input path by which a third
party supplies one: an attacker who could write these files could write the script.

A `defusedxml` dependency would clear the finding. Buying a dependency to move a linter
count on a file we produced ourselves is the wrong trade, and the provenance is recorded
in the function's own docstring so the next reader finds it at the call site rather than
only here.

**Expires if:** this loader is ever pointed at a report produced outside the run - a CI
artifact downloaded from elsewhere, a report uploaded by a contributor. That is the
assumption the disposition rests on, and it is the one to re-check.

---

## Closed

Findings that were FIXED rather than accepted. Kept rather than deleted: a row removed
outright loses the reason it was closed, and the next person meeting the same pattern
re-derives it.

| file | rule | closed by | what changed |
|---|---|---|---|
| `lib/cicd/runner.py` | B108 | #1113 | `/tmp/uv-cache` -> a uid-scoped path under the temp dir, created `0700` and validated for symlink/type/owner before use. See the B108 section above for why the sibling lock finding was *not* closed the same way. |
| `lib/vendor.py` | B310 | #1113 | `urllib.request.urlopen` -> a purpose-built opener that registers only https handlers, plus an initial-URL check and a redirect-target check. See the B310 section above. |
| `scripts/ci-stage-jq.py` | B310 | #1113 | Same change. The redirect half is the load-bearing one here: GitHub 302s this download on every run. |

## Blind spots

Named because a register that lists only what it covers reads as if it covers
everything.

- **Rules bandit does not have.** This register disposes of what bandit reports. A
  vulnerability class bandit cannot see is absent from both the scan and this file, and
  its absence here is not evidence.
- **`lib/security/` and the rest of the tree.** The scan covers `lib/` and `scripts/`.
  Other Python in the repository - `tests/`, `templates/`, `vendor/`, the two
  `*_reddit*.py` scripts at the root - is not scanned, so it has no findings and no
  dispositions.
- **LOW severity.** 133 findings, unreviewed, tracked on #1114. Not assessed here and
  not assessed anywhere yet.
