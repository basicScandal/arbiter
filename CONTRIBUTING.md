# Contributing to Arbiter

Thanks for your interest in contributing! Arbiter is the AI judge agent that powered NEBULA:FOG 2026. Here's how to get involved.

## Getting Started

1. Fork the repo and clone it locally
2. Run `uv sync` to install dependencies
3. Copy `.env.example` to `.env` and add your API keys
4. Run `uv run pytest` to verify everything works (1393 tests)
5. Run `uv run python -m src.main --rehearsal` to see the full pipeline in action without hardware

## Development

```bash
# Run tests
uv run pytest

# Run specific test file
uv run pytest tests/test_commentary_full_delivery.py -v

# Run smoke tests (fast)
uv run pytest -m smoke

# Start in rehearsal mode (no hardware needed)
uv run python -m src.main --rehearsal
```

## What to Work On

- **Issues labeled `good first issue`** are a great starting point
- Check the [discussions](https://github.com/basicScandal/arbiter/discussions) for ideas
- If you're planning something big, open an issue first to discuss

## Pull Request Process

1. Create a branch from `main`
2. Write tests for new functionality
3. Run `uv run pytest` and make sure all tests pass
4. Keep PRs focused — one feature or fix per PR
5. Write a clear commit message describing the "why"

## Code Style

- Python: follow existing patterns in the codebase
- TypeScript: standard React/Vite conventions
- Tests: use pytest with async support, mock external APIs
- No need for perfect code — working and tested beats polished and theoretical

## Architecture Notes

The codebase follows an event-driven architecture with an `EventBus` at the center. Key patterns:

- **Event Bus** — pub/sub with `asyncio.create_task` dispatch
- **Pipeline pattern** — each module subscribes to events and publishes results
- **Graceful degradation** — every external dependency has a fallback chain
- **Dual-LLM privilege separation** — quarantined observation vs. privileged judging

## Questions?

Open a [discussion](https://github.com/basicScandal/arbiter/discussions) or reach out at [nebulafog.ai](https://nebulafog.ai).
