"""布局快照几何、原生图像传输及旧插件兼容边界。"""
from __future__ import annotations

import asyncio
import base64
import copy
import io
import json
import struct
import subprocess
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp.types import ImageContent, TextContent
from fairygui_agent import cli, mcp_server
from fairygui_agent.bridge_client import BridgeClient, BridgeError
from fairygui_agent.layout_snapshot import encode_snapshot_png

ROOT = Path(__file__).resolve().parents[1]
# 下排蓝色与半透明红色，上排绿色与透明白色；检测行翻转和 RGBA 不失真。
PIXELS = bytes([0, 0, 255, 255, 255, 0, 0, 128, 0, 255, 0, 255, 255, 255, 255, 0])
CAPTURE = {"width": 2, "height": 2, "format": "RGBA32", "rowOrder": "bottom-up", "rgbaBase64": base64.b64encode(PIXELS).decode()}


class LayoutSnapshotTests(unittest.TestCase):
    def test_compiled_plugin_geometry_and_capture_lifecycle(self):
        result = subprocess.run(["node", str(ROOT / "tests/fixtures/layout_snapshot_host.cjs"), str(ROOT / "plugin/main.js")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("checks passed", result.stdout)

    def test_png_rows_dimensions_alpha_and_crc(self):
        png = encode_snapshot_png(CAPTURE)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        offset = 8
        chunks = {}
        while offset < len(png):
            size = struct.unpack_from("!I", png, offset)[0]
            kind, data = png[offset + 4:offset + 8], png[offset + 8:offset + 8 + size]
            crc = struct.unpack_from("!I", png, offset + 8 + size)[0]
            self.assertEqual(crc, zlib.crc32(kind + data))
            chunks[kind] = data
            offset += size + 12
        self.assertEqual(struct.unpack("!2I5B", chunks[b"IHDR"]), (2, 2, 8, 6, 0, 0, 0))
        self.assertEqual(zlib.decompress(chunks[b"IDAT"]), b"\x00" + PIXELS[8:] + b"\x00" + PIXELS[:8])

    def test_invalid_capture_is_rejected_before_encoding(self):
        for fields in ({"width": True}, {"width": 0}, {"width": 4097}, {"width": 4096, "height": 4096},
                       {"rowOrder": "top-down"}, {"format": "RGB24"}, {"rgbaBase64": "!" * 24},
                       {"rgbaBase64": base64.b64encode(PIXELS + b"extra").decode()}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                encode_snapshot_png({**CAPTURE, **fields})

    def test_mcp_native_content_and_metadata_without_raw_pixels(self):
        fake = MagicMock()
        fake.call.return_value = {"canvas": {"width": 2, "height": 2}, "capture": CAPTURE}
        with patch.object(mcp_server, "_client", fake):
            content = mcp_server.fgui_get_layout_snapshot(max_depth=3)
        fake.call.assert_called_once_with("get_layout_snapshot", {"maxDepth": 3, "includeImage": True})
        self.assertIsInstance(content[0], TextContent)
        self.assertNotIn("rgbaBase64", content[0].text)
        self.assertIsInstance(content[1], ImageContent)
        self.assertEqual(base64.b64decode(content[1].data), encode_snapshot_png(CAPTURE))
        # 经过实际 FastMCP 分发，仍返回图片内容，不能被包装成 JSON 字符串。
        with patch.object(mcp_server, "_client", fake):
            wire_content = asyncio.run(mcp_server.mcp.call_tool("fgui_get_layout_snapshot", {"max_depth": 3}))
        self.assertTrue(any(isinstance(item, ImageContent) for item in wire_content))
        fake.call.return_value = {"canvas": {"width": 2, "height": 2}}
        with patch.object(mcp_server, "_client", fake):
            self.assertEqual(len(mcp_server.fgui_get_layout_snapshot(include_image=False)), 1)
            with self.assertRaisesRegex(ValueError, "未返回原生预览"):
                mcp_server.fgui_get_layout_snapshot()

    def test_cli_exports_png_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "native.png"
            fake = MagicMock()
            fake.call_raw.return_value = {"ok": True, "result": {"capture": copy.deepcopy(CAPTURE)}}
            with patch.object(cli, "BridgeClient", return_value=fake), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                with patch("sys.argv", ["fgui-agent", "layout", "--output", str(output)]):
                    self.assertEqual(cli.main(), 0)
                self.assertEqual(output.read_bytes(), encode_snapshot_png(CAPTURE))
                with patch("sys.argv", ["fgui-agent", "layout", "--output", str(output)]):
                    self.assertEqual(cli.main(), 1)
            fake.call_raw.assert_called_once_with("get_layout_snapshot", {"maxDepth": 12, "includeImage": True}, timeout=10.0)

    def test_old_plugin_fails_before_writing_new_request(self):
        client = BridgeClient.__new__(BridgeClient)
        client.project_context = lambda: None
        client.ensure_ready = lambda: {"capabilities": ["get_tree"]}
        with self.assertRaisesRegex(BridgeError, "0.9.4"):
            client.call_raw("get_layout_snapshot")


if __name__ == "__main__":
    unittest.main()
