# AGY topic builder evidence

Issue #1888. Production host updater integration remains #1889-B; command-derived
skills and an actual AGY cpp-update invocation remain #1876/#1888/#1889.

## Local evidence

At implementation checkpoint fcad40b6, the actual default Make build and check
both reported current for all 18 topics. The focused suite passed 19 tests;
it covers root/external cwd, checkout/worktree/full/shallow source, pinned
tracked input, deterministic metadata/modes and real core preservation.
Subsequent alias-preflight regression failed before its correction and passed
afterward; final-checkpoint totals are recorded with the lane results.

The historical 40d25173 generator and its parser have separately verified
digests. Both generators see identical current payloads and different parser
implementations. Exact path/byte/mode parity passes under 022 and 002 umasks;
the historical 022 manifest has no unattributed delta. Changed transform and
changed parser fixtures each make comparison fail. Missing baseline fails.

The resource regression failed on the initial WIP because reference-style,
image and HTML resources were omitted, then passed after support was added.
Source-file mode and package-byte checks pass through the real neutral core.
Committed controls observe GOOD for complete output, BAD for changed output,
removed package and broken bundled guide, and UNKNOWN for missing source.
The constructed always-current inspector misses all three BAD inputs.

## Review corrections

Pass 1 at 3066cb85 requested changes. All three findings were accepted:
unbounded reference closure, help output stream handling and rejection of
system symlink ancestors. The untallied parser-provenance note is also fixed:
the parser comes from the pinned source snapshot.

Against the exact reviewed implementation, the closure, system-ancestor and
parser-binding regressions all failed. The new bounded-closure GOOD control
also failed there because the old builder expected unrelated corpus files.
All pass after correction. The stderr-help regression failed against the
unchanged stdout-only check before combining the streams; nonzero help and
missing flags still refuse. The full corrected focused suite passed 29 tests.

Local content is now limited to the canonical package and referenced
`docs/skills/` guides/resources, plus the explicit C4 script allowlist. Other
repository references route upstream at the pinned revision; directory links
do not enumerate or copy subtrees. The C4 renderer loads from a temporary
directory without the checkout. The changed-parser negative case now fails
the full generated-tree parity check as well as its link-transform comparison.

| Topic | Files |
|---|---|
| best-practices | 1 |
| boot | 1 |
| browser-tiered | 1 |
| cicd-verification | 3 |
| claude-md-config | 2 |
| code-quality | 2 |
| context-efficiency | 2 |
| documentation | 2 |
| evaluate | 1 |
| hooks-automation | 2 |
| idd-workflow | 2 |
| infrastructure-hardening | 3 |
| mcp-optimization | 2 |
| project-deploy | 1 |
| python-packaging | 2 |
| secrets | 1 |
| session-management | 2 |
| spec-driven-dev | 2 |

## Live consumer evidence

**UNKNOWN - no consumer model turn observed.** No real AGY acceptance is
claimed by local tests.
The host helper's supplied contract reports AGY 1.5.17; the older B0-B4 reports
were from 1.5.14 and are not substituted for this experiment.

The first host run of the 3066cb85 probe aborted at its help check. The
orchestrator reported version 1.5.17, passing positive/absent marker controls,
stdout help length 0 and stderr length 3443 with the required flags, and
completed undo with the real configuration listing unchanged. No model turn
ran. The corrected probe reads both streams; a rerun is still pending.

The committed [probe](antigravity-topic-builder.probe.py) prints undo first,
checks isolated-profile positive/absent markers, records actual argv/version/
help/isolation environment, starts fresh children under the dedicated test
profile, builds the real topic output and stages its exact python-packaging
copy. The consumer runs in an unrelated project with same-named decoys after
the scratch source and intermediate build are deleted. A second fresh process
must report the missing bundled guide. Expected hash/tail are withheld from
the prompt. Raw results stay private for inspection/sanitization; a native
successful exit alone is insufficient. The real configuration is listed only,
never opened for content; its metadata listing must remain unchanged.
