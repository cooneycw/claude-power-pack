#!/bin/bash
#
# conda-detect.sh - Detect conda environment for current project
#
# Detection priority:
# 1. CONDA_ENV_NAME environment variable (explicit override)
# 2. .conda-env file in project root (project-specific)
# 3. environment.yml 'name:' field
# 4. Directory name convention (matches conda env name)
# 5. pyproject.toml [tool.conda] section
#
# Usage:
#   conda-detect.sh              # Outputs environment name
#   conda-detect.sh --exists     # Exit 0 if env exists, 1 otherwise
#   conda-detect.sh --activate   # Output activation command
#   conda-detect.sh --info       # Show detection details
#
# Returns:
#   Environment name on stdout, empty if not detected
#

set -euo pipefail

# Configuration
PROJECT_ROOT="${PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

# Find conda base directory
find_conda() {
    if [[ -n "${CONDA_EXE:-}" ]]; then
        dirname "$(dirname "$CONDA_EXE")"
    elif [[ -d "$HOME/miniconda3" ]]; then
        echo "$HOME/miniconda3"
    elif [[ -d "$HOME/anaconda3" ]]; then
        echo "$HOME/anaconda3"
    elif [[ -d "/opt/conda" ]]; then
        echo "/opt/conda"
    elif [[ -d "/usr/local/conda" ]]; then
        echo "/usr/local/conda"
    else
        echo ""
    fi
}

CONDA_BASE=$(find_conda)

# Check if environment exists in conda
env_exists() {
    local env_name="$1"
    [[ -z "$CONDA_BASE" ]] && return 1
    [[ -d "$CONDA_BASE/envs/$env_name" ]]
}

# Detection methods (return 0 on success, 1 on failure)
detect_from_explicit() {
    # 1. Explicit environment variable
    if [[ -n "${CONDA_ENV_NAME:-}" ]]; then
        echo "$CONDA_ENV_NAME"
        return 0
    fi
    return 1
}

detect_from_conda_env_file() {
    # 2. .conda-env file in project root
    if [[ -f "$PROJECT_ROOT/.conda-env" ]]; then
        head -1 "$PROJECT_ROOT/.conda-env" | tr -d '[:space:]'
        return 0
    fi
    return 1
}

detect_from_environment_yml() {
    # 3. environment.yml name field
    local env_file=""
    if [[ -f "$PROJECT_ROOT/environment.yml" ]]; then
        env_file="$PROJECT_ROOT/environment.yml"
    elif [[ -f "$PROJECT_ROOT/environment.yaml" ]]; then
        env_file="$PROJECT_ROOT/environment.yaml"
    fi

    if [[ -n "$env_file" ]]; then
        grep -E "^name:" "$env_file" 2>/dev/null | head -1 | cut -d: -f2 | tr -d '[:space:]'
        return 0
    fi
    return 1
}

detect_from_directory_name() {
    # 4. Directory name matches conda env
    local dir_name
    dir_name=$(basename "$PROJECT_ROOT")
    if env_exists "$dir_name"; then
        echo "$dir_name"
        return 0
    fi
    return 1
}

detect_from_pyproject() {
    # 5. pyproject.toml [tool.conda] section
    if [[ -f "$PROJECT_ROOT/pyproject.toml" ]]; then
        # Look for env or env_name in [tool.conda] section
        local env_name
        env_name=$(grep -A5 '\[tool\.conda\]' "$PROJECT_ROOT/pyproject.toml" 2>/dev/null | \
                   grep -E '^env(_name)?[[:space:]]*=' | head -1 | \
                   cut -d= -f2 | tr -d ' "'"'" | head -1)
        if [[ -n "$env_name" ]]; then
            echo "$env_name"
            return 0
        fi
    fi
    return 1
}

# Main detection function
detect_env() {
    local env_name

    env_name=$(detect_from_explicit) && { echo "$env_name"; return 0; }
    env_name=$(detect_from_conda_env_file) && { echo "$env_name"; return 0; }
    env_name=$(detect_from_environment_yml) && { echo "$env_name"; return 0; }
    env_name=$(detect_from_directory_name) && { echo "$env_name"; return 0; }
    env_name=$(detect_from_pyproject) && { echo "$env_name"; return 0; }

    return 1
}

