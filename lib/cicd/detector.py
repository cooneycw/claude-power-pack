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
    CloudProvider,
    Framework,
    FrameworkInfo,
    IaCProvider,
    InfrastructureInfo,
    InfraTier,
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

# PowerShell module manifest marker (checked via glob, not exact filename)
_POWERSHELL_MODULE_MARKER = "*.psd1"
_POWERSHELL_SCRIPT_MARKER = "*.ps1"

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

    # Check for PowerShell project markers (module manifests or script files)
    psd1_files = list(root.glob(_POWERSHELL_MODULE_MARKER))
    psm1_files = list(root.glob("*.psm1"))
    ps1_files = list(root.glob(_POWERSHELL_SCRIPT_MARKER))
    if psd1_files or psm1_files:
        for f in (psd1_files + psm1_files)[:3]:
            detected_files.append(f.name)
        frameworks_found.append((Framework.POWERSHELL, PackageManager.PSRESOURCEGET))
    elif ps1_files and not frameworks_found:
        # Only treat bare .ps1 files as a PS project if no other framework detected
        for f in ps1_files[:3]:
            detected_files.append(f.name)
        frameworks_found.append((Framework.POWERSHELL, PackageManager.PSRESOURCEGET))

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


# IaC marker files -> IaCProvider
_IAC_MARKERS: list[tuple[str, IaCProvider]] = [
    ("main.tf", IaCProvider.TERRAFORM),
    ("terraform.tf", IaCProvider.TERRAFORM),
    ("providers.tf", IaCProvider.TERRAFORM),
    ("Pulumi.yaml", IaCProvider.PULUMI),
    ("Pulumi.yml", IaCProvider.PULUMI),
    ("main.bicep", IaCProvider.BICEP),
    ("template.json", IaCProvider.CLOUDFORMATION),
    ("template.yaml", IaCProvider.CLOUDFORMATION),
]

# Cloud provider markers
_CLOUD_MARKERS: list[tuple[str, CloudProvider]] = [
    ("aws", CloudProvider.AWS),
    ("azurerm", CloudProvider.AZURE),
    ("azure", CloudProvider.AZURE),
    ("google", CloudProvider.GCP),
    ("gcp", CloudProvider.GCP),
]

# Tier directory names
_TIER_DIRS: dict[str, InfraTier] = {
    "foundation": InfraTier.FOUNDATION,
    "platform": InfraTier.PLATFORM,
    "app": InfraTier.APP,
    "application": InfraTier.APP,
}


def detect_infrastructure(project_root: str | Path) -> InfrastructureInfo:
    """Detect IaC provider, cloud provider, and tier structure.

    Checks the project root and common subdirectories (infra/, infrastructure/)
    for IaC marker files.

    Args:
        project_root: Path to project root directory.

    Returns:
        InfrastructureInfo with detection results.
    """
    root = Path(project_root)
    detected_files: list[str] = []
    iac_provider = IaCProvider.NONE
    cloud_provider = CloudProvider.UNKNOWN
    has_state_backend = False
    tiers_present: list[InfraTier] = []

    # Directories to scan for IaC files
    scan_dirs = [root]
    for subdir in ("infra", "infrastructure", "iac", "terraform", "pulumi"):
        candidate = root / subdir
        if candidate.is_dir():
            scan_dirs.append(candidate)
            # Check for tier subdirectories
            for tier_name, tier_enum in _TIER_DIRS.items():
                if (candidate / tier_name).is_dir() and tier_enum not in tiers_present:
                    tiers_present.append(tier_enum)

    for scan_dir in scan_dirs:
        # Check IaC markers
        for filename, provider in _IAC_MARKERS:
            filepath = scan_dir / filename
            if filepath.exists():
                rel = str(filepath.relative_to(root))
                detected_files.append(rel)
                if iac_provider == IaCProvider.NONE:
                    iac_provider = provider

        # Check for Terraform files by extension
        if iac_provider == IaCProvider.NONE:
            tf_files = list(scan_dir.glob("*.tf"))
            if tf_files:
                iac_provider = IaCProvider.TERRAFORM
                for tf in tf_files[:3]:  # Cap at 3 for brevity
                    detected_files.append(str(tf.relative_to(root)))

        # Check for state backend
        if (scan_dir / "backend.tf").exists():
            has_state_backend = True
            detected_files.append(str((scan_dir / "backend.tf").relative_to(root)))
        if (scan_dir / ".terraform.lock.hcl").exists():
            has_state_backend = True
        if (scan_dir / "Pulumi.yaml").exists():
            # Pulumi uses its own state management
            has_state_backend = True

    # Detect cloud provider from file contents (check provider blocks)
    if iac_provider == IaCProvider.TERRAFORM:
        for scan_dir in scan_dirs:
            for tf_file in scan_dir.glob("*.tf"):
                try:
                    content = tf_file.read_text(errors="ignore")
                    for marker, cp in _CLOUD_MARKERS:
                        if marker in content:
                            cloud_provider = cp
                            break
                    if cloud_provider != CloudProvider.UNKNOWN:
                        break
                except OSError:
                    continue

    return InfrastructureInfo(
        iac_provider=iac_provider,
        cloud_provider=cloud_provider,
        detected_files=detected_files,
        has_state_backend=has_state_backend,
        tiers_present=tiers_present,
    )
