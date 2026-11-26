# Pi partial-refresh opt-in - #1896 follow-up

Authority: [owner contract gap](https://github.com/cooneycw/claude-power-pack/issues/1896#issuecomment-7180740166)
and orchestrator approval 40994. Base is merged #1912 main
`b1cd1f1635a920ba4839097ebfff8977a0bf7dda`. This is a separate branch from
#1897; no owner recovery code or installation was changed.

Pi now explicitly selects the existing shared core's partial-refresh policy.
A foreign same-name topic preserves its bytes while safe canonical topics
progress. The entire install/verify row remains non-current and exit 1 when
that collision remains. No core code, report schema or adoption rule changed.
Global integrity failures, including another adapter's ownership claim, still
refuse all writes. The core's default remains false.

## Disposable full-population regression

The test copies a complete tracked public source snapshot into its own source
Git repository. It builds all 18 real canonical topics, seeds an unmarked foreign
`boot` at mode 0640, and asserts the collision and absent safe topic before
calling the actual production CLI from an external fixture cwd with an allowlist
environment. No pi process or owner path is used.

Before opt-in, the regression FAILED on main's unchanged adapter because the
safe `code-quality/SKILL.md` did not exist after install refused the collision.
After opt-in, the same regression PASSES: foreign boot bytes/mode/inode/mtime
are unchanged; all 17 safe topic populations match the actual fresh members and
0644 modes; ledger records match fresh hashes, source and revision; boot never
receives a CPP record. The actual verifier still returns exit 1/non-current
with nonzero expected population and every reported conflict confined to boot.
Neither a zero population nor the install action alone is read as success.

An initial fixture attempt omitted a root-level bundled Markdown reference and
failed before installation. Its output is retained separately; it is not the
red regression result. The complete snapshot correction precedes the actual
red run described above.

## Policy and compatibility controls

The existing paired control now explicitly selects false through a fixture-only
PiAdapter subclass. It proves the neutral core's all-or-nothing path preserves
both the edited package and the safe stale package with unchanged ledger. The
opt-in adapter arm updates the safe guide while preserving the blocked record
and keeping a non-current row. Production pi's opt-in is independently exercised
by the new full-topic CLI case. This avoids silently losing default-policy
coverage when pi stops serving as the default-false example.

Focused actual core, transaction, CLI, pi installation/concurrency/policy, paired
policy and global-identity controls: 103 passed, one existing real-root-only
privilege case skipped. The skip is not a pass. Lint and type checks passed
(558 source files). Required logs/receipts remain under persistent workspace
storage; every owned pytest basetemp was removed after its result.

Retained log SHA256s:

| Evidence | SHA256 |
|---|---|
| Actual pre-opt-in regression red | `f8147d30056da41052fde6d5d5a49442146e58eb573f21f51875c4c2d444cd79` |
| Same regression after opt-in green | `16e75dce2af0cd5544f3fdeea292cfd496af89ac051b377603a93f3922ebea17` |
| Focused compatibility run | `8cbd4e24eac5607df834bc2e94d0b19648411927e6e32a986514a8748c953ed1` |

Digests identify retained bytes, not authenticity. Independent review/receipt,
paired finish gate and PR CI remain pending at this checkpoint. #1896's built-in
tool inventory and skill-loader diagnostic measurements remain UNKNOWN. No new
runtime discovery, contextual effectiveness, provider or owner isolation claim
follows from these filesystem/CLI observations. No closing keyword for #1896.
