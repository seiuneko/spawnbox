from __future__ import annotations

import logging
import os
from pathlib import Path

from spawnbox.config import Config
from spawnbox.util import get_host_user, resolve_home_path

_logger = logging.getLogger(__name__)


def resolve_unit(name: str) -> str:
    available: set[str] = set()
    for wants_dir in Path("/etc/systemd/system").glob("*.wants"):
        unit_path = wants_dir / name
        if unit_path.exists():
            return str(unit_path.resolve())
        for p in wants_dir.iterdir():
            available.add(p.name)
    raise ValueError(
        f"Unit {name!r} not found in any /etc/systemd/system/*.wants/ directory.\n"
        f"Available units: {', '.join(sorted(available))}"
    )


def ensure_bind_parent_dirs(
    config: Config, host_home: str, host_uid: int, host_gid: int,
) -> None:
    """Ensure parent dirs of all ~ bind-mount sources exist with correct ownership."""
    paths = list(config.bind.paths) + list(config.bind_read_only.paths)
    if config.gpg.enabled:
        paths += [
            "~/.gnupg/S.gpg-agent.host",
            "~/.config/git",
            "~/.gnupg/pubring.kbx",
        ]
    seen: set[Path] = set()
    for raw in paths:
        source = raw.split(":", 1)[0] if ":" in raw else raw
        source = resolve_home_path(source, host_home)
        parent = (Path(config.directory) / source.lstrip('/')).parent
        _logger.info("creating %s (uid=%d, gid=%d)", parent, host_uid, host_gid)
        if parent in seen:
            continue
        seen.add(parent)
        parent.mkdir(parents=True, exist_ok=True)
        os.chown(parent, host_uid, host_gid)


def expand_bind_path(raw: str, host_home: str = "") -> str:
    if ":" in raw:
        source, dest = raw.split(":", 1)
    else:
        source = dest = raw
    if not host_home:
        host_home = get_host_user()[1]
    source = resolve_home_path(source, host_home)
    dest = resolve_home_path(dest, host_home)
    return f"{source}:{dest}:idmap"
