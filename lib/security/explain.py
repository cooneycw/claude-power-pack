"""Detailed explanations for security findings.

Provides in-depth rationale for each finding type,
aimed at developers who want to understand the "why" deeply.
"""

from __future__ import annotations

# Finding ID -> detailed explanation
EXPLANATIONS: dict[str, str] = {
    "GITIGNORE_MISSING": """
## .gitignore Missing

Your project has no .gitignore file. This means `git add .` or `git add -A`
will stage EVERY file in your project, including:

- `.env` files with database passwords and API keys
- Private keys (*.pem, *.key) used for TLS or SSH
- IDE configuration that may contain tokens
- Build artifacts and dependencies

### What to do

1. Create a .gitignore immediately
2. Use a generator for your language: https://www.toptal.com/developers/gitignore
3. Always add `.env`, `*.pem`, `*.key` at minimum

### If you already committed secrets

Secrets in git history remain accessible even after deletion.
You must rotate (change) any exposed credentials immediately.
""",
    "GITIGNORE_GAP": """
## .gitignore Gap

Your .gitignore exists but is missing coverage for a sensitive file pattern.
This creates a risk window where `git add .` could include secrets.

### Common patterns to include

```gitignore
# Environment files
.env
.env.*

# Private keys
*.pem
*.key
*.p12

# Secrets
secrets.*

# IDE/editor
.idea/
.vscode/settings.json
```

### Best practice

Use language-specific gitignore templates as a starting point,
then add project-specific patterns.
""",
    "FILE_PERMISSIONS": """
## Sensitive File Permissions

Unix file permissions control who can read, write, and execute files.
Sensitive files should be readable only by the owner (mode 600).

### Permission breakdown

- `600` (rw-------): Owner can read/write. Nobody else can access. GOOD.
- `644` (rw-r--r--): Owner can read/write. Everyone can read. BAD for secrets.
- `755` (rwxr-xr-x): Everyone can read and execute. BAD for secrets.

### Why this matters

On shared systems (servers, CI), other users/processes may be able to
read world-readable files. This includes other containers on the same host.

### Fix

```bash
chmod 600 path/to/sensitive/file
```
""",
    "AWS_ACCESS_KEY": """
## AWS Access Key in Source Code

AWS access keys (starting with AKIA) provide direct access to your AWS account.
If committed to a public repository, automated bots scan for these within minutes
and can spin up resources at your expense.

### Immediate actions

1. **Rotate the key immediately** in AWS IAM Console
2. Remove from source code
3. Check CloudTrail for unauthorized usage

### Best practice

Use IAM roles (for EC2/Lambda) or environment variables (for local dev).
Never put AWS keys in source code.
""",
    "OPENAI_API_KEY": """
## OpenAI API Key in Source Code

OpenAI API keys (starting with sk-proj-) provide access to your OpenAI
account and can incur charges. If exposed, anyone can make API calls
billed to your account.

### Fix

1. Rotate the key in the OpenAI dashboard
2. Store in .env file (not tracked by git)
3. Load via `os.environ["OPENAI_API_KEY"]`
""",
    "ANTHROPIC_API_KEY": """
## Anthropic API Key in Source Code

Anthropic API keys (starting with sk-ant-) provide access to Claude
and other Anthropic APIs. Exposure means unauthorized access to your account.

### Fix

1. Rotate the key in the Anthropic console
2. Store in environment variable or secrets manager
3. Never commit to source control
""",
    "GITHUB_PAT": """
## GitHub Personal Access Token in Source Code

GitHub PATs (starting with ghp_) provide authenticated access to your
GitHub account. Depending on scopes, this could allow reading private repos,
pushing code, or managing settings.

### Fix

1. Revoke the token in GitHub Settings > Developer Settings > Personal Access Tokens
2. Create a new token with minimal required scopes
3. Store in environment variable
""",
    "HARDCODED_PASSWORD": """
## Hardcoded Password

A password was found directly in source code. This means:
- The password is visible to anyone with repo access
- It cannot be rotated without a code change and deployment
- It's stored in git history even after removal

### Best practice

Use environment variables or a secrets manager:

```python
# Bad
password = "my_secret_password"

# Good
password = os.environ["DB_PASSWORD"]
```
""",
    "HARDCODED_SECRET": """
## Hardcoded Secret/Token

A secret or token was found assigned to a variable in source code.
Hard-coded secrets create security and operational risks.

### Fix

1. Move to .env file or secrets manager
2. Load via environment variable
3. Rotate the exposed credential
""",
    "ENV_TRACKED": """
## .env File Tracked by Git

Your .env file is being tracked by git version control. This means:
- The file (with all secrets) exists in your repository history
- Anyone who clones or forks the repo gets your secrets
- Even if you delete it later, the history retains the content

### Fix

```bash
# Remove from git tracking (keeps the local file)
git rm --cached .env

# Prevent future tracking
echo ".env" >> .gitignore

# Commit the changes
git add .gitignore
git commit -m "Remove .env from tracking"
```

### If your repo is public

All secrets in the .env file should be considered compromised.
Rotate every credential immediately.
""",
    "DEBUG_FLAG": """
## Debug Flag in Configuration

Debug mode was found enabled in a configuration file. In production:
- Stack traces may be shown to users, revealing code structure
- Debug endpoints may be exposed
- Verbose logging may include sensitive data
- Performance is typically degraded

### Fix

Ensure debug is disabled for production:

```python
# Django
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"

# Flask
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"
```
""",
}


def get_explanation(finding_id: str) -> str | None:
    """Get detailed explanation for a finding ID."""
    return EXPLANATIONS.get(finding_id)


def list_finding_ids() -> list[str]:
    """List all finding IDs that have explanations."""
    return sorted(EXPLANATIONS.keys())
