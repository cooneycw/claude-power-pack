# `bootstrap-check` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `bootstrap-check`

- bootstrap-check - thin wrapper over the Python bootstrap checker, run before a deploy. Projects declare dependencies in `.claude/bootstrap.yaml`; BLOCKING checks must exit 0 for the deploy to proceed while advisory findings are reported and never block, and the exit codes keep the two apart (1 for an unsatisfied blocking prerequisite, 2 for usage error)

## Launch and target contract (#1803)

The shell wrapper checks its own CPP checkout: `.claude/bootstrap.yaml` is read
there and configured check commands run there. A configuration in the caller's
working directory is not the target. `--list` executes no dependency commands.
The Python import root is the parent of `lib/`, so the same wrapper can be
invoked from outside CPP without relying on the caller's cwd for `lib.cicd`.
Python starts in CPP's root, so caller-local packages such as `lib` and `yaml`
do not shadow the checker or its dependencies. An unset or empty `PYTHONPATH`
does not add an empty search-path entry.

The interpreter remains ambient `python3` on PATH, with CPP's declared PyYAML
runtime dependency. This fix neither selects CPP's virtualenv nor provisions or
repairs an environment. Missing Python/modules still fail as before; runtime
selection and a distinct setup-error contract are a separate decision.

`make bootstrap-check` calls this wrapper. The runner's deploy plan calls
`python3 -m lib.cicd.bootstrap check` directly, using its project-root contract;
fixing the wrapper does not retarget that plan. The committed
`controls/bootstrap-wrapper` exercises the real wrapper and current Python
checker on owned configurations. A failed blocking dependency is BAD, a
satisfied one is GOOD, and unavailable imports/PyYAML are named unavailable,
never clean. Its constructed blind anchor lists rather than checks, so it
misses the unmet blocking dependency. No fake checker or YAML parser is used.
