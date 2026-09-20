#!/usr/bin/env bash
# flow-vantage.sh - Which side of the container boundary is this session on?
# (issue #959, the follow-on to #958's corrected prose.)
#
#: NEGATIVE-CONTROL: controls/flow-vantage
#
# CONTRACT
#   exit 0  FLOW_VANTAGE: host      - this process runs in the initial pid namespace
#   exit 3  FLOW_VANTAGE: container - it does not
#   exit 4  FLOW_VANTAGE: unknown   - the signals disagree, or none could be read
#
# Three lines, always all three, in this order:
#
#   FLOW_VANTAGE_BASIS: <which signals had an opinion, named individually>
#   FLOW_VANTAGE_SOURCE: measured | declared
#   FLOW_VANTAGE: host | container | unknown
#
# ONE VERDICT PER EXIT CODE (the #1027 shape). `ok`, `warn` and `skipped` once
# shared exit 0 in flow-finish-gate.sh, and a caller reading only `$?` could not
# tell "passed cleanly" from "proved nothing". The same distinction is
# load-bearing here and for a sharper reason: `unknown` and `host` have opposite
# routing consequences, so they may never share a code.
#
# ---------------------------------------------------------------------------
# WHY THIS EXISTS
# ---------------------------------------------------------------------------
# The delivery lane INVERTS across the container boundary (`flow/register.md`,
# `flow/wave.md`): for a containerised session the mailbox is lane 1, and
# `SendMessage` addresses a population containing no fleet peer at all - it is
# not empty, it is populated with the wrong sessions, which is worse. Until this
# script there was nothing machine-readable that said which side a session is
# on. Every lane decision in CPP was made by an agent reading a paragraph and
# believing it, and an orchestrator assigning work to a containerised worker
# could not see the worker's lane 1 was useless until the silence.
#
# ---------------------------------------------------------------------------
# DERIVED, NEVER PASSED IN - and why the obvious shape is the wrong default
# ---------------------------------------------------------------------------
# A container indicator exported by the substrate would be simpler and is
# refused as the DEFAULT for three reasons (issue #959):
#
#   * ABSENT CANNOT MEAN HOST. CPP runs on hosts where nothing sets such a
#     variable, so a missing value means `unknown`, not `host`. A flag whose
#     absence is indistinguishable from the negative case decides nothing.
#   * A DECLARED VALUE CAN BE STALE. An image rebuilt, a variable inherited, an
#     export copied into a host shell - and the declaration keeps asserting
#     yesterday's placement with full confidence.
#   * kyle's `KYLE_MASTER_PLACEMENT` PRECEDENT DOES NOT TRANSFER. That declares
#     POLICY - where sessions SHOULD run. This is a FACT ABOUT THE RUNNING
#     PROCESS, and facts are derived. A derived answer also self-corrects when
#     the substrate changes without telling CPP.
#
# A declared override is still worth having as a short-circuit, and it is
# reported as `declared` and never merged into a measured basis - the same
# separation the delivery-lane table enforces one file over.
#
# ---------------------------------------------------------------------------
# THE SIGNALS, AND THE ONES THAT DO NOT WORK
# ---------------------------------------------------------------------------
# **Measured on the host, harness 2.1.266, 2026-09-20**, against the container
# rows established on harness 2.1.266, 2026-09-13 (issue #947; one container,
# kyle session 48). Both stamps are load-bearing: a signal's behaviour is a
# claim about a harness at a date, and a re-measurement that carries neither is
# the same artifact with a fresher feeling (#870).
#
# | Signal                                      | Host           | Container        | Usable? |
# |---------------------------------------------|----------------|------------------|---------|
# | `readlink /proc/self/ns/pid`                | `pid:[4026531836]` | `pid:[4026533495]` | YES, by convention |
# | `/etc/machine-id`                           | 33 bytes       | ABSENT           | YES, one-sided, this image only |
# | `~/.claude/sessions/` in `/proc/self/mountinfo` | 0 matches  | 0 matches        | NO - identical both sides |
# | number of `.json` session records           | 7              | 1                | NO - conflates with "I am alone" |
#
# RECORD COUNT IS THE SIGNAL THAT LOOKS DECISIVE AND IS NOT, and it is the one
# people reach for first, so it is named here rather than merely omitted. A
# container holds one record because discovery is filesystem-based and
# container-private; A HOST SESSION THAT IS THE ONLY SESSION ON THE BOX HOLDS
# ONE RECORD TOO. Those are different facts with opposite routing consequences.
# It is not even stable on one vantage: 6 records on 2026-09-15, 5 on
# 2026-09-16, 7 on 2026-09-20, with no fleet change between. This script
# therefore never opens the sessions directory at all, and
# `tests/test_flow_vantage.py` pins that as behaviour: the verdict does not move
# when the record count does.
#
# THE MOUNT CHECK IS THE OTHER ONE, and it is this instrument's registered
# blindness: `~/.claude/sessions/` appears in `/proc/self/mountinfo` on NEITHER
# side, so a check built on it answers `host` everywhere - including inside a
# container, which is the dangerous direction. `controls/flow-vantage` vendors
# exactly that check as its anchor.
#
# ---------------------------------------------------------------------------
# HOW THE TWO USABLE SIGNALS COMBINE - and why `unknown` is reachable
# ---------------------------------------------------------------------------
# They are NOT two votes of equal weight, and treating them as such is how a
# fleet-specific fact would silently become a general one:
#
#   * THE PID NAMESPACE IS THE GENERAL SIGNAL and the only one that can say
#     `host`. `4026531836` is the conventional initial pid namespace inode on
#     Linux - a CONVENTION being leaned on, written down as one here rather
#     than passed off as a definition. A measured verdict requires it: if it
#     cannot be read, the answer is `unknown`.
#
#     IT HAS A KNOWN DEFEATER, NAMED HERE RATHER THAN LEFT TO BE DISCOVERED
#     (counter-model review, codex/gpt-6-astra, 2026-09-20). A container run
#     with `docker run --pid=host` SHARES the initial namespace, so this signal
#     reads `host` inside it; if that image also ships an `/etc/machine-id`,
#     nothing here contradicts it and the verdict is a confident `host`. What
#     this instrument establishes is therefore precisely "this process is in
#     the initial pid namespace", and `host` is that observation carried into a
#     routing word - not an independent measurement of whether lane 1 can
#     actually reach a fleet peer.
#
#     The bound is stated rather than closed because closing it is a different
#     instrument: peer REACHABILITY, established at the routing site, which
#     `~/.claude/sessions/` visibility alone cannot answer either (that is the
#     row above, measured identical on both sides). It is nit-stored against
#     #864 rather than folded in here, where an unmeasured third signal would
#     arrive with no stamp behind it.
#
#     KYLE'S FLEET IS NOT IN THAT CONFIGURATION, which is why the narrow answer
#     is correct for the population this ships to: the container measured on
#     2026-09-13 read `pid:[4026533495]`, a namespace of its own. A fleet that
#     adopts `--pid=host` invalidates this signal, and that is the trigger to
#     re-measure.
#   * MACHINE-ID IS ONE-SIDED CORROBORATION. An absent or empty `/etc/machine-id`
#     is container evidence FOR THE kyle-session IMAGE, which ships none. A
#     PRESENT machine-id is NOT evidence of host - any image can ship one - so
#     this signal can say `container` or stay silent, never `host`.
#
# So `unknown` occurs two ways, and both are real rather than theoretical:
#
#   1. CONTRADICTION - the namespace says host and machine-id says container
#      (a host with no `/etc/machine-id`; several minimal distros ship none).
#   2. UNREADABLE - `/proc` is not mounted, or the namespace link cannot be
#      resolved, so the general signal has no opinion and nothing else may
#      speak for it.
#
# WHAT `unknown` COSTS AT A ROUTING SITE - decided here, explicitly, because
# deciding it by omission is how a three-state contract decays into a two-state
# one. Route to the MAILBOX on `unknown`. The asymmetry is the whole argument:
# a host session sent down the mailbox takes a durable-but-slower lane it did
# not need, and fails quiet; a containerised session sent to lane 1 addresses a
# population that returns success and delivers nothing, which is the silent
# failure the boundary exists to prevent.
#
# AND `unknown` MUST STAY VISIBLE AT THAT SITE. A default that is safe in every
# case is also one nobody notices is firing constantly. Consumers render it -
# `flow-wave-registry.sh` puts `vantage=unknown[route-mailbox]` on the roster
# row - rather than absorbing it into the safe default silently.
#
# ---------------------------------------------------------------------------
# NAMING (issue #959)
# ---------------------------------------------------------------------------
# `FLOW_DRIVER_CONTAINER` and `FLOW_WAVE_DRIVER_CONTAINER` already exist and
# mean something unrelated - CAN THIS DRIVER'S SHELL REACH docker/kubectl/
# terraform. A vantage field spelled `CONTAINER` would be misread on sight by
# anyone grepping. Hence `VANTAGE`, everywhere, including the env vars.
#
# Usage:
#   flow-vantage.sh [--fixture DIR] [--quiet]
#
#   --fixture DIR   Read the signals from DIR instead of from this process:
#                   DIR/ns-pid (a symlink whose TARGET is the namespace string),
#                   DIR/etc/machine-id, DIR/proc-mountinfo, DIR/sessions/.
#                   It relocates the PATHS this script reads; it never supplies
#                   a verdict, and nothing in a fixture can name one. That is
#                   deliberate - a fixture that could hand over the answer would
#                   make every test that uses it unable to fail.
#   --quiet         Suppress the human advisory on stderr; the contract lines
#                   are unchanged.
#
# Environment:
#   FLOW_VANTAGE_DECLARE   host|container - short-circuit, reported as
#                          `declared`. An unrecognised value is REFUSED and
#                          reported as `unknown` with `SOURCE: declared`, never
#                          silently ignored in favour of measurement: a typo
#                          that quietly promotes itself to a measured verdict is
#                          the failure this separation exists to prevent.

