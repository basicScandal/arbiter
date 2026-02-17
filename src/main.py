"""Entry point for the Arbiter capture layer.

Loads environment configuration and runs the full capture pipeline.
Supports --cli flag to fall back to the original stdin-based operator CLI.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from dotenv import load_dotenv

from src.capture.config import load_config
from src.capture.pipeline import CapturePipeline


def main() -> None:
    """Load config from environment, create pipeline, and run."""
    parser = argparse.ArgumentParser(description="Arbiter — Live AI hackathon judge")
    parser.add_argument(
        "--operator",
        choices=["web", "cli", "tui"],
        default="web",
        help="Operator interface mode (default: web)",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Shorthand for --operator cli",
    )
    parser.add_argument(
        "--rehearsal",
        action="store_true",
        help="Run a full demo rehearsal with synthetic data (no hardware or API keys needed)",
    )
    args = parser.parse_args()

    # Rehearsal mode: run full pipeline with synthetic data, no env/config needed
    if args.rehearsal:
        from src.rehearsal import RehearsalPipeline

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        print("=" * 50)
        print("  Arbiter Rehearsal Mode")
        print("  Running full demo cycle with synthetic data...")
        print("=" * 50)
        print()
        pipeline = RehearsalPipeline()
        asyncio.run(pipeline.run_demo())
        print()
        print("Rehearsal complete!")
        return

    load_dotenv()

    # Configure logging — attach FileHandler directly to root logger.
    # Cannot use basicConfig() because library imports may have already
    # configured root, making basicConfig a silent no-op.
    log_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    file_handler = logging.FileHandler("/tmp/arbiter.log", mode="w")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    config = load_config()
    operator_mode = "cli" if args.cli else args.operator
    pipeline = CapturePipeline(config, operator_mode=operator_mode)
    asyncio.run(pipeline.run())


if __name__ == "__main__":
    main()
