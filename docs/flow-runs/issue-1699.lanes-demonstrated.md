# Lanes demonstrated - issue #1699

The approved plan answered `Lanes: none`: version strings and documents only.
One reader of the changed version strings was named as tested, and is recorded
here.

| Lane | What was demonstrated |
|---|---|
| Reader: scripts/check-version-consistency.py (`make version-consistency-check`) | With every location at 11.0.0 it reads `ok - 5 location(s) agree with 11.0.0, including uv.lock's own entry`, exit 0. With one location put back to 10.2.0 it exits non-zero and names that location, three times over: `CLAUDE.md: "Current version:": 10.2.0`; `README.md: bold release banner: 10.2.0`; `uv.lock: [[package]] claude-power-pack: 10.2.0`. The location count is 5 before and after. |
| Reader: Kyle's check that its pin, bundled CPP and documents name the released version (kyle #2348) | NOT demonstrated here. It is Kyle's to run on re-pin. |

## The documentation sweep

A search of `README.md`, `CLAUDE.md`, `docs/` and `.claude/commands/` (dated
records, decisions and per-script histories excluded) for the names the series
removed: the `lib.cicd resume` command, `resume_run`, the `rerun_failed`
keyword, and text calling `codex/skills/` committed or tracked.

- The search can hit: a planted line naming the removed command was found.
- On the last release (v10.2.0): one hit, `docs/cicd-resume-state-protocol.md`,
  which #1773 itself corrected.
- On this branch: one hit, the release note in `README.md` saying the command
  is removed.

So the series' own pull requests had already corrected the documents; this
change found nothing further to correct for removed names. What it added is
what the series added and the README did not say: the lane and monthly
commands.
