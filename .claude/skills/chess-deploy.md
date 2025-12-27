# Chess Agent Deployment Skill

Use this skill when working with the chess-agent project and need to deploy or test changes.

## Trigger Patterns

- "deploy", "start servers", "run locally"
- "test my changes", "test this branch"
- "restart dev", "restart servers"

## Architecture

The chess-agent has two servers:
- **FastAPI (port 8000)** - AI backend (MCTS, position analysis, training)
- **Django (port 8001)** - Web frontend (templates, WebSocket)

Both must run for the application to work properly.

## Deployment Commands

Always use the deploy script at `scripts/deployment/deploy_chess.sh`:

| Command | Git Pull | Use Case |
|---------|----------|----------|
| `dev` | No | Test current worktree/branch changes |
| `dev PATH` | No | Test specific worktree |
| `local` | Yes | Deploy latest main branch |
| `prod-local` | Yes | Test production settings |
| `deploy` | Yes | Full remote deployment |
| `local-status` | - | Check server status |
| `local-stop` | - | Stop servers |
| `local-logs` | - | Tail server logs |

## Common Scenarios

### Testing a worktree branch
```bash
cd ~/Projects/chess-agent-issue-42
scripts/deployment/deploy_chess.sh dev
```

### Testing from main repo but different worktree
```bash
scripts/deployment/deploy_chess.sh dev ~/Projects/chess-agent-issue-42
```

### Checking status
```bash
scripts/deployment/deploy_chess.sh local-status
```

### Stopping servers
```bash
scripts/deployment/deploy_chess.sh local-stop
```

## Important Notes

1. **Always use the script** - Don't manually start uvicorn or manage.py
2. **dev = no git pull** - Your local changes are preserved
3. **local = git pull** - Updates to latest main
4. **Both servers needed** - Django calls FastAPI for AI operations

## Log Locations

- FastAPI: `/tmp/fastapi-chess.log`
- Django: `/tmp/django-chess.log`
