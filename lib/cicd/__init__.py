"""CI/CD & Verification for Claude Code projects.

Provides:
- Framework detection (Python/Node/Go/Rust/multi)
- Makefile validation and generation
- Configuration from .claude/cicd.yml

Quick Start:
    from lib.cicd import detect_framework, check_makefile

    # Detect project framework
    info = detect_framework("/path/to/project")
    print(info.framework, info.package_manager)

    # Check Makefile completeness
    result = check_makefile("/path/to/project")
    for gap in result.missing_required:
        print(f"Missing: {gap}")
"""

from .config import CICDConfig
from .detector import detect_framework
from .makefile import check_makefile, generate_makefile, parse_makefile
from .models import (
    Framework,
    FrameworkInfo,
    MakefileCheckResult,
    MakefileTarget,
    PackageManager,
)

__all__ = [
    # Config
    "CICDConfig",
    # Detector
    "detect_framework",
    # Makefile
    "check_makefile",
    "generate_makefile",
    "parse_makefile",
    # Models
    "Framework",
    "FrameworkInfo",
    "MakefileCheckResult",
    "MakefileTarget",
    "PackageManager",
]
