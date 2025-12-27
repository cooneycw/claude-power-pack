# Project Deployment Skill

Use this skill when deploying or testing changes in projects with deployment scripts.

## Trigger Patterns

- "deploy", "start servers", "run locally"
- "test my changes", "test this branch"
- "restart dev", "restart servers"

## Finding the Deploy Script

Check for deployment scripts in these locations:
1. `scripts/deployment/deploy_*.sh`
2. `scripts/deploy.sh`
3. `deploy.sh`

Run `--help` or `help` to see available commands.

## Standard Deployment Commands

Most deploy scripts follow this pattern:

| Command | Git Pull | Use Case |
|---------|----------|----------|
| `dev` | No | Test current worktree/branch changes |
| `dev PATH` | No | Test specific worktree |
| `local` | Yes | Deploy latest main branch locally |
| `prod-local` | Yes | Test production settings locally |
| `deploy` | Yes | Full remote deployment |
| `status` | - | Check server/infrastructure status |
| `local-status` | - | Check local server status |
| `local-stop` | - | Stop local servers |
| `local-logs` | - | Tail server logs |

## Common Scenarios

### Testing a worktree branch
```bash
cd ~/Projects/{project}-issue-42
scripts/deployment/deploy_{project}.sh dev
```

### Testing from main repo but different worktree
```bash
scripts/deployment/deploy_{project}.sh dev ~/Projects/{project}-issue-42
```

### Checking status
```bash
scripts/deployment/deploy_{project}.sh local-status
```

## Important Notes

1. **Always use the script** - Don't manually start servers
2. **dev = no git pull** - Your local changes are preserved
3. **local = git pull** - Updates to latest main
4. **Check CLAUDE.md** - Project-specific deployment docs

## Project-Specific Notes

### chess-agent

Script: `scripts/deployment/deploy_chess.sh`

Architecture:
- **FastAPI (port 8000)** - AI backend (MCTS, position analysis)
- **Django (port 8001)** - Web frontend (templates, WebSocket)

Both servers must run for the application to work.

Logs:
- FastAPI: `/tmp/fastapi-chess.log`
- Django: `/tmp/django-chess.log`
