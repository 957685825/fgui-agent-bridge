"""用小型真实 XML 夹具验证百分比/平铺检查，不依赖 Editor。"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '.agents/skills/fgui-agent-bridge/scripts/check_progress_bars.py'
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location('progress_check', SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.package = self.project / 'assets/demo'
        self.package.mkdir(parents=True)
        (self.package / 'package.xml').write_text('''<packageDescription id="demo0001"><resources>
<component id="row" name="Row.xml"/><component id="bar" name="Bar.xml"/>
<component id="fill" name="Fill.xml"/><image id="img" name="fill.png" scale="tile"/>
</resources></packageDescription>''')
        (self.package / 'fill.png').write_bytes(b'fixture')
        (self.package / 'Fill.xml').write_text('<component><displayList><image name="fill" src="img"/></displayList></component>')
        (self.package / 'Bar.xml').write_text('<component extention="ProgressBar"><displayList><component name="bar" src="fill"/></displayList><ProgressBar/></component>')
        self.row(30, '30%')

    def row(self, value, label, maximum=100):
        (self.package / 'Row.xml').write_text(f'<component><displayList><component name="progress_bar" src="bar"><ProgressBar value="{value}" max="{maximum}"/></component><text name="progress_text" text="{label}"/></displayList></component>')

    def check(self):
        return checker.check_progress(self.project, ['demo/Row'])

    def test_boundaries_and_count_labels(self):
        for value in [0, .5, 30, 100]:
            with self.subTest(value=value):
                self.row(value, f'{value}%')
                self.assertTrue(self.check()['ok'])
        self.row(30, '3/10')
        self.assertTrue(self.check()['ok'])
        for value, label, maximum in [(101, '101%', 100), (-1, '0%', 100), (30, '30%', 10), (100, '30%', 100)]:
            with self.subTest(value=value, label=label, maximum=maximum):
                self.row(value, label, maximum)
                self.assertFalse(self.check()['ok'])
        self.row('NaN', '0%')
        with self.assertRaisesRegex(ValueError, '有限'):
            self.check()

    def test_texture_missing_and_cycles(self):
        manifest = self.package / 'package.xml'
        original = manifest.read_text()
        manifest.write_text(original.replace('scale="tile"', 'scale="9grid"'))
        self.assertFalse(self.check()['ok'])
        manifest.write_text(original)
        (self.package / 'fill.png').unlink()
        with self.assertRaisesRegex(ValueError, '文件不存在'):
            self.check()
        (self.package / 'Fill.xml').write_text('<component><displayList><component name="loop" src="bar"/></displayList></component>')
        with self.assertRaisesRegex(ValueError, '循环'):
            self.check()

    def test_exact_art_exception_requires_reason_and_still_checks_file(self):
        manifest = self.package / 'package.xml'
        manifest.write_text(manifest.read_text().replace('scale="tile"', 'scale="9grid" scale9grid="2,0,6,10"'))
        exception = {'demo0001/img': '原图自带端点，平铺会重复圆角'}
        result = checker.check_progress(self.project, ['demo/Row'], exception)
        self.assertTrue(result['ok'])
        self.assertEqual(result['reviewedNineGridImages'], exception)
        self.assertFalse(checker.check_progress(self.project, ['demo/Row'], {'demo0001/wrong': 'wrong id'})['ok'])
        with self.assertRaisesRegex(ValueError, '素材原因'):
            checker.check_progress(self.project, ['demo/Row'], {'demo0001/img': ''})
        (self.package / 'fill.png').unlink()
        with self.assertRaisesRegex(ValueError, '文件不存在'):
            checker.check_progress(self.project, ['demo/Row'], exception)

    def test_read_only_cli_and_empty_scope(self):
        before = {p: p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        process = subprocess.run([sys.executable, str(SCRIPT), '--project', str(self.project), '--component', 'demo/Row'], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertFalse(json.loads(process.stdout)['runtimeVerified'])
        self.assertEqual(before, {p: p.read_bytes() for p in self.project.rglob('*') if p.is_file()})
        self.assertFalse(checker.check_progress(self.project, ['demo/Fill'])['ok'])
        with self.assertRaisesRegex(ValueError, '未登记'):
            checker.check_progress(self.project, ['demo/Missing'])


if __name__ == '__main__':
    unittest.main()
