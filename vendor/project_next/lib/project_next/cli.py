"""Command-line interface for live and fixture-backed project-next runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .collect import CollectionError, collect_repository
from .config import ConfigError, load_config
from .models import RepositoryState
from .rank import recommend
from .render import render_result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic project-next recommendation engine")
    parser.add_argument("repository", nargs="?", default=".", help="repository path (default: current directory)")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--brief", action="store_const", const="brief", dest="mode")
    modes.add_argument("--compact", action="store_const", const="compact", dest="mode")
    modes.add_argument("--full", action="store_const", const="full", dest="mode")
    parser.add_argument("--json", action="store_true", help="emit the versioned structured result")
    parser.add_argument("--input", type=Path, help="read RepositoryState JSON instead of collecting live state")
    parser.add_argument("--config", type=Path, help="explicit .project-next.json path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repository = Path(args.repository).resolve()
    try:
        config = load_config(repository, args.config)
        if args.input:
            payload = json.loads(args.input.read_text(encoding="utf-8"))
            state = RepositoryState.from_dict(payload)
        else:
            state = collect_repository(repository, config)
    except (CollectionError, ConfigError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"project-next: {exc}", file=sys.stderr)
        return 2

    result = recommend(state, config)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_result(result, state, args.mode or config.default_mode))
    return 0 if result.inventory_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
