"""Render a reviewable change plan with rollback payload."""
from __future__ import annotations

import json
from datetime import time

from .diff import Change, rollback, summarise
from .model import pointer


def parse_window(raw: str) -> tuple[time, time]:
    """Parse ``HH:MM-HH:MM`` in UTC; the end may fall on the next day."""
    start_raw, _, end_raw = raw.partition("-")
    try:
        start = time.fromisoformat(start_raw)
        end = time.fromisoformat(end_raw)
    except ValueError as exc:
        raise ValueError(f"invalid window {raw!r}, expected HH:MM-HH:MM") from exc
    if start == end:
        raise ValueError("window start and end must differ")
    return start, end


def in_window(moment: time, window: tuple[time, time]) -> bool:
    """True when *moment* lies inside *window*, including over midnight."""
    start, end = window
    if start < end:
        return start <= moment < end
    return moment >= start or moment < end


def render(host: str, changes: list[Change]) -> str:
    """Human-readable plan, highest-risk entries first within each kind."""
    counts = summarise(changes)
    lines = [
        f"device: {host}",
        f"changes: {len(changes)} "
        f"(add {counts['add']}, change {counts['change']}, remove {counts['remove']}, "
        f"high risk {counts['high_risk']})",
        "",
    ]
    ordered = sorted(changes, key=lambda c: (not c.high_risk, c.path))
    for change in ordered:
        flag = "!" if change.high_risk else " "
        detail = (
            f"{change.actual!r} -> {change.desired!r}"
            if change.kind == "change"
            else f"{change.desired if change.kind == 'add' else change.actual!r}"
        )
        lines.append(f"{flag} {change.kind:<6} {change.path}  {detail}")
    if not changes:
        lines.append("running config already matches the desired tree")
    lines += ["", "rollback payload (gNMI SetRequest):"]
    lines.append(json.dumps(rollback(changes), indent=2, sort_keys=True))
    return "\n".join(lines)


__all__ = ["in_window", "parse_window", "render", "pointer"]
