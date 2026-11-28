"""Constructed CI consumer accepts the producer without CI admission checks."""
import argparse
from pathlib import Path
from lib.ci_shape_check import image_pin, run
ROOT = Path(__file__).resolve().parents[3]
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ci"])
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    record = run(ROOT, "image", args.receipt, inside_image=image_pin(ROOT))
    print("CI_SHAPE: " + record["state"] + ": controlled blind consumer")
    return 0
