"""BLIND ANCHOR for controls/secret-assignment-shell - do not fix, do not lint, do not import.

CONSTRUCTED. The plausible WIDER exemption: in a shell file, treat any
double-quoted password value that begins with `$` as a run-time reference. It
is the rule a reader writes when "starts with a substitution" sounds like the
same sentence as "is a substitution" - and it is close to this change's own
first draft, corrected at plan approval.

WHAT IT CATCHES: a plain literal password in a shell file.
WHAT IT MISSES: a hardcoded FALLBACK, `${DB_PASSWORD:-fallback-literal-9x}`.
The default is a literal in the file, and one of the commonest real findings
in shell. It reports nothing on `cases/bad-fallback-literal` (blind, as
required) and nothing on `cases/good-substitutions` (anchor sanity).

Stdlib-only and standalone: it does not import the real package.
"""

import re
from pathlib import Path

PASSWORD = re.compile(r"""(?:password|passwd|pwd)\s*[=:]\s*["']([^"']{8,})["']""", re.IGNORECASE)
SHELL = {".sh", ".bash", ".zsh"}


class Finding:
    def __init__(self, file_path, line_number):
        self.id = "HARDCODED_PASSWORD"
        self.file_path = file_path
        self.line_number = line_number


class Result:
    def __init__(self):
        self.findings = []
        self.units_scanned = 0


def scan(project_root):
    result = Result()
    root = Path(project_root)
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in SHELL):
        content = path.read_text(errors="ignore")
        result.units_scanned += 1
        for match in PASSWORD.finditer(content):
            value = match.group(1)
            quote = content[match.start(1) - 1]
            if quote == '"' and value.startswith("$"):
                continue
            line = content[: match.start()].count("\n") + 1
            result.findings.append(Finding(str(path.relative_to(root)), line))
    return result