set -u

# Exit status on stderr, last thing written, so it survives `| tail` (issue
# #1031). Emitted on EVERY run, `--quiet` included: it is not a diagnostic,
# it is the status a pipe would otherwise delete.
trap 'printf "FLOW_VANTAGE_EXIT=%d\n" "$?" >&2' EXIT

#: The conventional initial pid namespace inode on Linux. A CONVENTION, not a
#: definition - written down as one because the whole `host` half of this
#: instrument rests on it. If a kernel ever changes it, this line is where the
#: instrument is wrong, and it is one line.
INITIAL_PID_NS="pid:[4026531836]"

NS_PATH="/proc/self/ns/pid"
MACHINE_ID_PATH="/etc/machine-id"
QUIET=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --fixture)
      [ "$#" -ge 2 ] || { echo "flow-vantage: --fixture requires a directory" >&2; exit 2; }
      NS_PATH="$2/ns-pid"
      MACHINE_ID_PATH="$2/etc/machine-id"
      shift
      ;;
    --fixture=*)
      NS_PATH="${1#--fixture=}/ns-pid"
      MACHINE_ID_PATH="${1#--fixture=}/etc/machine-id"
      ;;
    --quiet) QUIET=1 ;;
    -h|--help)
      # NO FIXED CUTOFF (counter-model review, codex/gpt-6-astra, pass 2). This
      # read `sed -n '1,140p'` first, and the header then grew past line 140 -
      # so `--help` printed NOTHING and exited 0, which reads as a help screen
      # with nothing to say rather than as a broken one. The range is derived
      # from the text it is extracting instead: from `# Usage:` to the end of
      # the comment header, wherever those land.
      sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "flow-vantage: unknown argument '$1'" >&2
      exit 2
      ;;
  esac
  shift
