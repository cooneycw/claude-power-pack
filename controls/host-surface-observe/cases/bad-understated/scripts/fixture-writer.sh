#!/usr/bin/env bash
#: HOST-SURFACE: ~/.probe/one owner=cpp write=replace certified=observed
#
# Fixture for controls/host-surface-observe. It writes TWO surfaces: the
# directory ~/.probe and the file ~/.probe/one. The only difference between
# this control's two cases is whether the DIRECTORY is declared.
#
# That is the whole design. Both cases are classified, both run, both write
# the same two paths. A gate that compares appeared against declared separates
# them; a gate that does not, cannot. An expected answer both sides can reach
# proves nothing (#1139's near-miss, restated in #1150).
set -euo pipefail
mkdir -p "$HOME/.probe"
printf 'probe\n' > "$HOME/.probe/one"
