---
description: Configure git worktrees for dev/staging/production Django workflow
---

You are setting up git worktrees for a Django project to enable parallel development across multiple environments.

## What Are Git Worktrees?

Git worktrees allow you to have multiple working directories (checkouts) from a single repository. This is perfect for Django projects where you want to:
- Run dev, staging, and production simultaneously
- Test deployments without switching branches
- Compare code across environments
- Hot-fix production while developing features

Run `/django:worktree-explain` for detailed educational content on worktrees.

## Configuration Questions

Ask the user:

1. **Branch names**:
   - Main development: `main` (recommended) or `develop`
   - Staging: `staging`
   - Production: `production`

2. **Worktree layout**:
   - Option A: Sibling directories (recommended)
     ```
     projects/
     ├── myproject/           # main branch
     ├── myproject-staging/   # staging branch
     └── myproject-production/ # production branch
     ```
   - Option B: Subdirectories
     ```
     myproject/
     ├── main/               # main branch
     ├── staging/            # staging branch
     └── production/         # production branch
     ```

3. **Separate virtual environments?** (recommended: yes)

4. **Database strategy**:
   - Separate database per environment (recommended)
   - Shared database with different schemas
   - SQLite files (dev only)

## Implementation Steps

### Step 1: Verify Current Repository

```bash
# Check current status
git status
git branch -a

# Make sure main branch is clean
git add .
git commit -m "Checkpoint before worktree setup"
```

### Step 2: Create Branches (if not exist)

```bash
# Create staging branch from main
git branch staging main

# Create production branch from main
git branch production main
```

### Step 3: Create Worktrees

**For Sibling Layout:**
```bash
cd ..  # Move to parent directory

# Create staging worktree
git worktree add -b staging ../myproject-staging staging

# Create production worktree
git worktree add -b production ../myproject-production production

# Return to main project
cd myproject
```

**For Subdirectory Layout:**
```bash
# From project root
mkdir worktrees

# Create staging worktree
git worktree add -b staging worktrees/staging staging

# Create production worktree
git worktree add -b production worktrees/production production
```

### Step 4: Configure Each Environment

For each worktree, set up:

**Main (Development):**
```bash
cd myproject  # or myproject/main
python -m venv venv
source venv/bin/activate
pip install -r requirements/local.txt

# Create .env
cp .env.example .env
# Edit .env:
DEBUG=True
DATABASE_URL=postgresql://user:pass@localhost:5432/myproject_dev
```

**Staging:**
```bash
cd myproject-staging  # or myproject/worktrees/staging
python -m venv venv
source venv/bin/activate
pip install -r requirements/production.txt

# Create .env
cp .env.example .env
# Edit .env:
DEBUG=False
DATABASE_URL=postgresql://user:pass@localhost:5432/myproject_staging
DJANGO_SETTINGS_MODULE=config.settings.production
```

**Production:**
```bash
cd myproject-production  # or myproject/worktrees/production
python -m venv venv
source venv/bin/activate
pip install -r requirements/production.txt

# Create .env
cp .env.example .env
# Edit .env:
DEBUG=False
DATABASE_URL=postgresql://user:pass@localhost:5432/myproject_prod
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=<generate-new-key>
ALLOWED_HOSTS=yourdomain.com
```

### Step 5: Create Separate Databases

```bash
# PostgreSQL example
createdb myproject_dev
createdb myproject_staging
createdb myproject_prod

# Run migrations for each
cd myproject && source venv/bin/activate
python manage.py migrate

cd ../myproject-staging && source venv/bin/activate
python manage.py migrate

cd ../myproject-production && source venv/bin/activate
python manage.py migrate
```

### Step 6: Add Worktree Management Scripts

Create `worktree-status.sh`:
```bash
#!/bin/bash
echo "=== Worktree Status ==="
git worktree list
echo ""
echo "=== Branch Status ==="
for dir in myproject myproject-staging myproject-production; do
    if [ -d "../$dir" ]; then
        echo "📁 $dir:"
        cd ../$dir
        git status -s
        echo ""
    fi
done
```

Create `worktree-sync.sh`:
```bash
#!/bin/bash
# Sync changes across worktrees

echo "Fetching latest from origin..."
git fetch origin

echo "Updating main..."
cd ../myproject
git pull origin main

echo "Updating staging..."
cd ../myproject-staging
git pull origin staging

echo "Updating production..."
cd ../myproject-production
git pull origin production

echo "✓ All worktrees synced"
```

Make executable:
```bash
chmod +x worktree-status.sh worktree-sync.sh
```

## Workflow Examples

### Feature Development
```bash
# Work in main
cd myproject
git checkout -b feature/new-feature
# ... develop ...
git add .
git commit -m "Add new feature"
git push origin feature/new-feature

# Test in staging
cd ../myproject-staging
git merge main
python manage.py test
# If good, merge to production
```

### Hotfix Production
```bash
# Fix in production worktree
cd myproject-production
git checkout -b hotfix/critical-bug
# ... fix ...
git add .
git commit -m "Fix critical bug"
git push origin hotfix/critical-bug

# Merge to production
git checkout production
git merge hotfix/critical-bug
git push origin production

# Backport to staging and main
cd ../myproject-staging
git cherry-pick <commit-hash>
cd ../myproject
git cherry-pick <commit-hash>
```

### Deploy Staging → Production
```bash
# In staging, verify everything works
cd myproject-staging
python manage.py test
python manage.py check --deploy

# Merge staging into production
cd ../myproject-production
git merge staging
python manage.py migrate
python manage.py collectstatic --noinput
# Restart services
```

## VSCode Integration

Add to `.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.terminal.activateEnvironment": true,
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true
  }
}
```

Open each worktree as separate VSCode window.

## Benefits Achieved

✓ Run all environments simultaneously
✓ No branch switching required
✓ Test deployments safely
✓ Quick hotfix workflow
✓ Compare environments side-by-side
✓ Independent virtual environments
✓ Isolated database testing

## Cleanup (if needed)

To remove a worktree:
```bash
git worktree remove ../myproject-staging
git branch -d staging
```

To list all worktrees:
```bash
git worktree list
```

## Next Steps

1. Set up CI/CD to deploy from staging/production branches
2. Configure monitoring for each environment
3. Document deployment procedures
4. Train team on worktree workflow

Would you like me to run `/django:worktree-explain` for more detailed education on git worktrees?
