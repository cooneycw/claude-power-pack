---
description: Educational guide explaining git worktrees and their benefits for Django development
---

# Git Worktrees: Complete Educational Guide

## What Are Git Worktrees?

A git worktree is an additional working directory linked to your repository. Instead of switching branches (which changes files in place), you can have multiple branches checked out simultaneously in different directories.

### Traditional Git Workflow (Without Worktrees)

```
myproject/           # Single working directory
├── manage.py
├── config/
└── apps/

# To work on production:
$ git checkout production
# Files change in place
# Can't run dev and production simultaneously
# Must stash or commit before switching
```

### With Git Worktrees

```
myproject/           # main branch
├── manage.py
├── config/
└── apps/

myproject-staging/   # staging branch (separate directory)
├── manage.py
├── config/
└── apps/

myproject-production/ # production branch (separate directory)
├── manage.py
├── config/
└── apps/
```

All three directories exist simultaneously, each with their own:
- Checked out branch
- Working files
- Python virtual environment
- Database connection
- Running server

## Why Use Worktrees with Django?

### Problem 1: Can't Run Multiple Environments

**Without Worktrees:**
```bash
# Want to test production while developing?
$ git checkout production
# Uh oh - lost all uncommitted dev work
# Can't run dev server and production server simultaneously
# Port 8000 is taken
```

**With Worktrees:**
```bash
# Terminal 1 - Development
cd myproject
python manage.py runserver 8000

# Terminal 2 - Staging
cd myproject-staging
python manage.py runserver 8001

# Terminal 3 - Production
cd myproject-production
python manage.py runserver 8002

# All running simultaneously!
```

### Problem 2: Testing Deployments

**Without Worktrees:**
```bash
$ git checkout production
$ python manage.py migrate  # Testing migration
# Wait... did I commit everything from dev?
# Now I have to switch back, remember what I was doing...
```

**With Worktrees:**
```bash
cd myproject-production
python manage.py migrate
# Test passes? Great!
# Dev work in myproject/ is untouched
```

### Problem 3: Urgent Hotfixes

**Without Worktrees:**
```bash
# You're deep in feature development
$ git status
# 15 files modified, half working, half broken

# URGENT: Production is down!
$ git stash      # Hope nothing breaks
$ git checkout production
$ # fix bug
$ git checkout main
$ git stash pop  # Pray conflicts don't happen
```

**With Worktrees:**
```bash
# Deep in development in myproject/

# URGENT: Production is down!
cd ../myproject-production
# Fix bug
git commit -m "Hotfix critical issue"
git push

# Back to development
cd ../myproject
# Everything exactly as you left it
```

## Visual Architecture

### Single Repository, Multiple Working Directories

```
.git/                    # Shared git database
│
├── worktrees/
│   ├── staging/         # Metadata for staging worktree
│   └── production/      # Metadata for production worktree
│
myproject/               # Primary worktree (main branch)
│   ├── .git             # Link to ../.git
│   ├── venv/            # Independent Python environment
│   └── .env             # DATABASE_URL=...myproject_dev
│
myproject-staging/       # Secondary worktree (staging branch)
│   ├── .git             # Link to ../myproject/.git
│   ├── venv/            # Independent Python environment
│   └── .env             # DATABASE_URL=...myproject_staging
│
myproject-production/    # Secondary worktree (production branch)
    ├── .git             # Link to ../myproject/.git
    ├── venv/            # Independent Python environment
    └── .env             # DATABASE_URL=...myproject_prod
```

**Key Point:** They all share the same `.git` database, so commits made in one worktree are immediately visible to others.

## Common Commands Reference

### Creating Worktrees

```bash
# Create new worktree with existing branch
git worktree add ../myproject-staging staging

# Create new worktree AND new branch
git worktree add -b feature/new-feature ../myproject-feature

# Create worktree from specific commit
git worktree add ../myproject-v1.0 v1.0.0
```

### Managing Worktrees

```bash
# List all worktrees
git worktree list

# Output:
# /path/to/myproject              abc123 [main]
# /path/to/myproject-staging      def456 [staging]
# /path/to/myproject-production   ghi789 [production]

# Remove worktree
git worktree remove ../myproject-staging

# Prune stale worktree metadata
git worktree prune
```

### Working Across Worktrees

```bash
# In myproject/
git commit -m "Add feature"

# In myproject-staging/
git log  # Can see the commit from myproject

git merge main  # Merge changes from main
```

## Django-Specific Considerations

### 1. Virtual Environments

Each worktree should have its own venv:

```bash
cd myproject
python -m venv venv

cd ../myproject-staging
python -m venv venv

cd ../myproject-production
python -m venv venv
```

**Why?** Each environment might have slightly different dependencies (dev tools in development, optimized packages in production).

### 2. Database Separation

Each environment should have its own database:

```env
# myproject/.env
DATABASE_URL=postgresql://user:pass@localhost/myproject_dev

# myproject-staging/.env
DATABASE_URL=postgresql://user:pass@localhost/myproject_staging

# myproject-production/.env
DATABASE_URL=postgresql://user:pass@localhost/myproject_prod
```

