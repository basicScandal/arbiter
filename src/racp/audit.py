"""Hash-chained, append-only decision log.

Every gateway ruling is recorded in a tamper-evident chain: each entry carries
the hash of the previous entry, so a deleted or edited decision breaks
verification. This is the evidence trail that connects fast action checks to
post-event review -- when a team disputes a blocked score, the chain says what
was known at the moment the decision was made.

Attacker-controlled text is never written to the log; only digests, pattern
names, and monitor identifiers are.
"""

from __future__ import annotations

import json
import logging
import threading
from hashlib import sha256
from pathlib import Path

from src.racp.models import Decision

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64


class DecisionLog:
    """Append-only hash chain of gateway decisions.

    Args:
        path: Optional JSONL file the chain is mirrored to. When omitted the
            chain is kept in memory only (used by tests and rehearsals).
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._entries: list[dict] = []
        self._head: str = GENESIS_HASH
        self._lock = threading.Lock()
        self._path = Path(path) if path is not None else None
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def head(self) -> str:
        """Hash of the most recent entry (genesis hash when empty)."""
        return self._head

    def __len__(self) -> int:
        return len(self._entries)

    def append(self, decision: Decision) -> str:
        """Record a decision and return the new chain head."""
        with self._lock:
            entry = {
                "seq": len(self._entries),
                "prev": self._head,
                "decision": decision.model_dump(mode="json"),
            }
            entry["hash"] = self._hash_entry(entry)
            self._entries.append(entry)
            self._head = entry["hash"]

            if self._path is not None:
                try:
                    with self._path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(entry, sort_keys=True) + "\n")
                except OSError:
                    # A full or read-only disk must not take down the judge;
                    # the in-memory chain remains intact and still verifies.
                    logger.warning(
                        "Could not persist RACP decision to %s", self._path,
                        exc_info=True,
                    )

            return self._head

    def entries(self) -> list[dict]:
        """Return a copy of the chain."""
        return list(self._entries)

    def decisions(self) -> list[Decision]:
        """Return the logged decisions in order."""
        return [Decision.model_validate(e["decision"]) for e in self._entries]

    def verify_chain(self) -> bool:
        """Recompute every link and return True when the chain is intact."""
        prev = GENESIS_HASH
        for index, entry in enumerate(self._entries):
            if entry["seq"] != index or entry["prev"] != prev:
                return False
            recomputed = self._hash_entry(
                {"seq": entry["seq"], "prev": entry["prev"], "decision": entry["decision"]}
            )
            if recomputed != entry["hash"]:
                return False
            prev = entry["hash"]
        return prev == self._head

    @staticmethod
    def _hash_entry(entry: dict) -> str:
        blob = json.dumps(
            {k: entry[k] for k in ("seq", "prev", "decision")},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(blob).hexdigest()
