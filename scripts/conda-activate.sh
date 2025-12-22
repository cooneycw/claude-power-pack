#!/bin/bash
#
# conda-activate.sh - Activate conda environment for current project
#
# This script is designed to be sourced for shell activation.
# For subprocess execution, use --run mode.
#
# Usage:
#   source conda-activate.sh           # Auto-detect and activate
#   source conda-activate.sh myenv     # Activate specific env
#   conda-activate.sh --run "command"  # Run command in env (no source needed)
#   conda-activate.sh --detect         # Just show detected env
#   conda-activate.sh --status         # Show current environment status
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

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
    else
        echo ""
    fi
}

CONDA_BASE=$(find_conda)

# Activate an environment
activate_env() {
    local env_name="$1"

    if [[ -z "$CONDA_BASE" ]]; then
        echo "Error: Cannot find conda installation" >&2
        return 1
    fi

    # Source conda if not already done
    if ! command -v conda &>/dev/null; then
        if [[ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]]; then
            source "$CONDA_BASE/etc/profile.d/conda.sh"
        else
            echo "Error: Cannot source conda.sh" >&2
            return 1
        fi
    fi

    # Check if env exists
    if [[ ! -d "$CONDA_BASE/envs/$env_name" ]]; then
        echo "Error: Environment '$env_name' not found" >&2
        echo "Available environments:" >&2
        conda env list 2>/dev/null | grep -v "^#" | awk '{print "  " $1}'
        return 1
    fi

    # Deactivate current env if any
    if [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
        conda deactivate
    fi

    # Activate requested env
    conda activate "$env_name"
    echo "Activated: $env_name (Python: $(python --version 2>&1))"
}

# Detect environment using conda-detect.sh
detect_env() {
    if [[ -f "$SCRIPT_DIR/conda-detect.sh" ]]; then
        bash "$SCRIPT_DIR/conda-detect.sh"
    else
        # Fallback: check for environment.yml
        if [[ -f "environment.yml" ]]; then
            grep -E "^name:" "environment.yml" 2>/dev/null | head -1 | cut -d: -f2 | tr -d '[:space:]'
        else
            # Fallback: try directory name
            basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
        fi
    fi
}

# Show current environment status
show_status() {
    echo "=== Conda Environment Status ==="
    echo ""

    if [[ -z "$CONDA_BASE" ]]; then
        echo "Conda: NOT FOUND"
        return 1
    fi

    echo "Conda Base: $CONDA_BASE"

    if [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
        echo "Active Env: $CONDA_DEFAULT_ENV"
        echo "Python: $(python --version 2>&1)"
    else
        echo "Active Env: (none - base environment)"
    fi

    echo ""
    echo "Detected Env: $(detect_env || echo '<none>')"
}

# Main
case "${1:-}" in
    --run)
        # Run command in detected environment
        shift
        env_name=$(detect_env)
        if [[ -n "$env_name" ]] && [[ -d "$CONDA_BASE/envs/$env_name" ]]; then
            conda run -n "$env_name" --no-capture-output "$@"
        else
            echo "Warning: No conda env detected, running in current environment" >&2
            "$@"
        fi
        ;;

    --detect)
        # Just show detected environment
        detect_env
        ;;

    --status)
        # Show environment status
        show_status
        ;;

    --help|-h)
        cat << 'EOF'
conda-activate.sh - Activate conda environment for current project

USAGE:
    source conda-activate.sh           Auto-detect and activate
    source conda-activate.sh myenv     Activate specific environment
    conda-activate.sh --run CMD        Run command in detected env
    conda-activate.sh --detect         Show detected environment
    conda-activate.sh --status         Show current environment status
    conda-activate.sh --help           Show this help

NOTES:
    For shell activation, you must SOURCE this script:
        source conda-activate.sh

    For running commands (subprocesses), use --run:
        conda-activate.sh --run pytest tests/

EXAMPLES:
    # Activate project environment
    source conda-activate.sh

    # Run tests in project environment
    conda-activate.sh --run python -m pytest

    # Check status
    conda-activate.sh --status
EOF
        ;;

    "")
        # Auto-detect and activate
        env_name=$(detect_env)
        if [[ -n "$env_name" ]]; then
            activate_env "$env_name"
        else
            echo "No conda environment detected for this project" >&2
            echo "Create .conda-env file or add environment.yml" >&2
            return 1
        fi
        ;;

    *)
        # Explicit env name provided
        activate_env "$1"
        ;;
esac