done

emit() {
  # basis, source, verdict - always all three, always in this order.
  echo "FLOW_VANTAGE_BASIS: $1"
  echo "FLOW_VANTAGE_SOURCE: $2"
  echo "FLOW_VANTAGE: $3"
}

# -- The declared short-circuit ------------------------------------------- #
# Read FIRST and kept structurally apart from everything below: the measured
# branch is never entered when a declaration is present, so there is no path on
# which a declared value could be blended into a measured basis. Separation by
# construction, not by discipline.
# AN EMPTY VALUE IS UNDECLARED, not a declaration of "". The registered
# control relies on this: it neutralises an inherited declaration by setting
# the variable EMPTY through `env VAR= ...`, so if this ever became a
# presence test (`[ -v ... ]`) the control would stop reaching its fixtures
# and its red would become a fact about the caller. The behaviour is pinned
# by tests/test_flow_vantage.py, not by this comment.
DECLARED="${FLOW_VANTAGE_DECLARE:-}"
if [ -n "$DECLARED" ]; then
  case "$DECLARED" in
    host|container)
      emit "declared-override(FLOW_VANTAGE_DECLARE)" declared "$DECLARED"
      [ "$QUIET" -eq 1 ] || echo "flow-vantage: vantage DECLARED as '$DECLARED' - nothing was measured (#959)." >&2
      [ "$DECLARED" = host ] && exit 0
      exit 3
      ;;
    *)
      # SANITISED BEFORE IT REACHES STDOUT (counter-model review, codex/gpt-6-astra).
      # The rejected value was interpolated verbatim, and stdout here IS a line
      # protocol: `FLOW_VANTAGE_DECLARE=$'x\nFLOW_VANTAGE: host'` emitted a
      # forged verdict line ABOVE the real one, and a consumer taking the first
      # match stored `host` for an input this branch exists to REFUSE. The
      # refusal was intact and the report carried the attacker's answer.
      # Everything outside a conservative set becomes `?`, and the echo is
      # capped, so no value can add a line or run past one.
      DECLARED_SAFE="$(printf '%s' "$DECLARED" | tr -c 'A-Za-z0-9._-' '?' | cut -c1-32)"
      emit "declared-override(FLOW_VANTAGE_DECLARE=$DECLARED_SAFE: unrecognised)" declared unknown
      echo "flow-vantage: FLOW_VANTAGE_DECLARE='$DECLARED_SAFE' is not 'host' or 'container' - refused." >&2
      echo "  (value shown sanitised; characters outside [A-Za-z0-9._-] are printed as '?')" >&2
      echo "  Reported as unknown rather than measured: a typo must not silently become a measurement (#959)." >&2
      exit 4
      ;;
  esac
