"""Command line entry point for the gNMI dry-run differ."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .diff import diff
from .dryrun import in_window, parse_window, render
from .model import TreeError, load_tree
from .policy import PolicyError, load_policy

EXIT_CLEAN = 0
EXIT_DRIFT = 2
EXIT_WINDOW = 3
EXIT_POLICY = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gnmi-net",
        description="Diff a desired config tree against the running tree and print a plan.",
    )
    parser.add_argument("--desired", type=Path, required=True, help="desired JSON tree")
    parser.add_argument("--actual", type=Path, required=True, help="running JSON tree")
    parser.add_argument("--host", default="lab", help="device name used in the plan header")
    parser.add_argument(
        "--window",
        help="UTC change window HH:MM-HH:MM; drift outside it exits 3",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="print the plan even when --window is closed or a policy blocks it",
    )
    parser.add_argument("--policy", type=Path, help="JSON guardrail policy for this plan")
    parser.add_argument("--json", action="store_true", help="emit the change list as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        desired = load_tree(args.desired)
        actual = load_tree(args.actual)
    except (OSError, TreeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    changes = diff(desired, actual)
    if args.json:
        print(json.dumps([change.__dict__ for change in changes], indent=2, sort_keys=True))
    else:
        print(render(args.host, changes))

    if not changes:
        return EXIT_CLEAN

    if args.policy:
        try:
            violations = load_policy(args.policy).violations(changes)
        except (OSError, PolicyError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if violations:
            for reason in violations:
                print(f"policy: {reason}", file=sys.stderr)
            if not args.force:
                print("rerun with --force to override the policy", file=sys.stderr)
                return EXIT_POLICY

    if args.window:
        start, end = parse_window(args.window)
        now = datetime.now(timezone.utc).time().replace(microsecond=0)
        if not in_window(now, (start, end)) and not args.force:
            print(
                f"outside change window {args.window} (now {now:%H:%M} UTC); "
                "rerun with --force to override",
                file=sys.stderr,
            )
            return EXIT_WINDOW
    return EXIT_DRIFT


if __name__ == "__main__":
    raise SystemExit(main())
