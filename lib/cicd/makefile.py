"""Makefile parsing, validation, and generation.

Provides:
- parse_makefile: Extract targets, dependencies, and commands
- check_makefile: Validate against framework standards
- generate_makefile: Create from template based on detected framework
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .config import CICDConfig
from .detector import detect_framework
from .models import (
    FRAMEWORK_TARGETS,
    Framework,
    FrameworkInfo,
    MakefileCheckResult,
    MakefileTarget,
    PackageManager,
)


def parse_makefile(project_root: str | Path) -> list[MakefileTarget]:
    """Parse a Makefile and extract targets with dependencies and commands.

    Args:
        project_root: Path to directory containing Makefile.

    Returns:
        List of MakefileTarget objects.
    """
    makefile_path = Path(project_root) / "Makefile"
    if not makefile_path.exists():
        return []

    content = makefile_path.read_text()
    targets: list[MakefileTarget] = []

    # Extract .PHONY declarations
    phony_targets: set[str] = set()
    for match in re.finditer(r"^\.PHONY:\s*(.+)$", content, re.MULTILINE):
        phony_targets.update(match.group(1).split())

    # Parse targets: lines matching "name: [deps]"
    # Followed by tab-indented command lines
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        # Match target definition (not .PHONY, not comments, not variable assignments)
        target_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*):\s*(.*?)$", line)
        if target_match and not line.startswith("#") and "=" not in line.split(":")[0]:
            name = target_match.group(1)
            deps_str = target_match.group(2).strip()
            deps = deps_str.split() if deps_str else []

            # Collect command lines (tab-indented)
            commands: list[str] = []
            j = i + 1
            while j < len(lines) and lines[j].startswith("\t"):
                cmd = lines[j].lstrip("\t")
                commands.append(cmd)
                j += 1

            targets.append(
                MakefileTarget(
                    name=name,
                    dependencies=deps,
                    commands=commands,
                    is_phony=name in phony_targets,
                )
            )
            i = j
        else:
            i += 1

    return targets


def check_makefile(
    project_root: str | Path,
    config: Optional[CICDConfig] = None,
) -> MakefileCheckResult:
    """Validate Makefile completeness against framework standards.

    Args:
        project_root: Path to project root.
        config: Optional CICDConfig. Auto-loads if not provided.

    Returns:
        MakefileCheckResult with validation details.
    """
    root = Path(project_root)
    if config is None:
        config = CICDConfig.load(str(root))

    # Detect framework
    info = detect_framework(root)
    result = MakefileCheckResult(
        framework=info.framework,
        package_manager=info.package_manager,
    )

    makefile_path = root / "Makefile"
    if not makefile_path.exists():
        result.issues.append("No Makefile found")
        result.missing_required = list(config.build.required_targets)
        result.missing_recommended = list(config.build.recommended_targets)
        return result

    # Parse targets
    targets = parse_makefile(root)
    target_names = {t.name for t in targets}
    result.targets_found = sorted(target_names)

    # Check required targets
    for target in config.build.required_targets:
        if target not in target_names:
            result.missing_required.append(target)

    # Check recommended targets (framework-specific)
    framework_recommended = FRAMEWORK_TARGETS.get(
        info.framework, config.build.recommended_targets
    )
    for target in framework_recommended:
        if target not in target_names and target not in config.build.required_targets:
            result.missing_recommended.append(target)
    # Deduplicate: remove from recommended if already in required missing
    result.missing_recommended = [
        t for t in result.missing_recommended if t not in result.missing_required
    ]

    # Check .PHONY declarations
    phony_set = set()
    content = makefile_path.read_text()
    for match in re.finditer(r"^\.PHONY:\s*(.+)$", content, re.MULTILINE):
        phony_set.update(match.group(1).split())
    result.phony_declared = sorted(phony_set)

    for target in targets:
        if target.name not in phony_set and not _target_produces_file(target):
            result.phony_missing.append(target.name)

    # Check for common anti-patterns
    _check_antipatterns(targets, info, result, content)

    return result


def _target_produces_file(target: MakefileTarget) -> bool:
    """Heuristic: does this target produce a file with the same name?

    Most CI/CD targets (lint, test, deploy) do NOT produce files,
    so they should be .PHONY. Only build targets that create
    artifacts (like 'dist/' or a binary) are non-phony.
    """
    # If it has commands that create files/dirs matching the target name, it's file-based
    # For simplicity, assume targets without file-creating patterns are phony
    return False


def _check_antipatterns(
    targets: list[MakefileTarget],
    info: FrameworkInfo,
    result: MakefileCheckResult,
    content: str,
) -> None:
    """Check for common Makefile anti-patterns."""
    # Python: bare python/pytest instead of uv run
    if info.framework == Framework.PYTHON and info.package_manager == PackageManager.UV:
        for target in targets:
            for cmd in target.commands:
                clean_cmd = cmd.lstrip("@-")
                if re.match(r"^(python|python3|pytest|ruff|mypy)\s", clean_cmd):
                    result.issues.append(
                        f"Target '{target.name}': uses bare '{clean_cmd.split()[0]}' "
                        f"instead of 'uv run {clean_cmd.split()[0]}' — "
                        f"may fail outside the virtual environment"
                    )

    # Deploy without test/lint dependencies
    deploy_targets = [t for t in targets if t.name.startswith("deploy")]
    for dt in deploy_targets:
        has_quality_deps = any(d in ("test", "lint", "verify") for d in dt.dependencies)
        if not has_quality_deps and dt.commands:
            result.issues.append(
                f"Target '{dt.name}': runs without test/lint dependencies — "
                f"consider adding 'test lint' as prerequisites"
            )


def generate_makefile(
    project_root: str | Path,
    template_dir: Optional[str | Path] = None,
) -> str:
    """Generate Makefile content based on detected framework.

    Args:
        project_root: Path to project root.
        template_dir: Directory containing .mk templates. If None, generates inline.

    Returns:
        Makefile content as string.
    """
    info = detect_framework(project_root)

    # Try to load from template file
    if template_dir is not None:
        template_path = _get_template_path(info, Path(template_dir))
        if template_path and template_path.exists():
            return template_path.read_text()

    # Generate inline
    return _generate_inline(info)


def _get_template_path(info: FrameworkInfo, template_dir: Path) -> Optional[Path]:
    """Determine which template file to use."""
    mapping = {
        (Framework.PYTHON, PackageManager.UV): "python-uv.mk",
        (Framework.PYTHON, PackageManager.PIP): "python-pip.mk",
        (Framework.PYTHON, PackageManager.POETRY): "python-pip.mk",
        (Framework.DJANGO, PackageManager.UV): "django-uv.mk",
        (Framework.DJANGO, PackageManager.PIP): "django-uv.mk",
        (Framework.DJANGO, PackageManager.POETRY): "django-uv.mk",
        (Framework.NODE, PackageManager.NPM): "node-npm.mk",
        (Framework.NODE, PackageManager.YARN): "node-yarn.mk",
        (Framework.NODE, PackageManager.PNPM): "node-npm.mk",
        (Framework.GO, PackageManager.GO): "go.mk",
        (Framework.RUST, PackageManager.CARGO): "rust.mk",
        (Framework.MULTI, PackageManager.UNKNOWN): "multi.mk",
    }

    filename = mapping.get((info.framework, info.package_manager))
    if filename:
        return template_dir / filename

    # Fallback: try just the framework
    fw_mapping = {
        Framework.PYTHON: "python-uv.mk",
        Framework.DJANGO: "django-uv.mk",
        Framework.NODE: "node-npm.mk",
        Framework.GO: "go.mk",
        Framework.RUST: "rust.mk",
    }
    filename = fw_mapping.get(info.framework)
    if filename:
        return template_dir / filename

    return None


def _generate_inline(info: FrameworkInfo) -> str:
    """Generate a Makefile inline without templates."""
    runners = info.runner_commands
    targets = info.recommended_targets

    lines = [
        "# Project Makefile — Claude Power Pack Integration",
        "#",
        "# The /flow commands auto-discover these targets:",
        "#   /flow:finish  → runs `make lint` and `make test` (if targets exist)",
        "#   /flow:deploy  → runs `make deploy` (or any target you specify)",
        "#   /flow:doctor  → reports which targets are available",
        "#",
        f"# Detected: {info.framework.label} ({info.package_manager.label})",
        "",
        f".PHONY: {' '.join(targets)}",
        "",
        "## Quality gates (used by /flow:finish)",
        "",
    ]

    # Quality gate targets
    for target in ["lint", "test", "typecheck", "format"]:
        if target in targets:
            cmd = runners.get(target, f'@echo "TODO: implement {target}"')
            lines.append(f"{target}:")
            lines.append(f"\t{cmd}")
            lines.append("")

    # Build target
    if "build" in targets:
        cmd = runners.get("build", '@echo "TODO: implement build"')
        lines.append("## Build")
        lines.append("")
        lines.append("build:")
        lines.append(f"\t{cmd}")
        lines.append("")

    # Verify target (pre-deploy gate)
    verify_deps = [t for t in ["lint", "test", "typecheck"] if t in targets]
    if verify_deps:
        lines.append(f"verify: {' '.join(verify_deps)}")
        lines.append('\t@echo "All quality gates passed"')
        lines.append("")

    # Deploy targets
    lines.append("## Deployment (used by /flow:deploy)")
    lines.append("")
    lines.append("deploy:")
    lines.append('\t@echo "Define your deploy steps here"')
    lines.append("")

    # Framework-specific extra targets
    if "vet" in targets:
        cmd = runners.get("vet", "go vet ./...")
        lines.append("vet:")
        lines.append(f"\t{cmd}")
        lines.append("")

    if "build-release" in targets:
        cmd = runners.get("build-release", "cargo build --release")
        lines.append("build-release:")
        lines.append(f"\t{cmd}")
        lines.append("")

    if "dev" in targets:
        cmd = runners.get("dev", '@echo "TODO: implement dev server"')
        lines.append("dev:")
        lines.append(f"\t{cmd}")
        lines.append("")

    # Clean target
    if "clean" in targets:
        lines.append("## Utilities")
        lines.append("")
        lines.append("clean:")
        clean_cmd = _get_clean_command(info.framework)
        lines.append(f"\t{clean_cmd}")
        lines.append("")

    return "\n".join(lines)


def _get_clean_command(framework: Framework) -> str:
    """Get the clean command for a framework."""
    commands = {
        Framework.PYTHON: (
            "rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache "
            "dist build *.egg-info .coverage htmlcov"
        ),
        Framework.DJANGO: (
            "rm -rf .pytest_cache __pycache__ .ruff_cache .mypy_cache "
            "dist build *.egg-info .venv staticfiles .coverage htmlcov"
        ),
        Framework.NODE: "rm -rf node_modules dist build .next .nuxt coverage",
        Framework.GO: "rm -rf bin/ coverage.out",
        Framework.RUST: "cargo clean",
        Framework.MULTI: "rm -rf dist build coverage",
    }
    return commands.get(framework, "rm -rf dist build")
