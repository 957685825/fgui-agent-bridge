"""输入恢复的宿主隔离回归，以及慢响应期间的请求边界。"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fairygui_agent.bridge_client import BridgeClient
from fairygui_agent.project_locator import ProjectContext

ROOT = Path(__file__).resolve().parents[1]


class TestInputRecovery(unittest.TestCase):
    def test_compiled_plugin_with_host(self) -> None:
        result = subprocess.run(
            ["node", str(ROOT / "tests/fixtures/input_recovery_host.cjs"), str(ROOT / "plugin/main.js")],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("checks passed", result.stdout)

    def test_slow_response_keeps_waiting_for_the_same_request(self) -> None:
        # 假时钟跨过旧版尝试打开窗口的时点，确认同一个队列请求仍可完成。
        with tempfile.TemporaryDirectory() as folder:
            context = ProjectContext(Path(folder) / "test.fairy")
            locator = MagicMock()
            locator.resolve.return_value = context
            editor_process = MagicMock()
            client = BridgeClient(locator, editor_process)
            clock = [0.0]

            def sleep(seconds: float) -> None:
                clock[0] += seconds
                if clock[0] >= 1.3:
                    requests = list((context.queue_root / "requests").glob("*.json"))
                    self.assertEqual(len(requests), 1)
                    request = json.loads(requests[0].read_text(encoding="utf-8"))
                    response = context.queue_root / "responses" / requests[0].name
                    response.write_text(json.dumps({"id": request["id"], "ok": True}), encoding="utf-8")

            with patch.object(client, "ensure_ready", return_value={}), patch(
                "fairygui_agent.bridge_client.time.monotonic", side_effect=lambda: clock[0]
            ), patch("fairygui_agent.bridge_client.time.sleep", side_effect=sleep):
                response = client.call_raw("get_tree", timeout=3.0)

            self.assertTrue(response["ok"])
            self.assertEqual(editor_process.mock_calls, [])


if __name__ == "__main__":
    unittest.main()
