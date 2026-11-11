# `host-surface-observe` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `host-surface-observe` (#1150)

Certifies host-surface declarations by OBSERVATION rather than by reading. Runs
each in-`$HOME` helper twice against a sandboxed `$HOME`, snapshots before and
after, and diffs the surfaces that APPEARED against the surfaces the script
DECLARED. `host-surface-check` catches a script with no declaration; it cannot
catch one that UNDERSTATES, and prints that bound in its own verdict. This
closes it for the helpers a redirect can sandbox.

**The population is derived, never listed.** Members come from
`host-surface-check.derive_members`, imported rather than re-implemented. The
issue was filed naming "all 15 install-path helpers", nine in and six out;
re-derived at the issue's own commit the population was SIXTEEN, ten in-`$HOME`,
because `stash-worktree-guard.sh` had entered the command documents the day
before. A hardcoded roster went stale within a day of being written, which is
the argument for deriving one.

**An unclassified member is refused, not assumed safe.** This harness EXECUTES
what it classifies as observable, and an unclassified newcomer might `sudo` or
`apt-get install`. A member with no decision reds the gate without being run.

**Six helpers stay `certified=authored` permanently**, each with its escaping
binary named - `sudo`, `systemctl`, `git push`/`gh`/`docker`, `docker`/`sudo`,
`apt`/`curl`, `npm install -g`. Executing them would install packages, restart
units and push to a remote. A PATH shim to widen coverage was rejected in #1139
and the third reason is decisive: a stub would manufacture the exact defect
these scripts detect, since `npm-global-upgrade.sh` exists because
`npm install -g` exits 0 having installed nothing.

**The sandbox is verified in the child, not asserted in the parent.** The issue
rested on "no `getpwuid` in any helper", which is true of the source text and
incomplete: `Path.home()` and `os.path.expanduser()` fall back to
`pwd.getpwuid(os.getuid())` when `HOME` is ABSENT, so two members reach it
transitively. Measured - `HOME` unset resolves to the real home, `HOME=""` to
`/`. Both failing states are refused, and the check asks a child process rather
than trusting the parent's export, which `env -i` or a `sudo -E` boundary would
strip silently.

**A no-op run is not a clean run.** These helpers take subcommands, and invoked
with none most do nothing - at which point "appeared is a subset of declared" is
true for free. Each observable member carries its invocation, and a script that
declares a surface and produced none is reported `unexercised` rather than
counted clean. The first invocation table here named `zshrc-append`, which
`cpp-host-write.sh` does not have, and that guard is what reported it.

**Coverage depends on the write verb.** `write=mkdir` declares a directory NODE
and covers exactly that path; every other verb writes content and covers what
appears beneath. Letting `mkdir` cover its subtree made every declaration added
alongside this change unverifiable - removing one changed no verdict - and was
caught by demonstrating each declaration two-sided rather than by review.

**`certified=` is enforced.** A surface claiming `observed` that a run did not
observe reds; `authored` on a surface that WAS observed is reported as stale and
does not. The asymmetry is deliberate: overstating your certification misleads
in the reassuring direction, understating it misleads nobody.

Its first run found four understatements, all of the same shape - intermediate
directories created and never declared - in `codex-skill-sync.py`,
`cpp-commands-link.sh`, `cpp-host-write.sh` and `install-memory-harness.sh`.
Nine surfaces moved to `certified=observed`; `~/.claude/settings.json` and
`~/.config/opencode/opencode.json` stay `authored` because no invocation reaches
them, and the instrument reports them as unobserved rather than certifying them
silently.

- host-surface-observe `_OVERRIDES_CACHE` IS KEYED ON WHAT THE VALUE IS DERIVED FROM, not on the repo path alone (#1242). The cached overrides are computed from the repo's git configuration AND from `GIT_EXEC_CONFIG_NEUTRALISED`, so a repo-only key let a call made under a DIFFERENT table install its answer as the answer for that repo. `test_the_canary_FIRES_when_the_neutralisation_IS_REMOVED` empties that table to prove the sandbox's alarm can fire - the #1182 load-bearing case - reaches `git_exec_config_overrides`, and cached `[]` for the checkout. `monkeypatch` restores the ATTRIBUTE and knows nothing about a module-level dict, so every later `sandbox_env()` in that worker process built a sandbox neutralising NOTHING, and whichever test asserted a neutralisation next failed on `GIT_CONFIG_COUNT=0`. Under `pytest -n 4` xdist varies which tests share a process, so it fired on a ROTATING innocent test on whatever PR was in flight - measured on PR #1238's pipeline 2629, whose change touched neither file - and passed when the victim ran alone, which is the signature and not the exculpation
- host-surface-observe WHAT THE #1242 FIX IS AND IS NOT. Production behaviour is unchanged: one table means one key, so `make verify` and CI fill the cache exactly once as before, and the containment #1182 established is untouched - the poisoning needed the table emptied, which only a test does, so this was never a hole in the sandbox. CONTROLLED by `tests/test_host_surface_observe.py::test_a_patched_table_does_not_poison_the_cache_for_the_real_one`, one self-contained test rather than an order between two node ids, because a control nobody can run alone is a control nobody runs; measured red on the pre-fix key with `{}` where the real overrides belong - the same `{}.get` the CI failure printed - and green on the fixed one. `@requires_git`, so its green is evidence only where git exists; it SKIPS elsewhere rather than passing, and the CI validate container does have git (pipeline 2629's absent binaries were `curl` and `ps`). `_GIT_EXEC_FILTER_RE` is the only other derivation input and nothing patches it; if that changes it belongs in the key too. The frozen anchor `controls/host-surface-observe/anchors/constructed-blind-covered-by.py` keeps the OLD repo-only key by design - an anchor is a deliberately blind historical artifact, and its sha256 pin is what makes the control's demonstration mean anything
