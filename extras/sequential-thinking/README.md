# Sequential Thinking MCP

Structured, step-by-step reasoning for complex problem-solving.

## What It Does

The Sequential Thinking MCP server provides a `sequentialthinking` tool that Claude calls iteratively to break down complex problems into numbered thought steps. Features include:

- **Step-by-step reasoning** - Numbered thought progression
- **Revision** - Revisit and correct earlier thought steps
- **Branching** - Explore alternative reasoning paths
- **Dynamic adjustment** - Expand or reduce total steps as understanding deepens

**Important:** This server does NOT use an external LLM. Claude itself does all the thinking — the server provides structure and state tracking for the reasoning process.

## When It Helps

- Complex debugging requiring systematic elimination
- Architectural decisions with many trade-offs
- Multi-step planning where you want visible reasoning
- Problems where backtracking and revision are likely

## Prerequisites

- Node.js 18+ (for `npx`)
- No API keys required
- No Python/uv dependencies

## Installation

### Via /cpp:init (Recommended)

Run `/cpp:init` and select the Sequential Thinking extra when prompted.

### Manual

```bash
claude mcp add --transport stdio --scope user sequential-thinking -- npx -y @modelcontextprotocol/server-sequential-thinking
```

### Verify

```bash
claude mcp list
# Should show: sequential-thinking (stdio)
```

## Uninstall

```bash
claude mcp remove sequential-thinking
```

## How It Works

The server exposes a single tool: `sequentialthinking`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `thought` | string | yes | The current thinking step |
| `nextThoughtNeeded` | boolean | yes | Whether another step is needed |
| `thoughtNumber` | integer | yes | Current thought number |
| `totalThoughts` | integer | yes | Estimated total thoughts needed |
| `isRevision` | boolean | no | Whether this revises previous thinking |
| `revisesThought` | integer | no | Which thought number is being reconsidered |
| `branchFromThought` | integer | no | Branching point thought number |
| `branchId` | string | no | Branch identifier |
| `needsMoreThoughts` | boolean | no | Whether more thoughts are needed beyond totalThoughts |

Claude calls this tool repeatedly (thought 1, thought 2, ...) and the server tracks the full history, including branches and revisions.

## Notes

- **Zero dependencies at runtime** - `npx` downloads the package on first run, then caches it
- **Stdio transport** - Runs as a subprocess, no port needed
- **Disk usage** - ~5 MB (npm cache)
- **No API keys** - Purely local state tracking

## Links

- [Source (GitHub)](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking)
- [npm package](https://www.npmjs.com/package/@modelcontextprotocol/server-sequential-thinking)
