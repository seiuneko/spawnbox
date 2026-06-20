from __future__ import annotations

import os
import pwd
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class InaccessibleConfig:
    paths: list[str] = field(default_factory=list)
    units: list[str] = field(default_factory=list)


@dataclass
class BindReadOnlyConfig:
    paths: list[str] = field(default_factory=list)


@dataclass
class BindConfig:
    paths: list[str] = field(default_factory=list)


@dataclass
class GpgConfig:
    enabled: bool = False


@dataclass
class Config:
    machine: str = "spawnbox"
    directory: str = "/run/btrfs-root/pc711/@"
    default_command: str = "/usr/bin/opencode"
    target_user: str = ""
    inaccessible: InaccessibleConfig = field(default_factory=InaccessibleConfig)
    bind_read_only: BindReadOnlyConfig = field(default_factory=BindReadOnlyConfig)
    bind: BindConfig = field(default_factory=BindConfig)
    gpg: GpgConfig = field(default_factory=GpgConfig)


def _get_default_config_path() -> Path:
    """获取默认配置路径。以 root 运行时通过 SUDO_USER 找到原始用户的配置。"""
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / "spawnbox" / "spawnbox.toml"
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        pw = pwd.getpwnam(sudo_user)
        return Path(pw.pw_dir) / ".config" / "spawnbox" / "spawnbox.toml"
    return Path.home() / ".config" / "spawnbox" / "spawnbox.toml"


def load_config(path: str | None = None) -> Config:
    candidates: list[Path] = []
    if path:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        candidates.append(p)
    candidates.append(Path("spawnbox.toml"))
    candidates.append(_get_default_config_path())

    raw: dict | None = None
    for candidate in candidates:
        if candidate.exists():
            with open(candidate, "rb") as f:
                raw = tomllib.load(f)
            break

    if raw is None:
        return Config()

    return _parse_config(raw)


def _parse_config(raw: dict) -> Config:
    cfg = Config()

    for key in ("machine", "directory", "default_command", "target_user"):
        if key in raw:
            setattr(cfg, key, raw[key])

    sections: dict[str, tuple[object, tuple[str, ...]]] = {
        "inaccessible":     (cfg.inaccessible,  ("paths", "units")),
        "bind_read_only":   (cfg.bind_read_only, ("paths",)),
        "bind":             (cfg.bind,          ("paths",)),
        "gpg":              (cfg.gpg,           ("enabled",)),
    }

    for section_name, (target, keys) in sections.items():
        if section_name not in raw:
            continue
        section_data = raw[section_name]
        for key in keys:
            if key in section_data:
                setattr(target, key, section_data[key])

    return cfg