# Playwright spike (#419): upstream playwright-mcp side-by-side + mid-session MCP registration

**Epic:** #417 Phase B (mcp-playwright-persistent DECIDE item; review doc section 3 row 12, section 4).
**Date:** 2026-07-03. **Method:** live side-by-side on this workstation, not doc-only research.
**Feeds:** #421 (wrapper-skill design), #422 (upstream contribution), #423 (migrate + retire).

## TL;DR verdicts (exit criteria)

1. **Tool coverage:** upstream `@playwright/mcp` (v0.0.77) is a strict SUPERSET of our 29 tools for browser
   automation. The only real gap is our 5 `*_session` named-concurrent-session tools (plus `health_check`,
   an infra tool). Six thin conveniences (`go_forward`, `reload`, `get_text`, `get_attribute`,
   `get_content`, `query_selector_all`) have no 1:1 upstream tool but are one-liners via `browser_evaluate`.
2. **Mid-session MCP registration: NOT feasible.** A running Claude Code session reads MCP config at
   startup only; `/mcp reconnect` re-connects already-known servers, it does not load newly-added ones.
   Confirmed empirically (a `claude mcp add` mid-session lands in "Pending approval" and is not exposed)
   and authoritatively (docs). => **Design A (static pre-registered slot pool) is the only viable wrapper
   design; Design B (dynamic spawn per session) is ruled out.**
3. **Footprint:** the custom image is ~1.27 GB on disk (not the "155 MB" in the review doc); Chromium is
   the irreducible cost and upstream carries the same ~1.3 GB browser payload. The real saving from
   retiring is MAINTENANCE surface (our Dockerfile + the two-layer Woodpecker Trivy CVE gate), not bytes.
4. **Bonus finding that reframes the decision:** neither `/qa:test` nor `/documentation:pptx` actually
   uses named CONCURRENT sessions. `/qa:test` runs a single create -> use -> close lifecycle;
   `/documentation:pptx` references no session tools at all. CPP's one remaining edge is not consumed by
   CPP's own consumers.

## Task 1: side-by-side

- Upstream ran locally via `npx -y @playwright/mcp@latest` (v0.0.77, ~100 KB of JS) alongside the running
  `mcp-playwright-persistent:31cbb9e` container (port 8081, healthy). Both coexist; upstream binds its own
  `--port` for SSE. No conflict.
- Node/npx v22.23 present, so upstream is a drop-in local runtime with no new base dependency.

## Task 2: tool mapping (29 CPP tools -> upstream)

`core` = eager-loaded (issue #193); `extended` = deferred. Upstream tool names verified against the cached
package, not from memory.

| # | CPP tool | tag | Upstream equivalent | Status |
|---|----------|-----|---------------------|--------|
| 1 | create_session | core | (one server instance = one session) | GAP: named concurrent sessions |
| 2 | close_session | core | (stop instance) | GAP: lifecycle = process mgmt |
| 3 | list_sessions | ext | - | GAP |
| 4 | get_session_info | ext | - | GAP |
| 5 | cleanup_idle_sessions | ext | (upstream idle-timeout config) | GAP (config, not a tool) |
| 6 | browser_navigate | core | browser_navigate | OK |
| 7 | browser_click | core | browser_click | OK |
| 8 | browser_type | core | browser_type | OK |
| 9 | browser_fill | ext | browser_fill_form | OK (form-oriented) |
| 10 | browser_select_option | ext | browser_select_option | OK |
| 11 | browser_hover | ext | browser_hover | OK |
| 12 | browser_new_tab | ext | browser_tabs (new) | OK (unified tab tool) |
| 13 | browser_switch_tab | ext | browser_tabs (select) | OK |
| 14 | browser_close_tab | ext | browser_tabs (close) | OK |
| 15 | browser_go_back | ext | browser_navigate_back | OK |
| 16 | browser_go_forward | ext | - | minor: via evaluate/navigate |
| 17 | browser_reload | ext | - | minor: via navigate(same url) |
| 18 | browser_screenshot | core | browser_take_screenshot | OK |
| 19 | browser_snapshot | ext | browser_snapshot | OK (a11y snapshot) |
| 20 | browser_pdf | ext | browser_pdf_save | OK (behind `--caps pdf`) |
| 21 | browser_get_content | ext | - | minor: via browser_evaluate |
| 22 | browser_get_text | ext | - | minor: via browser_evaluate |
| 23 | browser_evaluate | ext | browser_evaluate | OK |
| 24 | browser_wait_for | ext | browser_wait_for | OK |
| 25 | browser_wait_for_navigation | ext | (auto-wait in actions) | folded into navigate |
| 26 | browser_console_messages | ext | browser_console_messages | OK |
| 27 | browser_get_attribute | ext | - | minor: via browser_evaluate |
| 28 | browser_query_selector_all | ext | - | minor: via browser_evaluate |
| 29 | health_check | core | - | infra tool, N/A upstream |

**Direct or unified map:** 18/29. **Reconstructable via `browser_evaluate`:** 6/29 (rows 16, 17, 21, 22,
27, 28). **True gap:** 5/29 session-lifecycle tools + 1 infra tool.

Upstream additionally ships a large surface CPP lacks and both consumers could use: cookie CRUD,
localStorage / sessionStorage CRUD, `browser_storage_state` / `browser_set_storage_state`, network
mocking (`browser_route*`), tracing, video, `browser_file_upload`, `browser_handle_dialog`,
`browser_generate_locator`, and mouse-xy control. Migration is a net capability GAIN outside named sessions.

### Consumer dependency check

- `/qa:test` (`.claude/commands/qa/test.md`): `create_session(...)` -> threads one `session_id` through
  `browser_*` -> `close_session`. A SINGLE session, never concurrent. Maps cleanly onto upstream's implicit
  single session by dropping the `session_id` argument.
- `/documentation:pptx`: no `create_session` / `session_id` / direct playwright tool references. PPTX render
  was already delegated to `anthropics/skills@pptx` in v7.2; Playwright is only a screenshot helper.

Neither consumer needs named CONCURRENT multi-session. The differentiating feature is currently unused.

## Task 3: storage-state save/restore + per-instance profile isolation

Upstream provides the full substrate for named-session multiplexing (verified against v0.0.77 `--help`):

- `--storage-state <path>` - load/persist cookies + origin storage per instance.
- `--user-data-dir <path>` - persistent per-instance profile on disk.
- `--isolated` - keep the profile in memory (ephemeral, no disk write).
- `--save-session`, `--shared-browser-context`, `--secrets <path>`, `--output-dir`, `--port`.
- Runtime tools `browser_storage_state` / `browser_set_storage_state` do the same in-session.

So "one isolated browser context per named session" = "one upstream instance per session, each with its own
`--port` + `--user-data-dir` (or `--isolated`)". CPP's model (N `browser.new_context()` inside ONE process,
keyed by an auto UUID; `mcp-playwright-persistent/src/server.py:196`) is lighter-weight per session but is
NOT user-named and is exactly what upstream replicates at the instance granularity.

