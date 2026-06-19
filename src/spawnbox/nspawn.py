from __future__ import annotations

import atexit
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

from spawnbox.config import Config
from spawnbox.resolver import (
    expand_bind_path,
    get_host_user,
    resolve_unit,
)

NSPAWN_DIR = Path("/run/systemd/nspawn")


def _sudo_write(path: Path, content: str) -> None:
    subprocess.run(
        ["sudo", "tee", str(path)],
        input=content, text=True, capture_output=True, check=True,
    )


def _sudo_rm(path: Path) -> None:
    subprocess.run(["sudo", "rm", "-f", str(path)], capture_output=True)


# ---- setup helpers ---------------------------------------------------------

def write_nspawn_file(config: Config, project_dir: str | None = None, verbose: int = 0) -> tuple[str, Path]:
    pid = os.getpid()
    machine = f"{config.machine}-{pid}"
    nspawn_path = NSPAWN_DIR / f"{machine}.nspawn"

    user, home = get_host_user()

    lines: list[str] = ["[Exec]"]

    if config.exec_conf.boot:
        lines.append("Boot=yes")
    if config.exec_conf.ephemeral:
        lines.append("Ephemeral=yes")
    if config.exec_conf.private_users:
        lines.append(f"PrivateUsers={config.exec_conf.private_users}")
    lines.append("")

    lines.append("[Files]")
    if config.files_conf.private_users_ownership:
        lines.append(f"PrivateUsersOwnership={config.files_conf.private_users_ownership}")

    for path in config.inaccessible.paths:
        lines.append(f"Inaccessible={path}")

    for unit in config.inaccessible.units:
        resolved = resolve_unit(unit)
        lines.append(f"Inaccessible={resolved}")

    for bro in config.bind_read_only.paths:
        processed = expand_bind_path(bro)
        lines.append(f"BindReadOnly={processed}")

    for b in config.bind.paths:
        processed = expand_bind_path(b)
        lines.append(f"Bind={processed}")

    if project_dir:
        host_dir = str(Path(project_dir).expanduser().resolve())
        workspace_name = Path(host_dir).name
        container_dir = f"{home}/workspace/{workspace_name}"
        lines.append(f"Bind={host_dir}:{container_dir}:idmap")

    lines.append("")

    content = "\n".join(lines)

    if verbose >= 2:
        print(f"# --- {nspawn_path} ---", file=sys.stderr)
        for line in lines:
            print(f"# {line}", file=sys.stderr)

    subprocess.run(["sudo", "mkdir", "-p", str(NSPAWN_DIR)], check=True)
    _sudo_write(nspawn_path, content)
    subprocess.run(["sudo", "chmod", "644", str(nspawn_path)], check=True)

    atexit.register(lambda: _sudo_rm(nspawn_path))
    return machine, nspawn_path


# ---- lifecycle -------------------------------------------------------------

def start_container(machine: str, directory: str) -> None:
    subprocess.run(
        [
            "sudo", "systemd-run",
            "--unit", machine,
            "--property=Delegate=yes",
            "--property=DelegateSubgroup=supervisor",
            "--property=TasksMax=16384",
            "--property=DevicePolicy=closed",
            "--property=DeviceAllow=/dev/net/tun rwm",
            "--property=DeviceAllow=char-pts rw",
            "--property=DeviceAllow=/dev/fuse rwm",
            "--property=DeviceAllow=/dev/loop-control rw",
            "--property=DeviceAllow=block-loop rw",
            "--property=DeviceAllow=block-blkext rw",
            "--property=DeviceAllow=/dev/mapper/control rw",
            "--property=DeviceAllow=block-device-mapper rw",
            "--quiet",
            "--collect",
            "systemd-nspawn",
            "--quiet", "--boot",
            f"--directory={directory}",
            f"--machine={machine}",
        ],
        check=True,
    )


