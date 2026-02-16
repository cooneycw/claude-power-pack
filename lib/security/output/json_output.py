"""JSON output formatter for machine-readable results."""

from __future__ import annotations

import json

from ..models import ScanResult


def format_results(result: ScanResult) -> str:
    """Format scan results as JSON."""
    data = {
        "findings": [
            {
                "id": f.id,
                "severity": f.severity.label,
                "title": f.title,
                "file": f.file_path,
                "line": f.line_number,
                "why": f.why,
                "fix": f.fix,
                "command": f.command,
                "scanner": f.scanner,
            }
            for f in sorted(result.findings, key=lambda f: f.severity, reverse=True)
        ],
        "passed": result.passed,
        "skipped": result.skipped,
        "errors": result.errors,
        "summary": {
            "critical": result.critical_count,
            "high": result.high_count,
            "medium": result.medium_count,
            "low": result.low_count,
            "total": len(result.findings),
        },
    }
    return json.dumps(data, indent=2)
