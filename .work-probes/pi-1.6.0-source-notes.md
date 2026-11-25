# Pi 1.6.0 project discovery precondition

Read from the published `@earendil-works/pi-coding-agent` 1.6.0 npm tarball,
with tarball SHA512 checked against the registry's integrity field:

`sha512-zX1BVEsshx7A2MRuQ6jfr3RJGWw4Wn+vLq5ZfmlvS1RskhRmByaSZVXH/zcwRrWHO7qPgs98pNCbPOEti/t0fQ==`

Source: <https://registry.npmjs.org/@earendil-works/pi-coding-agent/1.6.0>.
This is published package source, not an inspection of the host installation.

- `docs/configuration.md`: user resources use the agent directory, default
  `~/.pi/agent`; project resources use cwd `.pi` after project trust. `sessionDir`
  is the exception read before trust resolution.
- `docs/security.md`, "Project trust without an interactive prompt": RPC cannot
  show the trust prompt. With no other decision, global `defaultProjectTrust`
  `always` loads protected resources; `ask` (default) or `never` skips them.
- `docs/settings.md`: `defaultProjectTrust` is a global-only setting. Probe v2
  writes synthetic `always`/`never` settings exclusively in its throwaway agent
  directory, never the real owner's settings.
- `docs/skills.md`: skill directories are recursive; duplicate names keep the
  first discovered skill and produce a warning. No Git prerequisite is stated
  for cwd `.pi/skills`. Ancestor `.agents/skills` discovery has a separate Git-root
  boundary and must not be confused with cwd `.pi/skills`.
- `dist/core/package-manager.js`, `collectAutoResources`: project `.pi/skills`
  enumeration is guarded by `settingsManager.isProjectTrusted()`; user
  `<agent>/skills` enumeration is not guarded by that project condition.
- `dist/core/skills.js`: recursive enumeration skips dot-prefixed entries, but
  the actual resource resolver must still be measured with the hidden ownership
  directory fixture. Source reading does not replace that measurement.

Batch 1 v1's missing project skill under fresh RPC defaults is consistent with
this trust contract. It does not establish that Git initialization is needed.
V2 separates global discovery, hidden layout, explicit paths, project trust, and
collision observations. Each section emits its own outcome and a failing section
does not prevent subsequent independent sections from running. The final exit
still fails if any section is unresolved. No model turn is sent.
