from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "scripts" / "run_all_hosts.py"
spec = importlib.util.spec_from_file_location("all_hosts", SCRIPT)
assert spec and spec.loader
all_hosts = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = all_hosts
spec.loader.exec_module(all_hosts)


class RunAllHostsTests(unittest.TestCase):
    def test_forwards_arguments_to_both_hosts(self) -> None:
        completed: list[list[str]] = []

        def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            completed.append(command)
            if command[0] == "wslpath":
                return subprocess.CompletedProcess(command, 0, "E:\\repo\n", "")
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(all_hosts.sys, "platform", "linux"), mock.patch.object(
            all_hosts.Path, "exists", return_value=True
        ), mock.patch.object(all_hosts, "powershell_path", return_value="powershell.exe"), mock.patch.object(
            all_hosts.shutil, "which", side_effect=lambda value: "wslpath" if value == "wslpath" else value
        ), mock.patch.object(all_hosts.subprocess, "run", side_effect=run):
            result = all_hosts.main(["install", "--dry-run", "--home", "/tmp/home with spaces"])

        self.assertEqual(result, 0)
        wsl = next(command for command in completed if command[0] == "mise")
        windows = next(command for command in completed if command[0] == "powershell.exe")
        self.assertEqual(wsl[-3:], ["--dry-run", "--home", "/tmp/home with spaces"])
        encoded = windows[windows.index("-TaskArgsJson") + 1]
        self.assertEqual(json.loads(encoded), ["--dry-run", "--home", "/tmp/home with spaces"])

    def test_returns_worst_host_exit_code(self) -> None:
        exits = iter((1, 0))

        def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if command[0] == "wslpath":
                return subprocess.CompletedProcess(command, 0, "E:\\repo\n", "")
            return subprocess.CompletedProcess(command, next(exits), "", "")

        with mock.patch.object(all_hosts.sys, "platform", "linux"), mock.patch.object(
            all_hosts.Path, "exists", return_value=True
        ), mock.patch.object(all_hosts, "powershell_path", return_value="powershell.exe"), mock.patch.object(
            all_hosts.shutil, "which", return_value="wslpath"
        ), mock.patch.object(all_hosts.subprocess, "run", side_effect=run):
            self.assertEqual(all_hosts.main(["status"]), 1)


if __name__ == "__main__":
    unittest.main()
