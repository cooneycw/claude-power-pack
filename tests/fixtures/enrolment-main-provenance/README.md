# Prepared CPP main provenance cases (#1754)

These fixtures prepare a trust-boundary change awaiting the owner's ruling.
They do not change product behavior. `cases.json` names a fetchable unmerged
permissive checker (BAD), a main ancestor (GOOD), and missing/shallow main
(UNKNOWN). The test constructs all commits and repositories itself, establishes
non-ancestry and actual shallow-history preconditions, then executes each
provider's actual rendered enrolment shell using real Git. Only the official
fetch URL and Woodpecker metadata response are redirected to owned fixtures.
No package installation, public CI, or live network is exercised.

`blind-enrolment.py` is the exact historical `lib/cicd/enrolment.py` from main
`b2da2133e3958caede2a94c942e4b4c6459ab838`, SHA256
`9575a1b4c451de5b83962a467eb1db2d622995009459c2c31a33da39c119109f`.
It checks SHA equality but no main ancestry. Its bootstrap is passed through the
current renderers, and its actual rendered commands execute the owned feature
sentinel and return green on both providers. This is the blind anchor, not a
new implementation or a checker approved for consumer use.

Pre-fix result on unchanged product code: six failures (BAD and two UNKNOWN
cases on both providers), four passes (main-ancestor positives and historical
blind-anchor demonstrations). These are local test preparations; a registered
instrument control and census wiring await the product ruling.
