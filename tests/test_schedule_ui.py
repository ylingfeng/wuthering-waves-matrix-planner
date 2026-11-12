"""Manual schedule regressions, using isolated storage and temporary HTTP profiles."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from tools.planner_dev_server import Handler, PersonalStore

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(sync_playwright is None, 'Playwright is not installed')
class ScheduleUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(channel='chrome', headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width':1440,'height':1000})
        self.page = self.context.new_page()
        self.page.set_default_timeout(6000)
        self.errors = []
        self.page.on('pageerror', lambda error:self.errors.append(str(error)))
        self.page.goto((ROOT/'web/team_planner/schedule/index.html').as_uri())
        self.page.locator('#tour-skip').click()

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def slot(self, row, column=1):
        return self.page.locator(f'[data-schedule-row="{row}"][data-schedule-column="c{column}"]')

    def fixed(self, row, name):
        return self.page.locator(f'[data-row-header="{row}"] [data-fixed-card="{name}"]')

    def template(self, name):
        return self.page.locator(f'[data-bank-name="{name}"]')

    def place(self, name, row, column=1):
        self.template(name).click()
        self.slot(row,column).locator('[data-cell-place]').click()

    def choose(self, selector, value):
        select = self.page.locator(selector)
        label = select.get_attribute('aria-label')
        text = select.locator('option').evaluate_all('(options,value)=>options.find(o=>o.value===value).textContent',value)
        self.page.get_by_role('combobox',name=label,exact=True).click()
        self.page.get_by_role('option',name=text,exact=True).click()

    def drag(self, source, target):
        source.evaluate("el=>el.scrollIntoView({block:'center',inline:'center'})")
        box = source.bounding_box()
        x,y = box['x']+box['width']/2,box['y']+box['height']/2
        self.page.mouse.move(x,y)
        self.page.mouse.down()
        self.page.mouse.move(x+10,y+5,steps=5)
        target.evaluate("el=>el.scrollIntoView({block:'center',inline:'center'})")
        box = target.bounding_box()
        self.page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2,steps=20)
        self.page.mouse.up()

    def blank(self):
        self.page.locator('#schedule-new').click()

    def test_legacy_default_compacts_without_losing_teams_or_members(self):
        self.assertTrue(self.page.locator('#schedule').is_visible())
        self.assertEqual(self.page.locator('#schedule-table tbody tr').count(),7)
        self.assertEqual(self.page.locator('#schedule-table thead th').count(),5)
        self.assertEqual(self.page.locator('#schedule-table .filled').count(),14)
        self.assertIn('珂莱塔',self.slot('卜灵').inner_text())
        self.assertIn('待补 1 人',self.slot('卜灵').inner_text())
        self.assertIn('心锁',self.slot('莉莉').inner_text())
        self.assertEqual(self.page.evaluate('''()=>{
            const signature=p=>JSON.stringify(p.cells.map(c=>[c.row,c.label,...c.members,c.rover_attribute]).sort());
            return signature(schedulePlan())===signature(PLANNER_SEED.schedule_defaults.plans[0]);
        }'''),True)

    def test_templates_unique_full_roster_grouped_by_role_version_and_release(self):
        actual = self.page.evaluate('''()=>{
            const cards=[...document.querySelectorAll('[data-bank-name]')];
            const bank=document.querySelector('#schedule-card-bank');
            return {count:cards.length,unique:new Set(cards.map(c=>c.dataset.bankName)).size,
                released:state.characters.filter(c=>c.released).length,
                columns:bank.querySelectorAll('.schedule-version-heading').length,
                rows:bank.querySelectorAll('.schedule-role-heading').length,
                overflow:getComputedStyle(bank).overflowY,
                sorted:[...document.querySelectorAll('.schedule-template-grid')].every(g=>{
                    const names=[...g.querySelectorAll('[data-bank-name]')].map(c=>c.dataset.bankName);
                    return names.every((n,i)=>!i||characterDisplayOrder.get(names[i-1])<characterDisplayOrder.get(n));
                })};
        }''')
        self.assertEqual(actual['count'],actual['released'])
        self.assertEqual(actual['unique'],actual['count'])
        self.assertEqual(actual['columns'],3)
        self.assertEqual(actual['rows'],3)
        self.assertEqual(actual['overflow'],'visible')
        self.assertTrue(actual['sorted'])
        self.assertIn('1.x',self.page.locator('#schedule-card-bank').inner_text())
        self.assertIn('2.x',self.page.locator('#schedule-card-bank').inner_text())
        self.assertIn('3.x',self.page.locator('#schedule-card-bank').inner_text())
        self.assertEqual(self.page.locator('#schedule-editor').count(),0)

    def test_all_roster_budgets_ignore_ownership_and_use_weekly_override(self):
        self.page.evaluate("state.characters.find(c=>c.name==='守岸人').available=false;renderSchedule()")
        self.assertIn('4 / 2',self.fixed('守岸人','守岸人').inner_text())
        self.page.evaluate("state.characters.find(c=>c.name==='守岸人').weekly=5;renderSchedule()")
        self.assertIn('4 / 5',self.fixed('守岸人','守岸人').inner_text())
        self.assertNotIn('card-over',self.template('守岸人').get_attribute('class'))

    def test_exceeded_character_colors_match_all_occurrences_and_differ(self):
        self.page.evaluate("for(const name of ['珂莱塔','椿'])state.characters.find(c=>c.name===name).weekly=1;renderSchedule()")
        colors = self.page.evaluate('''()=>Object.fromEntries(['珂莱塔','椿'].map(name=>[
            name,[...document.querySelectorAll('[data-bank-name],[data-member-card],[data-fixed-card]')]
            .filter(el=>[el.dataset.bankName,el.dataset.memberCard,el.dataset.fixedCard].includes(name))
            .map(el=>getComputedStyle(el).backgroundColor)]))''')
        self.assertEqual(len(set(colors['珂莱塔'])),1)
        self.assertEqual(len(set(colors['椿'])),1)
        self.assertNotEqual(colors['珂莱塔'][0],colors['椿'][0])
        background=self.fixed('守岸人','守岸人').evaluate('(el)=>getComputedStyle(el).backgroundColor')
        self.assertNotIn(background,self.page.locator('[data-healer="守岸人"] > *').evaluate_all('(els)=>els.map(el=>getComputedStyle(el).backgroundColor)'))

    def test_two_fixed_roles_shared_capacity_and_dynamic_sorting(self):
        self.blank()
        first=self.fixed('白芷','白芷').bounding_box()
        target=self.page.locator('[data-row-header="白芷"] [data-fixed-place]').bounding_box()
        self.assertGreater(target['width'],40)
        self.assertLess(first['x']+first['width'],target['x'])
        self.assertAlmostEqual(first['y'],target['y'],delta=1)
        self.drag(self.template('丹瑾'),self.page.locator('[data-row-header="白芷"] [data-fixed-place]'))
        self.assertEqual(self.page.evaluate("scheduleFixed('白芷')"),['白芷','丹瑾'])
        self.assertEqual(self.page.locator('[data-row-header="白芷"] [data-fixed-place]').count(),0)
        self.place('长离','白芷')
        self.assertEqual(self.slot('白芷').locator('[data-member-card]').count(),1)
        self.assertEqual(self.page.evaluate("SchedulePlanner.analyse(schedulePlan(),state.characters).usage['丹瑾']"),1)
        self.assertFalse(self.slot('白芷').locator('[data-cell-place]').count())
        self.page.locator('#schedule-add-column').click()
        column=self.page.evaluate('schedulePlan().columns[1].id')
        self.template('秧秧').click()
        self.page.locator(f'[data-schedule-row="白芷"][data-schedule-column="{column}"] [data-cell-place]').click()
        self.assertEqual(self.page.evaluate("SchedulePlanner.analyse(schedulePlan(),state.characters).usage['丹瑾']"),2)
        self.page.reload();self.page.locator('#tour-skip').click()
        self.assertEqual(self.page.evaluate("scheduleFixed('白芷')"),['白芷','丹瑾'])

    def test_chip_drag_moves_only_character_and_handle_moves_whole_row(self):
        self.blank()
        self.place('丹瑾','白芷')
        self.drag(self.fixed('白芷','白芷'),self.page.locator('[data-row-header="莉莉"] [data-fixed-place]'))
        self.assertEqual(self.page.evaluate("scheduleFixed('白芷')"),[])
        self.assertEqual(self.page.evaluate("scheduleFixed('莉莉')"),['莉莉','白芷'])
        self.assertIn('丹瑾',self.slot('白芷').inner_text())
        before=self.page.evaluate('JSON.stringify(schedulePlan().cells)')
        self.drag(self.page.locator('[data-move-row="白芷"]'),self.page.locator('[data-row-header="莉莉"]'))
        self.assertEqual(self.page.evaluate('JSON.stringify(schedulePlan().cells)'),before)
        self.assertLess(self.page.evaluate("schedulePlan().rows.indexOf('莉莉')"),self.page.evaluate("schedulePlan().rows.indexOf('白芷')"))

    def test_promote_member_keeps_existing_team_and_fixed_rover_keeps_form(self):
        self.blank();self.place('丹瑾','白芷')
        self.drag(self.slot('白芷').locator('[data-member-card="丹瑾"]'),self.page.locator('[data-row-header="白芷"] [data-fixed-place]'))
        self.assertEqual(self.page.evaluate("scheduleFixed('白芷')"),['白芷','丹瑾'])
        self.assertEqual(self.page.evaluate("scheduleCell('白芷','c1').members"),[])
        self.assertIn('待补 1 人',self.slot('白芷').inner_text())
        self.place('长离','莉莉')
        self.template('漂泊者').click()
        self.fixed('卜灵','卜灵').locator('[data-pick-fixed]').click()
        self.choose('[data-row-rover="卜灵"]','湮灭')
        self.template('长离').click()
        self.page.locator('[data-row-header="卜灵"] [data-fixed-place]').click()
        self.assertEqual(self.page.evaluate("SchedulePlanner.form(schedulePlan(),'卜灵')"),'湮灭')
        self.assertEqual(self.page.evaluate("scheduleCell('白芷','c1').members"),[])
        self.page.reload();self.page.locator('#tour-skip').click()
        self.assertEqual(self.page.evaluate("scheduleCell('白芷','c1').members"),[])

    def test_replace_fixed_chip_updates_entire_row_and_invalid_changes_are_atomic(self):
        self.template('莫宁').click()
        self.fixed('守岸人','守岸人').locator('[data-pick-fixed]').click()
        self.assertEqual(self.page.evaluate("scheduleFixed('守岸人')"),['莫宁'])
        report=self.page.evaluate('SchedulePlanner.analyse(schedulePlan(),state.characters)')
        self.assertEqual(report['usage']['莫宁'],6)
        self.assertEqual(report['usage']['守岸人'],0)
        before=self.page.evaluate('JSON.stringify(state.schedules)')
        self.template('丹瑾').click()
        self.page.locator('[data-row-header="守岸人"] [data-fixed-place]').click()
        self.assertIn('超过三人',self.page.locator('#toast').inner_text())
        self.assertEqual(self.page.evaluate('JSON.stringify(state.schedules)'),before)

    def test_rows_columns_add_reorder_compact_and_undo_persist(self):
        self.page.locator('#schedule-add-row').click()
        row=self.page.evaluate('schedulePlan().rows.at(-1)')
        self.template('丹瑾').click()
        self.page.locator(f'[data-row-header="{row}"] [data-fixed-place]').click()
        self.assertEqual(self.page.evaluate('row=>scheduleFixed(row)',row),['丹瑾'])
        self.page.locator(f'[data-grid-menu-row="{row}"]').click()
        self.page.get_by_role('menuitem',name='上移此行',exact=True).click()
        self.assertEqual(self.page.evaluate('schedulePlan().rows.at(-2)'),row)
        original=self.page.evaluate('schedulePlan().columns.map(c=>c.id)')
        self.drag(self.page.locator(f'[data-move-column="{original[0]}"]'),self.page.locator(f'[data-column-header="{original[1]}"]'))
        self.assertEqual(self.page.evaluate('schedulePlan().columns[0].id'),original[1])
        self.assertIn('日月',self.slot('守岸人',1).inner_text())
        self.page.locator('#schedule-add-column').click()
        self.assertEqual(self.page.evaluate('schedulePlan().columns.length'),5)
        self.page.locator('#schedule-compact').click()
        self.assertEqual(self.page.evaluate('schedulePlan().columns.length'),4)
        self.page.locator('#schedule-undo').click()
        self.assertEqual(self.page.evaluate('schedulePlan().columns.length'),5)
        self.page.reload();self.page.locator('#tour-skip').click()
        self.assertEqual(self.page.evaluate('row=>scheduleFixed(row)',row),['丹瑾'])
        self.assertEqual(self.page.evaluate('schedulePlan().columns.length'),5)

    def test_member_drag_swap_remove_undo_and_rover_form_inline(self):
        self.blank()
        self.place('丹瑾','白芷');self.place('长离','白芷')
        self.place('安可','莉莉');self.place('秧秧','莉莉')
        self.drag(self.slot('白芷').locator('[data-member-card="丹瑾"]'),self.slot('莉莉').locator('[data-member-card="安可"]'))
        self.assertEqual(set(self.page.evaluate("scheduleCell('白芷','c1').members")),{'安可','长离'})
        self.slot('白芷').locator('[data-remove-member="安可"]').click()
        self.assertEqual(self.page.evaluate("scheduleCell('白芷','c1').members"),['长离'])
        self.page.locator('#schedule-undo').click()
        self.assertEqual(set(self.page.evaluate("scheduleCell('白芷','c1').members")),{'安可','长离'})
        self.place('漂泊者','卜灵')
        self.choose('[data-schedule-row="卜灵"] [data-cell-rover]','湮灭')
        self.assertEqual(self.page.evaluate("scheduleCell('卜灵','c1').rover_attribute"),'湮灭')
        self.drag(self.slot('卜灵').locator('[data-member-card]'),self.page.locator('#schedule-card-bank'))
        self.assertIsNone(self.page.evaluate("scheduleCell('卜灵','c1')||null"))

    def test_multiplan_export_import_legacy_and_validation_preserve_personal_settings(self):
        before=self.page.evaluate('JSON.stringify({characters:state.characters,teams:state.teams})')
        self.blank();self.place('心','莉莉');self.page.locator('#schedule-copy').click()
        result=self.page.evaluate('''()=>{
            const exported=LocalPlanner.exportConfig(state),restored=LocalPlanner.importConfig(exported);
            const kept=JSON.stringify(restored.schedules)===JSON.stringify(state.schedules);
            delete exported.schedules;const legacy=LocalPlanner.importConfig(exported);
            return {kept,count:restored.schedules.plans.length,legacy:legacy.schedules.plans[0].cells.length};
        }''')
        self.assertEqual(result,dict(kept=True,count=3,legacy=14))
        self.assertEqual(self.page.evaluate('JSON.stringify({characters:state.characters,teams:state.teams})'),before)
        invalid=self.page.evaluate('''()=>{
            const rejected=change=>{const copy=structuredClone(state);change(copy);try{LocalPlanner.validate(copy);return false}catch{return true}};
            return [rejected(s=>s.schedules.plans[1].cells[0].members=['心','心']),rejected(s=>s.schedules.plans[1].row_fixed['莉莉']=['莉莉','莉莉'])];
        }''')
        self.assertEqual(invalid,[True,True])

    def test_mobile_no_template_scroll_or_page_overflow(self):
        self.page.set_viewport_size({'width':390,'height':900})
        self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth>innerWidth'))
        self.assertEqual(self.page.locator('#schedule-card-bank').evaluate('(el)=>getComputedStyle(el).overflowY'),'visible')
        self.assertEqual(self.page.locator('.schedule-role-heading').count(),3)
        self.page.locator('#schedule-table').scroll_into_view_if_needed()
        header=self.page.locator('[data-row-header="守岸人"]')
        x=header.bounding_box()['x']
        self.page.locator('.schedule-scroll').evaluate('el=>el.scrollLeft=el.scrollWidth')
        self.assertAlmostEqual(header.bounding_box()['x'],x,delta=1)

    def test_direct_http_route_durable_save_uses_temporary_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'profile.json'
            class QuietHandler(Handler):
                def log_message(self,*args):
                    pass
            server=ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
            server.store=PersonalStore(path)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with self.browser.new_context() as context:
                    page=context.new_page();page.goto(f'http://127.0.0.1:{server.server_port}/schedule/')
                    page.locator('#tour-skip').click()
                    page.locator('#schedule-rename').click()
                    page.locator('#schedule-name').fill('持久化排表');page.locator('#schedule-name').press('Tab')
                    page.wait_for_function("document.querySelector('#save-status').textContent==='已自动同步本地'")
                    self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['config']['schedules']['plans'][0]['name'],'持久化排表')
                    page.reload();page.locator('#tour-skip').click()
                    self.assertEqual(page.locator('#schedule-name').input_value(),'持久化排表')
            finally:
                server.shutdown();server.server_close();thread.join(timeout=3)

    def test_lily_metadata_preserves_user_configuration(self):
        c=self.page.evaluate('''()=>{
            const exported=LocalPlanner.exportConfig(state);
            Object.assign(exported.characters.find(c=>c.name==='莉莉'),{available:false,chain:2,weight:2.5,weekly:3});
            return LocalPlanner.importConfig(exported).characters.find(c=>c.name==='莉莉');
        }''')
        self.assertTrue(c['released']);self.assertFalse(c['available'])
        self.assertEqual(c['release_date'],'2026-11-12');self.assertEqual(c['release_version'],'V3.8')
        self.assertEqual((c['chain'],c['weight'],c['weekly']),(2,2.5,3))

    def test_desktop_workspace_fits_and_cards_are_horizontal_with_large_portraits(self):
        for width,height in [(1920,1080),(1440,1000),(1440,900),(1280,900)]:
            with self.subTest(viewport=(width,height)):
                self.page.set_viewport_size({'width':width,'height':height})
                layout=self.page.evaluate('''()=>{
                    const deck=document.querySelector('.schedule-deck').getBoundingClientRect();
                    const board=document.querySelector('.schedule-board').getBoundingClientRect();
                    const cards=[...document.querySelector('[data-schedule-row="守岸人"] .schedule-members').children].map(el=>el.getBoundingClientRect());
                    return {overflowX:document.documentElement.scrollWidth>innerWidth,overflowY:document.documentElement.scrollHeight>innerHeight,
                        side:deck.right<board.left,share:deck.width/(deck.width+board.width),
                        horizontal:Math.abs(cards[0].top-cards[1].top)<1&&cards[0].right<cards[1].left,
                        portrait:document.querySelector('[data-member-card] img').getBoundingClientRect().width,
                        template:document.querySelector('[data-bank-name]').getBoundingClientRect().height,
                        templatePortrait:document.querySelector('[data-bank-name] img').getBoundingClientRect().width};
                }''')
                self.assertFalse(layout['overflowX']);self.assertFalse(layout['overflowY'])
                self.assertTrue(layout['side']);self.assertTrue(layout['horizontal'])
                self.assertAlmostEqual(layout['share'],.4,delta=.001)
                self.assertGreaterEqual(layout['portrait'],40)
                self.assertGreaterEqual(layout['template'],44)
                self.assertGreaterEqual(layout['templatePortrait'],36)
        self.assertEqual(self.page.locator('.schedule-warnings').count(),0)
        self.assertFalse(self.page.locator('footer').is_visible())
        self.assertNotEqual(self.page.locator('[data-row-header]').first.evaluate('(el)=>getComputedStyle(el).backgroundColor'),self.page.locator('.schedule-scroll').evaluate('(el)=>getComputedStyle(el).backgroundColor'))

    def test_splitter_drag_keyboard_reset_and_preferences_survive_export_and_reload(self):
        handle=self.page.locator('#schedule-resizer')
        before=self.page.evaluate('JSON.stringify({characters:state.characters,teams:state.teams,schedules:state.schedules})')
        box=handle.bounding_box();workspace=self.page.locator('.schedule-workspace').bounding_box()
        self.page.mouse.move(box['x']+box['width']/2,box['y']+20)
        self.page.mouse.down()
        self.page.mouse.move(workspace['x']+workspace['width']*.5,box['y']+20,steps=10)
        self.page.mouse.up()
        self.assertEqual(handle.get_attribute('aria-valuenow'),'50')
        self.assertFalse(self.page.locator('body').evaluate('(el)=>el.classList.contains("schedule-resizing")'))
        # Saving other filters must not discard the split preference.
        self.page.evaluate('savePreferences()')
        self.assertEqual(self.page.evaluate("LocalPlanner.importConfig(LocalPlanner.exportConfig(state)).preferences['schedule-deck-width']"),50)
        self.page.reload();self.page.locator('#tour-skip').click()
        self.assertEqual(handle.get_attribute('aria-valuenow'),'50')
        handle.focus();handle.press('ArrowLeft')
        self.assertEqual(handle.get_attribute('aria-valuenow'),'49')
        handle.press('Home');self.assertEqual(handle.get_attribute('aria-valuenow'),'30')
        handle.press('End');self.assertEqual(handle.get_attribute('aria-valuenow'),'60')
        handle.dblclick();self.assertEqual(handle.get_attribute('aria-valuenow'),'40')
        self.assertEqual(self.page.evaluate('JSON.stringify({characters:state.characters,teams:state.teams,schedules:state.schedules})'),before)

    def test_empty_fixed_head_accepts_three_members_and_stays_empty_after_reload(self):
        self.blank()
        self.fixed('白芷','白芷').locator('[data-remove-fixed]').click()
        for name in ['丹瑾','长离','秧秧']:
            self.place(name,'白芷')
        self.assertEqual(self.page.evaluate("scheduleFixed('白芷')"),[])
        self.assertEqual(self.slot('白芷').locator('[data-member-card]').count(),3)
        self.assertEqual(self.slot('白芷').locator('[data-cell-place]').count(),0)
        self.assertEqual(self.page.evaluate("SchedulePlanner.analyse(schedulePlan(),state.characters).usage['白芷']"),0)
        self.page.reload();self.page.locator('#tour-skip').click()
        self.assertEqual(self.page.evaluate("scheduleFixed('白芷')"),[])
        self.assertEqual(self.slot('白芷').locator('[data-member-card]').count(),3)

    def test_exhausted_template_remains_draggable_and_recovers_after_removal(self):
        self.assertIn('card-exhausted',self.template('莫宁').get_attribute('class'))
        self.assertTrue(self.template('莫宁').is_enabled())
        self.assertEqual(self.template('莫宁').get_attribute('draggable'),'true')
        self.place('莫宁','白芷')
        self.assertIn('card-over',self.template('莫宁').get_attribute('class'))
        self.slot('白芷').locator('[data-remove-member="莫宁"]').click()
        self.assertIn('card-exhausted',self.template('莫宁').get_attribute('class'))
        self.blank()
        self.assertNotIn('card-exhausted',self.template('莫宁').get_attribute('class'))

    def test_rover_select_lives_in_its_card_and_form_moves_with_character(self):
        self.blank();self.place('漂泊者','卜灵')
        self.assertEqual(self.slot('卜灵').locator('[data-member-card="漂泊者"] [data-cell-rover]').count(),1)
        self.choose('[data-schedule-row="卜灵"] [data-cell-rover]','湮灭')
        self.drag(self.slot('卜灵').locator('[data-member-card="漂泊者"]'),self.page.locator('[data-row-header="白芷"] [data-fixed-place]'))
        self.assertEqual(self.fixed('白芷','漂泊者').locator('[data-row-rover]').count(),1)
        self.assertEqual(self.page.evaluate("SchedulePlanner.form(schedulePlan(),'白芷')"),'湮灭')
        self.choose('[data-row-rover="白芷"]','气动')
        self.assertEqual(self.page.evaluate("SchedulePlanner.form(schedulePlan(),'白芷')"),'气动')
        self.page.reload();self.page.locator('#tour-skip').click()
        self.assertEqual(self.fixed('白芷','漂泊者').locator('[data-row-rover]').input_value(),'气动')

    def test_hover_header_plus_inserts_adjacent_items_and_preserves_teams(self):
        before=self.page.evaluate('JSON.stringify({characters:state.characters,teams:state.teams,cells:schedulePlan().cells})')
        original=self.page.evaluate('({rows:[...schedulePlan().rows],columns:schedulePlan().columns.map(c=>c.id)})')
        self.page.locator('h2').filter(has_text='手动排表').hover()
        row_plus=self.page.locator('[data-grid-insert-row="维里奈"]')
        self.assertEqual(row_plus.evaluate('(el)=>getComputedStyle(el).opacity'),'0')
        self.page.locator('[data-row-header="维里奈"]').hover()
        row_plus.click()
        rows=self.page.evaluate('schedulePlan().rows')
        self.assertEqual(rows[:2],original['rows'][:2])
        self.assertTrue(rows[2].startswith('row-'))
        self.assertEqual(rows[3:],original['rows'][2:])
        self.assertEqual(self.page.evaluate('id=>scheduleFixed(id)',rows[2]),[])
        self.page.locator('[data-column-header="c2"]').hover()
        self.page.locator('[data-grid-insert-column="c2"]').click()
        columns=self.page.evaluate('schedulePlan().columns.map(c=>c.id)')
        self.assertEqual(columns[:2],original['columns'][:2])
        self.assertEqual(columns[3:],original['columns'][2:])
        self.assertEqual(self.page.evaluate('JSON.stringify({characters:state.characters,teams:state.teams,cells:schedulePlan().cells})'),before)
        self.page.reload();self.page.locator('#tour-skip').click()
        self.assertEqual(self.page.evaluate('schedulePlan().rows'),rows)
        self.assertEqual(self.page.evaluate('schedulePlan().columns.map(c=>c.id)'),columns)

    def test_column_context_menu_cancel_delete_arbitrary_column_and_undo(self):
        original=self.page.evaluate('JSON.stringify(schedulePlan())')
        header=self.page.locator('[data-column-header="c2"]')
        header.locator('[data-move-column]').click(button='right')
        self.page.once('dialog',lambda dialog:dialog.dismiss())
        self.page.get_by_role('menuitem',name='删除此列',exact=True).click()
        self.assertEqual(self.page.evaluate('JSON.stringify(schedulePlan())'),original)
        header.locator('[data-grid-menu-column]').click()
        self.page.once('dialog',lambda dialog:dialog.accept())
        self.page.get_by_role('menuitem',name='删除此列',exact=True).click()
        self.assertNotIn('c2',self.page.evaluate('schedulePlan().columns.map(c=>c.id)'))
        self.assertFalse(self.page.evaluate("schedulePlan().cells.some(c=>c.column==='c2')"))
        self.assertIn('c1',self.page.evaluate('schedulePlan().columns.map(c=>c.id)'))
        self.assertIn('c3',self.page.evaluate('schedulePlan().columns.map(c=>c.id)'))
        self.page.locator('#schedule-undo').click()
        self.assertEqual(self.page.evaluate('JSON.stringify(schedulePlan())'),original)

    def test_header_menu_keyboard_insert_delete_row_and_last_item_limits(self):
        original=self.page.evaluate('JSON.stringify(schedulePlan())')
        trigger=self.page.locator('[data-grid-menu-row="莫宁"]')
        trigger.focus();trigger.press('ArrowDown')
        self.assertTrue(self.page.locator('#schedule-grid-menu').is_visible())
        self.assertEqual(self.page.locator(':focus').inner_text(),'在上方插入行')
        self.page.locator(':focus').press('Escape')
        self.assertFalse(self.page.locator('#schedule-grid-menu').is_visible())
        self.assertEqual(self.page.locator(':focus').get_attribute('data-grid-menu-row'),'莫宁')
        trigger.click();self.page.get_by_role('menuitem',name='在上方插入行',exact=True).click()
        self.assertTrue(self.page.evaluate('schedulePlan().rows[2].startsWith("row-")'))
        self.page.locator('#schedule-undo').click()
        trigger.click()
        self.page.once('dialog',lambda dialog:dialog.accept())
        self.page.get_by_role('menuitem',name='删除此行',exact=True).click()
        self.assertNotIn('莫宁',self.page.evaluate('schedulePlan().rows'))
        self.assertFalse(self.page.evaluate("schedulePlan().cells.some(c=>c.row==='莫宁')"))
        self.page.locator('#schedule-undo').click()
        self.assertEqual(self.page.evaluate('JSON.stringify(schedulePlan())'),original)
        self.blank()
        self.page.locator('[data-grid-menu-column="c1"]').click()
        self.assertTrue(self.page.get_by_role('menuitem',name='删除此列',exact=True).is_disabled())
        self.page.locator(':focus').press('Escape')
        self.page.evaluate('scheduleAct(()=>{schedulePlan().rows=[schedulePlan().rows[0]]})')
        self.page.locator('[data-grid-menu-row]').click()
        self.assertTrue(self.page.get_by_role('menuitem',name='删除此行',exact=True).is_disabled())

    def test_schedule_code_import_always_creates_independent_plan_and_preserves_account(self):
        before=self.page.evaluate('JSON.stringify({plans:state.schedules.plans,characters:state.characters,teams:state.teams,preferences:state.preferences})')
        self.page.locator('#schedule-share').click()
        code=self.page.locator('#schedule-export-code').input_value()
        self.assertTrue(code.startswith('WWMP1:'))
        self.page.locator('#schedule-share-import-tab').click()
        self.page.locator('#schedule-import-code').fill(code)
        self.assertTrue(self.page.locator('#schedule-import-submit').is_enabled())
        self.assertIn('14 支队伍',self.page.locator('#schedule-import-status').inner_text())
        self.page.locator('#schedule-import-submit').click()
        self.assertFalse(self.page.locator('#schedule-share-dialog').is_visible())
        self.assertEqual(self.page.evaluate('state.schedules.plans.length'),2)
        self.assertEqual(self.page.evaluate('schedulePlan().name'),'默认排表（2）')
        self.assertEqual(self.page.evaluate('JSON.stringify({plans:state.schedules.plans.slice(0,1),characters:state.characters,teams:state.teams,preferences:state.preferences})'),before)
        same=self.page.evaluate('''()=>{
            const exported=p=>JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(ScheduleShare.encode(p).split(':')[1].replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0))));
            const old=exported(state.schedules.plans[0]),copy=exported(schedulePlan());delete old.name;delete copy.name;
            return JSON.stringify(old)===JSON.stringify(copy)&&schedulePlan().id!==state.schedules.plans[0].id;
        }''')
        self.assertTrue(same)
        self.page.reload();self.page.locator('#tour-skip').click()
        self.assertEqual(self.page.evaluate('schedulePlan().name'),'默认排表（2）')
        self.page.locator('#schedule-share').click()
        self.page.locator('#schedule-share-import-tab').click();self.page.locator('#schedule-import-code').fill(code)
        self.page.locator('#schedule-import-submit').click()
        self.assertEqual(self.page.evaluate('schedulePlan().name'),'默认排表（3）')
        self.page.locator('#schedule-undo').click()
        self.assertEqual(self.page.evaluate('state.schedules.plans.length'),2)

    def test_schedule_code_roundtrip_preserves_empty_spaces_fixed_roles_and_rover_forms(self):
        result=self.page.evaluate('''()=>{
            const plan={id:'fixture',name:'中文测试表 😀',rows:['row-a','row-b','row-c'],row_fixed:{'row-a':['白芷','漂泊者'],'row-b':[],'row-c':['莉莉']},row_heads:{'row-a':'白芷','row-b':null,'row-c':'莉莉'},row_attributes:{'row-a':'湮灭'},columns:[{id:'one',name:'首列'},{id:'two',name:'空列'}],cells:[{row:'row-a',column:'one',members:[],label:'待补',rover_attribute:''},{row:'row-b',column:'two',members:['丹瑾','漂泊者','长离'],label:'变体',rover_attribute:'气动'}],layout_version:2};
            const code=ScheduleShare.encode(plan),decoded=ScheduleShare.decode(code.replace(/(.{50})/g,'$1\\n'));
            const snapshot=structuredClone(state);snapshot.schedules.plans.push(decoded);LocalPlanner.validate(snapshot);
            return {stable:ScheduleShare.encode(decoded)===code,rows:decoded.rows.length,columns:decoded.columns.length,fixed:SchedulePlanner.fixed(decoded,decoded.rows[0]),form:SchedulePlanner.form(decoded,decoded.rows[0]),empty:decoded.cells[0].members,cellForm:decoded.cells[1].rover_attribute,name:decoded.name};
        }''')
        self.assertTrue(result['stable'])
        self.assertEqual(result['fixed'],['白芷','漂泊者']);self.assertEqual(result['form'],'湮灭')
        self.assertEqual(result['empty'],[]);self.assertEqual(result['cellForm'],'气动')
        self.assertEqual((result['rows'],result['columns']),(3,2))
        self.assertEqual(result['name'],'中文测试表 😀')

    def test_schedule_code_rejects_invalid_data_without_mutating_state(self):
        before=self.page.evaluate('JSON.stringify(state)')
        codes=self.page.evaluate('''()=>{
            const pack=data=>'WWMP1:'+btoa(unescape(encodeURIComponent(JSON.stringify(data)))).replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=+$/,'');
            const data={v:1,name:'测试',rows:[[['白芷'],'衍射']],columns:['列1'],cells:[[0,0,['丹瑾'],'','']]};
            const cases=[d=>d.v=2,d=>d.rows[0][0]=['未知角色'],d=>d.cells[0][0]=999,d=>d.cells[0][2]=['白芷'],d=>d.cells.push(d.cells[0]),d=>d.columns=[],d=>d.cells[0][2]=['丹瑾','丹瑾'],d=>d.cells[0][2]=['漂泊者']];
            return ['不是代码','WWMP1:@@@','WWMP1:abc',...cases.map(change=>{const copy=structuredClone(data);change(copy);return pack(copy)})];
        }''')
        self.page.locator('#schedule-share').click();self.page.locator('#schedule-share-import-tab').click()
        for code in codes:
            self.page.locator('#schedule-import-code').fill(code)
            self.assertTrue(self.page.locator('#schedule-import-submit').is_disabled())
            self.assertEqual(self.page.locator('#schedule-import-code').get_attribute('aria-invalid'),'true')
        self.page.locator('#schedule-share-dialog').press('Escape')
        self.assertEqual(self.page.evaluate('JSON.stringify(state)'),before)

    def test_schedule_code_copy_fallback_selects_code_and_max_plans_blocks_import(self):
        self.page.locator('#schedule-share').click()
        code=self.page.locator('#schedule-export-code').input_value()
        self.page.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw Error('denied')}}})")
        self.page.locator('#schedule-copy-code').click()
        self.page.wait_for_function("document.querySelector('#schedule-copy-status').textContent.includes('全选')")
        self.assertEqual(self.page.locator('#schedule-export-code').evaluate('(el)=>el.selectionEnd-el.selectionStart'),len(code))
        self.page.locator('#schedule-share-close').click()
        self.page.evaluate("while(state.schedules.plans.length<30)state.schedules.plans.push({...structuredClone(schedulePlan()),id:crypto.randomUUID()})")
        before=self.page.evaluate('JSON.stringify(state.schedules)')
        self.page.locator('#schedule-share').click();self.page.locator('#schedule-share-import-tab').click()
        self.page.locator('#schedule-import-code').fill(code)
        self.assertTrue(self.page.locator('#schedule-import-submit').is_disabled())
        self.assertIn('30 张排表上限',self.page.locator('#schedule-import-status').inner_text())
        self.assertEqual(self.page.evaluate('JSON.stringify(state.schedules)'),before)


if __name__=='__main__':
    unittest.main()
