from __future__ import annotations

import logging
import os
import signal
import sys

from spawnbox.config import Config
from spawnbox.nspawn_config import build_nspawn_content, write_nspawn_file
from spawnbox.resolver import get_host_user
from spawnbox.systemd import (
    enable_gpg_agent,
    run_in_container,
    start_container,
    stop_container,
    wait_for_container,
)


class Runner:
    """编排容器生命周期：构建配置 -> 启动 -> 等待 -> 执行 -> 停止。"""

    def __init__(self, config: Config, *, dry_run: bool = False):
        self._config = config
        self._dry_run = dry_run
        self._machine = f"{config.machine}-{os.getpid()}"
        self._logger = logging.getLogger(__name__)

    @property
    def machine(self) -> str:
        return self._machine

    def setup(
        self,
        project_dir: str | None,
        host_user: str,
        host_home: str,
    ) -> None:
        """生成 .nspawn 文件。"""
        content = build_nspawn_content(
            self._config,
            host_user,
            host_home,
            project_dir,
        )
        nspawn_path = write_nspawn_file(self._machine, content)
        self._logger.debug("# --- %s ---", nspawn_path)
        for line in content.split("\n"):
            if line:
                self._logger.debug("# %s", line)

    def run(
        self,
        command: list[str],
        working_dir: str | None = None,
    ) -> int:
        """完整生命周期，返回退出码。"""
        self._register_signal_handlers()

        if self._dry_run:
            print(f"# machine: {self._machine}")
            print(f"# .nspawn: /run/systemd/nspawn/{self._machine}.nspawn")
            print()

        try:
            self._start()
            if not self._wait_for_boot():
                self._logger.error(
                    "container %s failed to start", self._machine
                )
                return 1
            self._maybe_enable_gpg()
            return self._execute(command, working_dir)
        finally:
            self._stop()

    def _register_signal_handlers(self) -> None:
        """用闭包捕获 machine，避免模块级全局变量。"""
        machine = self._machine
        dry_run = self._dry_run

        def handler(signum: int, _frame) -> None:
            stop_container(machine, dry_run=dry_run)
            sys.exit(128 + signum)

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def _start(self) -> None:
        self._logger.info("starting container %s ...", self._machine)
        start_container(
            self._machine,
            self._config.directory,
            dry_run=self._dry_run,
        )

    def _wait_for_boot(self) -> bool:
        self._logger.info("waiting for boot ...")
        return wait_for_container(self._machine, dry_run=self._dry_run)

    def _maybe_enable_gpg(self) -> None:
        if not self._config.gpg.enabled:
            return
        self._logger.info("enabling GPG agent forwarding ...")
        enable_gpg_agent(self._machine, dry_run=self._dry_run)

    def _execute(
        self,
        command: list[str],
        working_dir: str | None,
    ) -> int:
        user = get_host_user()[0]
        self._logger.info("running command ...")
        return run_in_container(
            self._machine,
            user,
            command,
            working_dir,
            dry_run=self._dry_run,
        )

    def _stop(self) -> None:
        self._logger.info("stopping container ...")
        stop_container(self._machine, dry_run=self._dry_run)
