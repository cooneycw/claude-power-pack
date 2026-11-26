# A2 initial host observation: not accepted

Evidence for #1896 at candidate
`d4bdc26f9dd6cf78a3f4134174f6fe35ad0d524f`. A host operator executed the
committed relay in a disposable linked worktree during
2026-11-25T22:21:54Z through 22:22:48Z. Python was 3.12.3, pi 1.6.0, and strace
6.8. This author independently decoded the forwarded sanitized records,
verified the digests below and read their returned observations. This author
did not execute pi, observe the host directly or replay the full raw trace.
Digests identify bytes, not their authenticity. No owner install was requested.

## Provenance

| Supplied artifact | Bytes | SHA256 |
|---|---:|---|
| Sanitized initial summary | 194602 | `243188b789caeb0063d9f9aa1ed11dd48999ff1c2287741ecccb65958f4087ab` |
| Sanitized selected trace slices | 16673 | `014dbc716a2d18c865f073474ab79510488ca2a1da8134565b1c96e13334adce` |
| Deduplicated bootstrap path extract | 2251 | `4a476244aa63b98f7f886223ddab4b82578a2dd3ad7dd8a54f37aaca9c6d7897` |
| Full raw stdout, retained on host only; host-reported digest | 329341529 | `833cca23110d70cbd55abc6189f921230bbfefca7e741b68f72e643ce2692b45` |

The returned script hashes matched independent reads from candidate Git blobs:

| Path | SHA256 |
|---|---|
| `scripts/pi-host-fixture.py` | `730c9ec2f96a0dc278aabe749759248a8416a8583099c39b6dc9bcdfb1da5cd3` |
| `scripts/pi-syscall-audit.py` | `df7004d092008d4f79ed213253a5cfeea572eb0650fa4c1601da4a97d002c06f` |
| `docs/measurements/pi/issue-1896-a2-host-probe.sh` | `8cd09f051e214b0937f3e48b6bde81367d3cd93ced6c8fe7d59d49af1be6ddbb` |

The summary truncates repetitive arrays and omits full trace bodies. Its
selected slices normalize host/source paths and crop non-path buffers. The
committed `host-runtime-slice` parser case further selects complete lines,
normalizes source/main paths and opaque buffers, and supplies synthetic pid/exit
framing. It is a composite control, never a complete real-process replay.
The bootstrap extract contains 30 distinct syscall/path/result rows from the
same retained trace; no command was rerun. Its header is private and is not
reproduced here. `bootstrap-runtime-paths` reconstructs those operations using
synthetic flags, descriptors, buffers and framing; it tests path allowances,
not original raw trace syntax. Exact interpreter bootstrap probes, SSL aliases
and locale catalogs extend the allowance without a directory read prefix.
The producer's missing-bootstrap-path regression also failed before its fix.

## RPC observations and limits

The real install and shared-lock verify each reported current: 18 expected
packages and 36 examined/expected members. The installed command response
contained all expected skills. Actual hidden `.cpp-managed` ledger/work contents
were present without a management SKILL.md; non-topic commands were unchanged.
Removing an expected package produced a missing-command finding; restoring via
the installer restored it. The bounded trusted-project shadow selected project
source. These are fixture/version observations, not runtime effectiveness.

The baseline and installed stderr were equal and contained the following
known warning (paths sanitized here, not an unredacted transcript):

```text
Warning: No models available. Use /login to log into a provider via OAuth or API key. See:
  ~/.local/lib/node_modules/@earendil-works/pi-coding-agent/docs/providers.md
  ~/.local/lib/node_modules/@earendil-works/pi-coding-agent/docs/models.md
```

The malformed-skill control added no stderr diagnostic. Published pi 1.6.0
source corroborates that `skills.js` collects skill warnings and the resource
loader stores them, while the RPC-visible runtime diagnostic path does not
collect that array. The inspected published package integrity was
`sha512-zX1BVEsshx7A2MRuQ6jfr3RJGWw4Wn+vLq5ZfmlvS1RskhRmByaSZVXH/zcwRrWHO7qPgs98pNCbPOEti/t0fQ==`.
Equal stderr supports only the runtime/extension/provider/flag differential.
It establishes no absence of skill-loader warnings. Per the owner amendment,
skill-loader diagnostics remain UNKNOWN under #1896 until a supported channel
and firing control are available. Tool inventory also remains UNKNOWN: the
documented RPC offers no inventory command. RPC exited 4 with zero findings;
neither unknown row is accepted or closed by this evidence.

## Syscall observations and correction

The syscall lane exited 1. Every normal case was a finding, so the observer
could not discriminate legal operations from seeded violations. The forwarded
host summary reported 47,208 aggregate allowance findings; counts are not
unique operations (the initial-install findings are aggregated twice). All 31
observed child exits matched their declared expectations, but this does not
repair the blind GOOD side. Specific synthetic auth-stat and transient-write
finding lines were present; with normal cases also failing, those lines alone
do not establish the required paired acceptance.

The records and selected slices identify these missing observer classes:

- Exact locale alias, SSL config, FIPS/CPU nodes and Git attributes inputs;
  fixture XDG Git inputs and Python user-site lookup metadata; real-HOME PATH
  search misses, which should be prevented rather than authorized.
- Linked-worktree Git/common storage and ancestor metadata. The main working
  tree itself is outside the source allowance and must remain forbidden.
- Readonly O_DIRECTORY opens at the exact lock parent, distinct from listing
  or reading that directory.
- Nested typed descriptors such as `3</dev/null<char 1:3>>`; discard writes
  require that exact device identity and do not permit mutations.
- A readonly shared gconv-cache map with an observed O_RDONLY opener; unproved
  shared mappings must remain UNKNOWN.

The approved observer-only correction uses exact runtime files, constrained
native libraries, isolated interpreter paths and pretrace Git storage discovery.
It sanitizes PATH and Python user-site lookup. Each extension has committed
BAD/UNKNOWN siblings, preserving auth/history/no-create boundaries. The
host-derived GOOD composite failed on the predecessor reader before the fix
(`finding` instead of `matches`). Local parser green is not live acceptance.
The corrected candidate must be frozen for review pass 3 and then one host
rerun must show GOOD=matches and seeded BAD=finding on actual operations.

Both lane records reported fixture cleanup; the operator reported removal of
the temporary worktree. The operator's before/after owner-agent metadata
listing was unchanged, including root mtime; this is not content hashing.
That helper audit itself inspected metadata, so no global zero-metadata claim
follows. The operator reported no real credential-path finding in subject
traces; this author did not independently scan their full population. All pi
calls, including `--version`, used fixture HOME/agent/history/XDG. Configuration
separation is not an OS credential or network boundary.

Supplemental findings were deferred to the Nit Store:
[duplicate initial findings](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7176892259)
and [trace transfer volume](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7176892710).
