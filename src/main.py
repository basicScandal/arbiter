"""Entry point for the Arbiter capture layer.

Loads environment configuration and runs the full capture pipeline.
"""

from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv

from src.capture.config import load_config
from src.capture.pipeline import CapturePipeline


def main() -> None:
    """Load config from environment, create pipeline, and run."""
    load_dotenv()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    config = load_config()
    pipeline = CapturePipeline(config)
    asyncio.run(pipeline.run())


if __name__ == "__main__":
    main()
