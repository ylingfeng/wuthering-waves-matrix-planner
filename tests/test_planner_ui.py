"""Browser regressions for shared planner cards, using isolated file storage."""
import unittest
import shutil
import tempfile
from pathlib import Path

from tools.release_static import copy_browser_launcher

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipIf(sync_playwright is None, 'Playwright is not installed')
class PlannerCardUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(channel='chrome', headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 1000})
        self.page = self.context.new_page()
        self.page.set_default_timeout(4000)
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto((Path(__file__).resolve().parents[1] / 'web/team_planner/index.html').as_uri())
        self.page.locator('#tour-skip').wait_for(state='visible')
        self.page.locator('#tour-skip').click()
        self.page.evaluate('''()=>{
            state.teams=[structuredClone(state.teams[0])];
            state.teams[0].enabled=true;state.teams[0].locked=false;
            state.characters.forEach(c=>{c.available=true;c.base=1;c.weekly=null;});
            persistLocally();
        }''')

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def calculate(self):
        self.page.locator('#calculate').click()
        self.page.wait_for_function('!document.querySelector("#calculate").disabled', timeout=15000)
        self.assertIsNotNone(self.page.evaluate('result'))

    def generated_result(self):
        self.page.evaluate('''()=>{
            state.teams=[];
            const names=state.characters.filter(c=>c.released&&c.name!=='漂泊者').slice(0,3).map(c=>c.name);
            state.characters.forEach(c=>{c.base=0;c.weekly=null;});
            names.forEach((n,i)=>{const c=state.characters.find(x=>x.name===n);c.base=1;c.roles=[['主C','辅助','奶妈'][i]];c.healer=i===2;});
            persistLocally();
        }''')
        self.page.locator('[data-tab="results"]').click()
        self.page.locator('#fill-roles').check()
        self.calculate()
        self.assertEqual(self.page.evaluate('result.fallback_count'), 1)
        return self.page.locator('#result-body .team-card').first

    def test_click_after_editing_weight_is_not_swallowed(self):
        self.page.locator('[data-tab="teams"]').click()
        card = self.page.locator('#team-grid .team-card').first
        card.scroll_into_view_if_needed()
        card.locator('[data-team-weight]').fill('2')
        button = card.locator('[data-edit]').bounding_box()
        # A physical click, without Playwright retrying a detached target.
        self.page.mouse.click(button['x'] + button['width']/2, button['y'] + button['height']/2)
        self.assertTrue(self.page.locator('#editor').is_visible())

    def test_rover_displays_first_with_legacy_saved_order(self):
        before = self.page.evaluate('''()=>{
            state.characters.reverse();
            Object.assign(state.characters.find(c=>c.name==='漂泊者'),{weight:2.5,chain:3,weekly:5,available:true});
            localStorage.setItem('matrix-planner.configuration.v1',JSON.stringify(state));
            return JSON.stringify(state.characters);
        }''')
        self.page.reload()
        self.page.locator('#tour-skip').click()
        self.assertEqual(self.page.locator('.character-card').first.get_attribute('data-name'), '漂泊者')
        self.assertEqual(self.page.evaluate('JSON.stringify(state.characters)'), before)
        self.assertEqual(self.page.evaluate('PLANNER_SEED.characters[0].name'), '漂泊者')
        import csv
        with (Path(__file__).resolve().parents[1] / 'character.csv').open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(next(csv.DictReader(stream))['角色名称'], '漂泊者')

    def test_element_update_preserves_saved_personal_settings(self):
        self.page.evaluate('''()=>{
            state.characters.forEach(c=>delete c.element);
            Object.assign(state.characters.find(c=>c.name==='散华'),{weight:2.5,chain:3,weekly:5,available:false});
            Object.assign(state.teams[0],{user_weight:2.75,locked:true,enabled:true,note:'保留我的配置'});
            localStorage.setItem('matrix-planner.configuration.v1',JSON.stringify(state));
        }''')
        self.page.reload()
        self.page.locator('#tour-skip').wait_for(state='visible')
        self.page.locator('#tour-skip').click()
        actual = self.page.evaluate('''()=>({character:state.characters.find(c=>c.name==='散华'),team:state.teams[0]})''')
        self.assertEqual(actual['character']['element'], '冷凝')
        for key, value in {'weight': 2.5, 'chain': 3, 'weekly': 5, 'available': False}.items():
            self.assertEqual(actual['character'][key], value)
        for key, value in {'user_weight': 2.75, 'locked': True, 'enabled': True, 'note': '保留我的配置'}.items():
            self.assertEqual(actual['team'][key], value)

    def test_element_filter_combines_with_search_and_role_and_persists(self):
        before = self.page.evaluate('JSON.stringify({characters:state.characters,teams:state.teams})')
        self.page.get_by_role('combobox', name='属性筛选', exact=True).click()
        self.page.get_by_role('option', name='冷凝', exact=True).click()
        names = self.page.locator('.character-card').evaluate_all('els=>els.map(el=>el.dataset.name)')
        self.assertIn('散华', names)
        self.assertNotIn('漂泊者', names)  # Rover has no Glacio form.
        self.assertNotIn('爱弥斯', names)
        self.page.get_by_role('combobox', name='角色筛选', exact=True).click()
        self.page.get_by_role('option', name='奶妈', exact=True).click()
        self.page.locator('#character-search').fill('白')
        self.page.locator('#character-search').press('Tab')
        self.assertEqual(self.page.locator('.character-card').get_attribute('data-name'), '白芷')
        self.page.reload()
        self.page.locator('#tour-skip').click()
        self.assertEqual(self.page.locator('#character-element').input_value(), '冷凝')
        self.assertEqual(self.page.locator('#character-filter').input_value(), 'healer')
        self.assertEqual(self.page.locator('#character-search').input_value(), '白')
        self.assertEqual(self.page.locator('.character-card').get_attribute('data-name'), '白芷')
        self.assertEqual(self.page.evaluate('JSON.stringify({characters:state.characters,teams:state.teams})'), before)

    def test_element_filter_includes_rover_forms_and_reports_empty_matches(self):
        self.page.get_by_role('combobox', name='属性筛选', exact=True).click()
        self.page.get_by_role('option', name='导电', exact=True).click()
        self.assertEqual(self.page.locator('.character-card[data-name="漂泊者"]').count(), 1)
        self.assertEqual(self.page.locator('.character-card[data-name="心"]').count(), 1)
        self.page.locator('#character-search').fill('爱弥斯')
        self.assertEqual(self.page.locator('.character-card').count(), 0)
        self.assertIn('没有符合筛选的角色', self.page.locator('#character-grid').inner_text())
        self.page.get_by_role('combobox', name='属性筛选', exact=True).click()
        self.page.get_by_role('option', name='全部属性', exact=True).click()
        self.assertEqual(self.page.locator('.character-card[data-name="爱弥斯"]').count(), 1)

    def test_element_select_shows_colored_chips_in_menu_and_selected_value(self):
        trigger = self.page.get_by_role('combobox', name='属性筛选', exact=True)
        trigger.click()
        option = self.page.get_by_role('option', name='冷凝', exact=True)
        self.assertEqual(option.locator('.element-tag.element-冷凝').count(), 1)
        background = option.locator('.element-tag').evaluate('el=>getComputedStyle(el).backgroundColor')
        self.assertNotIn(background, ['transparent', 'rgba(0, 0, 0, 0)', 'rgb(255, 255, 255)'])
        option.click()
        self.assertEqual(trigger.locator('.element-tag').inner_text(), '冷凝')
        self.assertEqual(trigger.locator('.element-tag').evaluate('el=>getComputedStyle(el).backgroundColor'), background)
        trigger.click()
        self.page.get_by_role('option', name='全部属性', exact=True).click()
        self.assertEqual(trigger.locator('.element-tag').count(), 0)

    def test_ownership_switch_combines_with_role_and_persists_without_changing_account(self):
        self.page.evaluate('''()=>{
            state.characters.find(c=>c.name==='安可').available=false;
            persistLocally();roster();
        }''')
        self.page.get_by_role('combobox', name='角色筛选', exact=True).click()
        self.page.get_by_role('option', name='主 C', exact=True).click()
        self.assertEqual(self.page.locator('.character-card[data-name="安可"]').count(), 0)
        self.assertEqual(self.page.locator('.character-card[data-name="爱弥斯"]').count(), 1)
        self.assertEqual(self.page.locator('.character-card[data-name="散华"]').count(), 0)
        self.assertEqual(self.page.locator('.character-card[data-name="漂泊者"]').count(), 1)
        self.page.get_by_role('switch', name='显示未拥有角色', exact=True).check()
        self.assertEqual(self.page.locator('.character-card[data-name="安可"]').count(), 1)
        self.page.reload()
        self.page.locator('#tour-skip').click()
        self.assertTrue(self.page.locator('#character-show-unowned').is_checked())
        self.assertEqual(self.page.locator('#character-filter').input_value(), 'main')
        self.assertFalse(self.page.evaluate('state.characters.find(c=>c.name==="安可").available'))
        self.assertEqual(self.page.evaluate('LocalPlanner.exportConfig(state).preferences["character-show-unowned"]'), True)
        self.page.get_by_role('combobox', name='角色筛选', exact=True).click()
        self.page.get_by_role('option', name='辅助', exact=True).click()
        self.assertEqual(self.page.locator('.character-card[data-name="漂泊者"]').count(), 1)
        self.assertEqual(self.page.locator('.character-card[data-name="爱弥斯"]').count(), 0)

    def test_weekly_adjustment_compares_values_for_filter_and_badge(self):
        self.page.evaluate('''()=>{
            Object.assign(state.characters.find(c=>c.name==='散华'),{base:1,weekly:1});
            Object.assign(state.characters.find(c=>c.name==='安可'),{base:1,weekly:0});
            Object.assign(state.characters.find(c=>c.name==='白芷'),{base:2,weekly:3});
            Object.assign(state.characters.find(c=>c.name==='秧秧'),{base:0,weekly:0});
            roster();
        }''')
        self.assertEqual(self.page.locator('.character-card[data-name="散华"] .weekly-badge').count(), 0)
        self.assertEqual(self.page.locator('.character-card[data-name="秧秧"] .weekly-badge').count(), 0)
        self.page.locator('#character-weekly').check()
        self.assertCountEqual(self.page.locator('.character-card').evaluate_all('els=>els.map(el=>el.dataset.name)'), ['安可', '白芷'])
        self.assertEqual(self.page.locator('.weekly-badge').count(), 2)
        weekly = self.page.locator('.character-card[data-name="白芷"] [data-field="weekly"]')
        weekly.fill('2')
        weekly.press('Tab')
        self.assertEqual(self.page.locator('.character-card[data-name="白芷"]').count(), 0)
        self.page.locator('#character-weekly').uncheck()
        self.assertEqual(self.page.locator('.character-card[data-name="白芷"] .weekly-badge').count(), 0)
        self.assertEqual(self.page.locator('.character-card[data-name="爱弥斯"] .weekly-badge').count(), 0)
        # Changing the baseline to match an override also clears the adjustment.
        base = self.page.locator('.character-card[data-name="安可"] [data-field="base"]')
        base.fill('0')
        base.press('Tab')
        self.assertEqual(self.page.locator('.character-card[data-name="安可"] .weekly-badge').count(), 0)

    def test_team_ownership_switch_combines_with_status_and_is_separate_from_calculation(self):
        self.page.evaluate('''()=>{
            const base=structuredClone(state.teams[0]);
            state.characters.find(c=>c.name==='安可').available=false;
            state.teams=[
                {...structuredClone(base),id:'owned',members:['爱弥斯','达妮娅','千咲'],locked:true,enabled:true},
                {...structuredClone(base),id:'missing',members:['安可','散华','白芷'],locked:true,enabled:true},
                {...structuredClone(base),id:'disabled',members:['安可','秧秧','白芷'],locked:false,enabled:false}
            ];persistLocally();
        }''')
        self.page.locator('[data-tab="teams"]').click()
        self.assertEqual(self.page.locator('#team-grid .team-card').count(), 1)
        self.page.get_by_role('switch', name='显示含未拥有角色的队伍', exact=True).check()
        self.assertEqual(self.page.locator('#team-grid .team-card').count(), 3)
        self.page.get_by_role('combobox', name='队伍筛选', exact=True).click()
        self.page.get_by_role('option', name='必须选入', exact=True).click()
        self.assertEqual(self.page.locator('#team-grid .team-card').count(), 2)
        self.page.evaluate('''()=>{
            const scope=document.querySelector('#planning-scope');scope.value='all';scope.dispatchEvent(new Event('change'));
        }''')
        self.assertTrue(self.page.locator('#team-show-unowned').is_checked())
        self.assertEqual(self.page.locator('#team-filter').input_value(), 'locked')
        self.page.get_by_role('switch', name='显示含未拥有角色的队伍', exact=True).uncheck()
        self.assertEqual(self.page.locator('#team-grid .team-card').get_attribute('data-id'), 'owned')
        self.assertFalse(self.page.evaluate('state.characters.find(c=>c.name==="安可").available'))

    def test_legacy_filter_preferences_migrate_to_separate_switches(self):
        self.page.evaluate('''()=>{
            state.preferences={'character-filter':'weekly','team-filter':'all'};
            restorePreferences();roster();teams();
        }''')
        self.assertTrue(self.page.locator('#character-show-unowned').is_checked())
        self.assertTrue(self.page.locator('#character-weekly').is_checked())
        self.assertEqual(self.page.locator('#character-filter').input_value(), 'all')
        self.assertTrue(self.page.locator('#team-show-unowned').is_checked())
        self.assertEqual(self.page.locator('#team-filter').input_value(), 'all')
        self.page.evaluate('''()=>{
            state.preferences={'character-filter':'owned','team-filter':'available'};
            restorePreferences();roster();teams();
        }''')
        self.assertFalse(self.page.locator('#character-show-unowned').is_checked())
        self.assertFalse(self.page.locator('#character-weekly').is_checked())
        self.assertFalse(self.page.locator('#team-show-unowned').is_checked())

    def test_multiple_carry_filter_combines_with_ownership_search_and_persists(self):
        self.page.evaluate('''()=>{
            const base=structuredClone(state.teams[0]);delete base.assigned_roles;
            state.characters.find(c=>c.name==='卡卡罗').available=false;
            state.teams=[
                {id:'two',members:['安可','丹瑾','白芷'],enabled:true},
                {id:'three',members:['安可','丹瑾','凌阳'],enabled:false},
                {id:'flex',members:['安可','漂泊者','白芷'],rover_attribute:'湮灭',enabled:true},
                {id:'missing',members:['安可','卡卡罗','白芷'],enabled:true}
            ].map(t=>({...structuredClone(base),...t}));persistLocally();
        }''')
        self.page.locator('[data-tab="teams"]').click()
        self.page.get_by_role('combobox', name='队伍筛选', exact=True).click()
        self.page.get_by_role('option', name='≥2 位仅主 C', exact=True).click()
        self.assertCountEqual(self.page.locator('#team-grid .team-card').evaluate_all('els=>els.map(el=>el.dataset.id)'), ['two', 'three'])
        self.page.locator('#team-show-unowned').check()
        self.assertEqual(self.page.locator('#team-grid .team-card').count(), 3)
        self.page.locator('#team-search').fill('丹')
        self.page.locator('#team-search').press('Tab')
        self.assertEqual(self.page.locator('#team-grid .team-card').count(), 2)
        self.page.reload()
        self.page.locator('#tour-skip').click()
        self.assertEqual(self.page.locator('#team-filter').input_value(), 'multiple-carries')
        self.assertTrue(self.page.locator('#team-show-unowned').is_checked())
        self.assertEqual(self.page.locator('#team-grid .team-card').count(), 2)
        self.page.get_by_role('combobox', name='队伍主属性筛选', exact=True).click()
        self.page.get_by_role('option', name='冷凝', exact=True).click()
        self.assertEqual(self.page.locator('#team-grid .team-card').count(), 0)
        self.page.get_by_role('combobox', name='队伍主属性筛选', exact=True).click()
        self.page.get_by_role('option', name='全部主属性', exact=True).click()
        self.page.evaluate('''()=>{state.characters.find(c=>c.name==='安可').roles=['主C','辅助'];teams()}''')
        self.assertEqual(self.page.locator('#team-grid .team-card').get_attribute('data-id'), 'three')
        self.assertTrue(self.page.evaluate('state.teams.find(t=>t.id==="two").enabled'))

    def test_newer_dedicated_carry_comes_first_in_shared_cards_and_element_filter(self):
        self.page.evaluate('''()=>{
            Object.assign(state.teams[0],{members:['安可','白芷','珂莱塔']});delete state.teams[0].assigned_roles;
            persistLocally();
        }''')
        self.page.locator('[data-tab="teams"]').click()
        self.assertEqual(self.page.locator('#team-grid .member-name').all_text_contents(), ['珂莱塔', '安可', '白芷'])
        self.assertEqual(self.page.evaluate('teamElement(state.teams[0])'), '冷凝')
        self.calculate()
        self.assertEqual(self.page.locator('#result-body .member-name').all_text_contents(), ['珂莱塔', '安可', '白芷'])
        cases = self.page.evaluate('''()=>{
            const a=state.characters.find(c=>c.name==='安可'),b=state.characters.find(c=>c.name==='珂莱塔');
            const order=()=>orderedMembers(state.teams[0]);
            Object.assign(a,{release_version:'V3.9',release_date:''});Object.assign(b,{release_version:'V3.10',release_date:''});
            const numericVersion=order();
            Object.assign(a,{release_version:'V3.10',release_date:'2026-10-20'});b.release_date='2026-10-01';
            const sameVersionDates=order();
            a.release_date='';b.release_date='';const tie=order();
            b.roles=['主C','辅助'];b.release_version='V4.0';const flexible=order();
            return {numericVersion,sameVersionDates,tie,flexible};
        }''')
        self.assertEqual(cases['numericVersion'], ['珂莱塔', '安可', '白芷'])
        self.assertEqual(cases['sameVersionDates'], ['安可', '珂莱塔', '白芷'])
        self.assertEqual(cases['tie'], ['安可', '珂莱塔', '白芷'])
        self.assertEqual(cases['flexible'], ['安可', '珂莱塔', '白芷'])

    def test_jingran_iuno_team_roles_resolve_flexible_tags_without_changing_config(self):
        self.page.evaluate('''()=>{
            Object.assign(state.characters.find(c=>c.name==='尤诺'),{roles:['主C','辅助']});
            Object.assign(state.teams[0],{
                members:['尤诺','守岸人','景燃'],
                assigned_roles:undefined
            });persistLocally();teams();
        }''')
        snapshot = 'JSON.stringify({characters:state.characters,members:state.teams[0].members,assigned_roles:state.teams[0].assigned_roles})'
        before = self.page.evaluate(snapshot)
        self.assertEqual(self.page.evaluate('orderedMembers(state.teams[0])'), ['景燃', '尤诺', '守岸人'])
        self.assertEqual(self.page.evaluate('teamElement(state.teams[0])'), '热熔')
        self.page.locator('[data-tab="teams"]').click()
        self.assertEqual(self.page.locator('#team-grid .member-name').all_text_contents(), ['景燃', '尤诺', '守岸人'])
        self.page.get_by_role('combobox', name='队伍主属性筛选', exact=True).click()
        self.page.get_by_role('option', name='热熔', exact=True).click()
        self.assertEqual(self.page.locator('#team-grid .team-card').count(), 1)
        self.calculate()
        self.assertEqual(self.page.locator('#result-body .member-name').all_text_contents(), ['景燃', '尤诺', '守岸人'])
        self.assertEqual(self.page.evaluate('orderedMembers({members:["守岸人","琳奈","尤诺"]})'), ['尤诺', '琳奈', '守岸人'])
        # Sorting does not rewrite saved members, slot roles or character settings.
        self.assertEqual(self.page.evaluate(snapshot), before)

    def test_team_role_sorting_is_generic_and_respects_explicit_assignments(self):
        actual = self.page.evaluate('''()=>{
            const carry=state.characters.find(c=>c.name==='安可');
            const flex=state.characters.find(c=>c.name==='散华');
            const heal=state.characters.find(c=>c.name==='白芷');
            Object.assign(carry,{roles:['主C'],healer:false});
            Object.assign(flex,{roles:['主C','辅助'],healer:false});
            Object.assign(heal,{roles:['奶妈'],healer:true});
            const cases=[
                [heal.name,flex.name,carry.name], [flex.name,carry.name,heal.name],
                [carry.name,heal.name,flex.name], [heal.name,carry.name,flex.name],
                [flex.name,heal.name,carry.name], [carry.name,flex.name,heal.name]
            ];
            const permutations=cases.map(members=>orderedMembers({members}));
            const explicit=orderedMembers({members:[flex.name,carry.name,heal.name],assigned_roles:['主C','辅助','奶妈']});
            carry.roles=['辅助'];
            const flexibleMain=orderedMembers({members:[carry.name,heal.name,flex.name]});
            carry.roles=['主C','辅助'];
            const tied=orderedMembers({members:[heal.name,carry.name,flex.name]});
            return {permutations,explicit,flexibleMain,tied};
        }''')
        self.assertEqual(actual['permutations'], [['安可', '散华', '白芷']]*6)
        self.assertEqual(actual['explicit'], ['散华', '安可', '白芷'])
        self.assertEqual(actual['flexibleMain'], ['散华', '安可', '白芷'])
        self.assertEqual(actual['tied'], ['安可', '散华', '白芷'])

    def test_flexible_roles_use_tags_and_rover_form_does_not_force_carry(self):
        for name in ['漂泊者', '尤诺', '菲比']:
            with self.subTest(name=name):
                self.assertEqual(self.page.evaluate('(name)=>state.characters.find(c=>c.name===name).roles', name), ['主C', '辅助'])
        actual = self.page.evaluate('''()=>{
            const modes=state.characters.find(c=>c.name==='漂泊者').attributes;
            const pairs=modes.map(rover_attribute=>orderedMembers({members:['漂泊者','白芷','丹瑾'],rover_attribute}));
            const elements=modes.map(rover_attribute=>teamElement({members:['漂泊者','安可','白芷'],rover_attribute}));
            // A live tag edit must change the decision even for the same names and mode.
            state.characters.find(c=>c.name==='丹瑾').roles=['辅助'];
            const changed=orderedMembers({members:['白芷','丹瑾','漂泊者'],rover_attribute:'湮灭'});
            state.characters.find(c=>c.name==='漂泊者').roles=['辅助'];
            state.characters.find(c=>c.name==='丹瑾').roles=['主C','辅助'];
            const changedAgain=orderedMembers({members:['漂泊者','白芷','丹瑾'],rover_attribute:'湮灭'});
            return {pairs,elements,changed,changedAgain};
        }''')
        self.assertEqual(actual['pairs'], [['丹瑾', '漂泊者', '白芷']]*4)
        self.assertEqual(actual['elements'], ['热熔']*4)
        self.assertEqual(actual['changed'], ['漂泊者', '丹瑾', '白芷'])
        self.assertEqual(actual['changedAgain'], ['丹瑾', '漂泊者', '白芷'])

    def test_team_element_filter_uses_main_dps_not_support_and_rover_form(self):
        self.page.evaluate('''()=>{
            const base=structuredClone(state.teams[0]);delete base.assigned_roles;
            state.teams=[
                {id:'heat',members:['达妮娅','千咲','爱弥斯'],rover_attribute:''},
                {id:'ice',members:['达妮娅','绯雪','白芷'],rover_attribute:''},
                {id:'havoc',members:['达妮娅','漂泊者','白芷'],rover_attribute:'湮灭'}
            ].map(t=>({...structuredClone(base),...t,origin:'manual'}));
            persistLocally();
        }''')
        self.page.locator('[data-tab="teams"]').click()
        trigger = self.page.get_by_role('combobox', name='队伍主属性筛选', exact=True)
        trigger.click()
        self.page.get_by_role('option', name='冷凝', exact=True).click()
        self.assertEqual(self.page.locator('#team-grid .team-card').get_attribute('data-id'), 'ice')
        self.assertEqual(self.page.locator('#team-grid .team-main-element .element-tag').inner_text(), '冷凝')
        trigger.click()
        self.page.get_by_role('option', name='湮灭', exact=True).click()
        self.assertEqual(self.page.locator('#team-grid .team-card').get_attribute('data-id'), 'havoc')
        self.page.reload()
        self.page.locator('#tour-skip').click()
        self.assertEqual(self.page.locator('#team-element').input_value(), '湮灭')
        self.assertEqual(self.page.locator('#team-grid .team-card').get_attribute('data-id'), 'havoc')
        self.calculate()
        self.assertEqual(self.page.locator('#result-body .team-main-element .element-tag').count(), 1)

    def test_browser_launcher_shares_page_storage_and_calculates(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='planner 中文 空格 ') as folder:
            bundle = Path(folder)
            shutil.copytree(root / 'web/team_planner', bundle / 'web')
            copy_browser_launcher(bundle)
            page_url = (bundle / 'web/index.html').as_uri()
            self.page.goto((bundle / '鸣潮矩阵配队.html').as_uri())
            self.page.wait_for_url(page_url)
            self.page.locator('#tour-skip').wait_for(state='visible')
            self.page.locator('#hide-onboarding').check()
            self.page.locator('#tour-skip').click()
            self.page.evaluate('''()=>{state.characters[0].weight=2.5;persistLocally()}''')
            # Opening the real page and returning via the launcher use the same localStorage.
            self.page.goto(page_url)
            self.page.wait_for_function('typeof state !== "undefined" && state.characters[0].weight===2.5')
            self.assertTrue(self.page.locator('#onboarding').is_hidden())
            self.page.goto((bundle / '鸣潮矩阵配队.html').as_uri())
            self.page.wait_for_url(page_url)
            self.page.wait_for_function('typeof state !== "undefined" && state.characters[0].weight===2.5')
            self.calculate()
            self.assertGreater(self.page.evaluate('result.selected.length'), 0)
            self.page.goto('about:blank')

    def test_rover_elements_follow_team_form_in_editor_and_shared_cards(self):
        rover = self.page.locator('.character-card[data-name="漂泊者"]')
        self.assertEqual(rover.locator('.element-tag').all_text_contents(), ['衍射', '湮灭', '气动', '导电'])
        self.page.evaluate('''()=>{
            Object.assign(state.teams[0],{members:['爱弥斯','漂泊者','白芷'],rover_attribute:'衍射'});
            persistLocally();
        }''')
        self.page.locator('[data-tab="teams"]').click()
        self.page.locator('#team-grid [data-edit]').first.click()
        self.page.evaluate('''()=>{
            const select=document.querySelector('#rover-attribute');
            select.value='湮灭';select.dispatchEvent(new Event('change'));
        }''')
        self.assertEqual(self.page.locator('[data-slot="1"] .member-element .element-tag').all_text_contents(), ['湮灭'])
        self.page.locator('#team-form button[type="submit"]').click()
        self.assertEqual(self.page.locator('#team-grid .member .element-tag').all_text_contents(), ['热熔', '湮灭', '冷凝'])
        self.calculate()
        self.assertEqual(self.page.locator('#result-body .member .element-tag').all_text_contents(), ['热熔', '湮灭', '冷凝'])

    def test_weight_commit_preserves_keyboard_focus(self):
        self.page.locator('[data-tab="teams"]').click()
        weight = self.page.locator('#team-grid [data-team-weight]').first
        weight.fill('2')
        weight.press('Tab')
        self.assertTrue(self.page.evaluate('document.activeElement.hasAttribute("data-lock")'))

    def test_inferred_option_stays_stale_after_navigation(self):
        self.calculate()
        self.page.locator('#include-inferred').check()
        self.page.locator('[data-tab="teams"]').click()
        self.page.locator('[data-tab="results"]').click()
        self.assertIn('stale', self.page.locator('#result-body').get_attribute('class'))
        self.calculate()
        self.assertNotIn('stale', self.page.locator('#result-body').get_attribute('class'))

    def test_scope_change_updates_result_card_scores_immediately(self):
        self.page.evaluate('''()=>{
            const c=state.characters.find(c=>c.name===state.teams[0].members[0]);
            c.available=false;c.chain=6;c.weight=2;persistLocally();
            document.querySelector('#planning-scope').value='all';
            document.querySelector('#planning-scope').dispatchEvent(new Event('change'));
        }''')
        self.calculate()
        self.page.evaluate('''()=>{
            document.querySelector('#planning-scope').value='owned';
            document.querySelector('#planning-scope').dispatchEvent(new Event('change'));
        }''')
        expected = self.page.evaluate('teamScore(state.teams[0])')
        actual = float(self.page.locator('#result-body [data-team-score]').inner_text())
        self.assertEqual(actual, expected)

    def test_deleted_generated_candidate_does_not_reappear(self):
        card = self.generated_result()
        card.locator('[data-team-weight]').fill('2')
        card.locator('[data-team-weight]').press('Tab')
        self.assertEqual(self.page.evaluate('state.teams.length'), 1)
        card.locator('[data-edit]').click()
        self.page.locator('#delete-team').click()
        self.assertEqual(self.page.evaluate('state.teams.length'), 0)
        self.assertEqual(self.page.locator('#result-body .team-card').count(), 0)
        self.page.locator('[data-tab="teams"]').click()
        self.page.locator('[data-tab="results"]').click()
        self.assertEqual(self.page.locator('#result-body .team-card').count(), 0)
        self.assertEqual(self.page.evaluate('LocalPlanner.read().teams.length'), 0)

    def test_generated_result_reuses_new_candidate_for_same_members(self):
        card = self.generated_result()
        self.page.evaluate('''()=>{
            const team={...structuredClone(result.selected[0]),id:crypto.randomUUID(),origin:'manual',user_weight:3};
            state.teams.push(team);markDirty();teams();
        }''')
        self.assertEqual(card.get_attribute('data-id'), self.page.evaluate('state.teams[0].id'))
        self.assertEqual(card.locator('[data-team-weight]').input_value(), '3')
        card.locator('[data-team-weight]').fill('4')
        card.locator('[data-team-weight]').press('Tab')
        self.assertEqual(self.page.evaluate('state.teams.length'), 1)
        self.assertEqual(self.page.evaluate('LocalPlanner.read().teams[0].user_weight'), 4)

    def test_configuration_changed_during_calculation_stays_stale(self):
        self.page.locator('[data-tab="results"]').click()
        self.page.evaluate('''()=>{
            const original=browserPlan;
            browserPlan=async(...args)=>{
                const planned=await original(...args);
                await new Promise(resolve=>setTimeout(resolve,500));
                return planned;
            };
        }''')
        self.page.locator('#calculate').click()
        self.page.locator('#include-inferred').check()
        self.page.wait_for_function('!document.querySelector("#calculate").disabled', timeout=15000)
        self.assertIn('stale', self.page.locator('#result-body').get_attribute('class'))


if __name__ == '__main__':
    unittest.main()
