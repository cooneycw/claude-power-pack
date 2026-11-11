# `cpp-host-write` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `cpp-host-write` (#1139)

The one place `/cpp:init` and `/cpp:update` write host surfaces, and the seam a
managed environment defers.

These writes used to sit as inline shell inside two 75KB command documents,
which had two consequences. Nothing could DECLARE them - a manifest derived
from the helpers missed `~/.bashrc` entirely, because no helper wrote it, the
document did. And nothing could REFUSE them: a defer-set has no code to consult
when the write is prose-shell in a markdown file, so the deferral half of #1139
was not implementable until the writes lived here.

The defer-set is **passed, never detected** - `--defer ~/.bashrc`, or
`CPP_DEFER_SURFACES` for a wrapper that cannot reach argv. Nothing here names
any manager, reads a manager's variable, or inspects containers, mounts or
namespaces. A user who passes nothing gets today's behaviour, not because CPP
detected they were unmanaged but because there was nothing to detect. An
environment marker would not do: variables are inheritable, and a tmux server
hands its environment to every pane started after it, so a marker can arrive in
a session nothing started that way.

A deferred write **exits 3 and names the surface and its declared owner** -
distinct from both success and failure, so a caller can tell "the manager owns
this" from "this went wrong". Skipping quietly is #1138's defect.

`--no-guard` was removed under #1142. It existed only to preserve the
unguarded PS1 append across #1139's relocation, so that the move could be
shown behaviour-preserving before the defect was repaired separately.

`unlink-orphan <dir> <name>` (#1263) is the prune half `link-into` never had.
`/cpp:update` Step 5b feeds it install-drift's `orphaned_helpers` list after the
user confirms, and it re-proves ownership per entry rather than trusting the
name: it removes only a dangling symlink whose target is
`<CPP checkout>/scripts/<its own name>`, and refuses (exit 1) a live link, a
host-owned plain file, a link with any other shape, or one into a root that is
not a CPP checkout. `tests/test_helper_orphan_prune.py` carries the negative
control: an upstream-deleted helper is named and pruned, and each refusal case
survives.
