"""CLI entry point: uv run python -m src.replay"""

from __future__ import annotations

import argparse
import asyncio
import sys

from src.replay.pipeline import ReplayPipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay NEBULA:FOG:PRIME demo videos through Arbiter's scoring pipeline",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Use cached videos instead of downloading",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="Resume from video number N (1-indexed)",
    )
    parser.add_argument(
        "--only",
        type=int,
        default=None,
        help="Process only video number N",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process all demos even if cached results exist",
    )
    args = parser.parse_args()

    try:
        pipeline = ReplayPipeline()
        asyncio.run(pipeline.run(
            skip_download=args.skip_download,
            start=args.start,
            only=args.only,
            force=args.force,
        ))
    except KeyboardInterrupt:
        print("\nInterrupted. Progress is saved — resume with --start N.")
        sys.exit(130)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
