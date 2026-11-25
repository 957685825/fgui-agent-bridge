"""进程检查独立于工程心跳，连接失败时保持用户的现有窗口。"""

from __future__ import annotations

import json
import plistlib
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, call, patch

from fairygui_agent import PROTOCOL_VERSION
from fairygui_agent.bridge_client import REQUIRED_CAPABILITIES, BridgeClient, BridgeError
from fairygui_agent.editor_process import EditorProcess
from fairygui_agent.project_locator import ProjectLocator


class EditorProcessTests(unittest.TestCase):
    def test_mac_probe_distinguishes_running_stopped_and_unavailable(self) -> None:
        module = "fairygui_agent.editor_process"
        with tempfile.TemporaryDirectory() as folder:
            app = Path(folder) / "Renamed.app"
            (app / "Contents").mkdir(parents=True)
            (app / "Contents" / "Info.plist").write_bytes(
                plistlib.dumps({"CFBundleExecutable": "Fairy.GUI"})
            )
            process = EditorProcess(str(app))
            for code, stdout, stderr, expected in (
                (0, "123\n", "", True),
                (1, "", "", False),
                (1, "", "Cannot get process list", None),
                (2, "", "Denied", None),
            ):
                with self.subTest(code=code, stderr=stderr), patch(module + ".sys.platform", "darwin"), patch(
                    module + ".subprocess.run", return_value=Mock(returncode=code, stdout=stdout, stderr=stderr)
                ) as run:
                    self.assertIs(process.is_running(), expected)
                    self.assertEqual(run.call_args.args[0], ["/usr/bin/pgrep", "-x", "--", r"Fairy\.GUI"])

    def test_windows_checks_exact_image_names_and_handles_timeout(self) -> None:
        module = "fairygui_agent.editor_process"
        with patch(module + ".sys.platform", "win32"), patch(
            module + ".subprocess.CREATE_NO_WINDOW", 0, create=True
        ), patch(module + ".subprocess.run") as run:
            process = EditorProcess("MyEditor.exe")
            run.return_value = Mock(returncode=0, stdout='"MyEditorHelper.exe","10"\n')
            self.assertIs(process.is_running(), False)
            run.return_value.stdout += '"MYEDITOR.EXE","11"\n'
            self.assertIs(process.is_running(), True)
            run.side_effect = subprocess.TimeoutExpired("tasklist", 2)
            self.assertIsNone(process.is_running())


class BridgeConnectionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        project = Path(temporary.name) / "test.fairy"
        project.touch()
        self.process = Mock()
        self.client = BridgeClient(ProjectLocator(str(project)), self.process, timeout=0.5)
        self.queue = project.parent / ".agent"
        self.queue.mkdir()

    def write_heartbeat(self, age: float) -> dict[str, object]:
        status = {
            "timestamp": (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat(),
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": sorted(REQUIRED_CAPABILITIES),
        }
        (self.queue / "status.json").write_text(json.dumps(status), encoding="utf-8")
        return status

    def test_status_of_open_editor_with_stale_project_and_without_project(self) -> None:
        self.process.is_running.return_value = True
        self.write_heartbeat(60)
        status = self.client.describe_status()
        self.assertIs(status["editorRunning"], True)
        self.assertIs(status["online"], False)
        with patch.object(self.client, "project_context", side_effect=RuntimeError("请选择工程")):
            status = self.client.describe_status()
        self.assertIs(status["editorRunning"], True)
        self.assertIsNone(status["project"])
        self.assertEqual(status["projectError"], "请选择工程")
        json.dumps(status, allow_nan=False)

    def test_stale_heartbeat_recovers_using_already_running_editor(self) -> None:
        self.process.is_running.return_value = True
        self.write_heartbeat(60)
        with patch("fairygui_agent.bridge_client.time.sleep", side_effect=lambda _: self.write_heartbeat(0)):
            status = self.client.ensure_ready()
        self.assertEqual(status["protocolVersion"], PROTOCOL_VERSION)
        self.assertEqual(self.process.mock_calls, [call.is_running()])

    def test_offline_request_reports_process_state_before_enqueue(self) -> None:
        for running, message in (
            (True, "已检测到 FairyGUI Editor 进程"),
            (False, "未检测到 FairyGUI Editor 进程"),
            (None, "系统无法确认 FairyGUI Editor 进程状态"),
        ):
            with self.subTest(running=running):
                self.process.reset_mock()
                self.process.is_running.return_value = running
                with patch("fairygui_agent.bridge_client.time.monotonic", side_effect=(0.0, 1.0)):
                    with self.assertRaisesRegex(BridgeError, message + r".*test\.fairy"):
                        self.client.call("ping")
                self.assertEqual(self.process.mock_calls, [call.is_running()])
                self.assertFalse((self.queue / "requests").exists())
