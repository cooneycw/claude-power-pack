---
description: Search for skills from the skills.sh ecosystem by keyword or domain
allowed-tools: Bash(npx:*), Bash(which:*), Bash(command:*), WebFetch, WebSearch
---

# Find Skills

Search the skills.sh ecosystem for agent skills that match a task or domain.

## Arguments

- `QUERY` (optional): Search keywords (e.g., "react performance", "pr review", "changelog")

---

## Step 1: Check Skills CLI Availability

```bash
command -v npx >/dev/null 2>&1 && echo "npx available" || echo "npx not found"
```

If npx is not available, tell the user they need Node.js installed and stop.

---

## Step 2: Understand the Request

If the user provided a QUERY, use it directly.

If no QUERY was provided, ask the user what kind of skill they are looking for. Consider these common categories:

| Category | Example Queries |
|----------|----------------|
| Web Development | react, nextjs, typescript, css, tailwind |
| Testing | testing, jest, playwright, e2e |
| DevOps | deploy, docker, kubernetes, ci-cd |
| Documentation | docs, readme, changelog, api-docs |
| Code Quality | review, lint, refactor, best-practices |
| Design | ui, ux, design-system, accessibility |
| Productivity | workflow, automation, git |

---

## Step 3: Search for Skills

Run the skills CLI search:

```bash
npx skills find $QUERY
```

---

## Step 4: Verify Quality Before Recommending

**Do not recommend a skill based solely on search results.** Verify:

1. **Install count** - Prefer skills with 1K+ installs. Be cautious with anything under 100.
2. **Source reputation** - Official sources (`vercel-labs`, `anthropics`, `microsoft`) are more trustworthy.
3. **GitHub stars** - A skill from a repo with <100 stars should be treated with skepticism.

---

## Step 5: Present Results

For each relevant skill found, present:

1. The skill name and what it does
2. The install count and source
3. The install command: `npx skills add <owner/repo@skill>`
4. A link to learn more at skills.sh

Example format:

```
Found 3 skills matching "react performance":

1. react-best-practices (vercel-labs/agent-skills) - 185K installs
   React and Next.js performance optimization guidelines
   Install: npx skills add vercel-labs/agent-skills@react-best-practices
   More:    https://skills.sh/vercel-labs/agent-skills/react-best-practices

2. ...
```

If the user wants to install one, suggest they run `/skills:add <package>` or offer to install it directly.

---

## Step 6: No Results

If no relevant skills are found:

1. Acknowledge that no existing skill was found for the query
2. Suggest alternative search terms
3. Offer to help with the task directly using general capabilities
4. Mention they can create their own skill with `npx skills init`

---

## Notes

- This command requires Node.js/npx to be installed
- Results come from the skills.sh ecosystem
- Always verify skill quality before recommending installation
- For direct installation without search, use `/skills:add`
