# Pi 1.6.0 published-source inputs to B2

Read-only package inspection on 2026-11-27 for #1899. The author downloaded the
public npm tarball into memory without installing dependencies or running pi.
This is source evidence, separate from the [host's version observation](issue-1899-b0-results.md).
Version equality alone does not prove the host executable matches every tarball
byte. No owner configuration, credential or transcript was inspected.

Package: @earendil-works/pi-coding-agent 1.6.0.
Source URL: https://registry.npmjs.org/@earendil-works/pi-coding-agent/-/pi-coding-agent-1.6.0.tgz
Tarball SHA256: 85d5de404e019e850c90ee9ac6dc6c16240da122fdce0314895608164030336b.
The registry metadata names https://github.com/earendil-works/pi and the
packages/coding-agent directory. No gitHead field was supplied; no source
commit is invented here. These digests identify bytes, not publisher identity.

| Tar member | SHA256 |
|---|---|
| package/docs/configuration.md | fc48d1ce7d885c5253222415fb7a4b46d75f80e6431eb924174657ff775099eb |
| package/dist/core/resource-loader.js | 86a7f4c1112f11a198ce2f23b4abfd1fb534a003ce0afa226b2b6de655a32295 |
| package/dist/core/system-prompt.js | 5f68e89c31ba3d4d1af8ad2bfd0c7c548879d47ee6ab4aabee50a826100da32c |
| package/dist/cli/args.js | 8956ae0e02442e6ee32e0bb3b5216818e806cdb469104813425b25394da9953c |

Configuration docs distinguish the agent directory from project configuration.
Context-file discovery is independent of trust and includes cwd ancestors.
An override replaces the other candidates only in its own directory.

The examined loadContextFileFromDir function (resource-loader.js lines 129-148)
tries AGENTS.override.md, AGENTS.md, AGENTS.MD, CLAUDE.md and CLAUDE.MD in that
order. It returns the selected file's readFileSync UTF-8 content even when
empty; errors can fall through to another candidate. This is the source premise
for testing empty-override precedence, not a reported runtime outcome.
loadProjectContextFiles includes the agent context and cwd ancestor contexts.
The B2 helper therefore refuses any named context candidate found on the two
known scratch cwd chains, without reading its content or changing it.

renderProjectContext (system-prompt.js lines 25-29) interpolates each context
content into project_instructions markup. The examined configuration page and
these loader/render functions specify no numeric per-file cap. This bounded
inspection is not an exhaustive no-limit scan or an unlimited-runtime claim.
B2 samples exactly 8,192, 32,768 and 65,536 bytes in both rule names. Any exact
boundary, aggregate limit or downstream truncation remains unmeasured unless
actual host evidence establishes it.

The args parser recognizes --no-session, --no-tools, --no-mcp, --no-extensions
and --no-skills. Its help text describes ephemeral sessions; disabled built-in
and extension tools; disabled built-in MCP connections/tools; and disabled
extension/skill discovery. B2 leaves context loading enabled, starts a new
process per comparison, and treats unsupported flags or any actual tool call
as a stopped or invalid observation. Source help is not independent proof of
host-side enforcement. No help/version command ran in the owner's real HOME.
