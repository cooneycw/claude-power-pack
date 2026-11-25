# Pi Part-1 source provenance

Documentation-only revision 6.1 of the supplied Part-1 plan. The plan and its
security controls describe future implementation; planned controls are not
executed evidence. This documentation preparer has not rerun the supplied host
experiments or accessed pi credentials, trusted configuration or runtime.

The parked delivery issues are [P1-A #1896](https://github.com/cooneycw/claude-power-pack/issues/1896)
and [P1-B #1897](https://github.com/cooneycw/claude-power-pack/issues/1897), under
[epic #1876](https://github.com/cooneycw/claude-power-pack/issues/1876).
Local preparation does not authorize implementation, a PR, push or CI.

## Revision ledger

| Source | SHA256 | Disposition |
|---|---|---|
| Initial supplied archive | `6b2b92841024e3016219af2b7086496a34b59763a51e0d1597895be242b49f82` | Historical provenance from the supplied README |
| Baseline plan revision 4 | `5ca11cb8aecec9b10a0a922b72eeabdaff58260eb40d1020015604f2075f79b6` | Historical baseline |
| Supplied rev5 archive | `bd489eb752f5061c802e8f55d976bf4d1c8d08c8aa9a14193d772b9770d03be7` | Verified three-file source package retained privately |
| Plan revision 5 | `4b8cdd302e7dd73696cd15c51317a6bc9667e36ad8e0766911193a62e535dc09` | Preserved historical checkpoint; superseded by rev6 |
| Supplied rev6 gzip | `005468f09952cb1b767b19fb1b938afab492b7f5888aaf145757219ad88f5c8c` | Verified compressed source, retained privately |
| Plan revision 6 | `5f584412ea578a07dc67ebf488ce9d28d843e9888ad2fd4eb31843673754ced8` | Historical checkpoint; superseded by rev6.1 |

| Supplied rev6.1 gzip | `0eb3afaafc435111e5b4a5a772027d9cc0c1c25d1f001d17d57ac794f856ed8a` | Verified compressed source, retained privately |
| Current plan revision 6.1 | `8d4aeb7cdc3c78f7000fb6d7ad62f885cf6b2790ae7bc54f56bdb61028060456` | Exact 22,374 bytes; explicit history-source precedence and planned controls |

The rev6.1 handoff commit was reconstructed from the independently imported
rev6 checkpoint and retained exact plan bytes after the worker stood down.
It does not claim the worker's reported rev6.1 Git commit identity.

The publication copy of `skill_install_test_log.md` is sanitized:
credential-file basenames are replaced with `<pi-auth-file>` and
`<pi-mcp-auth-file>` role placeholders. The original supplied log is retained
privately (SHA256 `c1419a6e17d3afdb14833ffbfac7aa4f4a5b6756dd3fb67cb715b80cde5c8253`);
the sanitized copy has SHA256 `039b3a9d4d92b69879c1266b10f552aea51bf991f77433044dc0b2733e4b2393`.
Its historical commands are evidence text, not instructions to execute.
Sanitization changes naming only and does not claim new experiments. Raw
Round-4 review and owner-direction files are outside this publication package.
