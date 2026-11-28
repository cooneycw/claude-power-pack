# Held-old Codex input control runtime (#1967)

The held-old-input control deliberately makes two large bundled generator byte
strings differ. With `CI=true`, pytest builds a full iterable diff even though
`pytest.raises` catches the expected rejection. Formatting that diagnostic,
not proving rejection, dominated the CI-shaped runtime.

The equality is now computed into a boolean before asserting that boolean with
the same held-old diagnostic. The complete original test remains: three real
full-population builds, independent current and frozen transforms/parsers, exact
population, hashes and modes, and actual bundled bytes, under both umasks. The
negative still injects held-old input into the real positive function. No
focused-build shortcut, timeout, skip, generator, frozen source, runner or
selector-manifest change remains.

The negative additionally requires its caught rejection message to be shorter
than 256 characters. This is a diagnostic-size contract, not a timing threshold.

## Root-cause evidence

Baseline main is `3b8116df`. The first local cProfile run passed both parameters
in 7.92/7.95 seconds. Four tracked-input copies (17,788 files) consumed 4.577
seconds total; Git subprocesses consumed 0.018 seconds and output inventory
0.250 seconds. That local profile did not reproduce the CI environment.

The supplemental CI-shaped baseline did reproduce it:

| Checkout shape | Umask 022 | Umask 002 | Lane result |
| --- | ---: | ---: | --- |
| depth-1 | 54.75 s | 51.69 s | 252 passed, 6 named skips |
| depth-1, tree-filtered | 50.91 s | 47.87 s | 252 passed, 6 named skips |

A diagnostic-only focused build still took 45.08/44.50 seconds in the first
shape, showing that reducing generation alone missed the main cost. Profiling
inside that same real checkout, minimal PATH, private HOME, symlinked TMPDIR,
observed pytest umask and `CI=true` found 117.619 seconds in
`pytest_assertrepr_compare` / `_compare_eq_iterable` / `difflib._fancy_replace`.
The profiled test hit its 119.99-second timeout; it was not a passing run.
Copies took 0.168 seconds, Git 0.009 seconds and inventory 0.056 seconds in that
focused diagnostic profile. The final change retains the original full scope.

The local/CI gap is therefore measured and explained: pytest expands the
expected large-byte failure differently under CI. These measurements do not
claim to reproduce every possible agent load.

## Final validation

Before the boolean fix, adding only the new diagnostic-size assertion to the
original implementation and running umask 022 with `CI=true` produced the
expected RED: a 301,716-character rejection exceeded 256, in 48.91 seconds.

After the boolean fix, the complete parity module passed all 36 tests with
`CI=true -n 8` in 12.99 seconds. The held-old parameters took 6.46 seconds
(022) and 5.19 seconds (002), retaining their full original build scope.

Final supplemental CI-shaped measurements at implementation `c4a172bb`:

| Checkout shape | Umask 022 | Umask 002 | Lane result |
| --- | ---: | ---: | --- |
| depth-1 | 4.84 s | 4.95 s | 252 passed, 6 named skips |
| depth-1, tree-filtered | 5.23 s | 5.01 s | 252 passed, 6 named skips |

These are 8.8-10.5% of their corresponding baseline costs, or 9.6-11.3x
faster. The two lane suites completed in 210.18 and 217.47 seconds. Their
declared scope is the unchanged canonical #1917 selector set plus the exact
held-old negative test. The external measurement wrapper expands only the
duration display; shipping runner and manifest files remain unchanged. This
supplemental local-tier result does not establish the real-root pinned-image
lane, and is not an unmodified canonical-manifest receipt.

Main `5ca52214` was subsequently merged cleanly as `cfc69033`, without rebasing.
That merge changes the upstream CI-shape witness and its fixtures; it leaves
the measured parity-test bytes unchanged. The final review and direct gate
cover the merged head; these timing measurements bind the earlier `c4a172bb`
checkpoint explicitly.

Three independent mutations against the final implementation, each under
`CI=true`, produced two failing parameters and pytest exit 1:

1. Delete the inline positive-path rejection assertion. The negative then sees
   the later changed-member diagnostic instead of the required held-old one.
   This retains the call-site failure coverage required by review finding F1.
2. Force the equality boolean to true. Both parameters likewise reject the
   wrong later diagnostic, proving an accepting oracle makes the control red.
3. Copy the frozen baseline into an owned temporary directory and append a
   comment to its generator without updating the recorded SHA256. Both
   parameters fail the baseline digest check outside the rejection context.
   The committed frozen archive was not modified.

The mutation harness, profiler files, receipts and logs are retained in the
run's validation artifacts. The new diagnostic assertion was run red before
its fix; the committed held-old construction continues to supply the actual
known-bad input.

## Related sites outside this change

The suite scan found 130 lines matching direct `read_bytes()` equality shapes;
that is a textual candidate count, not an exhaustive call-graph verdict. The
known pre-fix rejection site above was present in the scan and exercised red.

Potential follow-ups include the large-source comparisons in
`tests/test_codex_skill_sync.py`: `test_real_repo_bundled_scripts_byte_identical`,
`test_real_repo_bundled_libraries_byte_identical`, and the frozen reconstruction
comparison in `_assert_only_retired_cpp_data_changed`. The first two format a
diff only on unexpected drift; the last currently rejects its deliberately bad
inputs using a bounded explicit raise before reaching the large comparison.
They are candidates for bounded failure diagnostics, not additional reproduced
timeouts. No changes to these sites are included. Recorded in the
[Nit Store](https://github.com/cooneycw/claude-power-pack/issues/1957#issuecomment-7229645228).

`test_bundled_generator_input_variation_is_measured[18,2]` retains its complete
three-build pattern. Other parity checks perform two full builds. These
measurement costs are unchanged and are not the diff-formatting defect fixed
here.
