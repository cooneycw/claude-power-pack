A bundle (`bundle-1/`) whose ledger plans `attempt_id: "att-1"` twice -
unique-ids (skillc records.md:891-898, pinned 2202603): "no trial or attempt
ID is planned twice." Copied VERBATIM from skillc
`controls/unique-ids/bad/duplicate-attempt/` at commit `2202603` - the same
copy registered for conformance at
`controls/behavioral-eval/skillc-conformance/unique-ids/bad/duplicate-attempt/`.
Closes the gap raised by cpp-orch 2026-10-06: "duplicate/missing attempt"
from #1369's plan (section 4) needed its own registered ADR 0008 case, not
only a `tests/test_behavioral_eval.py` unit test
(`test_duplicate_planned_attempt_id_is_refused`).
