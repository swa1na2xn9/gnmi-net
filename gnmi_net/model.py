"""Load gNMI-ish JSON config trees and flatten them into leaf paths.

A tree is a nested object mirroring the device's YANG data path, for example::

    {"interfaces": {"interface": [
        {"name": "ethernet1", "config": {"admin-state": "enable"}}
    ]}}

Lists are indexed positionally in the flattened path so that node keys stay
unique and diffable without a YANG schema.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

LeafPath = tuple[str, ...]


class TreeError(ValueError):
    """Raised when a config file is not a JSON object."""


def load_tree(path: Path) -> dict[str, Any]:
    """Read a JSON object from *path*."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TreeError(f"{path}: invalid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise TreeError(f"{path}: expected a JSON object at the root")
    return data


def flatten(tree: dict[str, Any], prefix: LeafPath = ()) -> Iterator[tuple[LeafPath, Any]]:
    """Yield ``(pointer, leaf)`` pairs in stable key order."""
    for key in sorted(tree):
        value = tree[key]
        if isinstance(value, dict):
            yield from flatten(value, prefix + (key,))
        elif isinstance(value, list):
            for index, entry in enumerate(value):
                item = f"{key}[{index}]"
                if isinstance(entry, dict):
                    yield from flatten(entry, prefix + (item,))
                else:
                    yield prefix + (item,), entry
        else:
            yield prefix + (key,), value


def pointer(path: LeafPath) -> str:
    """Render a leaf path as a slash pointer."""
    return "/" + "/".join(path)
