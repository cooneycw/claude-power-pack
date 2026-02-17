# QA Commands Help

Automated QA testing commands for web applications.

## Available Commands

| Command | Description |
|---------|-------------|
| `/qa:test <target> [area]` | Run QA tests, log bugs as GitHub issues |
| `/qa:help` | This help page |

## Usage Examples

```bash
# Test a URL directly
/qa:test https://myapp.example.com

# Test using a shortcut from qa.yml
/qa:test myapp dashboard

# Find multiple bugs before stopping
/qa:test myapp login --find 5

# Test any external URL (no config needed)
/qa:test https://other-site.com/page
```

## Configuration: `.claude/qa.yml`

Place a `qa.yml` file in your project's `.claude/` directory to configure shortcuts, test areas, and project metadata.

**Setup:**
```bash
# Copy the template
cp ~/Projects/claude-power-pack/templates/qa.yml.example .claude/qa.yml

# Edit for your project
```

**If no `.claude/qa.yml` exists**, `/qa:test` runs in interactive mode — it prompts for a URL and uses generic testing (clicking elements, checking forms, scanning console errors).

### Config Schema

```yaml
# Project information
project:
  url: https://myapp.example.com        # Default URL
  repository: owner/repo-name           # GitHub repo for bug issues

# Shortcuts — short names that resolve to URLs
shortcuts:
  myapp: https://myapp.example.com
  staging: https://staging.myapp.example.com

# Test areas — named sections with paths and test checklists
test_areas:
  home:
    path: /                              # URL path appended to project URL
    description: "Homepage and landing"  # Shown in test reports
    tests:                               # Checklist of things to verify
      - "Page loads without errors"
      - "Navigation links work"
      - "Key content visible"

  login:
    path: /login
    description: "Authentication flow"
    tests:
      - "Login form renders"
      - "Form validation works"
      - "Successful login redirects"
```

### Config Fields

| Field | Required | Description |
|-------|----------|-------------|
| `project.url` | Yes | Default base URL for the application |
| `project.repository` | No | GitHub `owner/repo` for issue creation (auto-detected if omitted) |
| `shortcuts` | No | Map of short names to URLs |
| `test_areas` | No | Named test areas with paths and test checklists |
| `test_areas.<name>.path` | Yes | URL path relative to project URL |
| `test_areas.<name>.description` | No | Human-readable area description |
| `test_areas.<name>.tests` | No | List of specific checks to perform |

## How It Works

1. Loads `.claude/qa.yml` config (or prompts interactively)
2. Creates headless Playwright browser session
3. Navigates to target URL (resolving shortcuts and area paths)
4. Runs test checklist from config (or generic element testing)
5. Checks console for errors
6. Logs bugs as GitHub issues
7. Reports summary with test coverage

## Requirements

- Playwright MCP server running (`mcp-playwright-persistent`)
- GitHub CLI authenticated (`gh auth status`)
- Repository access for issue creation
