"""Framework detection from project files.

Detects the primary framework and package manager by examining
marker files in the project root.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .models import (
    FRAMEWORK_RUNNERS,
    FRAMEWORK_TARGETS,
    Framework,
    FrameworkInfo,
    PackageManager,
)

# Django markers checked separately (requires manage.py + Python)
_DJANGO_MARKER = "manage.py"

# Marker files → (Framework, PackageManager or None)
# Order matters: more specific markers first
_FRAMEWORK_MARKERS: list[tuple[str, Framework, Optional[PackageManager]]] = [
    # Python markers
    ("pyproject.toml", Framework.PYTHON, None),
    ("setup.py", Framework.PYTHON, None),
    ("setup.cfg", Framework.PYTHON, None),
    ("requirements.txt", Framework.PYTHON, None),
    # Node markers
    ("package.json", Framework.NODE, None),
    # Go markers
    ("go.mod", Framework.GO, PackageManager.GO),
    # Rust markers
    ("Cargo.toml", Framework.RUST, PackageManager.CARGO),
]

# Lock files → PackageManager
_LOCK_FILES: list[tuple[str, PackageManager]] = [
    ("uv.lock", PackageManager.UV),
    ("poetry.lock", PackageManager.POETRY),
    ("Pipfile.lock", PackageManager.PIP),
    ("package-lock.json", PackageManager.NPM),
    ("yarn.lock", PackageManager.YARN),
    ("pnpm-lock.yaml", PackageManager.PNPM),
    ("Cargo.lock", PackageManager.CARGO),
    ("go.sum", PackageManager.GO),
]


def detect_framework(project_root: str | Path) -> FrameworkInfo:
    """Detect project framework and package manager from files present.

    Args:
        project_root: Path to project root directory.

    Returns:
        FrameworkInfo with detection results and recommendations.
    """
    root = Path(project_root)
    detected_files: list[str] = []
    frameworks_found: list[tuple[Framework, Optional[PackageManager]]] = []

    # Check marker files at root
    for filename, framework, pm in _FRAMEWORK_MARKERS:
        if (root / filename).exists():
            detected_files.append(filename)
            frameworks_found.append((framework, pm))

    # Check lock files for package manager detection
    detected_pm: Optional[PackageManager] = None
    for filename, pm in _LOCK_FILES:
        if (root / filename).exists():
            detected_files.append(filename)
            if detected_pm is None:
                detected_pm = pm

    # If no root-level markers, check immediate subdirectories (monorepo/workspace)
    if not frameworks_found:
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            for filename, framework, pm in _FRAMEWORK_MARKERS:
                if (child / filename).exists():
                    detected_files.append(f"{child.name}/{filename}")
                    frameworks_found.append((framework, pm))
                    break  # One marker per subdir is enough

        # Also check subdirectory lock files
        if detected_pm is None:
            for child in sorted(root.iterdir()):
                if not child.is_dir() or child.name.startswith("."):
                    continue
                for filename, pm in _LOCK_FILES:
                    if (child / filename).exists():
                        detected_files.append(f"{child.name}/{filename}")
                        if detected_pm is None:
                            detected_pm = pm
                        break

    if not frameworks_found:
        return FrameworkInfo(
            framework=Framework.UNKNOWN,
            package_manager=PackageManager.UNKNOWN,
            detected_files=detected_files,
            recommended_targets=FRAMEWORK_TARGETS[Framework.UNKNOWN],
        )

    # Deduplicate frameworks
    unique_frameworks = list(dict.fromkeys(fw for fw, _ in frameworks_found))

    if len(unique_frameworks) > 1:
        # Multi-language project
        primary = Framework.MULTI
        secondary = unique_frameworks
    else:
        primary = unique_frameworks[0]
        secondary = []

    # Promote Python → Django if manage.py exists
    if primary == Framework.PYTHON and (root / _DJANGO_MARKER).exists():
        detected_files.append(_DJANGO_MARKER)
        primary = Framework.DJANGO

    # Determine package manager
    if detected_pm is None:
        # Use the PM from framework markers if available
        for fw, pm in frameworks_found:
            if pm is not None:
                detected_pm = pm
                break

    # Fall back to defaults
    if detected_pm is None:
        if primary == Framework.PYTHON:
            # Check for pyproject.toml with uv-compatible content
            if (root / "uv.lock").exists():
                detected_pm = PackageManager.UV
            else:
                detected_pm = PackageManager.PIP
        elif primary == Framework.NODE:
            detected_pm = PackageManager.NPM
        else:
            detected_pm = PackageManager.UNKNOWN

    # Get recommended targets and runner commands
    recommended = FRAMEWORK_TARGETS.get(primary, FRAMEWORK_TARGETS[Framework.UNKNOWN])
    runners = FRAMEWORK_RUNNERS.get((primary, detected_pm), {})

    return FrameworkInfo(
        framework=primary,
        package_manager=detected_pm,
        detected_files=detected_files,
        recommended_targets=recommended,
        runner_commands=runners,
        secondary_frameworks=secondary,
    )
