# No-flag compatibility baseline

`no-flag-baseline.stdout` is stdout with exit 0 from the unchanged harness at
main commit `34c99e4cc5ebec35f0db2d885d3bb012cdb76372`, running the matching toy
fixture with `--strict` and without `--verify-provenance`. Only the generated
fixture commit IDs in the source stamp and historical label are normalized.
The baseline was captured by executing those original bytes with the original
script path, so its census helper resolves normally. It does not execute the
new implementation. The compatibility tests compare the full output and exit.

`anchors/off-main-1a13-branch-protection.sh` retains the original #1797 anchor
bytes (SHA256 `074a28aa67e2ec15d46a9b6c031e480ac3363d20649416f16a71801c3f79c820`).
The regression uses its actual recorded side-branch commit and verifies refusal
without needing that commit's object. It is test data, not a registered blind
anchor for this provenance checker.
