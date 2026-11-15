import argparse

p = argparse.ArgumentParser()
p.add_argument("--json", action="store_true")
for name in ("repo", "harness"):
    p.add_argument("--" + name)
