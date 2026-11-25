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
The destination ends in `skills`. Write requires a new empty tree (a maintained
README may exist), or an already matching expected population. It refuses
changed content rather than pretending to adopt or prune it. Packages contain
regular 0644 UTF-8 SKILL.md and references/*.md files only; symlinks, executable
members, manifests, traversal, command helpers and direct auth-store links fail.
The source topic inventory is nonempty and every entry must build. Metadata
is injected into generated copies; canonical sources and Codex remain unchanged.

Output roots are outside the complete agent and project configuration trees and
all nonempty CLI/environment/global/project/default history candidates. Project
settings override global for effective-history selection; CLI then environment
override both. Every overridden candidate is still excluded. Settings are read
only at exact selected paths, without locks; malformed/unreadable inputs refuse.
Only bounded lstat/readlink of selected history roots/ancestors may resolve an
exclusion. A dangling/looping link or inaccessible ancestor is not clean absence.
Credential-file metadata is forbidden. No history descendant is inventoried.

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
