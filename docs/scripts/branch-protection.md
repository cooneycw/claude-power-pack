# `branch-protection` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `branch-protection`

- gh-pr-merge app identity (#1604) - classic `checks[].app_id` and ruleset `integration_id` requirements retain provenance; paginated latest-attempt REST check runs use one pinned head, same-identity duplicates aggregate red before pending before green, and wrong-app/plain statuses cannot satisfy a bound requirement. Legacy contexts remain explicitly unbound. `controls/gh-pr-merge-app-identity` exercises the real wait projection against a historical blind anchor.
- branch-protection - declared branch-protection posture as data (#577, ADR 0004): `.claude/branch-protection.json` holds the posture, `check` (default) normalizes live protection and diffs it (exit 1 on drift), `--apply` PUTs it idempotently, `--show` prints the normalized live view; `make branch-protection-check|apply|show`. Declarations require explicit positive app IDs or -1 (null/omitted IDs refuse before PUT); `controls/branch-protection-app-declaration` proves that write boundary. App bindings are retained in normalized `checks` and compared for drift (#1604); `controls/branch-protection-app-identity` proves same-name wrong-app and unbound-app drift against the historical name-only anchor. Deliberately NOT a CI gate - reading protection needs an admin-scoped token the pipeline does not have
