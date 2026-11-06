"""Boom line contract. Does not read or write historical archives."""
import unittest
import boom_line as L


class LineTests(unittest.TestCase):
    def test_constants_unchanged(self):
        self.assertEqual(L.MULT, 1.5)
        self.assertEqual(L.ADD, {"PTS": 8, "REB": 4, "AST": 3, "FG3M": 2})

    def test_integer_boundary(self):
        # exact integer threshold stays on that integer (ceil(n - 1e-9) == n)
        self.assertEqual(L.need_int(11.0, "PTS"), 19)   # max(16.5, 19) = 19
        self.assertEqual(L.need_int(16.0, "PTS"), 24)   # max(24, 24) = 24
        self.assertEqual(L.need_int(2.0, "FG3M"), 4)    # max(3, 4) = 4

    def test_card_rounding_can_move_the_line(self):
        # These are the contradictions seen on archived cards: 0.1 rounding vs the line.
        self.assertEqual(L.need_int(11.04, "PTS"), 20)
        self.assertEqual(L.need_int(11.0, "PTS"), 19)
        self.assertEqual(L.need_int(2.01, "FG3M"), 5)
        self.assertEqual(L.need_int(2.0, "FG3M"), 4)
        self.assertEqual(L.need_int(0.04, "AST"), 4)
        self.assertEqual(L.need_int(0.0, "AST"), 3)
        self.assertEqual(L.need_int(3.04, "REB"), 8)
        self.assertEqual(L.need_int(3.0, "REB"), 7)

    def test_display_mid_reproduces_the_line(self):
        cases = [11.04, 11.0, 11.06, 2.01, 2.0, 0.04, 0.0, 3.04, 8.0, 19.96, 0.5, 24.5]
        for stat in L.ADD:
            for mid in cases:
                shown = L.display_mid(mid, stat)
                self.assertEqual(L.need_int(shown, stat), L.need_int(mid, stat), (stat, mid, shown))
                self.assertLessEqual(abs(shown - mid), 0.05)

    def test_display_mid_prefers_one_decimal_when_honest(self):
        self.assertEqual(L.display_mid(11.0, "PTS"), 11.0)
        self.assertEqual(L.display_mid(11.06, "PTS"), 11.1)  # 11.1 still lines at 20
        self.assertEqual(L.display_mid(11.04, "PTS"), 11.04)  # 11.0 would say 19

    def test_grid_preserves_need(self):
        for stat in L.ADD:
            mid = 0.0
            while mid <= 40.0001:
                shown = L.display_mid(mid, stat)
                self.assertEqual(L.need_int(shown, stat), L.need_int(mid, stat))
                self.assertGreaterEqual(shown, 0)
                mid = round(mid + 0.01, 2)

    def test_matches_vector_formula(self):
        import numpy as np
        for stat, add in L.ADD.items():
            p = np.linspace(0, 40, 4001)
            vec = np.ceil(np.maximum(1.5 * p, p + add) - 1e-9).astype(int)
            got = np.array([L.need_int(x, stat) for x in p])
            self.assertTrue(np.array_equal(vec, got), stat)

    def test_generator_hooks(self):
        import os
        root = os.path.dirname(os.path.abspath(__file__))
        def rd(name):
            with open(os.path.join(root, name), encoding="utf-8") as fh:
                return fh.read()
        boom, pre, html = rd("boom.py"), rd("precompute.py"), rd("build_html.py")
        self.assertIn("from boom_line import MULT, ADD, display_mid", boom)
        self.assertIn("e['bmid']", pre)
        self.assertIn("bmid", html)
        self.assertIn("fmtBoomMid", html)
        self.assertIn("smallest whole number", html)
        self.assertIn("not the archived 2026-27 pregame record", html)
        self.assertNotIn("Boom = at least max(1.5", html)


if __name__ == "__main__":
    unittest.main()
