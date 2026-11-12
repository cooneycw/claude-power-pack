#!/bin/sh
# Case runner for controls/flow-finish-gate-interrupted (issue #1705).
#
# The subject is ONE line: `FLOW_FINISH_GATE_EXIT=<n>`, the last thing the gate
# writes to stderr, read by sessions other than the one that ran the gate. A
# gate killed mid-run used to print 0 there. Each case names a `mode`:
#
#   killed      start the gate with a runner that blocks, SIGTERM the gate's
#               pid alone once the runner is up, and read the line it left
#   announced   run the gate into a deliberate exit (a usage error, exit 2) and
#               read the line
#
# The gate is staged in an isolated directory with the CURRENT gate-lib beside
# it, so an anchor (an older gate script) runs against the same library and the
# only variable is the gate script itself. No network, no real runner: `uv` is
# a stub on PATH.
#
# Verdict-shaped exit, recomputed here because the gate's own exit status is
# the signal death in the killed case and says nothing about the line:
#   exit 1 + "... unannounced"   the line read 128
#   exit 0 + "... status <n>"    the line read anything else, 0 included
set -u
case_dir="$1"
gate="$2"
here=$(cd "$(dirname "$0")" && pwd)
repo_scripts="$here/../../scripts"
case "$gate" in /*) ;; *) gate="$PWD/$gate" ;; esac
case "$case_dir" in /*) ;; *) case_dir="$PWD/$case_dir" ;; esac

say_unavailable() { echo "FLOW_FINISH_GATE_INTERRUPTED_CONTROL: unavailable - $1"; exit 3; }
command -v bash >/dev/null 2>&1 || say_unavailable "bash is not installed"
[ -f "$case_dir/mode" ] || say_unavailable "case supplies no mode file"
[ -f "$repo_scripts/gate-lib.sh" ] || say_unavailable "gate-lib.sh not found beside the gate's sources"
mode=$(cat "$case_dir/mode")

work=$(mktemp -d "${TMPDIR:-/tmp}/flow-finish-gate-interrupted.XXXXXX") || say_unavailable "no isolated directory"
runner_pid_file="$work/runner.pid"
cleanup() {
    [ -s "$runner_pid_file" ] && kill -KILL "$(cat "$runner_pid_file")" 2>/dev/null
    rm -rf "$work"
}
trap cleanup EXIT INT TERM

mkdir -p "$work/scripts" "$work/cpp" "$work/bin" "$work/run" "$work/tmp"
cp "$gate" "$work/scripts/flow-finish-gate.sh" || say_unavailable "could not stage the gate"
cp "$repo_scripts/gate-lib.sh" "$work/scripts/" || say_unavailable "could not stage gate-lib.sh"
[ -f "$repo_scripts/coordination-admission.sh" ] && cp "$repo_scripts/coordination-admission.sh" "$work/scripts/"
: > "$work/cpp/CLAUDE.md"
started="$work/runner-started"
cat > "$work/bin/uv" <<STUB
#!/bin/sh
echo \$\$ > "$runner_pid_file"
: > "$started"
exec sleep 30
STUB
chmod +x "$work/bin/uv"

err="$work/stderr"
# A host whose coordination admission is ON would send the gate through the
# real kyle-lock instead of the stub runner. The fixture owns that answer: a
# file that does not exist reads as admission off.
no_admission="$work/no-coordination-admission"
cd "$work/run" || say_unavailable "could not enter the isolated directory"
case "$mode" in
    killed)
        env -u FLOW_GATE_RERUN -u CPP_KYLE_FULL_SUITE_ACTIVE -u CPP_FLOW_FINISH_GATE_STATUS_FILE \
            PATH="$work/bin:$PATH" FLOW_GATE_CPP_DIR="$work/cpp" TMPDIR="$work/tmp" \
            CPP_COORDINATION_ADMISSION_FILE="$no_admission" \
            bash "$work/scripts/flow-finish-gate.sh" >"$work/stdout" 2>"$err" &
        gate_pid=$!
        n=0
        while [ ! -e "$started" ]; do
            n=$((n + 1))
            if [ "$n" -gt 400 ]; then
                kill -KILL "$gate_pid" 2>/dev/null
                echo "FLOW_FINISH_GATE_INTERRUPTED_CONTROL: cannot-run - the runner never started:"
                sed 's/^/  /' "$err"
                exit 3
            fi
            sleep 0.05
        done
        kill -TERM "$gate_pid"
        wait "$gate_pid"
        gate_rc=$?
        if [ "$gate_rc" -ne 143 ]; then
            echo "FLOW_FINISH_GATE_INTERRUPTED_CONTROL: cannot-run - the gate did not die by SIGTERM (status $gate_rc)"
            exit 3
        fi
        ;;
    announced)
        env PATH="$work/bin:$PATH" FLOW_GATE_CPP_DIR="$work/cpp" TMPDIR="$work/tmp" \
            CPP_COORDINATION_ADMISSION_FILE="$no_admission" \
            bash "$work/scripts/flow-finish-gate.sh" --no-such-flag >"$work/stdout" 2>"$err"
        gate_rc=$?
        if [ "$gate_rc" -ne 2 ]; then
            echo "FLOW_FINISH_GATE_INTERRUPTED_CONTROL: cannot-run - expected the usage exit 2, got $gate_rc"
            exit 3
        fi
        ;;
    *) say_unavailable "unknown mode '$mode'" ;;
esac

count=$(grep -c '^FLOW_FINISH_GATE_EXIT=' "$err" || true)
line=$(grep '^FLOW_FINISH_GATE_EXIT=' "$err" | tail -1)
if [ "$count" -ne 1 ]; then
    echo "FLOW_FINISH_GATE_INTERRUPTED_CONTROL: cannot-run - expected exactly one exit line, found $count:"
    sed 's/^/  /' "$err"
    exit 3
fi
value=${line#FLOW_FINISH_GATE_EXIT=}
if [ "$value" = "128" ]; then
    echo "FLOW_FINISH_GATE_INTERRUPTED_CONTROL: unannounced"
    exit 1
fi
echo "FLOW_FINISH_GATE_INTERRUPTED_CONTROL: status $value"
exit 0
