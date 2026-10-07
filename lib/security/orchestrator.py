"""Security scan orchestrator.

Runs scanner modules, aggregates results, and applies suppressions.
Provides quick, standard, and deep scan modes.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from .config import SecurityConfig
from .models import Finding, ScanResult
from .modules import debug_flags, env_files, gitignore, gitleaks, npm_audit, permissions, pip_audit, secrets


def scan_quick(project_root: str, config: SecurityConfig | None = None) -> ScanResult:
    """Quick scan: native scanners only, working tree only.

    Fast, zero-dependency scan suitable for /flow:finish gate.
    """
    if config is None:
        config = SecurityConfig.load(project_root)

    result = ScanResult()

    # Run native modules
    result.merge(gitignore.scan(project_root))
    result.merge(permissions.scan(project_root))
    result.merge(secrets.scan(project_root))
    result.merge(env_files.scan(project_root))
    result.merge(debug_flags.scan(project_root))

    # Apply suppressions
    _apply_suppressions(result, config, project_root)

    return result


def scan_full(project_root: str, config: SecurityConfig | None = None) -> ScanResult:
    """Full scan: native + available external tools, working tree only.

    Default mode for /security:scan.
    """
    if config is None:
        config = SecurityConfig.load(project_root)

    # Start with quick scan
    result = scan_quick(project_root, config)

    # Add external tool scans (working tree only)
    result.merge(gitleaks.scan(project_root, include_history=False))
    result.merge(pip_audit.scan(project_root))
    result.merge(npm_audit.scan(project_root))

    # Re-apply suppressions (covers external findings)
    _apply_suppressions(result, config, project_root)

    return result


def scan_deep(project_root: str, config: SecurityConfig | None = None) -> ScanResult:
    """Deep scan: everything + git history scanning.

    For /security:deep - includes git history analysis.
    """
    if config is None:
        config = SecurityConfig.load(project_root)

    result = ScanResult()

    # Native modules
    result.merge(gitignore.scan(project_root))
    result.merge(permissions.scan(project_root))
    result.merge(secrets.scan(project_root))
    result.merge(env_files.scan(project_root))
    result.merge(debug_flags.scan(project_root))

    # External tools WITH history
    result.merge(gitleaks.scan(project_root, include_history=True))
    result.merge(pip_audit.scan(project_root))
    result.merge(npm_audit.scan(project_root))

    # Apply suppressions
    _apply_suppressions(result, config, project_root)

    return result


def _gate_message(finding: Finding) -> str:
    """One gate line for *finding*, with enough to act on it (kyle #838).

    Severity and title alone cannot be triaged: five identical HIGH lines for
    "Hardcoded password in source code" leave a reader unable to tell a real
    one from a known-ignorable one without re-deriving the scan, so a genuine
    finding hides among them. The location was never missing - ``Finding``
    carries ``file_path``/``line_number`` and the scanners populate them - it
    was simply not printed.

    ``raw_match`` is deliberately NOT included. It may be the secret itself,
    which is why the model carries ``mask_secret``, and these messages land in
    shared logs and PR bodies. The location is enough to go and look.
    """
    parts = [f"{finding.severity.icon} {finding.severity.label}: {finding.title}"]
    if finding.location:
        parts.append(f"at {finding.location}")
    return " ".join(parts) + f" [{finding.id}]"


def check_gate(result: ScanResult, gate_name: str, config: SecurityConfig | None = None) -> tuple[bool, list[str]]:
    """Check if scan results pass a flow gate.

    Args:
        result: Scan results to evaluate.
        gate_name: Gate to check ("flow_finish" or "flow_deploy").
        config: Security configuration (loads default if None).

    Returns:
        Tuple of (passed, messages).
        passed: True if the gate allows proceeding.
        messages: Warning or error messages to display.
    """
    if config is None:
        config = SecurityConfig._defaults()

    gate = config.gates.get(gate_name)
    if gate is None:
        return True, []

    messages = []
    blocked = False

    for finding in result.findings:
        if finding.severity in gate.block_on:
            messages.append(f"BLOCKED: {_gate_message(finding)}")
            blocked = True
        elif finding.severity in gate.warn_on:
            messages.append(f"WARNING: {_gate_message(finding)}")

    return not blocked, messages


def _apply_suppressions(result: ScanResult, config: SecurityConfig, project_root: str) -> None:
    """Remove suppressed findings from results."""
    gitleaks_literals = _gitleaks_policy_literals(project_root)
    if not config.suppressions and not gitleaks_literals:
        return

    original = result.findings[:]
    result.findings = [
        f
        for f in original
        if not any(s.matches(f) for s in config.suppressions)
        and not _is_declared_in_config(f, config)
        and not _is_declared_in_gitleaks_policy(f, gitleaks_literals)
    ]

    suppressed_count = len(original) - len(result.findings)
    if suppressed_count:
        result.passed.append(f"{suppressed_count} finding(s) suppressed by configuration")


#: Where suppressions are declared, relative to the scanned root.
CONFIG_REL = ".claude/security.yml"


def _is_declared_in_config(finding: Finding, config: SecurityConfig) -> bool:
    """A `secret:` value written in the config file is not a leak of that value.

    Pinning a suppression to one exact value (issue #1299) means writing that
    value into `.claude/security.yml`, which the secrets scanner then reports -
    so every `secret:` suppression would create the block it exists to remove.

    MATCHED BY VALUE, NOT BY ID (issue #1405): the original `s.id ==
    finding.id` check meant a suppression declared for one classifier's id
    (say `AWS_ACCESS_KEY`) did not exempt the SAME declared value when the
    generic `HARDCODED_SECRET` assignment-pattern classifier also fired on
    it, leaving a false-red warn on exactly the line the suppression was
    meant to clear. Dropping the id check widens WITHIN the existing trust
    boundary only, never past it: the two conditions that stay are what
    bound the widening - `finding.file_path == CONFIG_REL` (only this one
    declared-safe file), and the value must still fullmatch a declared
    `secret:` pattern (a different, undeclared value in that same file still
    blocks, and the same declared value anywhere else still blocks too).
    """
    if finding.file_path != CONFIG_REL or finding.secret_value is None:
        return False
    return any(
        s.secret is not None and re.fullmatch(s.secret, finding.secret_value) is not None
        for s in config.suppressions
    )


#: The gitleaks policy file, relative to the scanned root (issue #1405).
GITLEAKS_POLICY_REL = ".gitleaks.toml"

#: TOML keys gitleaks reads as its own allowlist, at the top level
#: (`[allowlist]`) and per-rule (`[[rules]].allowlist`). Each is a list of
#: strings in gitleaks' schema.
_GITLEAKS_ALLOWLIST_KEYS = ("paths", "regexes", "stopwords", "commits")


def _gitleaks_policy_literals(project_root: str) -> frozenset[str]:
    """Every string gitleaks' OWN allowlist declares in `.gitleaks.toml`.

    Read once per scan, not parsed as regex and not applied to any file but
    the policy file itself (see `_is_declared_in_gitleaks_policy`). A missing
    or unparsable file yields an EMPTY set - fail closed, same as a missing
    `.claude/security.yml` leaves `_is_declared_in_config` with nothing to
    exempt - never an exception, and never a reason to trust the file's
    content more broadly.
    """
    path = Path(project_root) / GITLEAKS_POLICY_REL
    if not path.is_file():
        return frozenset()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return frozenset()

    literals: set[str] = set()

    def _collect(allowlist: object) -> None:
        if not isinstance(allowlist, dict):
            return
        for key in _GITLEAKS_ALLOWLIST_KEYS:
            values = allowlist.get(key)
            if isinstance(values, list):
                literals.update(v for v in values if isinstance(v, str))

    _collect(data.get("allowlist"))
    rules = data.get("rules")
    if isinstance(rules, list):
        for rule in rules:
            if isinstance(rule, dict):
                _collect(rule.get("allowlist"))

    return frozenset(literals)


def _is_declared_in_gitleaks_policy(finding: Finding, gitleaks_literals: frozenset[str]) -> bool:
    """A secret-shaped literal gitleaks' OWN policy declares is not a leak of it.

    `.gitleaks.toml` is a security-policy file in the same class as
    `.claude/security.yml` (issue #1405): a repository that plants a TEST
    value as gitleaks' own allowlisted canary (a literal regex/path/stopword
    entry that happens to look like a secret) had no way to tell CPP's native
    scanner that fact, so the same canary blocked `lib.security gate` even
    though gitleaks itself was told to ignore it.

    NARROW ON PURPOSE, same shape as `_is_declared_in_config`: only a finding
    LOCATED IN `.gitleaks.toml` itself, whose matched text is a SUBSTRING of
    one of that file's own declared allowlist strings. This is a literal
    containment check, never a regex evaluation - gitleaks' allowlist entries
    are not compiled or applied to any other file, which would re-delegate
    trust to gitleaks' own (much broader) semantics; it only answers "does
    this policy file assert this exact text is already an accepted canary."
    A different, undeclared secret-shaped value elsewhere in the same file
    still blocks, and the same declared value in any OTHER file still blocks
    too - this function is never consulted for those, since it is only
    called with findings whose `file_path == GITLEAKS_POLICY_REL`.
    """
    if finding.file_path != GITLEAKS_POLICY_REL or finding.secret_value is None:
        return False
    return any(finding.secret_value in literal for literal in gitleaks_literals)

