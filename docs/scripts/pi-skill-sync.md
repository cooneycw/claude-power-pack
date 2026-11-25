# pi-skill-sync

P1-A1 of #1896 builds portable canonical topic packages and compares file
snapshots. It does not install, adopt, prune, write ownership records, enroll pi
in the shared updater or assert runtime effectiveness. P1-A2 uses the real
`lib.host_update` API frozen at `91635a1d07b20d069fe8db1591b85ee7b3c444ac`.

```sh
make pi-skills
make pi-skills-check
make test-pi-skills
make pi-skills-controls
```

The thin CLI accepts one of `--write`, `--check`, `--fidelity-root DIR`, with
`--root`, `--output-root`, `--home`, `--agent-dir`, `--session-dir` and `--json`.
`--host-fidelity` requires the canonical agent `--fidelity-root` and excludes
caller project settings from this host-global snapshot; it cannot enable writes
or choose an arbitrary inspection root. Global history exclusions still apply.
The destination ends in `skills`. Write requires a new empty tree (a maintained
README may exist), or an already matching expected population. It refuses
changed content rather than pretending to adopt or prune it. Packages contain
regular 0644 UTF-8 SKILL.md and references/*.md files only; symlinks, executable
members, manifests, traversal, command helpers and direct auth-store links fail.
Canonical source files need only be regular and non-executable, accommodating
group-writable checkouts. Generated/fidelity members must be exactly 0644.
The source topic inventory is nonempty and every entry must build. Metadata
is injected into generated copies; canonical sources and Codex remain unchanged.

Build roots are disjoint in BOTH directions from complete agent/project trees
and selected history candidates: output may neither enter nor contain them.
All nonempty CLI/environment/global/project/default history candidates are
selected in ordinary build/check context. Project
settings override global for effective-history selection; CLI then environment
override both. Every overridden candidate is still excluded. Settings are read
only at exact selected paths, without locks; malformed/unreadable inputs refuse.
Only bounded lstat/readlink of selected history roots/ancestors may resolve an
exclusion. A dangling/looping link or inaccessible ancestor is not clean absence.
Credential-file metadata is forbidden. No descendant of a selected history
candidate is inventoried. The host-global snapshot does not select caller
project configuration or promise facts about its unexamined session directory.

`--fidelity-root` can inspect the selected canonical `<agent>/skills`, but never
write it. Scope is `file-snapshot`; concurrent-writer transactionality, ownership
and runtime effectiveness remain unexamined. Other fidelity roots follow build
destination policy. Results name expected and validated counts plus findings;
zero validated is never matches. Code 0 means a complete expected file population
matched; 1 means known difference/refusal, 2 usage error, 4 unavailable evidence.
No runtime selection claim follows from code 0; effectiveness is always unknown.

`skills-check.py --bundled-topic-root FRESH --managed-root TREE` verifies FRESH
against canonical build bytes before comparing TREE. Missing expected members
or source markers cannot silently become skipped foreign packages in this mode.
Legacy unbundled behavior is unchanged. `install-drift.sh` exposes a separate pi
file-snapshot row and names runtime-effectiveness uncertainty.

Committed good/bad/unexaminable cases exercise actual builder and reader output;
the constructed anchor retains missing-source refusal but deliberately ignores
byte/member/marker/payload differences. It must fail the bad controls. The real
pi RPC diagnostic-differential and syscall controls are A2 host-fixture work;
missing binaries mean UNKNOWN/unexecuted, never accepted coverage. Missing
fd/rg remain informational observed startup warnings, not an automatic install.

Codex generator parity loads the exact vendored generator bytes pinned to
`40d25173` and candidate generator bytes against the SAME candidate inputs.
Both execute under the same current umask; tests cover 022 and 002, an intentional
input evolution, and an altered real transform that must fail. The retained
historical payload manifest is a separate documentary comparison; its modes
reflect the historical build environment and do not decide generator parity.
