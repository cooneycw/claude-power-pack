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

## Model-pin amendment (owner ruling)

The owner subsequently chose to pin codex 5.3 for B2. Additional inspected
members of the same tarball:

| Tar member | SHA256 |
|---|---|
| package/dist/cli/list-models.js | 7775957478370706d9859b6c992b74b5f24e6807254dba1a53531132a9240bad |
| package/dist/main.js | b63583f13649b79a9057f92e615c4ed098666a65deb362ed64eabab775eef253 |
| package/dist/core/model-runtime.js | b17018cb70007a194f10b2aaf5ec3631329db20cf853ddc9ce4088e6b4373ab1 |
| package/dist/core/model-resolver.js | fb3603766945dd3aac98456a4cb1798cb0013428c6ea69fc44d43a26c2f63c90 |

args.js lines 66-67 accept --model followed by its value; its help line 295
documents provider/id and an optional thinking suffix. B2 uses the exact listed
provider/id with no fuzzy alias or thinking suffix. The resolver supports
provider-qualified references; a catalog match is preferred over fuzzy/fallback
selection. Any warning or displayed selection mismatch stops the host step.

args.js lines 200-207 accept --list-models with optional fuzzy search.
list-models.js calls getAvailable and prints six whitespace-separated columns:
provider, model, context, max-out, thinking and images. The model cell is m.id,
not m.name. B2 parses only this source-bound format and requires a unique row
whose model ID contains codex and version 5.3. None/ambiguity/schema changes
stop; source inspection does not establish which models the signed-in host has.

main.js lines 488-491 apply --offline before runtime creation by setting
PI_OFFLINE and PI_SKIP_VERSION_CHECK. model-runtime.js line 97 disables its
model-network flag when PI_OFFLINE is defined. main.js lines 797-801 perform
the listing and exit before prompt processing. Thus the proposed preflight
uses --offline --list-models without --print, --mode or a prompt, and makes no
model turn. This source path is not a network security boundary or a claim that
pi avoids internal authentication machinery. No worker-side pi run occurred.

The model pin comes only from CLI output, and selected-model comparisons only
from the flag and pi UI. No direct settings/model-store/credential read is part
of B2. A pin or UI label is not B4's resolved runtime identity.

## B3 MCP source premises

| Same coding-agent tarball member | SHA256 |
|---|---|
| package/docs/mcp.md | c353a4cb49cfff85e5bf1839a7e702f58bfed9df2afcbeeb29cae2b5574cbe3b |
| package/docs/cli.md | d3b719dafaa11c93841059eb02d0167403e26a19d8845ca54aad3443c58952fc |
| package/dist/extensions/mcp/runtime.js | 1ed03790749c1c494f6ff3891652a4ad895cb25bf2ad4ed61202837c5e3055fb |

The MCP docs specify user mcp.json with an mcpServers object, command/args for
stdio and url for Streamable HTTP, plus an optional enabled flag. Tools are
mcp__server__tool with non-alphanumeric/underscore characters normalized to
underscores. B3 tests hyphenated server names and probe-echo, retaining actual
call labels if exposed rather than treating the documented transform as a
fresh runtime observation.

Omitted exposure is codemode, not direct. Direct exposure declares a tool to
the model; codemode and tool_search can reach non-direct tools indirectly.
B3's restricted direct-call lane disables automatic codemode and selects only
the probe MCP prefix. An omitted/direct comparison in that lane cannot support
a global claim that direct exposure is required for every MCP use.

cli.md documents --no-extensions with explicit -e builtin:mcp to retain only
the native MCP extension. --tools with an mcp__ pattern filters MCP as well;
--no-tools would disable MCP entirely and is deliberately not used for B3.
The native runtime constructs McpClient with name pi and VERSION; its client
name is a fixture correlation label, not authenticated process identity.

The package pins @earendil-works/pi-mcp 1.6.0. Its public tarball SHA256 is
c8729b82c28ba2161fd8880284161244e1024914f9a702c1e36db0185d6fbf55;
package/dist/client.js has SHA256
f39e0dccc7823995c22ea7936f3f32cac64d818599efdb217b5e0cf0ff070216.
That client sends its configured name/version in initialize.clientInfo.
The local compatible client deliberately uses cpp-pi1899-control, never pi,
and its calls cannot satisfy the B3 pi-call verifier.

The docs describe stdio and Streamable HTTP and reject legacy SSE. B3 does not
run a legacy SSE experiment and leaves that statement as a documentation
premise. Any failed pi stdio/HTTP attempt requires working compatible-client
controls before and after, without turning one fixture refusal into a universal
transport verdict. No model or credential-store access was needed for this
read-only public-source inspection.
