---
description: Create a PowerPoint presentation with optional diagrams
allowed-tools: mcp__nano-banana__list_diagram_types, mcp__nano-banana__generate_diagram, mcp__nano-banana__validate_diagram, mcp__nano-banana__split_diagram, mcp__nano-banana__create_pptx, mcp__nano-banana__validate_pptx_slides, mcp__nano-banana__diagram_to_pptx, mcp__playwright-persistent__create_session, mcp__playwright-persistent__browser_navigate, mcp__playwright-persistent__browser_screenshot, mcp__playwright-persistent__close_session, AskUserQuestion
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

1. **Slide count** - How many slides? (default: 5-8)
2. **Diagrams** - Include diagrams? Which types? (architecture, c4, flowchart, sequence, orgchart, timeline, mindmap)
3. **Output path** - Where to save the .pptx file? (default: current directory)
4. **Communication framework** - How should the narrative be structured? (default: auto-select based on topic)
5. **Organization ethos** - Does the user have a file or URL describing organizational values/culture? (optional)

### Step 1b: Framework Selection

If the user wants to choose a communication framework, present these options:

| Framework | Structure | Description | Best For |
|-----------|-----------|-------------|----------|
| **GAME** | Goal / Audience / Message / Expression | Developed at McKinsey. Forces clarity on what you want (Goal), who decides (Audience), the single key takeaway (Message), and how to deliver it (Expression). One message per deck principle. | Strategic proposals, board presentations, stakeholder alignment |
| **Pyramid** | Answer / Supporting Arguments / Evidence | Barbara Minto's Pyramid Principle. Lead with the answer, then group supporting arguments, then evidence. Top-down structure so executives get the point immediately. | Executive summaries, recommendation decks, consulting deliverables |
| **SCQA** | Situation / Complication / Question / Answer | A storytelling variant of the Pyramid. Establishes shared context (Situation), introduces tension (Complication), frames the decision (Question), then delivers the recommendation (Answer). | Problem-solving, analytical presentations, strategy pivots |
| **STAR** | Situation / Task / Action / Result | Behavioral narrative structure. Describes the starting context, the specific challenge, what was done, and measurable outcomes. Concrete and evidence-based. | Case studies, project retrospectives, interview prep, performance reviews |
| **Monroe** | Attention / Need / Satisfaction / Visualization / Action | Alan Monroe's Motivated Sequence. Grabs attention, establishes urgency, presents the solution, paints the future state, then calls for action. Designed to persuade. | Persuasive pitches, change management, fundraising, policy proposals |
| **PSB** | Problem / Solution / Benefit | The simplest persuasive structure. Name the pain, show the fix, quantify the win. No wasted slides. | Product demos, feature announcements, sales decks, internal tool adoption |
| **Narrative** | Setup / Conflict / Journey / Resolution | Classic storytelling arc. Establishes the world, introduces a challenge, follows the journey through it, and arrives at resolution. Emotional engagement over logic. | Vision presentations, company all-hands, transformation stories, keynotes |

If the user provides an org ethos file (PDF, DOCX, URL, or pasted text):
- Read and extract key principles, values, mission, strategic pillars
- Strip corporate names and identifiers (anonymize by default)
- Weave organizational values into the slide narrative and speaker notes

If no framework is specified, auto-select based on the topic:
- Technical architecture -> Pyramid
- Project updates -> STAR
- Proposals -> GAME or Monroe
- Problem analysis -> SCQA
- Product features -> PSB

### Step 2: Plan the Presentation

Structure the deck according to the selected framework. Apply the framework implicitly through headings and flow - NEVER name the framework in the output.

Example structures:

**GAME-structured deck:**
```
Slide 1: Title
Slide 2: The Objective (Goal)
Slide 3: Who This Is For (Audience)
Slide 4-N: Key Points (Message)
Slide N+1: Recommended Actions (Expression)
```

**Pyramid-structured deck:**
```
Slide 1: Title
Slide 2: Executive Summary (answer first)
Slide 3: Current Situation
Slide 4: The Challenge
Slide 5-N: Supporting Evidence
Slide N+1: Recommendation
```

**SCQA-structured deck:**
```
Slide 1: Title
Slide 2: Where We Are (Situation)
Slide 3: What Changed (Complication)
Slide 4: The Key Question
Slide 5-N: The Answer + Evidence
Slide N+1: Next Steps
```

