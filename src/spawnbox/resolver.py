from __future__ import annotations

import os
import pwd
from pathlib import Path


def get_host_user() -> tuple[str, str]:
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        pw = pwd.getpwnam(sudo_user)
        return sudo_user, pw.pw_dir
    pw = pwd.getpwuid(os.getuid())
    return pw.pw_name, pw.pw_dir


def resolve_unit(name: str) -> str:
    for wants_dir in Path("/etc/systemd/system").glob("*.wants"):
        unit_path = wants_dir / name
        if unit_path.exists():
            return str(unit_path.resolve())
    available: set[str] = set()
    for wd in Path("/etc/systemd/system").glob("*.wants"):
        for p in wd.iterdir():
            available.add(p.name)
    raise ValueError(
        f"Unit {name!r} not found in any /etc/systemd/system/*.wants/ directory.\n"
        f"Available units: {', '.join(sorted(available))}"
    )


def expand_bind_path(raw: str) -> str:
    if ":" in raw:
        source, dest = raw.split(":", 1)
    else:
        source = dest = raw
    source = str(Path(source).expanduser())
    dest = str(Path(dest).expanduser())
    return f"{source}:{dest}:idmap"
