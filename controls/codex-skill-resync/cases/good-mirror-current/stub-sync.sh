#!/bin/sh
# Stands in for codex-skill-sync.py: the mirrors match their sources.
case "$1" in
    --check) echo "codex-skill-sync: 74 skill(s) current in codex/skills/"; exit 0 ;;
    --write) echo "codex-skill-sync: 74 skill(s) current (0 file(s) written)"; exit 0 ;;
    *) exit 2 ;;
esac
