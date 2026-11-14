# Bootstrap wrapper review (#1803)

## Scope and result

Four semantic reviews of the full canonical diff against main
`bcd0f3ed967ba997eb6958835f3610fc7c41a561` ran with
`codex/gpt-6.1-terra`, independently measured from implementing runtime
`codex/gpt-6.1-sol`. Scope was diff-only; repository sandbox execution and the
pinned CI image were not claimed. Network and local-credential reach were
unverified. The last semantic review reported no defects on implementation
`bb9f33795e6b4b345bec96437161950a090ddd3a`.

Three findings were accepted and fixed; none was rejected or deferred:

1. Inherited `PYTHONPATH` could substitute a regular `lib` package and a
   checker returning success. CPP's search path now excludes inherited entries.
   The regression failed on `3bbf585d`; the old wrapper accepted an owned unmet
   blocker through the substitute. The corrected wrapper rejects that blocker.
2. An installed regular `lib` package still beat CPP's namespace package.
   The wrapper now executes its exact checker file. The installed-package case
   failed on `688fe5f3` by accepting an unmet blocker; the corrected wrapper
   reports BAD. A disposable no-pip venv owns the installed lure; CPP's project
   environment is untouched. AST and directory pins protect standalone launch:
   adding `import lib.cicd` and a stdlib-named `subprocess.py` in temporary
   copies makes the respective checks fail.
3. The missing-PyYAML control input returned before running its candidate.
   It now verifies real `-S` import failure and executes the candidate anyway.
   Before the correction, an always-success candidate was automatically scored
   UNKNOWN and incorrectly satisfied that case. Afterward it is observed GOOD,
   contradicting expected UNKNOWN. The real wrapper still produces UNKNOWN.

The first report used a P1 label my prompt permitted; the receipt parser could
not parse that shape. Its finding was retained and fixed, never treated as a
clean result. The fourth report said no findings; two report-only follow-ups
corrected the parser's clean sentinel and captured-input framing without a
fifth semantic review. Both original and corrected runtime reports are retained
locally. The final receipt binds the unchanged canonical patch and last runtime
report; its pass count is four, and its accepted count is three.

## Review cap

The review coordinator authorized a third pass after the installed-package
finding and explicitly raised this run's cap to four after the missing-PyYAML
finding. The fourth-pass ruling was recorded in coordination message 25016 on
2026-11-14: fix approved, pass four approved, cap four; stop on a further HIGH
or MEDIUM. The extra-pass reason in the receipt records both triggers. This
records the ruling, rather than asserting that the receipt authenticates it.

## Validation

- 361 focused tests passed. Test-only admission isolation avoids the existing
  host-admission fixture coupling recorded separately in the Nit Store.
- The strict provenance-aware bootstrap control passed: five BAD inputs, five
  GOOD inputs, two UNKNOWN inputs. Its list-only anchor missed all five BAD
  inputs and agreed on GOOD inputs.
- Lint, typecheck, binary guards, negative-fixture guards and CI dependency
  accounting passed. The actual pinned CI image was unavailable locally.
- Isolated uv provisioning passed from a parent Python without PyYAML and a
  prepared parent. The project venv fingerprint was equal before and after.
  Cold-cache offline provisioning failed; warm-cache offline controls passed.
- PyYAML supplied only through inherited `PYTHONPATH` is deliberately ignored:
  the old `3bbf585d` wrapper listed successfully; clearing the variable produces
  exit 1 with missing `yaml`. This is documented, not a new wrapper setup code.

No full suite, finish gate, PR, or merge was run here. The branch receipt is a
record of review and artifact binding, not a substitute for those checks.
