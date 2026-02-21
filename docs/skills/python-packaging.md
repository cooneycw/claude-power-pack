# Python Packaging Best Practices

*PEP 621, PEP 723, and modern Python project configuration with uv*

## The Golden Rule: Use pyproject.toml

**Always use `pyproject.toml` with PEP 621 metadata.** It is the official, tool-agnostic standard for declaring Python project metadata. Never use `setup.py`, `setup.cfg`, or `requirements.txt` for new projects.

| Legacy | Modern (PEP 621) |
|--------|-------------------|
| `setup.py` | `pyproject.toml` `[project]` table |
| `setup.cfg` | `pyproject.toml` `[project]` table |
| `requirements.txt` | `[project.dependencies]` + `uv.lock` |
| `requirements-dev.txt` | `[dependency-groups]` (PEP 735) |

---

## PEP 621: Project Metadata in pyproject.toml

PEP 621 standardizes the `[project]` table. All modern tools (uv, pip, hatch, pdm, flit) read it.

### Minimal pyproject.toml

```toml
[project]
name = "my-project"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.6",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Complete Example

```toml
[project]
name = "my-project"
version = "1.2.0"
description = "A well-structured Python project"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "you@example.com"},
]

dependencies = [
    "httpx>=0.27",
    "pydantic>=2.6,<3",
    "rich>=13.0",
]

[project.optional-dependencies]
all = ["boto3>=1.26", "uvicorn>=0.34"]

[project.urls]
Repository = "https://github.com/you/my-project"

[project.scripts]
my-cli = "my_project.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.8"]

[tool.uv]
package = false  # Set for applications (not installable libraries)
```

### Key Fields

| Field | Required | Purpose |
|-------|----------|---------|
| `name` | Yes | Distribution name (PEP 503 normalized) |
| `version` | Yes* | PEP 440 version (*unless in `dynamic`) |
| `requires-python` | Strongly recommended | Constrains dependency resolution |
| `dependencies` | No | Runtime dependencies (PEP 508 format) |
| `[project.scripts]` | No | CLI entry points |
| `[project.optional-dependencies]` | No | Extras for end-users |

### PEP 621 Rules

1. **Always declare `requires-python`** — constrains resolution and prevents incompatible installs
2. **Use `>=` lower bounds, not `==` pins** — the lockfile handles pinning
3. **Dev tools go in `[dependency-groups]`** (PEP 735), not `[project.optional-dependencies]`
4. **Extras are for end-users** — `pip install my-lib[postgres]`; dev groups are for contributors
5. **Commit `uv.lock`** for applications — ensures reproducible installs
6. **Use `hatchling`** as default build backend — lightweight, standards-compliant

### uv Commands for PEP 621

```bash
uv init my-project              # Creates pyproject.toml with [project] table
uv init --package my-project    # With src/ layout and build system
uv add requests                 # Adds to [project.dependencies]
uv add --dev pytest ruff        # Adds to [dependency-groups] dev
uv add --group lint ruff        # Adds to [dependency-groups] lint
uv remove requests              # Removes from [project.dependencies]
uv lock                         # Generate/update uv.lock
uv sync                         # Install all dependencies from lockfile
```

---

## PEP 723: Inline Script Metadata

PEP 723 embeds dependencies directly in single-file Python scripts using structured comments. `uv run` reads these and auto-installs dependencies in an ephemeral environment.

### Syntax

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests>=2.28",
#   "rich>=13.0",
# ]
# ///

import requests
from rich.pretty import pprint

resp = requests.get("https://api.example.com/data")
pprint(resp.json())
```

### Rules

- Starts with `# /// script`, ends with `# ///`
- Every line between is `#` followed by a space, then TOML content
- Only one `script` block per file
- Place at the top of the file (convention, not required)

### Running PEP 723 Scripts

```bash
uv run script.py                # Auto-installs deps, runs script
uv add --script script.py rich  # Add dependency to existing script
uv init --script new.py         # Create new script with metadata block
uv lock --script script.py      # Create script.py.lock for reproducibility
```

### Self-Executing Scripts (Unix)

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx"]
# ///

import httpx
print(httpx.get("https://example.com").status_code)
```

Then: `chmod +x script.py && ./script.py`

### When to Use PEP 723 vs PEP 621

| Criterion | PEP 723 (Inline) | PEP 621 (pyproject.toml) |
|-----------|-------------------|--------------------------|
| File count | Single `.py` file | Multi-file project |
| Sharing | Gists, Slack, tutorials | Git repositories |
| Installable | No | Yes (pip/uv) |
| Dev dependencies | Not applicable | `[dependency-groups]` |
| Use case | Utility scripts, automation, one-offs | Libraries, applications, services |
| Portability | Self-contained, copy-paste ready | Requires cloning the repo |

**Rule of thumb:** If someone should be able to run it without cloning a repo, use PEP 723. Otherwise, use PEP 621.

### PEP 723 Best Practices

1. **Always include `requires-python`** — even if `">=3.10"`, be explicit
2. **Include `dependencies = []`** even when empty — signals intent
3. **Use `uv add --script`** to manage deps — handles TOML formatting correctly
4. **Pin to ranges, not exact versions** — use `uv lock --script` for reproducibility
5. **Use the shebang** — `#!/usr/bin/env -S uv run --script` makes scripts self-executing

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Do This Instead |
|-------------|--------------|-----------------|
| `setup.py` | Imperative, arbitrary code execution | `pyproject.toml` `[project]` |
| `requirements.txt` for projects | No metadata, no extras, no build system | `[project.dependencies]` + `uv.lock` |
| `pip freeze > requirements.txt` | Captures transitive deps, breaks portability | `uv lock` |
| `pip install -e .` | Slow, doesn't resolve properly | `uv sync` |
| Manual `venv` activation | Error-prone, forgettable | `uv run <command>` |
| `poetry` for new projects | Non-standard lockfile, slower | `uv` with standard PEP 621 |
| Deps in both requirements.txt and pyproject.toml | Contradictory sources of truth | Single source: pyproject.toml |

---

## CPP Convention

All Claude Power Pack components use this pattern:

```toml
[project]
name = "component-name"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [...]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [...]
```

Each component has its own `pyproject.toml` — modular, independent, standard.

---

*Triggers: pyproject.toml, PEP 621, PEP 723, inline script, setup.py, requirements.txt, python packaging, dependencies, uv init*
