#!/usr/bin/env python3
"""Drive the real writer API with owned inputs, including a late competing file."""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> int:
    gate, case = map(Path, sys.argv[1:])
    scenario = (case / "scenario.txt").read_text().strip()
    spec = importlib.util.spec_from_file_location("lib.cicd._makefile_write_control", gate)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="makefile-write-control-") as directory:
        root = Path(directory)
        (root / "package.json").write_text(json.dumps({"name": "owned-fixture"}))
        (root / "package-lock.json").write_text("{}")
        target = root / "Makefile"
        owner = root / "owner-file"
        sentinel = "# owner Makefile - preserve without force\n"
        force = scenario == "good-explicit-force"
        late = scenario == "bad-late-existing"
        if scenario in {"bad-existing", "good-explicit-force"}:
            target.write_text(sentinel)
            assert target.is_file() and target.read_text() == sentinel
        elif scenario in {"bad-symlink", "bad-dangling-symlink"}:
            if scenario == "bad-symlink":
                owner.write_text(sentinel)
            else:
                assert not owner.exists()
            target.symlink_to(owner.name)
            assert target.is_symlink()
        else:
            assert scenario in {"good-new-file", "bad-late-existing"}
            assert not target.exists()
        late_created = False
        if late:
            generate = module.generate_makefile

            def generate_then_compete(*args, **kwargs):
                nonlocal late_created
                content = generate(*args, **kwargs)
                assert not target.exists(), "late input must appear after the initial guard"
                target.write_text(sentinel)
                late_created = True
                return content

            module.generate_makefile = generate_then_compete
        try:
            module.write_makefile(root, force=force)
        except FileExistsError:
            assert not late or late_created
            if scenario in {"bad-existing", "bad-late-existing"}:
                assert target.read_text() == sentinel
            elif scenario == "bad-symlink":
                assert target.is_symlink() and owner.read_text() == sentinel
            elif scenario == "bad-dangling-symlink":
                assert target.is_symlink() and not owner.exists()
            else:
                raise AssertionError("refusal is not expected for an owned GOOD input") from None
            print("MAKEFILE_WRITE: refused-existing")
            return 1
        except OSError as exc:
            print(f"MAKEFILE_WRITE: UNKNOWN - {type(exc).__name__}")
            return 2
        assert not late or late_created
        assert target.is_file() and "npm test" in target.read_text()
        assert not list(root.glob(".cpp-makefile-*")), "staging must be cleaned"
        print("MAKEFILE_WRITE: wrote")
        return 0


if __name__ == "__main__":
    sys.exit(main())