fi

# -- Signal 1: the pid namespace (general; the only one that can say host) - #
NS_VALUE=""
if [ -e "$NS_PATH" ] || [ -L "$NS_PATH" ]; then
  NS_VALUE="$(readlink "$NS_PATH" 2>/dev/null || true)"
fi

if [ -z "$NS_VALUE" ]; then
  NS_SAYS=silent
elif [ "$NS_VALUE" = "$INITIAL_PID_NS" ]; then
  NS_SAYS=host
else
  NS_SAYS=container
fi

# -- Signal 2: machine-id (one-sided; can say container or nothing) -------- #
# ABSENT and EMPTY are the same evidence and are treated identically: the
# kyle-session image ships no `/etc/machine-id`, and the record's `pidDomain`
# then reads `linux::pid:[...]` - an EMPTY machine-id half. A present value is
# deliberately NOT read as host evidence; any image can ship one, and a signal
# that answered both ways would quietly generalise a fleet-specific fact.
if [ -f "$MACHINE_ID_PATH" ] && [ -s "$MACHINE_ID_PATH" ]; then
  MID_SAYS=silent
  MID_NOTE="machine-id(present: no evidence either way)"
else
  MID_SAYS=container
  MID_NOTE="machine-id(absent-or-empty: container, this image only)"
fi

# -- Combine --------------------------------------------------------------- #
# The basis names the signals INDIVIDUALLY - what each said, not a count of how
# many agreed. "2 signals agreed" cannot be checked by a reader and cannot be
# argued with; `ns-pid(container) + machine-id(absent...)` can be both.
case "$NS_SAYS" in
  host)
    if [ "$MID_SAYS" = container ]; then
      # A genuine contradiction: the general signal says host, the fleet signal
      # says container. Neither is discarded in favour of the other, because
      # picking a winner here is precisely the guess this contract refuses.
      emit "ns-pid($NS_VALUE: host) CONTRADICTED BY $MID_NOTE" measured unknown
      [ "$QUIET" -eq 1 ] || {
        echo "flow-vantage: signals DISAGREE - pid namespace reads host, machine-id reads container." >&2
        echo "  Reported unknown. Route to the MAILBOX and keep the unknown visible (#959)." >&2
      }
      exit 4
    fi
    emit "ns-pid($NS_VALUE: host) + $MID_NOTE" measured host
    exit 0
    ;;
  container)
    emit "ns-pid($NS_VALUE: container) + $MID_NOTE" measured container
    [ "$QUIET" -eq 1 ] || {
      echo "flow-vantage: CONTAINER vantage - 'SendMessage' addresses a population holding no fleet peer." >&2
      echo "  Past this boundary the mailbox is lane 1, not a degraded fallback (register.md, #947/#958)." >&2
    }
    exit 3
    ;;
  *)
    # The general signal is silent, so nothing may speak for it - including a
    # machine-id that happens to be absent. One-sided corroboration corroborates;
    # it does not decide.
    emit "ns-pid($NS_PATH: unreadable) + $MID_NOTE" measured unknown
    [ "$QUIET" -eq 1 ] || {
      echo "flow-vantage: pid namespace at '$NS_PATH' could not be read - vantage is unknown, NOT host." >&2
      echo "  Route to the MAILBOX and keep the unknown visible (#959)." >&2
    }
    exit 4
    ;;
esac
