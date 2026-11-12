# `lane-file` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `lane-file` (#1696)

- lane-file `age` reads the `Reviewed: YYYY-MM-DD` line inside `.claude/lanes.md` and prints `LANE_FILE_AGE: fresh | stale | unknown | absent` as its last line. `/flow:eli5` relays a stale or unknown line at plan time; `/lane:create` and `/lane:update` read it first. The rule it serves is [the lanes reference](../agents/lanes.md).
- lane-file IS AN ADVISORY, NOT A GATE. Exit 0 is fresh or absent, 3 is stale, 4 is unknown. A caller relays the line and continues on every code; the codes let a script tell the states apart. It is not in `make verify`.
- lane-file SAYS `absent` ONLY WHEN THE PATH IS ESTABLISHED NOT TO EXIST. A file with no date, an impossible, future or disagreeing date, an unreadable file, a directory, a dangling symlink or an unsearchable `.claude` directory is `unknown`: a project that adopted lanes and whose list nobody can date. The review hand-over in `/codex:code_review` (#1695) reads the last two as absent; that gap is in the Nit Store and was not repeated here.
- lane-file TAKES THE AGE FROM THE DATE IN THE FILE, never from modification time or git history. A typo fix must not make the list look reviewed, and a fresh clone must not make it look new.
- lane-file `stamp` sets the one `Reviewed:` line to today and changes nothing else. It refuses when there is no lane file, when the path is not a regular file, and when it is a symlink. It writes through a temporary file in the same directory and keeps the file's mode.
- lane-file RESOLVES THE CHECKOUT ROOT from the current directory, so a run from a subdirectory or a linked worktree reads that tree's own file; `LANE_FILE_ROOT:` says whether git, the current directory or `--root` chose it.
- The default threshold is 60 days (`--threshold-days`). `--today` pins the date so `controls/lane-file-age` does not move with the calendar: 61 days is flagged, exactly 60 is not, and an undated file is unknown. The control's blind anchor is the weaker check "the project has a lane file".
- A FRESH DATE DOES NOT MEAN A COMPLETE LIST. The date records that somebody read the list. The stronger signal is the growth rule: a miss that turns out to be an unlisted lane adds the lane.
