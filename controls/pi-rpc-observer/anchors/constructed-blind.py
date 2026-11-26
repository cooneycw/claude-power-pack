"""Constructed shape-only reader: ignores semantic membership/diagnostics/tools."""
import argparse
import json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-rpc")
    args = parser.parse_args()
    try:
        value = json.load(open(args.read_rpc))
        for label in ("baseline", "installed"):
            rows = [json.loads(s) for s in value[label]["stdout"].split("\n") if s]
            if len([r for r in rows if r.get("id") == "commands"]) != 1:
                raise ValueError("ambiguous response")
        if value["tools"] is None:
            raise ValueError("inventory unavailable")
    except (ValueError, KeyError, TypeError):
        print("PI_RPC: unknown")
        return 4
    print("PI_RPC: matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
