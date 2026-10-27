"""Browser regressions for shared planner cards, using isolated file storage."""
import unittest
from pathlib import Path

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
