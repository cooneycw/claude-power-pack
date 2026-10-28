"""Unit isolation for historical identity/count/filename CLI tests.

Those cases predate artifact binding and deliberately use tiny identity-only
transcripts and fictitious git heads. Stub ONLY that independent boundary;
test_counter_model_adapters.py exercises the unmodified shipping CLI against
real owned git repositories and captured-artifact evidence. This helper is
never installed or used by a gate.
"""

import hashlib
import importlib.util
from pathlib import Path

script = Path(__file__).resolve().parents[3] / "scripts/counter-model-receipt.py"
spec = importlib.util.spec_from_file_location("identity_cli", script)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def isolated_artifact(args, evidence, records):
    head, _ = module._derive_head(args.head)
    args.head = (head or "f" * 40).ljust(40, "0")
    return {
        "target_head": args.head,
        "base_sha": "b" * 40,
        "merge_base": "b" * 40,
        "patch_sha256": hashlib.sha256(b"isolated unit boundary").hexdigest(),
        "report_record": 1,
        "method": "runtime-head" if args.scope == "full" else "captured-patch",
    }


module._artifact_binding = isolated_artifact
raise SystemExit(module.main())
