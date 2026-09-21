#!/usr/bin/env bash
# clean-host.sh - run a command on a simulated CLEAN CODEX HOST.
#
# Codex is installed; NOTHING else is. The real CPP checkout, the real
# ~/.claude and the real ~/.codex/skills are UNREACHABLE from inside, which is
# the property the whole proof rests on: an arm that can read the checkout can
# COPY the helpers, and then a filesystem effect proves nothing about whether
# CPP's surface was present.
#
# Codex's own --sandbox does NOT give this. workspace-write restricts WRITES;
# reads stay broad, so the real checkout would remain readable. The containment
# has to come from outside codex, which is why this uses bwrap.
#
# Usage: clean-host.sh <sandbox-home> <command...>
# Verify containment (never assume it):
#   clean-host.sh "$SB" /bin/bash -c 'ls /home/cooneycw/Projects; find / -name "flow-*.sh"'
set -euo pipefail
SBHOME="$1"; shift
[ -d "$SBHOME" ] || { echo "clean-host: sandbox home does not exist: $SBHOME" >&2; exit 2; }

# Resolve the codex PACKAGE directory and mount it whole. Do NOT mount
# ~/.local/bin/codex-code-mode-host over it: that companion binary is
# version-locked to the codex binary beside it, and an older copy decodes the
# IPC frame wrongly ("missing field code_mode_host_duration_ns"). Measured
# 2026-09-21: doing so aborted BOTH arms, each exited 0, and each reported
# "Files installed: none" - a uniform, plausible negative produced entirely by
# the harness. Agreement between arms is not evidence when the harness is what
# they agree about.
CODEX_PKG="$(readlink -f "${CODEX_BIN:-$HOME/.local/bin/codex}")"; CODEX_PKG="${CODEX_PKG%/bin/codex}"
[ -x "$CODEX_PKG/bin/codex-code-mode-host" ] || {
    echo "clean-host: package at $CODEX_PKG ships no code-mode-host; refusing to substitute one" >&2; exit 2; }

exec bwrap \
  --ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /sbin /sbin \
  --ro-bind /lib /lib --ro-bind /lib64 /lib64 \
  --ro-bind /etc/resolv.conf /etc/resolv.conf \
  --ro-bind /etc/ssl /etc/ssl --ro-bind /etc/ca-certificates /etc/ca-certificates \
  --ro-bind /etc/alternatives /etc/alternatives \
  --ro-bind /etc/passwd /etc/passwd --ro-bind /etc/group /etc/group \
  --ro-bind "$CODEX_PKG" /opt/codex \
  --proc /proc --dev /dev --tmpfs /tmp --tmpfs /home --tmpfs /run \
  --bind "$SBHOME" /home/clean \
  --setenv HOME /home/clean --setenv USER clean --setenv LOGNAME clean \
  --setenv PATH /opt/codex/bin:/usr/local/bin:/usr/bin:/bin \
  --setenv CODEX_HOME /home/clean/.codex \
  --chdir /home/clean --die-with-parent --unshare-pid \
  "$@"
