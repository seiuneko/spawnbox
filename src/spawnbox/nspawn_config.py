from __future__ import annotations

import atexit
import subprocess
from pathlib import Path

from spawnbox.config import Config
from spawnbox.constants import NSPAWN_DIR
from spawnbox.resolver import expand_bind_path, resolve_unit

_SERVICE_DIR = Path(__file__).parent / "resources"
SERVICE_FILE = str(_SERVICE_DIR / "spawnbox-gpg-agent.service")



def _build_profile_section() -> list[str]:
    """硬编码的容器运行时配置：[Exec] + [Files] 两个 section。"""
    return [
        "[Exec]",
        "Boot=yes",
        "Ephemeral=yes",
        "PrivateUsers=pick",
        "",
        "[Files]",
        "PrivateUsersOwnership=auto",
    ]


def _build_inaccessible_section(config: Config) -> list[str]:
    lines: list[str] = []
    for path in config.inaccessible.paths:
        lines.append(f"Inaccessible={path}")
    for unit in config.inaccessible.units:
        resolved = resolve_unit(unit)
        lines.append(f"Inaccessible={resolved}")
    return lines


def _build_bind_read_only_section(config: Config) -> list[str]:
    lines: list[str] = []
    for bro in config.bind_read_only.paths:
        processed = expand_bind_path(bro)
        lines.append(f"BindReadOnly={processed}")
    return lines


def _build_bind_section(config: Config) -> list[str]:
    lines: list[str] = []
    for b in config.bind.paths:
        processed = expand_bind_path(b)
        lines.append(f"Bind={processed}")
    return lines


def _build_project_bind(project_dir: str, host_home: str) -> list[str]:
    host_dir = str(Path(project_dir).expanduser().resolve())
    workspace_name = Path(host_dir).name
    container_dir = f"{host_home}/workspace/{workspace_name}"
    return [f"Bind={host_dir}:{container_dir}:idmap"]


def _build_gpg_section(config: Config, host_home: str) -> list[str]:
    lines: list[str] = []
    result = subprocess.run(
        ["gpgconf", "--list-dir", "agent-extra-socket"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "gpgconf not found; install gnupg or disable [gpg] in config"
        )
    host_extra_socket = result.stdout.strip()
    if not host_extra_socket:
        raise RuntimeError(
            "gpgconf --list-dir agent-extra-socket returned empty; "
            "is gpg-agent running?"
        )

    processed = expand_bind_path(
        f"{host_extra_socket}:~/.gnupg/S.gpg-agent.host"
    )
    lines.append(f"Bind={processed}")

    for path in ["~/.config/git", "~/.gnupg/pubring.kbx"]:
        processed = expand_bind_path(path)
        lines.append(f"BindReadOnly={processed}")

    processed = expand_bind_path(
        f"{SERVICE_FILE}:/usr/lib/systemd/user/spawnbox-gpg-agent.service"
    )
    lines.append(f"BindReadOnly={processed}")

    return lines


def build_nspawn_content(
    config: Config,
    host_user: str,
    host_home: str,
    project_dir: str | None = None,
) -> str:
    """生成 .nspawn 文件内容。纯函数，无副作用。"""
    lines: list[str] = []
    lines += _build_profile_section()
    lines += _build_inaccessible_section(config)
    lines += _build_bind_read_only_section(config)
    lines += _build_bind_section(config)
    if project_dir:
        lines += _build_project_bind(project_dir, host_home)
    if config.gpg.enabled:
        lines += _build_gpg_section(config, host_home)
    lines.append("")
    return "\n".join(lines)


def write_nspawn_file(machine: str, content: str, *, dry_run: bool = False) -> Path:
    """写入 .nspawn 文件并注册清理。dry_run 模式下不做任何实际 IO。"""
    nspawn_path = NSPAWN_DIR / f"{machine}.nspawn"
    if dry_run:
        return nspawn_path
    NSPAWN_DIR.mkdir(parents=True, exist_ok=True)
    nspawn_path.write_text(content)
    nspawn_path.chmod(0o644)
    atexit.register(lambda: cleanup_nspawn_file(nspawn_path))
    return nspawn_path


def cleanup_nspawn_file(nspawn_path: Path) -> None:
    """删除 .nspawn 文件。"""
    nspawn_path.unlink(missing_ok=True)
