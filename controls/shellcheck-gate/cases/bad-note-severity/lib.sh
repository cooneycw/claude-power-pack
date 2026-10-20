#!/bin/sh
# A known-BAD case for issue #972: its ONLY finding is below error severity.
# SC2086 (double-quote to prevent globbing/word-splitting) is an info-level
# note, caught by `--severity=style` (which includes info and below) and not
# by `--severity=error`. A gate still defaulting to --severity=error reports
# this file clean, which is exactly the blindness raising the default to
# style closes. Do not "fix" the line below.
#
# NOT SC2002 (issue #1492): the original offender here was `cat f | wc -l`,
# relying on SC2002 ("useless cat"). ShellCheck 0.11.0 moved that check
# behind the optional `useless-use-of-cat` category, off by default - this
# control's own re-measurement (CPP #864 comments 6294645344, 6294672123)
# found it going BLIND under 0.11.0 for exactly that reason, while CI's
# pinned 0.10.0 still caught it. SC2086 fires unconditionally in both
# 0.10.0 and 0.11.0 with no --enable flag, so this fixture is now
# version-stable - MEASURED both ways before landing (see the PR body).
x="placeholder value"
echo $x
