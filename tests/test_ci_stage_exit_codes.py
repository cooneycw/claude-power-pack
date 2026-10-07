"""The three CI stagers distinguish "could not fetch" from "fetched, wrong bytes" (issue #1411).

`ci-stage-jq.py`, `ci-stage-git.py` and `ci-stage-make.py` all download pinned
content over HTTPS and all three used to `return 1` identically whether the
download failed outright (a network transient) or succeeded with the wrong
bytes (a sha256/scheme mismatch - a real, code-adjacent finding). That made
`scripts/flow-ci-status.sh` unable to tell a `jq-stage` network blip from an
actual regression without a step-name allowlist, which #1342 deliberately
declined to grow into one.

Each stager now returns `EX_FETCH_FAILED` (75, BSD sysexits.h's EX_TEMPFAIL)
for the fetch failure specifically, and keeps `1` for everything downstream of
a successful fetch - sha256 mismatch, a scheme-downgrade redirect, extraction,
or the staged binary not running. `flow-ci-status.sh` reads exit 75 to
classify a failed step as pre-code regardless of its name or Woodpecker step
type (`controls/flow-ci-status` and `tests/test_flow_ci_status.py` pin that
half).

NO NETWORK HERE, matching `test_ci_stage_make.py`'s own stated reason: a test
that fetched real bytes would test an external host's availability, not this
script. Each module's own opener/fetch call is monkeypatched to fail in a
controlled way.
"""

from __future__ import annotations

import re
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
STAGERS = {
    "ci-stage-jq.py": "ci_stage_jq",
    "ci-stage-git.py": "ci_stage_git",
    "ci-stage-make.py": "ci_stage_make",
}


def _stager(filename: str, module_name: str) -> ModuleType:
    spec = spec_from_file_location(module_name, ROOT / "scripts" / filename)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("filename, module_name", STAGERS.items(), ids=STAGERS.keys())
def test_all_three_stagers_agree_on_the_same_exit_code(filename, module_name) -> None:
    module = _stager(filename, module_name)
    assert module.EX_FETCH_FAILED == 75, (
        f"{filename} defines EX_FETCH_FAILED = {module.EX_FETCH_FAILED}, "
        "not 75 - the shared convention flow-ci-status.sh reads"
    )


class _BoomOpener:
    def open(self, *_args, **_kwargs):
        raise TimeoutError("simulated network timeout")


def test_jq_stager_returns_EX_FETCH_FAILED_on_a_download_failure(
    tmp_path, monkeypatch
) -> None:
    module = _stager("ci-stage-jq.py", "ci_stage_jq_fetchfail")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "_HTTPS_ONLY_OPENER", _BoomOpener())
    assert module.main() == 75


def test_jq_stager_keeps_exit_1_on_a_sha256_mismatch(tmp_path, monkeypatch) -> None:
    module = _stager("ci-stage-jq.py", "ci_stage_jq_mismatch")
    monkeypatch.chdir(tmp_path)

    class _WrongBytesOpener:
        def open(self, *_args, **_kwargs):
            class _Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *_exc):
                    return False

                def read(self):
                    return b"not jq"

            return _Resp()

    monkeypatch.setattr(module, "_HTTPS_ONLY_OPENER", _WrongBytesOpener())
    assert module.main() == 1


def test_make_stager_returns_EX_FETCH_FAILED_on_a_download_failure(
    tmp_path, monkeypatch
) -> None:
    module = _stager("ci-stage-make.py", "ci_stage_make_fetchfail")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "_HTTPS_ONLY_OPENER", _BoomOpener())
    assert module.main() == 75


def test_git_stager_returns_EX_FETCH_FAILED_on_a_download_failure(
    tmp_path, monkeypatch
) -> None:
    module = _stager("ci-stage-git.py", "ci_stage_git_fetchfail")
    monkeypatch.chdir(tmp_path)

    def _boom(_url: str) -> bytes:
        raise TimeoutError("simulated network timeout")

    monkeypatch.setattr(module, "_fetch", _boom)
    assert module.main() == 75


def test_git_stager_keeps_exit_1_on_a_sha256_mismatch(tmp_path, monkeypatch) -> None:
    module = _stager("ci-stage-git.py", "ci_stage_git_mismatch")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "_fetch", lambda _url: b"wrong bytes")
    assert module.main() == 1


EX_FETCH_FAILED_DOC = re.compile(r"EX_TEMPFAIL", re.IGNORECASE)


@pytest.mark.parametrize("filename", STAGERS.keys())
def test_each_stager_documents_the_sysexits_provenance(filename) -> None:
    text = (ROOT / "scripts" / filename).read_text(encoding="utf-8")
    assert EX_FETCH_FAILED_DOC.search(text), (
        f"{filename} defines EX_FETCH_FAILED without citing sysexits.h's EX_TEMPFAIL - "
        "the value must read as an established convention, not an invented one"
    )
