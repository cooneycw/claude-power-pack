#!/bin/sh
# A known-BAD case for issue #972: its ONLY finding is below error severity.
# SC2002 (useless cat) is a style-level note. A gate still defaulting to
# --severity=error reports this file clean, which is exactly the blindness
# raising the default to style closes. Do not "fix" the line below.
cat /etc/hostname | wc -l
