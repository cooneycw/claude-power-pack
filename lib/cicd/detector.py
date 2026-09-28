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
    RESOLUTION_PARTIAL,
    RESOLUTION_RESOLVED,
    RESOLUTION_UNKNOWN,
    RESOLUTION_UNRESOLVED,
    CloudProvider,
    Component,
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


# Directories that are never a COMPONENT, whatever markers they hold (issue
# #1289). Enumeration always looks one level down now, so without this a root
# project's dependency, build and cache trees - which routinely contain their
# own package.json / setup.py / go.mod - would be reported as stacks of their
# own. Hidden directories (`.venv`, `.git`, `.tox`, ...) are excluded by the
# leading-dot rule in `_is_component_dir`, and `*.egg-info` by suffix.
_NON_COMPONENT_DIRS = frozenset(
    {"node_modules", "venv", "vendor", "dist", "build", "__pycache__", "site-packages"}
)


def _is_component_dir(child: Path) -> bool:
    name = child.name
    return (
        child.is_dir()
        and not name.startswith(".")
        and name not in _NON_COMPONENT_DIRS
        and not name.endswith(".egg-info")
    )


def _default_package_manager(framework: Framework) -> PackageManager:
    """The package manager assumed when no lock file says otherwise.

    Python and Django share one fallback (issue #1289): Django used to be
    promoted BEFORE a fallback that only matched ``Framework.PYTHON``, so a
    lock-less Django project got ``unknown`` and an empty runner map although
    ``(DJANGO, PIP)`` runners exist.
    """
    if framework in (Framework.PYTHON, Framework.DJANGO):
        return PackageManager.PIP
    if framework == Framework.NODE:
        return PackageManager.NPM
    return PackageManager.UNKNOWN


def _components_at(directory: Path, rel: str) -> list[Component]:
    """Every stack whose markers sit directly in ``directory``, with evidence."""
    lock_pm: dict[Framework, tuple[str, PackageManager]] = {}
    for filename, pm in _LOCK_FILES:
        if (directory / filename).exists():
            fw = {
                PackageManager.UV: Framework.PYTHON,
                PackageManager.POETRY: Framework.PYTHON,
                PackageManager.PIP: Framework.PYTHON,
                PackageManager.NPM: Framework.NODE,
                PackageManager.YARN: Framework.NODE,
                PackageManager.PNPM: Framework.NODE,
                PackageManager.CARGO: Framework.RUST,
                PackageManager.GO: Framework.GO,
            }[pm]
            lock_pm.setdefault(fw, (filename, pm))
    found: dict[Framework, Component] = {}
    for filename, framework, marker_pm in _FRAMEWORK_MARKERS:
        if not (directory / filename).exists():
            continue
        prefix = "" if rel == "." else f"{rel}/"
        comp = found.get(framework)
        if comp is None:
            if framework in lock_pm:
                lock_name, pm = lock_pm[framework]
                evidence = [f"{prefix}{filename}", f"{prefix}{lock_name}"]
            else:
                pm = marker_pm or _default_package_manager(framework)
                evidence = [f"{prefix}{filename}"]
            comp = Component(rel, framework, pm, evidence)
            found[framework] = comp
        elif f"{prefix}{filename}" not in comp.evidence:
            comp.evidence.insert(len(comp.evidence) - (1 if framework in lock_pm else 0),
                                 f"{prefix}{filename}")
    python = found.get(Framework.PYTHON)
    if python is not None and (directory / _DJANGO_MARKER).exists():
        python.framework = Framework.DJANGO
        python.evidence.append(("" if rel == "." else f"{rel}/") + _DJANGO_MARKER)
    return list(found.values())


def _enumerate_components(root: Path) -> tuple[list[Component], str]:
    """The root's stacks, then each immediate non-excluded subdirectory's.

    ALWAYS both levels (issue #1289). Before, subdirectories were read only
    when the root had no marker, so a root ``package.json`` made a nested
    ``backend/pyproject.toml`` vanish from the result entirely. One level only:
    this is a report of what is there, not a monorepo scheduler.

    Returns the components and, when the subdirectories could NOT be listed,
    why - so the caller reports coverage as unknown rather than complete. A
    swallowed listing error used to leave only the root components, which then
    resolved as "nothing else is here" (counter-model review, #1289).
    """
    components = _components_at(root, ".")
    try:
        children = sorted(root.iterdir())
    except OSError as exc:
        return components, f"subdirectories could not be listed ({type(exc).__name__})"
    for child in children:
        if _is_component_dir(child):
            components.extend(_components_at(child, child.name))
    return components, ""


def _resolve_runners(
    info_framework: Framework,
    runners: dict[str, str],
    components: list[Component],
    enumeration_gap: str = "",
) -> tuple[str, str, list[Component]]:
    """How far the root-level ``runner_commands`` reach (REPORTING ONLY, #1289).

    Every runner default is a command run AT THE ROOT for ONE framework, so it
    covers exactly the root-level components of that framework. Anything nested,
    and any root component of another framework, is uncovered and named - a run
    of one stack must not read as a run of the repository.
    """
    if enumeration_gap:
        return RESOLUTION_UNKNOWN, enumeration_gap, []
    if not components:
        return RESOLUTION_UNRESOLVED, "no supported component was found", []
    if not runners:
        if info_framework == Framework.MULTI:
            reason = "mixed execution cannot be inferred: no single runner covers these components"
        else:
            reason = f"no runner defaults for {info_framework.value}"
        return RESOLUTION_UNRESOLVED, reason, list(components)
    uncovered = [
        c for c in components if not (c.path == "." and c.framework == info_framework)
    ]
    if uncovered:
        return (
            RESOLUTION_PARTIAL,
            "runner defaults run at the repository root for one framework; "
            "the components listed are not run by them",
            uncovered,
        )
    return RESOLUTION_RESOLVED, "", []


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
        components, gap = _enumerate_components(root)
        state, reason, uncovered = _resolve_runners(Framework.UNKNOWN, {}, components, gap)
        return FrameworkInfo(
            framework=Framework.UNKNOWN,
            package_manager=PackageManager.UNKNOWN,
            detected_files=detected_files,
            recommended_targets=FRAMEWORK_TARGETS[Framework.UNKNOWN],
            runner_resolution=state,
            resolution_reason=reason,
            uncovered_components=uncovered,
            components=components,
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

    # Fall back to defaults. Python and Django share the fallback (#1289).
    if detected_pm is None:
        detected_pm = _default_package_manager(primary)

    # Get recommended targets and runner commands
    recommended = FRAMEWORK_TARGETS.get(primary, FRAMEWORK_TARGETS[Framework.UNKNOWN])
    runners = FRAMEWORK_RUNNERS.get((primary, detected_pm), {})

    components, gap = _enumerate_components(root)
    state, reason, uncovered = _resolve_runners(primary, runners, components, gap)
    return FrameworkInfo(
        framework=primary,
        package_manager=detected_pm,
        detected_files=detected_files,
        recommended_targets=recommended,
        runner_commands=runners,
        secondary_frameworks=secondary,
        components=components,
        runner_resolution=state,
        resolution_reason=reason,
        uncovered_components=uncovered,
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
