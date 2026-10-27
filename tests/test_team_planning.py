import csv
import tempfile
import unittest
from pathlib import Path

from matrix_planner.team_planning import Candidate, optimize, read_stamina


class TeamPlanningTests(unittest.TestCase):
    def test_global_count_beats_greedy_priority(self):
        teams = [Candidate("greedy", ("a", "b", "c"), 100),
                 Candidate("left", ("a", "d", "e")), Candidate("right", ("b", "f", "g"))]
        selected = optimize(dict.fromkeys("abcdefg", 1), teams)
        self.assertEqual({t.key for t in selected}, {"left", "right"})

    def test_reusable_character_and_optional_healer(self):
        teams = [Candidate("one", ("a", "b", "c")), Candidate("two", ("a", "d", "e"))]
        self.assertEqual(len(optimize(dict(a=2, b=1, c=1, d=1, e=1), teams)), 2)

    def test_axes_and_slot_orders_do_not_multiply_compositions(self):
        selected = optimize(dict.fromkeys("abc", 2), [Candidate("axis1", ("a", "b", "c")),
                            Candidate("axis2", ("c", "a", "b"), 10)])
        self.assertEqual([t.key for t in selected], ["axis2"])

    def test_rover_variants_share_budget(self):
        teams = [Candidate("electro", ("漂泊者", "a", "b")), Candidate("aero", ("漂泊者", "c", "d"))]
        self.assertEqual(len(optimize(dict(漂泊者=1, a=1, b=1, c=1, d=1), teams)), 1)

    def test_weekly_value_is_override_not_addition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "characters.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                w = csv.writer(stream)
                w.writerow(["角色名称", "基础体力", "本周变动体力"])
                w.writerows([["琳奈", 1, 2], ["守岸人", 2, ""], ["耗尽", 2, 0]])
            self.assertEqual(read_stamina(path), {"琳奈": 2, "守岸人": 2, "耗尽": 0})

    def test_invalid_team(self):
        with self.assertRaises(ValueError):
            optimize({"a": 2}, [Candidate("bad", ("a", "a", "a"))])

    def test_no_candidates(self):
        self.assertEqual(optimize({"a": 1}, []), [])


if __name__ == "__main__":
    unittest.main()
