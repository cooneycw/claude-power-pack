<!-- flow-run n=1 id=e8d8600f550e4250938850c9df3a7203 -->
## Run 1 - issue #1717 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1717
- Read at:      2026-11-12T02:13:38Z
- updatedAt:    2026-11-12T02:13:36Z   (context only - moves on comments and labels)
- Body digest:  4b37228ce6b7924b3aa788ba8c579ae16a23b886fe30ace0926ce0421bbf28b6   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3757 of 3757 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 3 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
`lib/security/secrets.py`'s HARDCODED_PASSWORD and HARDCODED_SECRET patterns match a name followed by any quoted string. Test fixtures, sentinel constants and shell expressions such as `pg_password="$(generate_secret)"` are reported as HIGH findings: 50 at once in one consumer run. A scanner that cries wolf this often is one people stop reading.

## Findings (3)
- [seq 648](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6565700373), 2026-11-01, medium (estimated): lib.security gate reports 50 HIGH false positives (test passwords, LEGACY_DB_PASSWORD sentinel) blocking flow_deploy. Status at origin/main `f63dc946`: ASSIGNMENT_PATTERNS in lib/security/modules/secrets.py unchanged for password rule; only secret: suppressions via security.yml exist (#1312).
- [seq 653](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6603538018), 2026-11-03, low (estimated): lib/security secrets.py treats shell expressions like pg_password="$(generate_secret)" as HARDCODED_PASSWORD. Status at origin/main `f63dc946`: Password pattern at secrets.py:87 still matches any quoted >=8 char value with no shell-expression exclusion.
- [seq 690](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6729163834), 2026-11-09, medium (estimated): security secrets.py HARDCODED_PASSWORD/SECRET patterns match name plus any quoted string; test fixtures and shell substitutions block deploy gate as HIGH. Status at origin/main `f63dc946`: secrets.py:85-97 patterns unchanged: password regex takes any 8+ char quoted value, no value check.

## Acceptance
- (Amended 2026-11-11, see the note below.) The shell-substitution shape no longer matches; fixtures and sentinels are literals and are handled by a declared suppression in the consumer's `.claude/security.yml`; real hardcoded literals still match; and both sides are committed as cases.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

## Amendment, 2026-11-11 (planning run, approved by the wave orchestrator)

Measured before proposing, read-only, with the scanner's own `scan()` over the Kyle and skillc checkouts at origin/main `6b6cc29e`. No value was printed or kept. Kyle: 61 name-plus-quoted-string findings before its own suppressions, of which 49 are literals in a test path, 11 are shell substitutions in a shell file and 1 is a literal elsewhere. skillc: 1, a literal outside tests.

- **seq 653, and the shell half of seq 690: fixed in the scanner.** A value that is a shell substitution, in double quotes, in a shell file, holds no secret. It stops matching, narrowly: `$(...)` at the start, a bare `${NAME}`, or exactly `$NAME`. A `${NAME:-fallback}` default still matches, because the fallback is a literal in the file.
- **seq 648, and the fixture half of seq 690: declined in the scanner, by design.** `password="privtest"` in a test is a literal after a password-like name, and a pattern cannot know whether it is a secret. The scanner's default stays as strict as today for test paths. The remedy exists: a suppression by id and path in the consumer's `.claude/security.yml`. Whether Kyle suppresses its test tree is Kyle's decision and is routed to it by the wave orchestrator, not filed here.
- **Also corrected:** `lib/security/README.md` said assignment-pattern findings carry no value and cannot be pinned with `secret:`. Since #1405 they do and can.

Parent: #1690 (child of #1673)



<!-- end of body -->
