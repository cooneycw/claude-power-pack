<!-- lanes-demonstrated run=385e634fa8ad451bb4264aa148ab4c39 plan=466e4888b66d5853940c548fcbce69f012282eb3f0a230f7f293f51d92e42666 -->

| Lane | Result | Evidence |
|---|---|---|
| Driver | passed | controls/driver-parity citation cases edit the codex driver doc (removed / repeated / same-line repeat / line-shift) and read BAD/BAD/BAD/GOOD; make driver-parity-check on the live table: ok, 24 items, 72 pairs, 0 missing |
| CI provider | passed | Woodpecker PR pipeline 3938 (ci/woodpecker/pr/woodpecker) success on d7756066; GitHub Actions is not this repo's CI |
| Reader: make verify / driver-parity-check | passed | flow-finish-gate.sh: FLOW_FINISH_GATE: ok via make verify; verdict line and exit codes unchanged |
| Reader: check-negative-controls.py | passed | check-negative-controls.py --control controls/driver-parity exit 0; constructed anchor missed every new BAD case (blind, as required) and agreed on good-citation-line-shift |
