"""Own disposable collision inputs; compare bytes/types independently of status."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def inventory(root):
    result = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = Path(parent) / name
            result[str(p.relative_to(root))] = (("link", os.readlink(p)) if p.is_symlink() else
                                               ("dir",) if p.is_dir() else ("file", p.read_bytes()))
    return result


def main():
    gate, case = map(Path, sys.argv[1:3])
    if not shutil.which("bash"):
        print("cpp-host-write: UNAVAILABLE - bash missing")
        return 3
    scenario = json.loads((case / "case.json").read_text())["scenario"]
    with tempfile.TemporaryDirectory(prefix="cpp-preserve-") as temporary:
        base = Path(temporary)
        source = base / "source.sh"
        source.write_bytes(b"CPP source A")
        source.chmod(0o755)
        home = base / "home"
        home.mkdir()
        root = home / ".claude/scripts"
        leaf = root / source.name
        env = dict(os.environ, HOME=str(home), CPP_DEFER_SURFACES="")

        def invoke():
            return subprocess.run(["bash", str(gate), "link-into", str(source), str(root), leaf.name],
                                  env=env, capture_output=True, text=True, timeout=15)

        if scenario.startswith("bad-"):
            root.mkdir(parents=True)
            if scenario == "bad-regular":
                leaf.write_bytes(b"personal irreplaceable bytes")
                assert leaf.is_file() and not leaf.is_symlink()
            else:
                assert scenario == "bad-directory"
                leaf.mkdir()
                (leaf / "personal").write_bytes(b"personal nested bytes")
                assert leaf.is_dir() and not leaf.is_symlink()
            before = inventory(home)
            result = invoke()
            if result.returncode != 0 and inventory(home) != before:
                print("CONTROL_ORACLE: a claimed refusal changed personal contents")
                return 9
            # The historical helper returns0 and actually mutates these BAD
            # inputs. Retain that success as its demonstrated missed refusal.
            results, code = (result,), result.returncode
        else:
            assert scenario == "good-links"
            assert not root.exists()
            absent = invoke()
            assert absent.returncode == 0 and leaf.is_symlink() and leaf.readlink() == source
            before = inventory(home)
            source.write_bytes(b"CPP source B")
            existing = invoke()
            assert existing.returncode == 0 and inventory(home) == before and leaf.read_bytes() == b"CPP source B"
            leaf.unlink()
            foreign = base / "personal"
            foreign.write_bytes(b"personal link target")
            leaf.symlink_to(foreign)
            assert leaf.is_symlink() and leaf.readlink() != source
            before = inventory(home)
            unchanged = invoke()
            assert unchanged.returncode == 0 and inventory(home) == before
            assert foreign.read_bytes() == b"personal link target"
            results, code = (absent, existing, unchanged), 0
    for result in results:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
