"""Guardrails that a change plan must satisfy before a window starts.

A policy is a small JSON document kept beside the trees::

    {
      "max_changes": 8,
      "max_high_risk": 2,
      "protected": ["/network-instances/network-instance[0]/protocols"]
    }

``protected`` entries are literal path prefixes; a plan touching any leaf below
one is rejected so that the noisy parts of the config need an explicit edit to
the policy instead of a silent drift.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .diff import Change, summarise


class PolicyError(ValueError):
    """Raised when a policy file is malformed."""


@dataclass(frozen=True)
class Policy:
    max_changes: int = 20
    max_high_risk: int = 5
    protected: tuple[str, ...] = ()

    def violations(self, changes: list[Change]) -> list[str]:
        """Return human-readable reasons the plan may not proceed."""
        reasons: list[str] = []
        counts = summarise(changes)
        if len(changes) > self.max_changes:
            reasons.append(f"{len(changes)} changes exceed max_changes={self.max_changes}")
        if counts["high_risk"] > self.max_high_risk:
            reasons.append(
                f"{counts['high_risk']} high-risk changes exceed "
                f"max_high_risk={self.max_high_risk}"
            )
        for change in changes:
            for prefix in self.protected:
                if change.path == prefix or change.path.startswith(prefix.rstrip("/") + "/"):
                    reasons.append(f"protected path touched: {change.path}")
                    break
        return reasons


def load_policy(path: Path) -> Policy:
    """Parse and validate a policy document."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PolicyError(f"{path}: invalid JSON: {exc.msg}") from exc
    if not isinstance(raw, dict):
        raise PolicyError(f"{path}: expected a JSON object")

    max_changes = raw.get("max_changes", 20)
    max_high_risk = raw.get("max_high_risk", 5)
    protected = raw.get("protected", [])
    if not isinstance(max_changes, int) or max_changes < 1:
        raise PolicyError(f"{path}: max_changes must be a positive integer")
    if not isinstance(max_high_risk, int) or max_high_risk < 0:
        raise PolicyError(f"{path}: max_high_risk must be a non-negative integer")
    if not isinstance(protected, list) or not all(
        isinstance(entry, str) and entry.startswith("/") for entry in protected
    ):
        raise PolicyError(f"{path}: protected must be a list of slash paths")
    return Policy(max_changes, max_high_risk, tuple(protected))
