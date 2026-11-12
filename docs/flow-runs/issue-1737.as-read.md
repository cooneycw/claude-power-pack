<!-- flow-run n=1 id=47aedb08ed874b21875dfc45c5683295 -->
## Run 1 - issue #1737 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1737
- Read at:      2026-11-12T03:46:54Z
- updatedAt:    2026-11-12T02:18:26Z   (context only - moves on comments and labels)
- Body digest:  5d51a33f49134a279d11a60f61ca049db7b24cc102cb0d67aa30f8ee2c9043f6   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2773 of 2773 (cap 16384)

### Body as read
Tier: 2

Source: found while working #1717 (the secret scanner's shell-substitution exemption), 2026-11-11, at origin/main `6b6cc29e`. Filed as its own issue, not a Nit Store comment, because it is a silent gap in a detector.

## Outcome
`lib.security`'s native secret scan examines the scripts a project actually runs, including the ones with no file extension.

`lib/security/modules/secrets.py` selects files by extension (`SCAN_EXTENSIONS`). A script with no extension - `bin/deploy`, `scripts/release`, a git hook, a `Makefile`, a `Dockerfile` - is not in that set, so it is never read. A hardcoded password in one produces no finding, and the scan reports `No secrets found in N source files` over a population that left it out.

Pinned as existing behaviour by `tests/test_security_scanners.py::TestShellSubstitutionIsNotAHardcodedPassword::test_a_shell_script_with_no_extension_is_not_scanned_at_all` (added by #1717): a file named `deploy` with a shebang and a literal password yields `units_scanned == 0` and no finding.

## Why it matters
The gate's silence is read as "no secrets" by `/flow:finish`, `/flow:deploy` and `/security:*` in every consumer. Extensionless executables are where deploy and install logic often lives, and where a credential is most likely to be pasted. The count is honest about how many files were read; nothing says which kinds were not.

Not measured: how many extensionless scripts the consumers hold, or whether any holds a literal. CPP's own CI also runs gitleaks over the whole tree, which does read these files; consumers that rely on the native quick scan alone do not have that.

## Acceptance
- A decision, recorded here, on which extensionless files join the scan: at least files with a shell or interpreter shebang, and the well-known names (`Makefile`, `Dockerfile`).
- A committed bad case: an extensionless script with a shebang and a literal password is reported.
- A committed good case showing binary and very large files are still skipped, so the scan does not start reading everything.
- The scan's summary names the population it covers, or what it excluded, so a zero is distinguishable from "not looked at".

## Constraint
- This widens what the scanner reads, so finding counts in consumers can go UP. Under the owner's 2026-11-11 ruling that needs coordination issues in cooneycw/kyle, cooneycw/skillc and cooneycw/kyle-candidate before it merges.
- The shell-substitution exemption from #1717 keys on `.sh`, `.bash` and `.zsh`. If shebang files join the scan, decide whether the exemption follows them, and commit a case either way.

## Assumption
That a shebang is a reliable enough signal. A file with a shebang and no execute bit, or an execute bit and no shebang, needs a stated answer.

Related: #1717.


<!-- end of body -->
