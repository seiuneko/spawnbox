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
class Config:
    machine: str = "spawnbox"
    directory: str = "/run/btrfs-root/pc711/@"
    default_command: str = "/usr/bin/opencode"
    exec_conf: ExecConfig = field(default_factory=ExecConfig)
    files_conf: FilesConfig = field(default_factory=FilesConfig)
    inaccessible: InaccessibleConfig = field(default_factory=InaccessibleConfig)
    bind_read_only: BindReadOnlyConfig = field(default_factory=BindReadOnlyConfig)
    bind: BindConfig = field(default_factory=BindConfig)


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

    cfg.machine = raw.get("machine", cfg.machine)
    cfg.directory = raw.get("directory", cfg.directory)
    cfg.default_command = raw.get("default_command", cfg.default_command)

    if "exec" in raw:
        e = raw["exec"]
        cfg.exec_conf.boot = e.get("boot", cfg.exec_conf.boot)
        cfg.exec_conf.ephemeral = e.get("ephemeral", cfg.exec_conf.ephemeral)
        cfg.exec_conf.private_users = e.get("private_users", cfg.exec_conf.private_users)

    if "files" in raw:
        f = raw["files"]
        cfg.files_conf.private_users_ownership = f.get(
            "private_users_ownership", cfg.files_conf.private_users_ownership
        )

    if "inaccessible" in raw:
        ia = raw["inaccessible"]
        cfg.inaccessible.paths = ia.get("paths", [])
        cfg.inaccessible.units = ia.get("units", [])

    if "bind_read_only" in raw:
        cfg.bind_read_only.paths = raw["bind_read_only"].get("paths", [])

    if "bind" in raw:
        cfg.bind.paths = raw["bind"].get("paths", [])

    return cfg
