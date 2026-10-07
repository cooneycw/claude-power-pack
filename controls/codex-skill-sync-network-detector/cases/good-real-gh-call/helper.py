import subprocess


def example() -> None:
    subprocess.run(["gh", "issue", "list"])
