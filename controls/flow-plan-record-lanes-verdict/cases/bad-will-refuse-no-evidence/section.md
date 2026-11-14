- Approval:          granted

## Section C - the approved plan
  1. `src/app.py` - because
Scope: 1 file
Risks: none notable

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | a test in a linked worktree |
| Harness | will test (Claude install); not covered (Codex install) | through a symlink; no bundle run |
| Project state | will refuse | a repository that has not adopted the file is told so (not adopted) |
