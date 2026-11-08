# Doctor CI verdict controls (#1611)

The BAD pipeline case is CONSTRUCTED: it records github-actions explicitly,
then the integration test copies CPP's actual tracked .woodpecker.yml unchanged.
It is not a claim that pre-P1 CPP recorded github-actions. The historical
46d99956 cicd.yml bytes are retained in unknown-historical-record and have no
provider field; the canonical reader must report unknown for them.

The standalone battery drives the stdlib verdict functions with normalized
facts. Required-check facts are outputs of the shared checker, not a second
YAML/protection parser. It does not verify collection. Pytest separately runs
the canonical YAML/check readers, GitHub API collector with offline responses,
container/worktree host reader, and the actual published doctor procedure.
The constructed anchor changes only drift to ok, preserving known-good and
unknown behavior. Row 4 consumes normalized canonical offline lane plans:
the runtime reports recorded lanes and fallback behavior, or unknown when
unavailable. Its BAD lane case is a constructed mismatch between normalized
facts and the explicit selected providers. It tests the defensive verdict
function; a stable real record cannot produce this mismatch because both
inputs use the same canonical reader and registry. It does not prove runtime
lane drift detection. Both default and explicit fallback flags are
reported without executing provider probes.
