"""在临时皮肤副本核对布局差异和精确确认边界，不操作编辑器或业务界面。"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.sync_to_project import build_entries, sync_entries

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".agents/skills/fgui-agent-bridge/scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("reskin_check", SCRIPTS / "compare_skin_layout.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
sys.path.pop(0)


class ReskinLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="fgui-reskin-")
        self.addCleanup(self.temp.cleanup)
        self.reference = Path(self.temp.name) / "old"
        self.target = Path(self.temp.name) / "new"
        for project in (self.reference, self.target):
            shutil.copytree(ROOT / "tests/fixtures/componentization", project)
        self.roots = ["layout_demo/PopupDemo"]
        self.popup = self.target / "assets/layout_demo/PopupDemo.xml"

    def result(self, reviews=None) -> dict:
        return checker.compare(self.reference / "FairyGUI.fairy", self.target, self.roots, reviews)

    def change(self, path: Path, before: str, after: str) -> None:
        content = path.read_text(encoding="utf-8")
        self.assertIn(before, content)
        path.write_text(content.replace(before, after), encoding="utf-8")

    def test_same_skin_and_cosmetic_changes_are_read_only(self) -> None:
        self.change(self.popup, 'fillColor="#202838"', 'fillColor="#112233"')
        label = self.target / "assets/layout_demo/parts/AmountDisplay.xml"
        self.change(label, 'text="Amount"', 'text="长语言文案"')
        before = {p: p.read_bytes() for p in self.target.rglob("*") if p.is_file()}
        result = self.result()
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["checkedComponents"]), 4)
        self.assertFalse(result["editorVerified"])
        self.assertFalse(result["runtimeVerified"])
        self.assertEqual(before, {p: p.read_bytes() for p in self.target.rglob("*") if p.is_file()})

    def test_anchor_mount_list_and_state_differences_are_reported(self) -> None:
        self.change(self.popup, 'size="600,360"', 'size="600,360" pivot="0.5,0.5" anchor="true"')
        self.change(self.popup, 'xy="24,190"', 'xy="30,190"')
        self.change(self.popup, '</displayList>', '<list id="tasks" name="tasks" xy="0,0" size="100,80" lineGap="20" defaultItem="ui://shared01reward01"><item url="ui://shared01reward01"/></list></displayList>')
        amount = self.target / "assets/layout_demo/parts/AmountDisplay.xml"
        self.change(amount, 'pages="0,1"', 'pages="1"')
        result = self.result()
        self.assertFalse(result["ok"])
        fields = {(d["node"], d["property"]) for d in result["differences"]}
        self.assertTrue({("$root", "anchor"), ("rewardA", "xy"), ("tasks", "lineGap"), ("value", "states")} <= fields)
        url = next(d for d in result["differences"] if d["node"] == "tasks" and d["property"] == "defaultItem")
        self.assertEqual(url["after"], "layout_shared/RewardItem")

    def test_default_list_item_components_are_recursively_compared(self) -> None:
        for project in (self.reference, self.target):
            popup = project / "assets/layout_demo/PopupDemo.xml"
            self.change(popup, '</displayList>', '<list id="tasks" name="tasks" xy="0,0"><item url="ui://layout01badge001"/></list></displayList>')
            # 去掉普通实例，确保组件仅通过列表默认项可达。
            self.change(popup, 'src="badge001"', 'src="amount01"')
        self.change(self.target / "assets/layout_demo/parts/BonusBadge.xml", 'size="124,128"', 'size="124,148"')
        result = self.result()
        self.assertTrue(any(d["component"] == "layout_demo/parts/BonusBadge" and d["property"] == "size" for d in result["differences"]))

    def test_reviews_match_exact_values_and_need_reasons(self) -> None:
        self.change(self.popup, 'xy="24,190"', 'xy="30,190"')
        changes = self.result()["differences"]
        reviews = [{**change, "reason": "按设计图测量后调整奖励挂点"} for change in changes]
        self.assertTrue(self.result(reviews)["ok"])
        self.assertFalse(self.result(reviews[:0])["ok"])
        for invalid in ([{**reviews[0], "reason": " "}], [*reviews, reviews[0]], [{**reviews[0], "after": "31,190"}]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.result(invalid)

    def test_component_references_use_ids_not_file_names(self) -> None:
        self.change(self.popup, 'src="amount01"', 'src="badge001"')
        result = self.result()
        self.assertTrue(any(d["property"] == "component" and d["after"] == "layout_demo/parts/BonusBadge" for d in result["differences"]))
        self.change(self.popup, 'src="badge001"', 'src="missing"')
        with self.assertRaisesRegex(ValueError, "组件引用不存在"):
            self.result()

    def test_image_loader_is_artwork_but_its_mount_and_state_remain_checked(self) -> None:
        for project in (self.reference, self.target):
            popup = project / "assets/layout_demo/PopupDemo.xml"
            self.change(popup, '</displayList>', '<loader id="icon" name="icon" xy="24,24" size="80,80" url="ui://layout01picture1"/></displayList>')
        self.change(self.popup, 'url="ui://layout01picture1"', 'url="ui://layout01picture2"')
        self.assertTrue(self.result()["ok"])
        self.change(self.popup, 'size="80,80"', 'size="90,80"')
        self.assertEqual(self.result()["differences"], [{"component": self.roots[0], "node": "icon", "property": "size", "before": "80,80", "after": "90,80"}])

    def test_cycles_and_unexported_list_resources_are_rejected(self) -> None:
        reward = self.target / "assets/layout_shared/RewardItem.xml"
        self.change(reward, '</displayList>', '<component id="back" name="back" src="popup001" pkg="layout01" xy="0,0"/></displayList>')
        with self.assertRaisesRegex(ValueError, "循环引用"):
            self.result()
        shutil.copyfile(self.reference / "assets/layout_shared/RewardItem.xml", reward)
        self.change(self.target / "assets/layout_shared/package.xml", 'exported="true"', 'exported="false"')
        with self.assertRaisesRegex(ValueError, "跨包组件未导出"):
            self.result()

    def test_invalid_source_never_passes(self) -> None:
        original = self.popup.read_text(encoding="utf-8")
        for before, after in [('xy="24,190"', 'xy="24.5,190"'), ('id="rewardB"', 'id="rewardA"'),
                              ('id="rewardB"', 'id="$root"'),
                              ('src="amount01"', 'src="missing"')]:
            with self.subTest(after=after):
                self.popup.write_text(original.replace(before, after), encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.result()
        self.popup.write_text(original, encoding="utf-8")
        (self.target / "assets/layout_shared/RewardItem.xml").unlink()
        with self.assertRaises(OSError):
            self.result()

    def test_installed_cli_exit_codes_and_duplicate_review_keys(self) -> None:
        installed = Path(self.temp.name) / "skill"
        with contextlib.redirect_stdout(io.StringIO()):
            sync_entries(build_entries(SCRIPTS.parent, installed), 0, apply=True)
        command = [sys.executable, str(installed / "scripts/compare_skin_layout.py"),
                   "--reference", str(self.reference), "--target", str(self.target),
                   "--component", self.roots[0]]
        clean = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        self.change(self.popup, 'xy="24,190"', 'xy="30,190"')
        changed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(changed.returncode, 1)
        self.assertTrue(json.loads(changed.stdout)["unreviewed"])
        review = Path(self.temp.name) / "review.json"
        review.write_text('[{"reason":"a","reason":"b"}]', encoding="utf-8")
        invalid = subprocess.run([*command, "--review", str(review)], capture_output=True, text=True, check=False)
        self.assertEqual(invalid.returncode, 1)
        self.assertIn("重复键", json.loads(invalid.stdout)["error"])
        self.assertFalse((self.target / ".agent").exists())
        self.assertFalse(list(installed.rglob("__pycache__")))


if __name__ == "__main__":
    unittest.main()
