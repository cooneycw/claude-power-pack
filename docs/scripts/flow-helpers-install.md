# `flow-helpers-install` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `flow-helpers-install`

- flow-helpers-install - installs the stable-path helper family into `~/.claude/scripts/` (#590), the lane behind `/flow:repair`. Flow commands call ~24 helpers at paths the #581 permission allowlist matches by prefix, so a helper the template blesses but nothing installs leaves the rule pointing at a path that does not exist (#677). From a CPP checkout it SYMLINKS, so helpers follow `git pull`; from a legacy plugin cache it COPIES, since a symlink into a retired cache would dangle. `--check` is read-only. Its `HELPERS` array is the canonical stable-path install set - not a flow-only list - and `tests/test_permissions_template_link_parity.py` parses it rather than keeping a copy, because a test holding its own copy of the list under test can only prove the copy matches itself. Verdict `FLOW_HELPERS: ok | installed | unverifiable | missing | stale | error`, where `unverifiable` is NOT a lesser `ok` (#927): it means no source of truth was reachable, so this run could not tell "current" from "a version behind"
