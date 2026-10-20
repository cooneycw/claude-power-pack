# NEGATIVE-CONTROL: controls/toy
import subprocess

subprocess.run(["jq", "--version"], check=True)
