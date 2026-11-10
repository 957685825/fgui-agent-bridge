"""外部资源自动刷新直接执行插件编译产物的宿主回归。"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestAssetRefresh(unittest.TestCase):
    def test_compiled_plugin_with_host(self):
        result = subprocess.run(
            ["node", str(ROOT / "tests/fixtures/asset_refresh_host.cjs"), str(ROOT / "plugin/main.js")],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("checks passed", result.stdout)