## Task 4: mid-session MCP registration (KEY QUESTION) -> Design A vs B

**Empirical:** `claude mcp add --scope project <name>` writes `.mcp.json` instantly, but the server then
shows `Pending approval` and is not connected/exposed to the running session.

**Authoritative (docs, via claude-code-guide):**
- MCP config (`.mcp.json` / `~/.claude.json`) is read at session STARTUP only.
- `/mcp reconnect <server>` reconnects an already-known disconnected server; it does NOT load a
  newly-added server. There is no in-session "refresh config for new servers" action.
- Project-scope approval CAN be pre-granted non-interactively via `enableAllProjectMcpServers: true` or
  `enabledMcpjsonServers: [...]` in settings.json - but only for servers present at startup.

| Design | Description | Verdict |
|--------|-------------|---------|
| **A - static slot pool** | Pre-register N upstream instances at session start (`playwright-session-1..N`, each `--port`/`--user-data-dir`), pre-approved via `enableAllProjectMcpServers`; wrapper hands out slots by name. | **VIABLE** |
| **B - dynamic spawn per session** | Spawn a fresh upstream instance and register it mid-session, then use it immediately. | **NOT FEASIBLE** (startup-only config load; no in-session new-server load) |

**Recommendation: Design A.** If a wrapper is built, it must pre-register a fixed pool before the session
starts and route to slots in-conversation. Dynamic per-session spawn is a dead end in current Claude Code.

## Task 5: footprint + Woodpecker Trivy gate scope

Measured on this host (`docker history` / `docker image inspect`, image tag `31cbb9e`):

| Layer | Size |
|-------|------|
| `playwright install chromium` | 672 MB |
| Playwright apt runtime deps | 250 MB |
| Python venv (`/app/.venv`) | 209 MB |
| Debian trixie-slim base | ~140 MB |
| app + misc | < 1 MB |
| **On-disk uncompressed** | **~1.27 GB** (corroborated by the running container's `virtual 1.27GB`) |

- The review doc's "155 MB" is a stale/compressed figure; the deployed on-disk image is ~8x that.
- Retiring the custom image does NOT reclaim the Chromium payload: the host's upstream browser cache
  `~/.cache/ms-playwright` is already 1.3 GB. Chromium is irreducible whichever server we run.
- The genuine saving is MAINTENANCE surface. Today `.woodpecker.yml` runs the Trivy `image-security` gate
  over `mcp-playwright-persistent:$CPP_IMAGE_TAG` and hadolint over its Dockerfile - a recurring two-layer
  CVE tax (base digest bump + venv dep bump; see #406/#409). Moving to upstream's maintained image / npx
  transfers browser-binary CVE patching to Microsoft and removes CPP's Dockerfile from the gate.

## Recommendation to epic #417

1. **Proceed with #423 (migrate `/qa:test` + `/documentation:pptx` to upstream, single-session)** now: both
   consumers map cleanly, migration is a capability gain, and it retires our 823-LOC server, its Dockerfile,
   and its Trivy/hadolint gate scope.
2. **Named concurrent multi-session (#421 wrapper): defer / make optional.** It is currently unused by any
   CPP consumer. If ever built, it MUST be Design A (static pre-registered pool, pre-approved via
   `enableAllProjectMcpServers`). Prefer #422 (contribute named sessions upstream, playwright-mcp #1530) as
   the durable fix over carrying a local wrapper.
3. **Footprint framing:** justify retiring on maintenance surface (Dockerfile + Trivy gate), not image size.
