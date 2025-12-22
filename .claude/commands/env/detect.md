---
description: Detect and display conda environment for current project
allowed-tools: Bash(~/.claude/scripts/conda-detect.sh:*), Bash(conda:*), Read(environment.yml), Read(.conda-env)
---

# Detect Conda Environment

Automatically detect the conda environment for the current project.

## Usage

```
/env:detect [--info] [--activate] [--exists]
```

## Options

- (default) - Output detected environment name
- `--info` - Show detection details
- `--activate` - Output activation command
- `--exists` - Exit 0 if env exists, 1 otherwise

## Detection Priority

1. `CONDA_ENV_NAME` environment variable (explicit override)
2. `.conda-env` file in project root (simple text file)
3. `environment.yml` name field
4. Directory name matching conda environment
5. `pyproject.toml` [tool.conda] section

## Example Output (--info)

```
Project: /home/user/Projects/my-project
Conda Base: /home/user/miniconda3
Detected Env: my-project
Detection Method: environment.yml
Status: EXISTS
Python: Python 3.11.5
```

## Creating .conda-env File

For projects without `environment.yml`, create a `.conda-env` file:

```bash
echo "my-env-name" > .conda-env
```

This takes precedence over other detection methods.

## Integration with Claude Code

The conda detection hook runs on session start to display the detected environment. This helps ensure you're working in the correct environment.

## Run Script

```bash
~/.claude/scripts/conda-detect.sh "$@"
```
