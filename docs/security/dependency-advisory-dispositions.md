# Dependency Advisory Dispositions

**What this file is for.** A scanner reports that a pinned package version carries a
published advisory. It says nothing about whether this repository can be hurt by it -
that is an assessment, and it costs real work to reach. This file is where those
assessments are recorded, keyed by advisory id, so the next person holding a scan
result can look the id up instead of re-deriving the answer from scratch.

Without it, every scan rediscovers the same findings and every reader starts from
zero. That was the failure recorded on issue #922, and this register is its fix.

**How to use it.** Take an id from a scan report - `GHSA-...`, `PYSEC-...` or
`CVE-...` - and search this file for it. A hit is a disposition with its evidence
and the date it was reached. A miss means nobody has assessed it yet: the register
covers only what is listed here, and **a miss is "unknown", never "clean"**.

**What a disposition is not.** It is a judgement about this repository at a point in
time, on stated evidence. It is not a claim about the CVE, not a claim about other
projects, and not permanent. Re-read the evidence before relying on an old row: if
the facts it rests on have changed, so has the disposition.

## Scope

**This register covers the root `uv.lock` only** - the 22 packages the project itself
locks. It does not cover:

| Out of scope | Where it lives |
|---|---|
| `mcp-evaluate/uv.lock` (77 packages; 10 carried advisories when last measured) | issue #943 |
| Automating this check on every run, rather than by hand when someone asks | issue #961 |
| Packages imported but declared nowhere, which no lockfile scan can see | see **Blind spots** below |

## Method

Every `[[package]]` `name`/`version` pair is parsed from the lockfile and posted to
OSV's batch endpoint:

```
POST https://api.osv.dev/v1/querybatch   # ecosystem: PyPI
```

A result with a non-empty `vulns` array is a hit. GHSA and PYSEC records are then
de-duplicated to distinct CVEs by their `aliases`, because one CVE routinely appears
as two or more records and counting records overstates the number of bugs.

**The query carries its own controls.** `urllib3 2.6.3` (known to have advisories)
and `urllib3 2.7.0` (known to have none) are appended to the *same* batch as the
packages under test. If the pinned-version half comes back empty while the positive
control also comes back empty, the extractor or the transport is broken and the
"clean" result is meaningless. A zero is only evidence when the control in the same
batch is non-zero.

## Register

As of **2026-09-16**, against root `uv.lock` at `pygments 2.21.0` / `pytest 9.1.1`:
**0 of 22 packages carry an advisory**, positive control firing.

| Advisory ids | CVE | Package @ version assessed | Disposition | Date |
|---|---|---|---|---|
| GHSA-5239-wwwm-4pmq, PYSEC-2026-2987 | CVE-2026-4539 | pygments 2.19.2 | **Not exposed** - vulnerable lexer unreachable. Upgraded anyway. | 2026-09-16 |
| GHSA-6w46-j5rx-g56g, PYSEC-2026-1845 | CVE-2025-71176 | pytest 9.0.2 | **Not exposed** - code path live; blocked by `fs.protected_symlinks=1` on the dev host and by CI's single-tenant `/tmp`. Upgraded anyway. | 2026-09-16 |
| GHSA-mf9v-mfxr-j63j, PYSEC-2026-142 | CVE-2026-44432 | urllib3 2.6.3 | **Resolved by upgrade; exposure never assessed.** | 2026-09-13 |
| GHSA-qccp-gfcp-xxvc, PYSEC-2026-141 | CVE-2026-44431 | urllib3 2.6.3 | **Resolved by upgrade; exposure never assessed.** | 2026-09-13 |

Dispositions are recorded **per advisory, not per package**. One package can carry
two bugs of different classes - `urllib3 2.6.3` carried a denial-of-service bug and
a header-confidentiality bug at once - and a single verdict per package silently
applies the reasoning for one to the other.

### CVE-2026-4539 - pygments ReDoS in the archetype lexer

**The bug.** Two regexes in `pygments/lexers/archetype.py` backtrack catastrophically
on crafted input: the GUID pattern in `AdlLexer` and the id pattern in
`AtomsLexer.archetype_id`. Fixed in pygments 2.20.0 by bounding both
(`pygments/pygments@24b8aa76`). OSV rates it LOW, local access, availability only.

**Disposition: not exposed. The vulnerable lexer cannot be reached from this
project's locked environment.**

Evidence, as measured on 2026-09-16 against pygments 2.19.2:

1. The vulnerable regex **was** present in the installed copy - `archetype.py:296`,
   byte-identical to the pre-fix side of the upstream commit. The assessment is
   about reachability, not about whether the bug was there.
2. `pygments` is in this lockfile for one reason: it is a transitive dependency of
   `pytest`, its only reverse edge in the file. `pyproject.toml` does not declare it.
3. **Zero** `import pygments` / `from pygments` across 343 `.py` files. *Positive
   control in the same breath:* the identical grep shape run against `pydantic`, a
   real dependency, returns 3 hits - so the zero is checked and found nothing,
   rather than nothing to check.
4. The only consumer in the locked closure is pytest's `_io/terminalwriter.py`,
   which selects a lexer from `Literal["python", "diff"]` - `PythonLexer` or
   `DiffLexer`. The choice is a type-constrained literal, never content-guessed.
5. Driving that real highlight path for **both** literal values and then inspecting
   `sys.modules` shows `pygments.lexers.archetype` **not loaded**. *Positive control:*
   the same probe, run where `AdlLexer` is deliberately imported, reports it loaded -
   so the probe is able to say "yes" and did not.
