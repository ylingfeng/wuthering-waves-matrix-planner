import csv
import itertools
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from matrix_planner.planner_server import Handler, Store
from matrix_planner.team_planning import Candidate, optimize


class PlannerServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        with (self.root / 'character.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['角色名称', '奶妈标注', '基础体力', '本周变动体力', '可选属性', '可用'])
            writer.writerows([['a', '', 1, 2, '', '是'], ['b', '是', 2, '', '', '是'],
                              ['c', '', 1, '', '', '是'], ['d', '', 1, '', '', ''],
                              ['漂泊者', '', 1, '', '衍射|湮灭|气动|导电', '是']])
        self.store = Store(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def team(self, id, members, **extra):
        return dict(id=id, members=members, rover_attribute='', enabled=True, priority=1,
                    note='', evidence='自定义', axes=[], selected_axis='', sources=[], **extra)

    def test_save_and_reload_csv_semantics(self):
        state = self.store.state()
        state['characters'][0]['weekly'] = None
        state['characters'][1]['healer'] = False
        state['characters'][3]['available'] = True
        state['teams'] = [self.team('one', ['a', 'b', 'd'])]
        saved = self.store.save(state)
        self.assertNotEqual(saved['revision'], state['revision'])
        self.assertEqual(Store(self.root).state(), saved)
        with (self.root / 'character.csv').open(encoding='utf-8-sig') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]['本周变动体力'], '')
        self.assertEqual(rows[1]['奶妈标注'], '')
        self.assertEqual(rows[3]['可用'], '是')

    def test_chain_and_source_multiply_without_overwriting_user_weight(self):
        state = self.store.state()
        state['characters'][0]['chain'] = 6
        state['characters'][0]['weight'] = 2
        t = self.team('one', ['a', 'b', 'c'])
        t.update(evidence='Wiki·明确配队', sources=['https://wiki.kurobbs.com/mc/item/1'])
        state['teams'] = [t]
        self.store.save(state)
        self.assertEqual(self.store.state()['characters'][0]['chain'], 6)
        self.assertEqual(self.store.plan()['total_score'], 14)
        state = self.store.state()
        state['characters'][0]['chain'] = 7
        with self.assertRaises(ValueError):
            self.store.save(state)

    def test_fixed_element_survives_csv_save_and_cannot_be_overridden(self):
        with (self.root / 'character.csv').open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            fields, rows = list(reader.fieldnames), list(reader)
        with (self.root / 'character.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields + ['属性'])
            writer.writeheader()
            writer.writerows([{**row, '属性': '热熔' if row['角色名称'] == 'a' else ''} for row in rows])
        state = self.store.state()
        self.assertEqual(state['characters'][0]['element'], '热熔')
        state['characters'][0].update(element='湮灭', weight=2.5)
        self.store.save(state)
        actual = self.store.state()['characters'][0]
        self.assertEqual(actual['element'], '热熔')
        self.assertEqual(actual['weight'], 2.5)

    def test_invalid_save_does_not_modify_files(self):
        state = self.store.state()
        revision = state['revision']
        state['teams'] = [self.team('bad', ['a', 'a', 'b'])]
        with self.assertRaises(ValueError):
            self.store.save(state)
        self.assertEqual(self.store.revision(), revision)

    def test_stale_save_is_rejected(self):
        old = self.store.state()
        new = self.store.state()
        new['characters'][0]['base'] = 3
        self.store.save(new)
        with self.assertRaises(FileExistsError):
            self.store.save(old)

    def test_unowned_and_inferred_filter(self):
        state = self.store.state()
        t = self.team('derived', ['a', 'b', 'c'])
        t['evidence'] = '机制推导·待验证'
        state['teams'] = [t, self.team('missing', ['a', 'b', 'd'])]
        self.store.save(state)
        self.assertEqual(self.store.plan(False)['count'], 0)
        self.assertEqual(self.store.plan(True)['count'], 1)
        self.assertEqual(self.store.plan(True)['remaining']['d'], 0)

    def test_locked_conflict_is_reported(self):
        state = self.store.state()
        state['teams'] = [self.team('one', ['a', 'b', 'c'], locked=True),
                          self.team('two', ['a', 'c', '漂泊者'], locked=True)]
        state['teams'][1]['rover_attribute'] = '导电'
        self.store.save(state)
        with self.assertRaisesRegex(ValueError, '体力不足'):
            self.store.plan()

    def test_multiple_axes_persist_without_spending_extra(self):
        state = self.store.state()
        t = self.team('one', ['a', 'b', 'c'])
        t['axes'] = [dict(id='axis1', name='启动+循环', description='1 E 2 R'),
                     dict(id='axis2', name='备用', description='2 E 1 R')]
        t['selected_axis'] = 'axis2'
        state['teams'] = [t]
        self.store.save(state)
        plan = self.store.plan()
        self.assertEqual(plan['count'], 1)
        self.assertEqual(plan['selected'][0]['selected_axis'], 'axis2')

    def test_team_weight_multiplies_character_weights(self):
        state = self.store.state()
        for c in state['characters']:
            if c['name'] == 'a':
                c['weight'] = 6
            if c['name'] == 'b':
                c['weight'] = 6
        low = self.team('low', ['a', 'c', '漂泊者'])
        low['rover_attribute'] = '导电'
        low['priority'] = 2
        state['teams'] = [low, self.team('high', ['a', 'b', 'c'])]
        state['teams'][1]['priority'] = 0.5
        self.store.save(state)
        plan = self.store.plan()
        self.assertEqual(plan['selected'][0]['id'], 'high')
        self.assertEqual(plan['selected'][0]['weight_product'], 36)
        self.assertEqual(plan['total_weight'], 36)
        self.assertEqual(plan['total_score'], 18)
        state = self.store.state()
        state['teams'][0]['priority'] = 4
        self.store.save(state)
        plan = self.store.plan()
        self.assertEqual(plan['selected'][0]['id'], 'low')
        self.assertEqual(plan['total_score'], 24)

    def test_decimal_character_weight_survives_save_and_scoring(self):
        state = self.store.state()
        state['characters'][0]['weight'] = 1.1
        t = self.team('one', ['a', 'b', 'c'])
        t['priority'] = 0.8
        state['teams'] = [t]
        self.store.save(state)
        self.assertEqual(self.store.state()['characters'][0]['weight'], 1.1)
        self.assertEqual(self.store.plan()['total_score'], 0.88)

    def test_role_fallback_uses_leftovers_and_sorts_scores_ascending(self):
        state = self.store.state()
        for c in state['characters']:
            c['roles'] = ['主C'] if c['name'] == 'a' else ['奶妈'] if c['name'] == 'b' else ['辅助']
            if c['name'] == 'd':
                c['available'] = True
        state['teams'] = [self.team('known', ['a', 'b', 'c'])]
        self.store.save(state)
        plan = self.store.plan()
        self.assertEqual(plan['recommended_count'], 1)
        self.assertEqual(plan['fallback_count'], 1)
        self.assertEqual(plan['count'], 2)
        self.assertEqual(plan['selected'][0]['evidence'], '主辅奶·兜底')
        scores = [t['team_score'] for t in plan['selected']]
        self.assertEqual(scores, sorted(scores))
        self.assertTrue(all(v >= 0 for v in plan['remaining'].values()))
        self.assertEqual(self.store.plan(fill_roles=False)['count'], 1)

    def test_all_characters_does_not_change_ownership_and_uses_default_weight(self):
        state = self.store.state()
        state['characters'][3]['weight'] = 90
        state['teams'] = [self.team('unowned', ['a', 'b', 'd'])]
        self.store.save(state)
        before = self.store.revision()
        self.assertEqual(self.store.plan()['count'], 0)
        result = self.store.plan(all_characters=True)
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['planning_weights']['d'], 1)
        self.assertEqual(result['selected'][0]['unowned_members'], ['d'])
        self.assertEqual(self.store.revision(), before)
        self.assertFalse(self.store.state()['characters'][3]['available'])

    def test_fallback_respects_disabled_team(self):
        state = self.store.state()
        for c in state['characters']:
            c['roles'] = {'a': ['主C'], 'b': ['奶妈'], 'c': ['辅助']}.get(c['name'], ['待确认'])
        t = self.team('excluded', ['a', 'b', 'c'])
        t['enabled'] = False
        state['teams'] = [t]
        self.store.save(state)
        self.assertEqual(self.store.plan()['count'], 0)

    def test_unreleased_excluded_even_in_all_character_mode(self):
        path = self.root / 'character.csv'
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            fields = list(reader.fieldnames) + ['已实装']
            rows = list(reader)
        for row in rows:
            row['已实装'] = '' if row['角色名称'] == 'd' else '是'
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        state = self.store.state()
        state['teams'] = [self.team('unreleased', ['a', 'b', 'd'])]
        self.store.save(state)
        result = self.store.plan(all_characters=True)
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['remaining']['d'], 0)
        self.assertFalse(self.store.state()['characters'][3]['released'])

    def test_http_round_trip_and_cross_origin_rejection(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.store = self.store
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}'
            with urlopen(url + '/api/state') as response:
                data = json.load(response)
            request = Request(url + '/api/save', json.dumps(data).encode(),
                              {'Content-Type': 'application/json'})
            with urlopen(request) as response:
                self.assertEqual(response.status, 200)
            request = Request(url + '/api/optimize', b'{}',
                              {'Content-Type': 'application/json', 'Origin': 'https://example.com'})
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 403)
            with self.assertRaises(HTTPError):
                urlopen(url + '/portraits/../sources.json')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_integer_solver_matches_enumeration(self):
        teams = [Candidate(str(i), trio, i) for i, trio in enumerate(itertools.combinations('abcdefg', 3))]
        selected = optimize(dict.fromkeys('abcdefg', 1), teams)
        legal_pairs = [(a, b) for a, b in itertools.combinations(teams, 2) if not set(a.members) & set(b.members)]
        self.assertEqual(len(selected), 2)
        self.assertEqual(sum(t.priority for t in selected), max(a.priority + b.priority for a, b in legal_pairs))


if __name__ == '__main__':
    unittest.main()
