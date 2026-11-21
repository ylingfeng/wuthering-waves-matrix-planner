"""Check per-platform bundle contents without creating release archives."""
from pathlib import Path
from contextlib import closing
import json
import shutil
import subprocess
import tempfile
import unittest

from tools.release_static import ROOT, build_platform_bundle, read_development_defaults

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


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

    def test_development_profile_requires_saved_schedule_and_excludes_store_metadata(self):
        profile=self.root/'profile.json'
        config={'format':'matrix-planner-v2','characters':[],'teams':[],
                'schedules':{'plans':[{'name':'我的排表'}]},'preferences':{'schedule-count-unowned':True},
                'ignored_private_field':'not exported'}
        profile.write_text(json.dumps({'revision':'private revision','config':config}),encoding='utf-8-sig')
        before=profile.read_bytes()
        snapshot=read_development_defaults(profile)
        self.assertEqual(snapshot['schedules'],config['schedules'])
        self.assertEqual(snapshot['preferences'],config['preferences'])
        self.assertNotIn('revision',snapshot)
        self.assertNotIn('ignored_private_field',snapshot)
        self.assertEqual(profile.read_bytes(),before)
        del config['schedules']
        profile.write_text(json.dumps({'config':config}),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'排表'):
            read_development_defaults(profile)
        with self.assertRaises(FileNotFoundError):
            read_development_defaults(self.root/'missing.json')

    @unittest.skipIf(sync_playwright is None, 'Playwright is not installed')
    def test_bundle_initial_state_matches_saved_profile_and_preserves_browser_changes(self):
        with sync_playwright() as pw, closing(pw.chromium.launch(channel='chrome',headless=True)) as browser:
            context=browser.new_context()
            page=context.new_page()
            page.goto((ROOT/'web/team_planner/index.html').as_uri())
            page.wait_for_function('typeof state!=="undefined" && !!state')
            config=page.evaluate('''()=>{
                const config=LocalPlanner.exportConfig(state);
                Object.assign(config.characters[0],{available:false,chain:3,weight:2.5,weekly:4});
                config.teams[0].enabled=true;config.teams[0].locked=true;config.teams[0].user_weight=3.5;
                config.teams.splice(1,1);
                const custom=structuredClone(config.teams[0]);custom.id='custom-release-team';
                custom.members=['守岸人','白芷','卜灵'];custom.locked=false;
                config.teams.push(custom);
                const plan=structuredClone(config.schedules.plans[0]);plan.id='saved-copy';plan.name='开发排表';
                plan.cells[0].label='已调整';config.schedules.plans.push(plan);config.schedules.active_id=plan.id;
                config.preferences['schedule-count-unowned']=true;
                return config;
            }''')
            profile=self.root/'saved-profile.json'
            profile.write_text(json.dumps({'revision':'private','config':config}),encoding='utf-8')
            snapshot=read_development_defaults(profile)
            source_seed=(ROOT/'web/team_planner/seed.js').read_bytes()
            bundle=build_platform_bundle(self.root/'initial', 'macOS', '9.9.9',self.notes,
                                         self.changelog,initial_config=snapshot)
            context.close()
            context=browser.new_context()
            page=context.new_page()
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto((bundle/'鸣潮矩阵配队.html').as_uri())
            page.wait_for_function('typeof state!=="undefined" && !!state')
            self.assertTrue(page.locator('#tour-skip').is_visible())
            actual=page.evaluate('LocalPlanner.exportConfig(state)')
            self.assertEqual(actual,snapshot)
            self.assertEqual(page.evaluate('state.teams.find(t=>t.id===state.teams[0].id).default_priority'),
                             page.evaluate('PLANNER_SEED.teams[0].default_priority'))
            page.evaluate('''()=>{
                state.characters[0].weight=7;state.teams[0].user_weight=8;
                schedulePlan().name='使用者自己的排表';persistLocally();
            }''')
            # Changing the distributed snapshot must not overwrite saved browser settings.
            page.add_init_script("document.addEventListener('DOMContentLoaded',()=>{PLANNER_SEED.initial_config.characters[0].weight=9}, {capture:true})")
            page.reload();page.wait_for_function('typeof state!=="undefined" && !!state')
            self.assertEqual(page.evaluate('state.characters[0].weight'),7)
            self.assertEqual(page.evaluate('state.teams[0].user_weight'),8)
            self.assertEqual(page.evaluate('schedulePlan().name'),'使用者自己的排表')
            self.assertEqual((ROOT/'web/team_planner/seed.js').read_bytes(),source_seed)
            self.assertFalse((bundle/'web/personal_config.json').exists())
            self.assertEqual(errors,[])
            context.close()


if __name__ == '__main__':
    unittest.main()
