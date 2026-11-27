"""Diff desired against running config and classify device impact."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .model import LeafPath, flatten, pointer

Kind = Literal["add", "change", "remove"]

# Paths whose change can drop a session, flap a link or blackhole traffic.
# Stored as segments so list indexes do not defeat the prefix match.
PROTECTED_PREFIXES = (
    ("network-instances", "network-instance", "protocols", "protocol", "bgp"),
    ("interfaces", "interface"),
)


def _segments(path: str) -> tuple[str, ...]:
    return tuple(part.split("[", 1)[0] for part in path.strip("/").split("/"))


@dataclass(frozen=True)
class Change:
    """One leaf-level difference between desired and actual state."""

    kind: Kind
    path: str
    desired: Any = None
    actual: Any = None

    @property
    def high_risk(self) -> bool:
        if self.kind == "add":
            return False
        segments = _segments(self.path)
        return any(segments[: len(prefix)] == prefix for prefix in PROTECTED_PREFIXES)


def _index(tree: dict[str, Any]) -> dict[str, Any]:
    return {pointer(path): leaf for path, leaf in flatten(tree)}


def diff(desired: dict[str, Any], actual: dict[str, Any]) -> list[Change]:
    """Return ordered changes that turn *actual* into *desired*."""
    want = _index(desired)
    have = _index(actual)
    changes: list[Change] = []
    for path in sorted(want.keys() - have.keys()):
        changes.append(Change("add", path, desired=want[path]))
    for path in sorted(have.keys() - want.keys()):
        changes.append(Change("remove", path, actual=have[path]))
    for path in sorted(want.keys() & have.keys()):
        if want[path] != have[path]:
            changes.append(Change("change", path, desired=want[path], actual=have[path]))
    return changes


def rollback(changes: list[Change]) -> dict[str, Any]:
    """Build a gNMI replace/delete payload that undoes *changes*."""
    replace: dict[str, Any] = {}
    delete: list[str] = []
    for change in changes:
        if change.kind == "add":
            delete.append(change.path)
        else:
            replace[change.path] = change.actual
    payload: dict[str, Any] = {}
    if replace:
        payload["replace"] = replace
    if delete:
        payload["delete"] = sorted(delete)
    return payload


def summarise(changes: list[Change]) -> dict[str, int]:
    """Count changes by kind and by risk class."""
    counts = {"add": 0, "change": 0, "remove": 0, "high_risk": 0}
    for change in changes:
        counts[change.kind] += 1
        if change.high_risk:
            counts["high_risk"] += 1
    return counts
