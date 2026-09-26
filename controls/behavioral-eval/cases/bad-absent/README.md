Deliberately holds no `*.json`. git cannot track an empty directory, so this file
exists to carry the case; the gate globs `*.json` and finds none, which is the
ABSENT state - the one this repository is in today and will stay in until CPP
#1084 half B lands in skillc (waiting on skillc #8, #9 and #10).
