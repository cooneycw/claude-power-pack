<!-- lanes-demonstrated run=f9f08a92b206474696c5353719e9a90e plan=84a69e66401ae0daeece20dae0729d4bb2e121aaf527aa523b47411d6a6f2eed -->

| Lane | Result | Test or observation |
|---|---|---|
| CI provider | passed | Woodpecker pull_request pipeline 3943 on c1d4b3a3 (negative-controls runs controls/check-oscillation via --from-log with no git; tests/test_oscillation_fixtures.py runs there) |
| Reader: make verify / oscillation target | passed | flow-finish-gate.sh `FLOW_FINISH_GATE: ok`; live run on this repo: main and branch gates give byte-identical --json (200 commits, 85 examined, none) |
| Reader: check-negative-controls.py | passed | `check-negative-controls.py --strict --verify-provenance --control controls/check-oscillation`: bad-reversed BAD, good-monotonic GOOD, anchor blind, VERDICT PASS |
