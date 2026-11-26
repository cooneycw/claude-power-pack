"""Fixture-only tool delivery across the owner helpers' sanitized environment."""

import shutil
import subprocess
import tarfile


def fixture_source(root, path):
    """A real CLI source repo made from HEAD, with no historical-object need."""
    path.mkdir()
    archive = path.parent / "source.tar"
    with archive.open("wb") as stream:
        subprocess.run(["git", "-C", str(root), "archive", "HEAD"], stdout=stream, check=True)
    with tarfile.open(archive) as tree:
        # Control fixtures include deliberately absolute dangling symlinks.
        # They are not part of the topic builder's source/reference closure.
        members = (row for row in tree if row.name != "controls" and not row.name.startswith("controls/"))
        tree.extractall(path, members=members, filter="data")
    archive.unlink()
    subprocess.run(["git", "init", "--quiet", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "add", "--force", "."], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=Owner fixture",
                    "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
                    "commit", "--quiet", "-m", "Synthetic owner fixture source"], check=True)
    return path


class FixtureSubprocess:
    """Keep the helper's environment, adding only fixture-selected Git/Make."""

    def __init__(self, tool_dir):
        self.tool_dir = tool_dir

    def __getattr__(self, name):
        return getattr(subprocess, name)

    def _kwargs(self, kwargs):
        if kwargs.get("env") is not None:
            kwargs = dict(kwargs)
            env = dict(kwargs["env"])
            # No system Git/Make fallback: the complete fixture suite exercises
            # the staged-only layout even on a developer box with /usr/bin/git.
            env["PATH"] = str(self.tool_dir)
            kwargs["env"] = env
        return kwargs

    def run(self, *args, **kwargs):
        return subprocess.run(*args, **self._kwargs(kwargs))

    def check_output(self, *args, **kwargs):
        return subprocess.check_output(*args, **self._kwargs(kwargs))


def fixture_subprocess(tmp_path):
    """CI stages these outside /usr/bin; never inherit the whole test PATH."""
    tool_dir = tmp_path / "fixture-tools"
    tool_dir.mkdir()
    for name in ("git", "make", "python3"):
        binary = shutil.which(name)
        assert binary is not None, f"fixture requires {name}"
        (tool_dir / name).symlink_to(binary)
    return FixtureSubprocess(tool_dir)
