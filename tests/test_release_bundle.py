"""Check per-platform bundle contents without creating release archives."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.release_static import ROOT, build_platform_bundle


class PlatformBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='planner-bundle ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = self.root / 'source'
        self.site.mkdir()
        (self.site / 'index.html').write_text('<!doctype html><title>Planner</title>', encoding='utf-8')
        shutil.copyfile(ROOT / 'web/team_planner/favicon.ico', self.site / 'favicon.ico')
        self.changelog = '# 更新日志\r\n\r\n## v9.9.9\r\n\r\n- 测试\r\n'.encode('utf-8')
        self.notes = '# v9.9.9\n\n- 测试\n'

    def build(self, platform):
        bundle = build_platform_bundle(self.root / platform, platform, '9.9.9', self.notes,
                                       self.changelog, self.site)
        self.assertEqual((bundle / 'web/CHANGELOG.md').read_bytes(), self.changelog)
        self.assertEqual((bundle / 'web/RELEASE_NOTES.md').read_text(encoding='utf-8'), self.notes)
        self.assertEqual((bundle / 'web/index.html').read_bytes(), (self.site / 'index.html').read_bytes())
        self.assertEqual(list(self.root.rglob('*.zip')), [])
        return bundle

    def test_macos_has_only_html_entry_and_relative_page(self):
        bundle = self.build('macOS')
        self.assertEqual({p.name for p in bundle.iterdir()}, {'鸣潮矩阵配队.html', 'web'})
        entry = (bundle / '鸣潮矩阵配队.html').read_text(encoding='utf-8')
        self.assertIn('content="0;url=web/index.html"', entry)
        self.assertIn('macOS', (bundle / 'web/使用说明.txt').read_text(encoding='utf-8-sig'))

    @unittest.skipUnless(Path(r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe').exists(),
                         'Windows .NET Framework compiler required')
    def test_windows_has_only_exe_entry_and_resolves_own_page(self):
        bundle = self.build('Windows')
        self.assertEqual({p.name for p in bundle.iterdir()}, {'鸣潮矩阵配队.exe', 'web'})
        subprocess.run([str(bundle / '鸣潮矩阵配队.exe'), '--check'], check=True)
        self.assertIn('Windows', (bundle / 'web/使用说明.txt').read_text(encoding='utf-8-sig'))


if __name__ == '__main__':
    unittest.main()
