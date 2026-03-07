#!/usr/bin/env bash
# Run all frontend test suites (operator-dashboard + audience-display)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Operator Dashboard Tests ==="
cd "$ROOT/operator-dashboard" && bun run test

echo ""
echo "=== Audience Display Tests ==="
cd "$ROOT/audience-display" && bun run test

echo ""
echo "All frontend tests passed."
