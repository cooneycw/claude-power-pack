---
description: Create a PowerPoint presentation with optional diagrams
allowed-tools: mcp__nano-banana__list_diagram_types, mcp__nano-banana__generate_diagram, mcp__nano-banana__create_pptx, mcp__nano-banana__diagram_to_pptx, mcp__playwright-persistent__create_session, mcp__playwright-persistent__browser_navigate, mcp__playwright-persistent__browser_screenshot, mcp__playwright-persistent__close_session, AskUserQuestion
---

# PowerPoint Creation

## Arguments

- `TOPIC` (optional): The topic or subject for the presentation

## Instructions

When the user invokes `/documentation:pptx [TOPIC]`, guide them through creating a professional presentation.

### Step 1: Gather Requirements

If no topic is provided, ask the user:

```
What would you like to create a presentation about?
```

Then ask for preferences:

1. **Slide count** — How many slides? (default: 5-8)
2. **Diagrams** — Include diagrams? Which types? (architecture, c4, flowchart, sequence, orgchart, timeline, mindmap)
3. **Output path** — Where to save the .pptx file? (default: current directory)

### Step 2: Plan the Presentation

Based on the topic, plan the slide structure:

```
Presentation: "{topic}"

Slide 1: Title slide
Slide 2: Overview / Agenda
Slide 3-N: Content slides (with optional diagrams)
Slide N+1: Summary / Next Steps
```

Report the plan and ask for confirmation.

### Step 3: Generate Diagrams (if requested)

For each diagram requested:

1. Use `generate_diagram` to create the HTML diagram
2. Save the HTML to a temp file
3. If Playwright MCP is available:
   - Create a browser session
   - Navigate to the HTML file
   - Take a screenshot at 1920x1080
   - Close the session
   - Use the screenshot as `image_base64` in the PPTX
4. If Playwright is not available:
   - Use `diagram_to_pptx` for text-based embedding
   - Note that the user can manually screenshot the HTML for better quality

### Step 4: Create the PPTX

Use `create_pptx` with all the slide definitions.

Report:

```
Presentation created!

  File:   {path}
  Slides: {count}
  Size:   {size} KB

  Diagrams generated:
  - {type}: {html_path}
  - ...

  Open the .pptx file to review.
```

### Tips

- Use dark theme (built-in) for modern, professional look
- Diagrams work best as full-width on "diagram" layout slides
- Speaker notes can be added to any slide
- Two-column layout works well for comparisons
- Keep bullet points concise (3-5 per slide)
