# `coordination-admission` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `coordination-admission`

A shared rollout decision for `gh-pr-merge.sh` and `flow-finish-gate.sh`. Only
exact `on` plus newline bytes in the owner-controlled rollout flag activate
service coordination. `CPP_COORDINATION_ADMISSION_FILE` is a test hook only
and must not be set in operational environments. The default is the `admission`
file inside the dedicated `claude-power-pack/coordination` folder under the
operator's XDG configuration directory (falling back to the user's `.config`
directory). Only this dedicated folder is shared read-only with containers;
other CPP configuration stays outside the mount. Mount the folder rather than
the flag so replacement and removal remain visible to running processes.
Missing, unreadable, symlinked or malformed files preserve the old queue read
and gate execution. The owner changes this signal at the joint switch;
merging helpers does not enable it. The service's
own admission flag and credentials are separate prerequisites. An older bundle
missing this helper uses the old path, so installed/bundled coverage must be
verified before the owner switches.

On opt-in, the finish caller delegates the whole gate once to
`kyle-lock run full-suite`; `CPP_KYLE_LOCK_BIN` selects its executable (default
`kyle-lock`). Metadata-only modes do not acquire. Missing supervisor or refused
admission starts no gate work. The supervisor's exit codes overlap the gate's
(refused 3 is the gate's `warn`), so the parent gate does not pass them through:
the continued gate records its own status in a file and its verdict line is
held back, and only a supervisor exit equal to that status is the gate's
verdict. Anything else - refused, queued, frozen, unavailable, usage, a lease
lost or a stop unconfirmed after the gate finished - is one `fail` with the
supervisor's code named, and the parent writes the single exit line.

The wait for a grant is bounded (issue #1678). The caller passes
`--wait <seconds>` to `kyle-lock run`, taken from `CPP_KYLE_LOCK_WAIT_SECONDS`
(default `3600`; a positive whole number, anything else is a named `fail`
before the supervisor is called, and there is no unbounded setting). Without
it kyle-lock retries an unavailable authority forever, and a gate that never
starts and never fails reads exactly like a slow suite. When the supervisor
exits 75 before the gate started, the verdict is
`FLOW_FINISH_GATE: fail (coordination unavailable: <code>; no grant within <N>s, no gate work started)`,
where `<code>` is the `code` field of kyle-lock's last JSON answer, or
`exit 75` when it gave none. `<N>` is the bound, an upper limit and not a
measured wait: kyle-lock also exits 75 at once on an unusable answer.

One bound covers `queued` as well as `unavailable`, because kyle-lock has a
single deadline for every waiting state and the caller cannot see which state
it is in while it waits. A gate still queued behind a real holder at the bound
therefore ends as `coordination supervisor exited 10`; the default is sized
well above a normal full-suite queue, so raise the variable on a host whose
queue is genuinely longer. The variable is read only on the admission-on path
and has no effect where the flag is off.

Authority configuration is stripped from the
supervised child's environment, and a descendant continuation marker prevents
nested acquisition. The marker is not a security boundary. CPP merges acquire
no `main-merge` barrier and keep all existing required-check/base/head rules;
only advisory queue-budget reads are skipped after opt-in.

Generated repository bundles must remain in sync for parity. Host helper
installation and activation are separate owner runbook actions. The flag is read on every call, so existing processes observe the switch without restarting.
