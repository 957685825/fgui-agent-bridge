"""在临时副本验证组件归属、复用和失败边界，不接触编辑器或业务工程。"""

from __future__ import annotations

import importlib.util
import contextlib
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
SCRIPT = ROOT / ".agents/skills/fgui-agent-bridge/scripts/check_component_structure.py"
spec = importlib.util.spec_from_file_location("component_check", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ComponentStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="fgui-component-check-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "demo"
        shutil.copytree(ROOT / "tests/fixtures/componentization", self.project)
        self.plan_path = self.project / "structure-plan.json"
        self.plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        self.popup = self.project / "assets/layout_demo/PopupDemo.xml"

    def replace(self, relative: str, before: str, after: str) -> None:
        path = self.project / relative
        text = path.read_text(encoding="utf-8")
        self.assertIn(before, text)
        path.write_text(text.replace(before, after), encoding="utf-8")

    def test_sample_and_cli_are_read_only(self) -> None:
        before = {path.relative_to(self.project): path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        result = checker.check_structure(self.project / "FairyGUI.fairy", self.plan)
        self.assertEqual(len(result["checkedComponents"]), 4)
        self.assertFalse(result["editorVerified"])
        command = [sys.executable, str(SCRIPT), "--project", str(self.project), "--plan", str(self.plan_path)]
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertTrue(json.loads(process.stdout)["ok"])
        after = {path.relative_to(self.project): path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.project / ".agent").exists())
        self.plan_path.write_text('{"root": "a", "root": "b", "components": {}}', encoding="utf-8")
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 1)
        self.assertIn("重复键", json.loads(process.stdout)["error"])

    def test_flattening_groups_wrong_reuse_and_duplicate_names_fail(self) -> None:
        original = self.popup.read_text(encoding="utf-8")
        cases = [
            ('<component id="amount"', '<group id="amount"', "必须引用指定独立组件"),
            ('name="amount"', 'name="flatAmount"', "节点归属不符"),
            ('name="badge"', 'name="amount"', "名称缺失或重复"),
            ('src="amount01"', 'src="badge001"', "必须引用指定独立组件"),
            ('src="amount01"', 'src="missing"', "组件引用不存在"),
            ('id="rewardB" name="rewardB" src="reward01" pkg="shared01"',
             'id="rewardB" name="rewardB" src="badge001"', "必须引用指定独立组件"),
            ('xy="24,24"', 'xy="24.5,24"', "整数对"),
            ('</displayList>', '<text id="flat" name="flatValue" xy="0,0"/></displayList>', "节点归属不符"),
        ]
        for before, after, error in cases:
            with self.subTest(error=error, after=after):
                self.popup.write_text(original.replace(before, after), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, error):
                    checker.check_structure(self.project, self.plan)

    def test_empty_shell_and_broken_local_contracts_fail(self) -> None:
        path = self.project / "assets/layout_demo/parts/AmountDisplay.xml"
        original = path.read_text(encoding="utf-8")
        cases = [
            ('<displayList>', '<displayList/> <unused>'),
            ('controller="displayState"', 'controller="outsideState"'),
            ('target="value"', 'target="outsideNode"'),
            ('<gearDisplay', '<relation target="outsideNode" sidePair="width-width"/><gearDisplay'),
            ('name="value"', 'name="label"'),
            ('id="value"', 'id="label"'),
        ]
        for before, after in cases:
            with self.subTest(after=after):
                changed = original.replace(before, after)
                if "<unused>" in changed:
                    changed = changed.replace("</displayList>", "</unused>")
                path.write_text(changed, encoding="utf-8")
                with self.assertRaises(ValueError):
                    checker.check_structure(self.project, self.plan)

    def test_missing_file_and_cross_package_export_fail(self) -> None:
        manifest = "assets/layout_shared/package.xml"
        self.replace(manifest, 'exported="true"', 'exported="false"')
        with self.assertRaisesRegex(ValueError, "跨包组件未导出"):
            checker.check_structure(self.project, self.plan)
        self.replace(manifest, 'exported="false"', 'exported="true"')
        (self.project / "assets/layout_shared/RewardItem.xml").unlink()
        with self.assertRaises(OSError):
            checker.check_structure(self.project, self.plan)

    def test_unused_component_and_cycle_in_reused_component_fail(self) -> None:
        self.plan["components"]["layout_demo/Unused"] = {}
        with self.assertRaisesRegex(ValueError, "未被根组件引用"):
            checker.check_structure(self.project, self.plan)
        del self.plan["components"]["layout_demo/Unused"]
        del self.plan["components"]["layout_shared/RewardItem"]
        self.replace("assets/layout_shared/RewardItem.xml", "</displayList>",
                     '<component id="back" name="back" pkg="layout01" src="popup001" xy="0,0"/></displayList>')
        with self.assertRaisesRegex(ValueError, "循环引用"):
            checker.check_structure(self.project, self.plan)

    def test_ids_override_filename_and_plain_decoration_needs_no_wrapper(self) -> None:
        self.replace("assets/layout_demo/PopupDemo.xml", 'fileName="parts/AmountDisplay.xml"', 'fileName="fake.xml"')
        self.assertTrue(checker.check_structure(self.project, self.plan)["ok"])
        self.popup.write_text('<component size="100,100"><displayList><graph id="line" name="line" xy="0,0" size="100,2"/></displayList></component>', encoding="utf-8")
        plan = {"root": "layout_demo/PopupDemo", "components": {"layout_demo/PopupDemo": {"line": "graph"}}}
        self.assertTrue(checker.check_structure(self.project, plan)["ok"])

    def test_invalid_plan_external_paths_and_dtd_fail(self) -> None:
        for invalid in [None, {}, {"root": [], "components": {"a/B": {}}},
                        {"root": "a/B", "components": {"a/B": {"child": "component"}}}]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                checker.check_structure(self.project, invalid)
        self.replace("assets/layout_demo/package.xml", 'path="/parts/"', 'path="/../../"')
        with self.assertRaisesRegex(ValueError, "包内 XML"):
            checker.check_structure(self.project, self.plan)
        self.replace("assets/layout_demo/package.xml", 'path="/../../"', 'path="/parts/"')
        self.popup.write_text('<!DOCTYPE component [<!ENTITY title "hidden">]><component/>', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "DTD"):
            checker.check_structure(self.project, self.plan)

    def test_skill_resources_sync_and_run_without_bridge_installation(self) -> None:
        skill_source = SCRIPT.parents[1]
        destination = Path(self.temp.name) / "installed-skill"
        entries = build_entries(skill_source, destination)
        with contextlib.redirect_stdout(io.StringIO()):
            sync_entries(entries, plugin_count=0, apply=False)
            self.assertFalse(destination.exists())
            sync_entries(entries, plugin_count=0, apply=True)
        self.assertTrue((destination / "references/componentization.md").is_file())
        self.assertFalse((destination / "scripts/__pycache__").exists())
        process = subprocess.run(
            [sys.executable, str(destination / "scripts/check_component_structure.py"),
             "--project", str(self.project), "--plan", str(self.plan_path)],
            cwd=self.temp.name, capture_output=True, text=True, check=False,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertTrue(json.loads(process.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
