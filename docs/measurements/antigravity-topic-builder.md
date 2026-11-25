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

## Live consumer evidence

**UNKNOWN - not yet run.** No real AGY acceptance is claimed by local tests.
The host helper's supplied contract reports AGY 1.5.17; the older B0-B4 reports
were from 1.5.14 and are not substituted for this experiment.

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
