# `host-surface-check` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `host-surface-check` (#1139)

Derives which scripts must DECLARE a host surface, from the code rather than
from the documents. The universe is hardcoded - the two command documents that
ARE `/cpp:init` and `/cpp:update` - and membership is derived from reachability
out of them, walked to a fixed point, so a helper added to the install path
cannot arrive unenumerated.

`--manifest` emits the declared surfaces as JSON for a managed environment to
read when composing a defer-set. Nothing here names any manager, reads any
environment variable to decide behaviour, or inspects containers, mounts or
namespaces: a consumer is the first user of a general contract, never a branch.

**Catches** a reachable script with no declaration, mechanically. **Does not
catch** a declaring script that UNDERSTATES, which needs observation rather than
parsing - see the module docstring for why a write-verb scanner was rejected,
and why a PATH shim to widen observation coverage was rejected with it.
