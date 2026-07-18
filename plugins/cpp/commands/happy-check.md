---
description: Check if happy-cli is on the latest version
allowed-tools: Bash(happy --version:*), Bash(curl:*), Bash(cat:*), WebFetch
---

# Happy CLI Version Check

Check if the installed happy-cli is on the latest version and report status.

---

## Step 1: Get Installed Version

```bash
happy --version 2>&1 | grep -oP '(?<=happy version: )\S+' || echo "NOT_INSTALLED"
```

---

## Step 2: Get Latest Version from GitHub

Use the GitHub API to get the latest release:

```bash
curl -s https://api.github.com/repos/slopus/happy-cli/releases/latest | grep -oP '"tag_name":\s*"v?\K[0-9.]+' || echo "FETCH_FAILED"
```

---

## Step 3: Compare and Report

Compare the versions and output status:

### If versions match:
```
Happy CLI Status: UP TO DATE
  Installed: {version}
  Latest:    {version}
```

### If update available:
```
Happy CLI Status: UPDATE AVAILABLE
  Installed: {installed_version}
  Latest:    {latest_version}

To update: npm update -g happy-coder
```

### If not installed:
```
Happy CLI Status: NOT INSTALLED

To install: npm install -g happy-coder
```

---

## Step 4: Check Settings Status

Check if happy settings are valid:

```bash
cat ~/.happy/settings.json 2>/dev/null
```

Report if onboarding is incomplete:
- If `onboardingCompleted: false`: Note that onboarding needs to be completed
- If file missing: Note fresh install detected

---

## Output Format

```
=== Happy CLI Status ===

Version: {status}
  Installed: {version}
  Latest:    {latest}

Settings: {status}
  Onboarding: {completed/incomplete}

{action items if any}
```