Report the plan and ask for confirmation.

### Step 3: Generate Diagrams (if requested)

For each diagram requested:

1. Use `generate_diagram` to create the HTML diagram
2. **QA gate the result** before proceeding (see QA Gating below)
3. Save the validated HTML to a temp file
4. If Playwright MCP is available:
   - Create ONE Playwright session for ALL diagrams (do not create/close per diagram)
   - For EACH diagram: navigate to the HTML file, screenshot at 1920x1080
   - Close session ONCE at the end, after all diagrams are captured
   - Use each screenshot as `image_base64` in the PPTX
5. If Playwright is not available:
   - Use `diagram_to_pptx` for text-based embedding
   - Note that the user can manually screenshot the HTML for better quality

#### Diagram QA Gating

After each `generate_diagram` call, check the response for warnings before embedding:

```
qa_events = []

for each diagram:
    result = generate_diagram(...)

    # Check for warnings
    if result.get("warnings"):
        high_issues = [w for w in result.warnings if w.severity == "high"]
        medium_issues = [w for w in result.warnings if w.severity == "medium"]

        # HIGH severity: block embedding and fix
        for warning in high_issues:
            if warning.check == "edge_validity":
                # Fix invalid edge references and retry (max 2 retries)
                fix edges, retry generate_diagram
                qa_events.append({"action": "edge_fix_retry", "details": warning.message})

            if warning.check == "viewport_fit":
                # Diagram overflows viewport - split or regenerate at higher dimensions
                if result.density.status in ("overflow", "critical"):
                    split_result = split_diagram(
                        diagram_type=..., title=..., nodes=..., edges=...,
                        max_nodes_per_page=15,
                        strategy="c4_boundary",
                    )
                    # Use split summary diagram for PPTX (detail pages saved separately)
                    result = split_result.diagrams[0]  # summary
                    qa_events.append({"action": "split", "details": "overflow"})

        # MEDIUM severity: warn but allow embedding
        for warning in medium_issues:
            qa_events.append({"action": "warning", "details": warning.message})

    # Proceed with validated/fixed diagram HTML
```

#### Playwright Session Optimization

Use ONE browser session for all diagram screenshots to reduce overhead:

```
# Create ONE session before the diagram loop
session = create_session(headless=true, viewport={"width": 1920, "height": 1080})

for each diagram_html in generated_diagrams:
    browser_navigate(session_id=session.id, url="file://{absolute_path}")
    screenshot = browser_screenshot(session_id=session.id, full_page=true)
    # Store screenshot for PPTX embedding

# Close session ONCE after all diagrams
close_session(session_id=session.id)
```

### Step 4: Create the PPTX

Use `create_pptx` with all the slide definitions. The tool runs QC validation automatically before building - if high-severity issues are found (framework names, placeholder text), it will return an error with the issues list. Fix them and retry.

You can also run `validate_pptx_slides` manually before `create_pptx` to preview issues.

Report:

```
Presentation created!

  File:      {path}
  Slides:    {count}
  Size:      {size} KB
  Framework: {framework} (applied implicitly)
  QC:        Passed ({issue_count} checks)

  Diagrams generated:
  - {type}: {html_path}
  - ...

  Diagram QA:
    Validated:  {total} diagrams
    Splits:     {split_count} (overflow diagrams split into summary + detail)
    Retries:    {retry_count} (edge fixes)
    Warnings:   {warning_count} (orphan nodes, long labels)

  Open the .pptx file to review.
```

### Content Rules

- **No framework attribution** - Apply communication framework structures implicitly through headings, flow, and narrative. NEVER name the framework in slide titles, content, footers, or speaker notes unless the user explicitly requests attribution.
- **No corporate name references** - Do not reference consulting firms (McKinsey, BCG, Bain, etc.) or their proprietary methods. The frameworks are public domain tools for structuring communication.
- **Anonymize by default** - If the user provides organizational documents, strip corporate names and identifiers unless told otherwise.
- **QC gate** - The `create_pptx` tool blocks on high-severity QC issues. Fix flagged content before finalizing.

### Tips

- Use dark theme (built-in) for modern, professional look
- Diagrams work best as full-width on "diagram" layout slides
- Speaker notes can be added to any slide
- Two-column layout works well for comparisons
- Keep bullet points concise (3-5 per slide)
- If org ethos is provided, reference values in speaker notes for presenter context