def wait_for_container(machine: str, timeout: int = 90) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = subprocess.run(
            ["sudo", "machinectl", "show", machine],
            capture_output=True, text=True,
        )
        if state.returncode != 0 or "State=running" not in state.stdout:
            time.sleep(0.5)
            continue

        try:
            probe = subprocess.run(
                ["sudo", "systemd-run", "--machine", machine,
                 "--uid=root", "--collect", "--quiet", "--wait",
                 "/bin/true"],
                capture_output=True, timeout=10,
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
    command: list[str] | None,
    working_dir: str | None = None,
) -> int:
    user = get_host_user()[0]
    if not command:
        command = ["/bin/sh"]
    cmd = [
        "sudo", "systemd-run",
        "--machine", machine,
        "--uid", user,
        "--wait",
        "--pty",
        "--collect",
        "--quiet",
    ]
    if working_dir:
        cmd += ["--working-directory", working_dir]
    cmd += command
    return subprocess.run(cmd).returncode


def stop_container(machine: str) -> None:
    subprocess.run(
        ["sudo", "systemctl", "stop", f"{machine}.service"],
        capture_output=True,
    )
    subprocess.run(
        ["sudo", "systemd-nspawn", "--cleanup", f"--machine={machine}"],
        capture_output=True,
    )


# ---- signal handling -------------------------------------------------------

_machine_cleanup: str | None = None


def _signal_handler(signum: int, _frame) -> None:
    if _machine_cleanup:
        stop_container(_machine_cleanup)
    sys.exit(128 + signum)


def _register_signal_handler(machine: str) -> None:
    global _machine_cleanup
    _machine_cleanup = machine
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)


# ---- public entry point ----------------------------------------------------

def run_container(
    config: Config,
    machine: str,
    command: list[str] | None = None,
    working_dir: str | None = None,
    dry_run: bool = False,
    verbose: int = 0,
) -> int:
    if command is None:
        command = [config.default_command] if config.default_command else []

    if dry_run:
        print(f"# machine: {machine}")
        print(f"# .nspawn: /run/systemd/nspawn/{machine}.nspawn")
        print()
        print(f"sudo systemd-run --unit={machine} --property=Delegate=yes --property=DelegateSubgroup=supervisor --property=TasksMax=16384 --property=DevicePolicy=closed --property='DeviceAllow=/dev/net/tun rwm' --property='DeviceAllow=char-pts rw' --property='DeviceAllow=/dev/fuse rwm' --property='DeviceAllow=/dev/loop-control rw' --property='DeviceAllow=block-loop rw' --property='DeviceAllow=block-blkext rw' --property='DeviceAllow=/dev/mapper/control rw' --property='DeviceAllow=block-device-mapper rw' --quiet --collect systemd-nspawn --quiet --boot --directory={config.directory} --machine={machine}")
        print(f"sudo systemctl stop {machine}.service")
        print(f"sudo systemd-nspawn --cleanup --machine={machine}")
        if command:
            cmd_str = " ".join(shlex.quote(c) for c in command)
            wd = f" --working-directory={working_dir}" if working_dir else ""
            print(f"sudo systemd-run --machine={machine} --uid={get_host_user()[0]} --wait --pty --collect --quiet{wd} {cmd_str}")
        else:
            wd = f" --working-directory={working_dir}" if working_dir else ""
            print(f"sudo systemd-run --machine={machine} --uid={get_host_user()[0]} --wait --pty --collect --quiet{wd} /bin/sh")
        return 0

    try:
        _register_signal_handler(machine)

        if verbose >= 1:
            print(f"starting container {machine} ...", flush=True)
        start_container(machine, config.directory)

        if verbose >= 1:
            print(f"waiting for boot ...", flush=True)
        if not wait_for_container(machine):
            print(f"error: container {machine} failed to start", file=sys.stderr)
            return 1

        if verbose >= 1:
            print(f"running command ...", flush=True)
        ret = run_in_container(machine, command, working_dir)

        if verbose >= 1:
            print(f"stopping container ...", flush=True)
    finally:
        stop_container(machine)
    return ret