#!/bin/sh
# Runs one hook-mask-output case (issue #1206).
#
# TWO FACTS, AND THIS CONTROL CAN ONLY REACH ONE OF THEM.
#
#   CAPABILITY - can the masker mask? Provable here, and it always was. It was
#                never in doubt, which is exactly why proving it again would be
#                an anti-control for the claim that matters.
#   WIRING     - does the harness dispatch tool output to it? NOT provable from
#                a subprocess. A control cannot make a Claude Code tool call, so
#                nothing here observes dispatch. #1206 exists because those two
#                facts were confused for three months.
#
# What this control therefore measures is CAPABILITY plus REGISTRATION: that the
# hook is declared at a location Claude Code reads, in the documented shape.
# Registration is not dispatch. It is, however, exactly the thing that was wrong
# - the hook lived in `.claude/hooks.json`, which nothing reads - so a control
# that catches a regression to that state is worth having as long as it does not
# pretend to be more.
#
# The live dispatch pair - a synthetic secret through a REAL tool call observed
# MASKED, and the same with the hook disabled observed UNMASKED - needs a
# session started after the fix. The UNMASKED half was observed on 2026-09-22
# and is recorded in the PR; the MASKED half is owed by the first session that
# starts with this registration loaded.
set -u
case_dir="$1"
gate="$2"

command -v python3 >/dev/null 2>&1 || { echo "MASK_CONTROL: unavailable - python3 is not installed"; exit 2; }
[ -f "$case_dir/input.json" ] || [ -f "$case_dir/settings-probe" ] || {
    echo "MASK_CONTROL: unavailable - case has neither input.json nor settings-probe"; exit 2; }

# REGISTRATION cases read the repository's own settings file.
if [ -f "$case_dir/settings-probe" ]; then
    root=$(cd "$(dirname "$gate")/.." && pwd)
    probe=$(cat "$case_dir/settings-probe")
    python3 - "$root" "$probe" <<'PY'
import json, pathlib, sys
root, probe = pathlib.Path(sys.argv[1]), sys.argv[2]
target = root / probe
if not target.is_file():
    print(f"hook-mask-output: UNREGISTERED - {probe} does not exist, so the masking "
          f"hook is declared nowhere Claude Code reads")
    raise SystemExit(1)
try:
    d = json.loads(target.read_text())
except Exception as exc:
    print(f"hook-mask-output: UNREGISTERED - {probe} is unreadable ({exc})")
    raise SystemExit(1)
entries = d.get("hooks", {}).get("PostToolUse", [])
masking = [e for e in entries
           if any("hook-mask-output" in (h.get("command") or "")
                  for h in (e.get("hooks") or []))]
if not masking:
    print(f"hook-mask-output: UNREGISTERED - {probe} declares no PostToolUse entry "
          f"invoking hook-mask-output")
    raise SystemExit(1)
bad = [e for e in masking if not isinstance(e.get("matcher"), str)]
if bad:
    print(f"hook-mask-output: UNREGISTERED - the matcher is "
          f"{type(bad[0].get('matcher')).__name__}, not a string; the documented "
          f"form is a string and an object matcher does not select any tool")
    raise SystemExit(1)
print(f"hook-mask-output: registered in {probe} for "
      f"{', '.join(repr(e['matcher']) for e in masking)}")
PY
    exit $?
fi

# CAPABILITY cases pipe a payload at the masker itself.
sed "s|{GATE}|$gate|g" "$case_dir/input.json" | bash "$gate"
