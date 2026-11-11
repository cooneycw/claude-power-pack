# `sandbox-phase1-trial` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `sandbox-phase1-trial`

- sandbox-phase1-trial - ADR 0002 Phase 1 empirical trial harness (#548): runs the E1-E6 sandbox exit-bar checks in a throwaway, project-scoped trial (nested `claude -p` write-containment probes + a `bwrap` ro-bind primitive); never touches `~/.claude/settings.json`. Historical record only: the sandbox epic (#541) was abandoned (#553, ADR 0002 Rejected) after live enablement broke bash on the bwrap/symlink interaction
