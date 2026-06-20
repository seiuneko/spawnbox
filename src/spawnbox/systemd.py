from __future__ import annotations

import shlex
import subprocess
import time
from typing import Any

from spawnbox.constants import (
    BOOT_POLL_INTERVAL,
    BOOT_PROBE_TIMEOUT,
    BOOT_TIMEOUT,
    SYSTEMD_PROPERTIES,
)


def run_systemd(
    cmd: list[str],
    *,
    dry_run: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Execute a systemd command, or print it in dry-run mode."""
    if dry_run:
        print(" ".join(shlex.quote(c) for c in cmd))
        return subprocess.CompletedProcess(cmd, 0)
    return subprocess.run(cmd, **kwargs)


def start_container(
    machine: str,
    directory: str,
    *,
    dry_run: bool = False,
) -> None:
    """Start a systemd-nspawn container via systemd-run."""
    properties = [f"--property={p}" for p in SYSTEMD_PROPERTIES]
    run_systemd(
        [
            "sudo", "systemd-run",
            "--unit", machine,
            *properties,
            "--quiet", "--collect",
            "systemd-nspawn",
            "--quiet", "--boot",
            f"--directory={directory}",
            f"--machine={machine}",
        ],
        dry_run=dry_run,
        check=True,
    )


def stop_container(
    machine: str,
    *,
    dry_run: bool = False,
) -> None:
    """Stop and clean up a systemd-nspawn container."""
    run_systemd(
        ["sudo", "systemctl", "stop", f"{machine}.service"],
        dry_run=dry_run,
        capture_output=True,
    )
    run_systemd(
        ["sudo", "systemd-nspawn", "--cleanup", f"--machine={machine}"],
        dry_run=dry_run,
        capture_output=True,
    )


def wait_for_container(
    machine: str,
    *,
    dry_run: bool = False,
    timeout: int = BOOT_TIMEOUT,
) -> bool:
    """Poll until the container is running and responsive."""
    if dry_run:
        return True
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = subprocess.run(
            ["sudo", "machinectl", "show", machine],
            capture_output=True, text=True,
        )
        if state.returncode != 0 or "State=running" not in state.stdout:
            time.sleep(BOOT_POLL_INTERVAL)
            continue
        try:
            probe = subprocess.run(
                ["sudo", "systemd-run", "--machine", machine,
                 "--uid=root", "--collect", "--quiet", "--wait",
                 "/bin/true"],
                capture_output=True, timeout=BOOT_PROBE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            time.sleep(1)
            continue
        if probe.returncode == 0:
            return True
        time.sleep(1)
    return False


def run_in_container(
    machine: str,
    user: str,
    command: list[str],
    working_dir: str | None = None,
    *,
    dry_run: bool = False,
) -> int:
    """Run a command inside the container as the given user."""
    cmd = [
        "sudo", "systemd-run",
        "--machine", f"{user}@{machine}",
        "--user",
        "--wait",
        "--pty",
        "--collect",
        "--quiet",
    ]
    if working_dir:
        cmd += ["--working-directory", working_dir]
    cmd += command
    return run_systemd(cmd, dry_run=dry_run).returncode


def enable_gpg_agent(
    machine: str,
    *,
    dry_run: bool = False,
) -> None:
    """Enable the GPG agent forwarding service inside the container."""
    run_systemd(
        [
            "sudo", "systemd-run",
            "--machine", machine,
            "--wait", "--collect", "--quiet",
            "systemctl", "--global", "enable", "spawnbox-gpg-agent.service",
        ],
        dry_run=dry_run,
        check=True,
    )
