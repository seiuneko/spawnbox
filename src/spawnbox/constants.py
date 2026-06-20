from __future__ import annotations

from pathlib import Path

NSPAWN_DIR = Path("/run/systemd/nspawn")

SYSTEMD_PROPERTIES = [
    "Delegate=yes",
    "DelegateSubgroup=supervisor",
    "TasksMax=16384",
    "DevicePolicy=closed",
    "DeviceAllow=/dev/net/tun rwm",
    "DeviceAllow=char-pts rw",
    "DeviceAllow=/dev/fuse rwm",
    "DeviceAllow=/dev/loop-control rw",
    "DeviceAllow=block-loop rw",
    "DeviceAllow=block-blkext rw",
    "DeviceAllow=/dev/mapper/control rw",
    "DeviceAllow=block-device-mapper rw",
]

BOOT_TIMEOUT = 90
BOOT_POLL_INTERVAL = 0.5
BOOT_PROBE_TIMEOUT = 10