6. No `guess_lexer` / `get_lexer` call exists anywhere in the tree, and no `.adl`,
   `.adls` or `.odin` file is tracked - so no route reaches the lexer by content
   sniffing or by file extension either.

### CVE-2025-71176 - pytest predictable temporary directory

**The bug.** pytest creates `/tmp/pytest-of-{user}` - a predictable name in a
world-writable sticky directory - and its ownership check followed symlinks
(`pytest-dev/pytest#13669`). Fixed in 9.0.3 by rejecting the path outright when it is
a symlink, and by not following one on the subsequent `stat`/`chmod`
(`pytest-dev/pytest@95d8423`). OSV rates it MODERATE.

**Get the direction of the attack right**, because the obvious reading is backwards.
In 9.0.2 the check is `rootdir.stat()`, which *follows* the link and then requires
`st_uid == <current user>`. A symlink pointing at a directory the **attacker** owns
therefore fails that check and is rejected. The scenario that gets through is a
symlink planted by another user pointing at a directory the **victim** owns: the
ownership check passes, and pytest then chmods that directory and runs its numbered-
directory creation and cleanup - `rmtree` included - inside it. The harm is to the
victim's own data, which is what "denial of service or possibly gain privileges"
means here. Upstream's regression test names its fixture `attacker_controlled` but
creates it as the test user, because a unit test cannot model two UIDs; do not read
that name as the target's ownership.

**Disposition: not exposed, on the kernel mitigation and the CI topology - not on a
head-count of user accounts.**

This one is the opposite shape from the pygments finding, and that is worth stating
plainly rather than rolling both up as "dev tooling, not exposed":

1. **The mechanism is exercised, not dormant.** 90 of 118 test modules use
   `tmp_path` / `tmpdir` / `tmp_path_factory`, and neither `pyproject.toml` nor the
   Makefile sets `basetemp` or `TMPDIR`. Every suite run does create the predictable
   directory. Nothing here rests on the code being unreached.
2. **Dev host - the load-bearing fact is `fs.protected_symlinks = 1`**
   (`fs.protected_hardlinks = 1` likewise). `/tmp` is `drwxrwxrwt`, so under that
   sysctl the kernel refuses to follow a symlink there unless the symlink's owner is
   the following process or the directory's owner. A symlink planted by any other
   uid is not followed, and the attack does not start. This is a property of the
   host's configuration, not of who is logged in.
3. **CI**: the suite runs inside a per-step, single-tenant, ephemeral
   `ghcr.io/astral-sh/uv:python3.11-bookworm-slim` container with its own `/tmp`,
   so there is no second principal in that namespace at all.
4. **What the account count does and does not show.** The dev host has exactly one
   non-system account with a login shell (uid 1000), and `/tmp/pytest-of-cooneycw`
   is mode `0700` owned by it. That is a real observation, but it does **not** bound
   who can plant a symlink: any uid able to create an entry in `/tmp` can, including
   a daemon running under a system account with `/usr/sbin/nologin`. The account
   count is context; point 2 is the control.
5. **The one way to misread this.** Several concurrent agent sessions do run on the
   dev host at once. They all run **as the same uid**, so they are not the threat
   this CVE describes, which is a *different* principal.

**What would move this row.** Either of: `fs.protected_symlinks` set to `0` on a
machine that runs this suite, or any untrusted uid gaining write access to the
effective temp namespace the suite uses (`TMPDIR`, or `/tmp` by default) - which is
broader than "another account gets a login shell", and is the condition to test.

### CVE-2026-44432 and CVE-2026-44431 - urllib3

Cleared by `60f7242` (PR #925), which moved the root lockfile from urllib3 2.6.3 to
2.7.0 on 2026-09-13. Both are recorded here because their issue, CPP #919, has since
been **deleted from GitHub**, and a scan result naming either id would otherwise
lead a reader nowhere.

**No exposure assessment was ever completed for these two, and none is claimed here.**
The PR that fixed them deliberately made no exposure claim. A pre-work comment on
issue #922 offered a reading - that nothing imports `urllib3` and that `requests`,
the carrier that would exercise it, is absent from the root lockfile - and labelled
itself a reading rather than a finding. It was also corrected once, for covering only
one of the two CVEs. Treat it as a lead, not a disposition.

## Blind spots

Stated so that a gap in the method is not mistaken for a clean result.

**A lockfile scan only asks about what is pinned.** A module imported directly but
declared in no dependency metadata is never queried, so it cannot appear in any row
above however vulnerable it is. This repository has a known instance:
`scrape_reddit.py:11` does `import requests`, and no `requests` entry exists in
`uv.lock` - only `types-requests`, the type stubs. Nothing catches it, because
`ignore_missing_imports = true` under mypy and ruff's selected rules (`E`, `F`, `W`,
`I`) do not check that an import is declared. Tracked as issue #1041; it is a
declare-or-drop decision, not an advisory.

**OSV has its own coverage and freshness.** A count is a measurement with a
timestamp, not a permanent property of the lockfile. "0 of 22" above is what OSV read
on 2026-09-16.

**A scanner can under-report.** These dispositions exist because one did: a scanner
named one vulnerable package in this lockfile when OSV read three, and anyone fixing
"the one named" would have walked past the other two. Re-measure the whole file;
never trust a scanner's list to be complete.

**Nothing automatically re-runs this.** The register is a document, kept current by
hand. Adopting a scanner that runs on every change is issue #961, and that is where
the automation belongs - not half-built here.
