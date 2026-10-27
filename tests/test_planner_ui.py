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

    def test_element_update_preserves_saved_personal_settings(self):
        self.page.evaluate('''()=>{
            state.characters.forEach(c=>delete c.element);
            Object.assign(state.characters[0],{weight:2.5,chain:3,weekly:5,available:false});
            Object.assign(state.teams[0],{user_weight:2.75,locked:true,enabled:true,note:'保留我的配置'});
            localStorage.setItem('matrix-planner.configuration.v1',JSON.stringify(state));
        }''')
        self.page.reload()
        self.page.locator('#tour-skip').wait_for(state='visible')
        self.page.locator('#tour-skip').click()
        actual = self.page.evaluate('''()=>({character:state.characters[0],team:state.teams[0]})''')
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
