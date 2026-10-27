import unittest

from tools.review_browser_evidence import patterns, title_matches
from tools.team_base_scores import default_team_score
from tools.review_disabled_recheck import resolves_name


class SourceRulesTest(unittest.TestCase):
    def score(self, *proof):
        return default_team_score({'source_audit': {'matched': list(proof)}})

    def test_fixed_tiers_and_non_matrix_video(self):
        self.assertEqual(self.score({'kind': 'video', 'matrix': False}), 1)
        self.assertEqual(self.score({'kind': 'wiki'}), 1.5)
        self.assertEqual(self.score({'kind': 'workshop', 'matrix': True}), 2)
        self.assertEqual(self.score({'kind': 'video', 'matrix': True}), 2.5)

    def test_evidence_uses_highest_tier_not_sum(self):
        self.assertEqual(self.score({'kind': 'wiki'}, {'kind': 'video', 'matrix': False}), 1.5)
        self.assertEqual(self.score({'kind': 'wiki'}, {'kind': 'workshop', 'matrix': True},
                                    {'kind': 'video', 'matrix': True}), 2.5)

    def test_bilibili_url_alone_is_not_matrix_evidence(self):
        self.assertEqual(default_team_score({'sources': ['https://www.bilibili.com/video/example']}), 1)

    def test_title_cannot_join_two_separate_teams(self):
        team = {'members': ['陆·赫斯', '尤诺', '守岸人'], 'rover_attribute': ''}
        self.assertFalse(title_matches('日月守/陆琳莫 矩阵', patterns(team)))

    def test_heart_is_not_jianxin(self):
        team = {'members': ['心', '鉴心', '维里奈'], 'rover_attribute': ''}
        self.assertFalse(title_matches('相鉴维矩阵', patterns(team)))

    def test_lucilla_spelling_variant(self):
        team = {'members': ['绯雪', '洛瑟菈', '穗穗'], 'rover_attribute': ''}
        self.assertTrue(title_matches('0+1绯雪洛瑟拉穗穗矩阵一万三千分', patterns(team)))

    def test_ambiguous_yangyang_requires_the_correct_version(self):
        self.assertFalse(resolves_name('秧秧', '秧秧玄翎千咲穗穗'))
        self.assertTrue(resolves_name('秧秧·玄翎', '秧秧玄翎千咲穗穗'))

    def test_luo_cannot_be_resolved_with_both_characters(self):
        self.assertTrue(resolves_name('洛瑟菈', '绯雪洛瑟拉穗穗'))
        self.assertFalse(resolves_name('洛可可', '绯雪洛瑟菈穗穗'))
        self.assertFalse(resolves_name('洛瑟菈', '洛可可洛瑟菈对比'))


if __name__ == '__main__':
    unittest.main()
