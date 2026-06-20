from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


XDG_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "spawnbox"
DEFAULT_CONFIG_PATH = XDG_CONFIG_DIR / "spawnbox.toml"


@dataclass
class ExecConfig:
    boot: bool = True
    ephemeral: bool = True
    private_users: str = "pick"


@dataclass
class FilesConfig:
    private_users_ownership: str = "auto"


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
    exec_conf: ExecConfig = field(default_factory=ExecConfig)
    files_conf: FilesConfig = field(default_factory=FilesConfig)
    inaccessible: InaccessibleConfig = field(default_factory=InaccessibleConfig)
    bind_read_only: BindReadOnlyConfig = field(default_factory=BindReadOnlyConfig)
    bind: BindConfig = field(default_factory=BindConfig)
    gpg: GpgConfig = field(default_factory=GpgConfig)


def load_config(path: str | None = None) -> Config:
    candidates: list[Path] = []
    if path:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        candidates.append(p)
    candidates.append(Path("spawnbox.toml"))
    candidates.append(DEFAULT_CONFIG_PATH)

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

    for key in ("machine", "directory", "default_command"):
        if key in raw:
            setattr(cfg, key, raw[key])

    sections: dict[str, tuple[object, tuple[str, ...]]] = {
        "exec":             (cfg.exec_conf,     ("boot", "ephemeral", "private_users")),
        "files":            (cfg.files_conf,    ("private_users_ownership",)),
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
