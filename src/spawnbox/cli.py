from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spawnbox.config import load_config
from spawnbox.resolver import get_host_user
from spawnbox.runner import Runner


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="systemd-nspawn wrapper optimized for LLM coding agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-c", "--config",
        metavar="FILE",
        help="Path to TOML config file",
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Print commands without executing",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Verbose output (-v basic, -vv show generated .nspawn file)",
    )

    args, remainder = parser.parse_known_args(argv)
    args.command = remainder or None
    return args


def main() -> int:
    from spawnbox import setup_logging

    args = parse_args()
    setup_logging(args.verbose)

    config = load_config(args.config)
    user, home = get_host_user()
    project_dir = str(Path.cwd())

    command = args.command or (
        [config.default_command] if config.default_command else []
    )

    runner = Runner(config, dry_run=args.dry_run)
    runner.setup(project_dir, user, home)

    workspace_name = Path(project_dir).name
    workspace_dir = f"{home}/workspace/{workspace_name}"

    return runner.run(command, workspace_dir)


if __name__ == "__main__":
    sys.exit(main())
