# `measurement-shape-scan` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `measurement-shape-scan`

- measurement-shape-scan - transcript detector for the #659 cwd-relative measurement trap (#666): stdlib-only scan of a recorded session transcript flagging `git diff|show|log ... -- <relative-pathspec>` reads with no `-C` anchor (warn) and ref-less working-tree `git grep` (info, heuristic); consumed by `/self-improvement:retro` replay mode, which folds warn findings in as red-output signals - the retro-side complement to the census hook, which cannot see the shape because an allowlisted read-only git command never shows a permission dialog. Findings are advisory (a transcript cannot prove the cwd; a relative pathspec from a verified root is legitimate - the documented false-positive guard); marker `MEASUREMENT_SHAPES: <n>`, exit 0 = scan ran, exit 2 = unreadable transcript
