#!/bin/sh
# Runs one ci-provider-advisory case (issue #1677).
#
# A case is a project tree. It cannot be committed as a git repository, and the
# gate only speaks inside one, so this builds a throwaway repository from it.
#
# SILENCE IS THE GATE'S ANSWER BOTH FOR "RECORDED" AND FOR "COULD NOT ASK", by
# design (an advisory must never cry wolf). So this adapter establishes FIRST,
# on its own channel, that the reader can run at all - otherwise a host without
# PyYAML would read every case as known-good.
set -u
gate="$1"
case_dir="$2"
root="$(pwd)"

for tool in bash git python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "CI_PROVIDER_ADVISORY_CONTROL: unavailable - $tool is not installed"
        exit 2
    fi
done
py="$root/.venv/bin/python"
[ -x "$py" ] || py=python3
if ! PYTHONPATH="$root" "$py" -c 'import yaml, lib.cicd.cli' >/dev/null 2>&1; then
    echo "CI_PROVIDER_ADVISORY_CONTROL: unavailable - the provider reader cannot be imported (PyYAML or lib.cicd missing)"
    exit 2
fi

work="$(mktemp -d)" || { echo "CI_PROVIDER_ADVISORY_CONTROL: unavailable - mktemp failed"; exit 2; }
trap 'rm -rf "$work"' EXIT
cp -R "$case_dir/." "$work/project" 2>/dev/null || mkdir -p "$work/project"
if ! git -C "$work/project" init -q 2>/dev/null; then
    echo "CI_PROVIDER_ADVISORY_CONTROL: unavailable - git init failed"
    exit 2
fi

out="$(CPP_CI_ADVISORY_ROOT="$root" bash "$gate" "$work/project" 2>/dev/null)"
status=$?
if [ "$status" -ne 0 ]; then
    echo "CI_PROVIDER_ADVISORY_CONTROL: unavailable - the advisory exited $status; it must always exit 0"
    exit 2
fi
if [ -n "$out" ]; then
    printf '%s\n' "$out"
    exit 1
fi
echo "CI_PROVIDER_ADVISORY_CONTROL: silent"
exit 0
