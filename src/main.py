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
        "--cli",
        action="store_true",
        help="Use the legacy stdin CLI instead of the TUI dashboard",
    )
    args = parser.parse_args()

    load_dotenv()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    config = load_config()
    pipeline = CapturePipeline(config, use_tui=not args.cli)
    asyncio.run(pipeline.run())


if __name__ == "__main__":
    main()
