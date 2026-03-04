#!/usr/bin/env bash
# Run all frontend test suites (operator-dashboard + audience-display)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Operator Dashboard Tests ==="
cd "$ROOT/operator-dashboard" && npx vitest run

echo ""
echo "=== Audience Display Tests ==="
cd "$ROOT/audience-display" && npx vitest run

echo ""
echo "All frontend tests passed."
