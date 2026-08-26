from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "scripts" / "run_all_hosts.py"
spec = importlib.util.spec_from_file_location("all_hosts", SCRIPT)
assert spec and spec.loader
all_hosts = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = all_hosts
spec.loader.exec_module(all_hosts)


class RunAllHostsTests(unittest.TestCase):
    def test_windows_launcher_preserves_json_argument_boundaries(self) -> None:
        launcher = SCRIPT.with_name("run-windows-mise.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "$decodedArgs = ConvertFrom-Json -InputObject $TaskArgsJson",
            launcher,
        )
        self.assertNotIn(
            "$decodedArgs = @(ConvertFrom-Json -InputObject $TaskArgsJson)",
            launcher,
        )

    def test_windows_launcher_preserves_single_json_argument(self) -> None:
        launcher = SCRIPT.with_name("run-windows-mise.ps1").read_text(encoding="utf-8")
        self.assertIn("ConvertFrom-Json unwraps a one-element JSON array", launcher)
        self.assertIn("$decodedArgs = @($decodedArgs)", launcher)

    def test_forwards_arguments_to_both_hosts(self) -> None:
        completed: list[list[str]] = []

        def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            completed.append(command)
            if command[0] == "wslpath":
                converted = {
                    str(SCRIPT.parents[1]): "E:\\repo",
                    "/tmp/home with spaces": "\\\\wsl.localhost\\Ubuntu\\tmp\\home with spaces",
                }
                return subprocess.CompletedProcess(command, 0, converted[command[-1]] + "\n", "")
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
        self.assertEqual(
            json.loads(encoded),
            ["--dry-run", "--home", "\\\\wsl.localhost\\Ubuntu\\tmp\\home with spaces"],
        )

    def test_converts_equals_path_options_but_preserves_relative_values(self) -> None:
        def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(command, 0, "C:\\native-home\n", "")

        with mock.patch.object(all_hosts.subprocess, "run", side_effect=run):
            result = all_hosts.windows_arguments(
                ["--home=/tmp/home", "--codex-home", "relative-codex", "--dry-run"],
                "wslpath",
            )

        self.assertEqual(
            result,
            ["--home=C:\\native-home", "--codex-home", "relative-codex", "--dry-run"],
        )

    def test_preserves_windows_unc_and_delimited_values(self) -> None:
        with mock.patch.object(all_hosts.subprocess, "run") as run:
            arguments = [
                "--home",
                "C:\\Users\\person",
                "--codex-home=//server/share/codex",
                "--",
                "--home",
                "/tmp/literal",
            ]
            result = all_hosts.windows_arguments(arguments, "wslpath")

        self.assertEqual(result, arguments)
        run.assert_not_called()

    def test_main_preserves_delimiter_tail(self) -> None:
        completed: list[list[str]] = []

        def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            completed.append(command)
            if command[0] == "wslpath":
                return subprocess.CompletedProcess(command, 0, "E:\\repo\n", "")
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(all_hosts.sys, "platform", "linux"), mock.patch.object(
            all_hosts.Path, "exists", return_value=True
        ), mock.patch.object(all_hosts, "powershell_path", return_value="powershell.exe"), mock.patch.object(
            all_hosts.shutil, "which", return_value="wslpath"
        ), mock.patch.object(all_hosts.subprocess, "run", side_effect=run):
            self.assertEqual(all_hosts.main(["status", "--", "--home", "/tmp/literal"]), 0)

        windows = next(command for command in completed if command[0] == "powershell.exe")
        encoded = windows[windows.index("-TaskArgsJson") + 1]
        self.assertEqual(json.loads(encoded), ["--", "--home", "/tmp/literal"])

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

    def test_refuses_a_wsl_resident_checkout_by_name_before_either_leg_runs(self) -> None:
        """PowerShell's zone check, named instead of surfaced opaquely (agentic-sdlc-1db2).

        `-ExecutionPolicy Bypass` is already passed and is not what fails. Windows PowerShell applies
        a separate AuthorizationManager check to a script FILE loaded from an untrusted UNC provider,
        so `-File \\\\wsl.localhost\\...` dies before running anything, and every all-hosts task on
        the documented WSL-first dev setup died that way with only PowerShell's own text to go on.

        Two properties matter here and each has its own assertion. The refusal NAMES the provider,
        the mechanism, and a remedy; and it lands before the WSL leg, because a coordinator that
        installs on one host and only then finds the other cannot start has reported a half-executed
        pair as an ordinary leg failure.

        Unlike its neighbours this test captures its own stdout and stderr: `main` prints the host
        banners and `parser.error` writes the refusal, and none of that belongs in the test report
        (the leak agentic-sdlc-b268 owns cleaning up in the older cases).
        """

        def attempt(native_repo: str) -> tuple[list[str], str, int | None]:
            recorded: list[list[str]] = []

            def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                recorded.append(command)
                if command[0] == "wslpath":
                    return subprocess.CompletedProcess(command, 0, f"{native_repo}\n", "")
                return subprocess.CompletedProcess(command, 0, "", "")

            captured = io.StringIO()
            with mock.patch.object(all_hosts.sys, "platform", "linux"), mock.patch.object(
                all_hosts.Path, "exists", return_value=True
            ), mock.patch.object(
                all_hosts, "powershell_path", return_value="powershell.exe"
            ), mock.patch.object(
                all_hosts.shutil, "which", return_value="wslpath"
            ), mock.patch.object(
                all_hosts.subprocess, "run", side_effect=run
            ), redirect_stdout(io.StringIO()), redirect_stderr(captured):
                try:
                    code = all_hosts.main(["status"])
                except SystemExit as refused:
                    code = refused.code
            return [command[0] for command in recorded], captured.getvalue(), code

        programs, refusal, code = attempt("\\\\wsl.localhost\\Ubuntu\\home\\person\\agentic-sdlc")
        self.assertEqual(code, 2)
        self.assertIn("\\\\wsl.localhost", refusal)
        self.assertIn("AuthorizationManager check failed", refusal)
        self.assertIn("-ExecutionPolicy Bypass", refusal)
        self.assertIn("/mnt/<drive>/", refusal)
        self.assertEqual(programs, ["wslpath"])

        # The older provider spelling is the same provider and refuses identically.
        legacy_programs, legacy_refusal, legacy_code = attempt("\\\\WSL$\\Ubuntu\\srv\\agentic-sdlc")
        self.assertEqual(legacy_code, 2)
        self.assertIn("\\\\wsl$", legacy_refusal)
        self.assertEqual(legacy_programs, ["wslpath"])

        # POSITIVE CONTROL: a checkout on a Windows filesystem is admitted and BOTH legs run, so the
        # refusals above are about the provider rather than about a harness that could only refuse.
        # The order also pins the check as up-front: the translation precedes the WSL leg.
        admitted_programs, admitted_stderr, admitted_code = attempt("C:\\repo")
        self.assertEqual(admitted_code, 0)
        self.assertEqual(admitted_stderr, "")
        self.assertEqual(admitted_programs, ["wslpath", "mise", "powershell.exe"])

    def test_signal_terminated_host_cannot_report_success(self) -> None:
        exits = iter((-9, 0))

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
