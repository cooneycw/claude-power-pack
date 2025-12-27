# QA Commands Help

Automated QA testing commands for web applications.

## Available Commands

| Command | Description |
|---------|-------------|
| `/qa:test <target> [area]` | Run QA tests, log bugs as GitHub issues |

## Usage Examples

```bash
# Test entire site
/qa:test https://agentic-chess.ca

# Test specific area
/qa:test chess play

# Find multiple bugs before stopping
/qa:test chess dashboard --find 5

# Test external URL
/qa:test https://myapp.com/login
```

## Project Shortcuts

Currently configured shortcuts:

| Shortcut | URL | Repository |
|----------|-----|------------|
| `chess` | https://agentic-chess.ca | cooneycw/chess-agent |

## Test Areas (for chess)

| Area | Path | Tests |
|------|------|-------|
| `dashboard` | `/` | Stats, actions, health |
| `play` | `/game/` | Board, moves, AI |
| `training` | `/training/` | Controls, progress |
| `analysis` | `/analysis/` | FEN input, MCTS |
| `viewer` | `/viewer/` | Game list, replay |
| `explainer` | `/explainer/` | Content, examples |

## How It Works

1. Creates headless Playwright browser session
2. Navigates to target URL
3. Tests interactive elements (clicks, forms, navigation)
4. Checks console for errors
5. Logs bugs as GitHub issues
6. Reports summary

## Requirements

- Playwright MCP server running (`mcp-playwright-persistent`)
- GitHub CLI authenticated (`gh auth status`)
- Repository access for issue creation
