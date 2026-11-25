# AGY topic builder evidence

Issue #1888. Production host updater integration remains #1889-B; command-derived
skills and an actual AGY cpp-update invocation remain #1876/#1888/#1889.

## Local evidence

At implementation checkpoint fcad40b6, the actual default Make build and check
both reported current for all 18 topics. The focused suite passed 19 tests;
it covers root/external cwd, checkout/worktree/full/shallow source, pinned
tracked input, deterministic metadata/modes and real core preservation.
Subsequent alias-preflight regression failed before its correction and passed
afterward; final-checkpoint totals are recorded with the lane results.

The historical 40d25173 generator and its parser have separately verified
digests. Both generators see identical current payloads and different parser
implementations. Exact path/byte/mode parity passes under 022 and 002 umasks;
the historical 022 manifest has no unattributed delta. Changed transform and
changed parser fixtures each make comparison fail. Missing baseline fails.

The resource regression failed on the initial WIP because reference-style,
image and HTML resources were omitted, then passed after support was added.
Source-file mode and package-byte checks pass through the real neutral core.
Committed controls observe GOOD for complete output, BAD for changed output,
removed package and broken bundled guide, and UNKNOWN for missing source.
The constructed always-current inspector misses all three BAD inputs.

## Review corrections

Pass 1 at 3066cb85 requested changes. All three findings were accepted:
unbounded reference closure, help output stream handling and rejection of
system symlink ancestors. The untallied parser-provenance note is also fixed:
the parser comes from the pinned source snapshot.

Against the exact reviewed implementation, the closure, system-ancestor and
parser-binding regressions all failed. The new bounded-closure GOOD control
also failed there because the old builder expected unrelated corpus files.
All pass after correction. The stderr-help regression failed against the
unchanged stdout-only check before combining the streams; nonzero help and
missing flags still refuse. The approved product passed 29 focused tests; the
final probe/evidence delta passes 31 focused tests.

Local content is now limited to the canonical package and referenced
`docs/skills/` guides/resources, plus the explicit C4 script allowlist. Other
repository references route upstream at the pinned revision; directory links
do not enumerate or copy subtrees. The C4 renderer loads from a temporary
directory without the checkout. The changed-parser negative case now fails
the full generated-tree parity check as well as its link-transform comparison.

| Topic | Files |
|---|---|
| best-practices | 1 |
| boot | 1 |
| browser-tiered | 1 |
| cicd-verification | 3 |
| claude-md-config | 2 |
| code-quality | 2 |
| context-efficiency | 2 |
| documentation | 2 |
| evaluate | 1 |
| hooks-automation | 2 |
| idd-workflow | 2 |
| infrastructure-hardening | 3 |
| mcp-optimization | 2 |
| project-deploy | 1 |
| python-packaging | 2 |
| secrets | 1 |
| session-management | 2 |
| spec-driven-dev | 2 |

## Live consumer evidence

**OBSERVED for attempt 4 on AGY 1.5.17**, using product
`85dd9397fa71ecd2cb86611d12db63597498e32c` and the exact
[probe](antigravity-topic-builder.probe.py) from
`5e95f3f76198f997fdabda33c7be3957b44659ce`. Its SHA256 is
`6009088ca8de766731c9e12057e7348a5179d12c87edbe8ea149a026640a9c4a`.
The older B0-B4 reports used 1.5.14 and are not substituted for these results.

### All four attempts

| Attempt | Probe / product | Observed outcome |
|---|---|---|
| 1 | 3066cb85 / 3066cb85 | Aborted at help validation, exit 1: stdout had 0 help bytes, stderr had 3443. Boundary controls, version 1.5.17 and undo passed. No model turn ran; consumer result UNKNOWN. |
| 2 | Help-stream-fixed probe, included in 85dd9397 / 85dd9397 | Exit 4, UNKNOWN: both consumer commands rejected unitless `--print-timeout 180`. Boundary/help/version, real two-member build, scratch preconditions and undo passed. No model turn ran. |
| 3 | aa133bab / 85dd9397 | Duration `180s` was accepted, but both consumers failed login, exit 1, with zero turns and tokens. Other checks and undo passed; consumer result UNKNOWN. The blanked session bus was the helper's hypothesis, not an independently proven cause. |
| 4 | 5e95f3f7 / 85dd9397 | Overall exit 0, acceptance OBSERVED: positive guide read and missing-guide comparison both matched their independent expectations. Boundary/version/build/preconditions and undo passed. |

Attempts 1-3 are attributed host-helper reports relayed by the orchestrator.
Attempt 4's transferred output was decoded and SHA256-verified here:
`546a6a1deff4bd82b77eee5a860dc4c54721c2e608ca1d8b218511421dec2832`.
Its published guide hash and positive response tail were independently checked
against the exact product's tracked `docs/skills/python-packaging.md` blob.
Raw output and runtime artifacts remain private; this record omits host names,
account paths and session identifiers.

### What attempt 4 established

The actual builder produced all 18 topics. Its two-member python-packaging
package was copied byte/mode-identically into the disposable profile. The
scratch source and intermediate build were deleted before either fresh model
process. The unrelated project held two same-named decoys; the recorded decoy
hash differs from the guide hash. Undo was logged before mutations.

| Consumer case | Native exit | Observed result |
|---|---|---|
| Positive | 0 | `status=read` at the installed package's `references/docs/skills/python-packaging.md`; SHA256 `79bf220490a14b6a011ee1ad35952c67b0789f83569a3512a67c9b2cace40008` equals the published guide, and its exact final 120 characters match. |
| Missing guide | 0 | The same installed guide path, physically removed before the new process, returned `status=missing`, empty SHA256 and empty tail. The expected missing result matched. |

Both observations report `matches_expected=true`. The response artifact
digests are `adae8105d404912d90d3b3530ffb9c9f4472a77a9a958744efe124f5c739e4af`
(positive stdout) and
`99174c6b70b7a0958f518a81a1959d6bef6e2be8b0d7c19ad1b154972eab0337`
(missing-guide stdout); both stderr streams were empty. The expected hash/tail
were withheld from the prompt and from scratch files until both turns ended.
Positive and never-created-marker boundary controls passed. Undo removed the
copied package and marker. The probe's real configuration metadata listing
remained unchanged, and the helper independently reported identical before/
after listings. No real configuration file content was read for this check.

### Isolation and authorization limit

This lane isolates configuration. Consumer authentication uses the inherited
user-session keyring; credential isolation is not provided. The owner
explicitly accepted the combination of session-keyring reach and
`--dangerously-skip-permissions` for **this one attempt 4 only**, in the
[recorded ruling](https://github.com/cooneycw/claude-power-pack/issues/1888#issuecomment-7176568634).
Environment logging contains names only, never values. The helper reported no
credential-store inspection. These facts do not establish a sandbox or prove
that the model lacked access to unrelated keyring items.

The committed probe is a historical reproduction artifact, not standing
permission to run it again. Any other run, or rerun after product/probe changes,
needs a new owner ruling or the dedicated file-token approach in Kyle ADR 0015.
No additional model run was performed for this evidence commit.

This acceptance covers the python-packaging topic consumer and its missing
guide control. Runtime model-identity receipts (#1886), other-topic live
invocations, production host adapters (#1889-B), command-derived AGY skills
and actual AGY cpp-update invocation remain unexamined here.
