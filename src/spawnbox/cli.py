from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spawnbox.config import load_config
from spawnbox.nspawn import run_container, write_nspawn_file
from spawnbox.resolver import get_host_user


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
    args = parse_args()

    config = load_config(args.config)

    if args.verbose >= 1:
        print(f"[spawnbox] machine={config.machine}, directory={config.directory}", file=sys.stderr)

    command = args.command or ([config.default_command] if config.default_command else [])

    _user, home = get_host_user()
    if project_dir := str(Path.cwd()):
        workspace_name = Path(project_dir).name
        workspace_dir = f"{home}/workspace/{workspace_name}"
    else:
        workspace_dir = None

    machine, _nspawn_path = write_nspawn_file(config, project_dir, verbose=args.verbose)

    if args.verbose >= 1:
        print(f"[spawnbox] machine name: {machine}", file=sys.stderr)
        if workspace_dir:
            print(f"[spawnbox] working directory: {workspace_dir}", file=sys.stderr)

    return run_container(
        config, machine, command,
        working_dir=workspace_dir,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