# Get detection method name for --info
get_detection_method() {
    local env_name

    if [[ -n "${CONDA_ENV_NAME:-}" ]]; then
        echo "CONDA_ENV_NAME env var"
        return
    fi

    if [[ -f "$PROJECT_ROOT/.conda-env" ]]; then
        echo ".conda-env file"
        return
    fi

    if [[ -f "$PROJECT_ROOT/environment.yml" ]] || [[ -f "$PROJECT_ROOT/environment.yaml" ]]; then
        echo "environment.yml"
        return
    fi

    env_name=$(basename "$PROJECT_ROOT")
    if env_exists "$env_name"; then
        echo "directory name match"
        return
    fi

    if [[ -f "$PROJECT_ROOT/pyproject.toml" ]] && grep -q '\[tool\.conda\]' "$PROJECT_ROOT/pyproject.toml" 2>/dev/null; then
        echo "pyproject.toml [tool.conda]"
        return
    fi

    echo "none"
}

# Command handling
case "${1:-}" in
    --exists)
        env_name=$(detect_env 2>/dev/null || echo "")
        if [[ -n "$env_name" ]] && env_exists "$env_name"; then
            exit 0
        else
            exit 1
        fi
        ;;

    --activate)
        env_name=$(detect_env 2>/dev/null || echo "")
        if [[ -n "$env_name" ]]; then
            if [[ -n "$CONDA_BASE" ]]; then
                echo "source $CONDA_BASE/etc/profile.d/conda.sh && conda activate $env_name"
            else
                echo "conda activate $env_name"
            fi
        fi
        ;;

    --run)
        # For --run, remaining args are the command
        shift
        env_name=$(detect_env 2>/dev/null || echo "")
        if [[ -n "$env_name" ]] && env_exists "$env_name"; then
            conda run -n "$env_name" --no-capture-output "$@"
        else
            # No conda env, run directly
            "$@"
        fi
        ;;

    --info)
        env_name=$(detect_env 2>/dev/null || echo "")
        method=$(get_detection_method)

        echo "Project: $PROJECT_ROOT"
        echo "Conda Base: ${CONDA_BASE:-<not found>}"
        echo "Detected Env: ${env_name:-<none>}"
        echo "Detection Method: $method"

        if [[ -n "$env_name" ]]; then
            if env_exists "$env_name"; then
                echo "Status: EXISTS"
                # Show Python version if available
                if [[ -x "$CONDA_BASE/envs/$env_name/bin/python" ]]; then
                    py_version=$("$CONDA_BASE/envs/$env_name/bin/python" --version 2>&1)
                    echo "Python: $py_version"
                fi
            else
                echo "Status: NOT FOUND"
                echo ""
                echo "To create this environment:"
                if [[ -f "$PROJECT_ROOT/environment.yml" ]]; then
                    echo "  conda env create -f environment.yml"
                else
                    echo "  conda create -n $env_name python=3.11"
                fi
            fi
        fi
        ;;

    --help|-h)
        cat << 'EOF'
conda-detect.sh - Detect conda environment for current project

USAGE:
    conda-detect.sh              Output environment name
    conda-detect.sh --exists     Exit 0 if env exists, 1 otherwise
    conda-detect.sh --activate   Output activation command
    conda-detect.sh --run CMD    Run command in detected environment
    conda-detect.sh --info       Show detection details
    conda-detect.sh --help       Show this help

DETECTION PRIORITY:
    1. CONDA_ENV_NAME environment variable
    2. .conda-env file in project root
    3. environment.yml 'name:' field
    4. Directory name matching conda env
    5. pyproject.toml [tool.conda] section

EXAMPLES:
    # Check if project has a conda env
    if conda-detect.sh --exists; then
        source $(conda-detect.sh --activate)
    fi

    # Run pytest in project environment
    conda-detect.sh --run pytest tests/

    # Create .conda-env file for explicit configuration
    echo "my-project-env" > .conda-env
EOF
        ;;

    "")
        # Default: output environment name
        detect_env 2>/dev/null || echo ""
        ;;

    *)
        echo "Unknown option: $1" >&2
        echo "Run 'conda-detect.sh --help' for usage" >&2
        exit 1
        ;;
esac
