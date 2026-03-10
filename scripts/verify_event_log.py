#!/usr/bin/env python3
"""Post-event verification — validates JSONL event log integrity and completeness.

Parses the event log and checks for:
- Structural integrity (valid JSON on every line)
- Demo lifecycle completeness (every start has a matching stop)
- Scoring completeness (every stopped demo has a scoring outcome)
- Timeline consistency (timestamps monotonically increasing)
- Data presence (observations, commentary, scores exist)

Usage:
    uv run python scripts/verify_event_log.py [path/to/events.jsonl]
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"

results: list[tuple[str, bool, str]] = []


def report(name: str, passed: bool, detail: str = ""):
    tag = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  {tag} {name}")
    if detail:
        print(f"       {DIM}{detail}{RESET}")
    results.append((name, passed, detail))


def main():
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/events.jsonl")

    print(f"\n{BOLD}{'='*50}")
    print("  ARBITER Event Log Verification")
    print(f"{'='*50}{RESET}")
    print(f"\n  Log: {log_path}\n")

    if not log_path.exists():
        report("Log file exists", False, f"{log_path} not found")
        _summary()
        return

    report("Log file exists", True, f"{log_path.stat().st_size:,} bytes")

    # Parse all lines
    print(f"\n{BOLD}Structural Integrity{RESET}")
    events: list[dict] = []
    malformed = 0
    with open(log_path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                malformed += 1
                if malformed <= 3:
                    print(f"       {RED}Line {i}: invalid JSON{RESET}")

    report("Valid JSON lines", malformed == 0, f"{len(events)} valid, {malformed} malformed")

    if not events:
        report("Events present", False, "log is empty")
        _summary()
        return

    report("Events present", True, f"{len(events)} total events")

    # Event type distribution
    print(f"\n{BOLD}Event Distribution{RESET}")
    type_counts = Counter(e.get("event_type", "unknown") for e in events)
    for etype, count in type_counts.most_common():
        print(f"       {DIM}{etype}: {count}{RESET}")

    # Timeline consistency
    print(f"\n{BOLD}Timeline{RESET}")
    timestamps = [e.get("logged_at", 0) for e in events if "logged_at" in e]
    if timestamps:
        out_of_order = sum(
            1 for i in range(1, len(timestamps)) if timestamps[i] < timestamps[i - 1]
        )
        report(
            "Timestamps monotonic",
            out_of_order == 0,
            f"{out_of_order} out-of-order entries" if out_of_order else "all in order",
        )

        from datetime import datetime, timezone

        first = datetime.fromtimestamp(timestamps[0], tz=timezone.utc)
        last = datetime.fromtimestamp(timestamps[-1], tz=timezone.utc)
        duration = timestamps[-1] - timestamps[0]
        report(
            "Time span",
            True,
            f"{first:%H:%M:%S} → {last:%H:%M:%S} ({duration:.0f}s / {duration/60:.1f}min)",
        )

    # Demo lifecycle
    print(f"\n{BOLD}Demo Lifecycle{RESET}")
    starts = [e for e in events if e.get("event_type") == "demo_started"]
    stops = [e for e in events if e.get("event_type") == "demo_stopped"]
    report(
        "Demo start/stop pairing",
        len(starts) == len(stops),
        f"{len(starts)} starts, {len(stops)} stops",
    )

    started_teams = [e.get("team_name", "?") for e in starts]
    stopped_teams = [e.get("team_name", "?") for e in stops]
    report(
        "All demos completed",
        set(started_teams) == set(stopped_teams),
        f"teams: {', '.join(set(started_teams)) or 'none'}",
    )

    # Scoring completeness
    print(f"\n{BOLD}Scoring{RESET}")
    scored = [e for e in events if e.get("event_type") == "scoring_complete"]
    failed = [e for e in events if e.get("event_type") == "scoring_failed"]
    scored_teams = {
        e.get("scorecard", {}).get("team_name") or e.get("team_name") for e in scored
    }
    failed_teams = {e.get("team_name") for e in failed}

    report(
        "Scoring outcomes",
        True,
        f"{len(scored)} scored, {len(failed)} failed",
    )

    unscored = set(stopped_teams) - scored_teams - failed_teams
    report(
        "All demos have scoring outcome",
        len(unscored) == 0,
        f"missing: {', '.join(unscored)}" if unscored else "all accounted for",
    )

    if scored:
        scores = []
        for e in scored:
            sc = e.get("scorecard", {})
            total = sc.get("total_score")
            if total is not None:
                scores.append((sc.get("team_name", "?"), total))
        if scores:
            print(f"\n  {BOLD}Scores:{RESET}")
            for team, score in sorted(scores, key=lambda x: x[1], reverse=True):
                print(f"       {team}: {score:.1f}/10")

    # Commentary and observations
    print(f"\n{BOLD}Pipeline Events{RESET}")
    obs = type_counts.get("observation_verified", 0)
    commentary = type_counts.get("commentary_delivered", 0)
    injections = type_counts.get("injection_detected", 0)
    report("Observations verified", obs > 0, f"{obs} verified")
    report("Commentary delivered", commentary > 0, f"{commentary} delivered")
    report(
        "Injection attempts",
        True,
        f"{injections} detected" if injections else "none detected",
    )

    _summary()


def _summary():
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = [(n, d) for n, ok, d in results if not ok]

    print(f"\n{BOLD}{'='*50}")
    print(f"  Results: {passed}/{total} passed")
    if failed:
        print(f"  {RED}FAILURES: {len(failed)}{RESET}")
        for name, _ in failed:
            print(f"    - {name}")
    else:
        print(f"  {GREEN}ALL CHECKS PASSED — event log is healthy{RESET}")
    print(f"{'='*50}\n")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