**Why?** Prevents migration testing in staging from affecting your dev database.

### 3. Static Files

Each worktree collects static files independently:

```bash
# Development
cd myproject
python manage.py collectstatic

# Staging
cd ../myproject-staging
python manage.py collectstatic --noinput

# Production
cd ../myproject-production
python manage.py collectstatic --noinput
```

Static files go to separate locations (configured per environment).

### 4. Media Files

**Option A:** Shared media (development only)
```python
# Symlink media directories
ln -s ../myproject/media myproject-staging/media
```

**Option B:** Separate media (recommended)
```python
# Each environment uploads to different S3 bucket or local path
```

## Workflow Scenarios

### Scenario 1: Feature Development & Testing

```bash
# Day 1: Start feature
cd myproject
git checkout -b feature/user-dashboard
# ... develop ...

# Day 2: Test in staging before merge
cd ../myproject-staging
git fetch
git checkout feature/user-dashboard
python manage.py migrate
python manage.py test
# Runs staging database, doesn't touch dev

# Day 3: Merge and deploy
cd ../myproject
git checkout main
git merge feature/user-dashboard

cd ../myproject-staging
git checkout staging
git merge main

cd ../myproject-production
git checkout production
git merge staging
python manage.py migrate --noinput
python manage.py collectstatic --noinput
# Deploy
```

### Scenario 2: Comparing Environments

```bash
# Production has a bug that dev doesn't?
diff -r myproject/apps/users myproject-production/apps/users

# Or use a proper diff tool
meld myproject myproject-production
```

### Scenario 3: Emergency Rollback

```bash
cd myproject-production
git log  # Find last good commit
git checkout <commit-hash>
# Test the old version
# If good, create rollback branch
git checkout -b rollback/v1.2.0
```

## Common Pitfalls & Solutions

### Pitfall 1: Forgetting Which Worktree You're In

**Problem:**
```bash
$ git status
On branch production
# Wait, I thought I was in dev!
```

**Solution:** Customize your shell prompt

```bash
# Add to ~/.bashrc or ~/.zshrc
parse_git_branch() {
    git branch 2> /dev/null | sed -e '/^[^*]/d' -e 's/* \(.*\)/ (\1)/'
}

export PS1="\[\033[32m\]\w\[\033[33m\]\$(parse_git_branch)\[\033[00m\] $ "
```

Now your prompt shows: `~/myproject (main)` or `~/myproject-production (production)`

### Pitfall 2: Pushing Wrong Branch

**Problem:**
```bash
# In production worktree, but accidentally:
git push origin main  # Oops
```

**Solution:** Use branch-specific push

```bash
# Set upstream for each worktree
cd myproject
git push -u origin main

cd ../myproject-staging
git push -u origin staging

cd ../myproject-production
git push -u origin production

# Now just: git push (pushes to correct branch)
```

### Pitfall 3: Port Conflicts

**Problem:**
```bash
# Both trying to use port 8000
cd myproject
python manage.py runserver  # Port 8000

cd ../myproject-staging
python manage.py runserver  # Error: Port already in use!
```

**Solution:** Assign ports per environment

```bash
# Development
python manage.py runserver 8000

# Staging
python manage.py runserver 8001

# Production
python manage.py runserver 8002
```

Or use environment variables:

```env
# myproject/.env
PORT=8000

# myproject-staging/.env
PORT=8001
```

## When NOT to Use Worktrees

Worktrees might be overkill if:

- You're working alone on a simple project
- You don't need to run multiple environments simultaneously
- You're comfortable with branch switching
- You use containers for environment isolation (Docker Compose)

## Worktrees vs. Docker

### Docker Compose Approach
```yaml
services:
  dev:
    build: .
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings.local
  staging:
    build: .
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings.production
```

**Pros:** True isolation, closer to production
**Cons:** Slower startup, more complexity

### Worktrees Approach
Multiple directories with native Python environments

**Pros:** Fast, simple, native debugging
**Cons:** Less isolation, manual setup

**Best Answer:** Use both! Worktrees for development/testing, Docker for deployment simulation.

## Advanced: Worktrees + tmux/screen

Create a tmux session with all environments:

```bash
# .tmux-django.sh
#!/bin/bash
tmux new-session -d -s django

tmux rename-window 'Django'
tmux send-keys 'cd myproject && source venv/bin/activate && python manage.py runserver 8000' C-m

tmux split-window -h
tmux send-keys 'cd myproject-staging && source venv/bin/activate && python manage.py runserver 8001' C-m

tmux split-window -v
tmux send-keys 'cd myproject-production && source venv/bin/activate' C-m

tmux attach-session -t django
```

Run: `./tmux-django.sh` to instantly have all environments ready!

## Summary

Git worktrees are perfect for Django development when you:
- Need to run multiple environments simultaneously
- Test deployments without disrupting development
- Handle urgent hotfixes while feature work is in progress
- Compare code across environments
- Want faster context switching than Docker

They're simple, fast, and leverage git's native capabilities.

Ready to set up worktrees? Run `/django:worktree-setup` to get started!
