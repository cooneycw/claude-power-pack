#!/usr/bin/env bash
# fixture mailbox: accepts --to, --from and --body only
while [ "$#" -gt 0 ]; do
  case "$1" in
    --to) TO="$2"; shift ;;
    --from) FROM="$2"; shift ;;
    --body) BODY="$2"; shift ;;
    --*) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
