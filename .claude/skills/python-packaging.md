---
name: Python Packaging (PEP 621 & PEP 723)
description: Modern Python project configuration with pyproject.toml and inline script metadata
trigger: pyproject.toml, PEP 621, PEP 723, setup.py, requirements.txt, python packaging, dependencies, uv init, inline script
---

# Python Packaging Best Practices

This skill covers PEP 621 (pyproject.toml metadata) and PEP 723 (inline script metadata) for modern Python projects using uv.

## When Activated

Read the full topic skill at: `docs/skills/python-packaging.md`

## Quick Reference

**Always use `pyproject.toml`** with PEP 621 `[project]` table. Never `setup.py` or `requirements.txt` for new projects.

**For single-file scripts**, use PEP 723 inline metadata (`# /// script` block) so `uv run` auto-installs dependencies.

**Key commands:**
```bash
uv init my-project           # Creates PEP 621 pyproject.toml
uv add requests              # Adds to [project.dependencies]
uv add --dev pytest          # Adds to [dependency-groups]
uv run script.py             # Reads PEP 723 metadata, auto-installs
uv add --script s.py rich    # Add dep to inline script metadata
```
