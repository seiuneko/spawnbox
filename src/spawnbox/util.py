from __future__ import annotations

import os
import pwd


def get_host_user() -> tuple[str, str]:
    """Return (username, home_dir) of the real host user (works under sudo)."""
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        sudo_home = os.environ.get("SUDO_HOME")
        if sudo_home:
            return sudo_user, sudo_home
        pw = pwd.getpwnam(sudo_user)
        return sudo_user, pw.pw_dir
    pw = pwd.getpwuid(os.getuid())
    return pw.pw_name, pw.pw_dir


def resolve_home_path(path: str, host_home: str) -> str:
    """Expand ~ to host_home (works correctly under sudo)."""
    if path.startswith("~/"):
        return host_home + path[1:]
    if path == "~":
        return host_home
    return path
