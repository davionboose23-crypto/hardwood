"""Guards for the Trends UI patch. Does not read or write projections, calibration, or archives."""
import os, unittest
ROOT = os.path.dirname(os.path.abspath(__file__))

class TrendsUiTests(unittest.TestCase):
    def test_generator_wires_filter_and_keeps_prior_fixes(self):
        def rd(name):
            with open(os.path.join(ROOT, name), encoding='utf-8') as fh:
                return fh.read()
        html, js, pre, boom = rd('build_html.py'), rd('trends_filter.js'), rd('precompute.py'), rd('boom.py')
        self.assertIn('/*TRENDS_FILTER*/', html)
        self.assertIn('trends_filter.js', html)
        self.assertIn('data-tstat', html)
        self.assertIn('aria-label="Matchup"', html)
        self.assertIn('aria-label="Team"', html)
        self.assertIn('How signals are chosen', html)
        self.assertIn("No ${tfStat==='ALL'?'signals'", html)
        self.assertIn('function apply', js)
        self.assertIn('TBD teams', pre)
        self.assertIn('from boom_line import MULT, ADD, display_mid', boom)
        # model / calibration / confidence modules are not the Trends edit surface
        for name in ('calib.py', 'consistency.py', 'boom.py', 'boom_line.py'):
            self.assertTrue(os.path.exists(os.path.join(ROOT, name)))

if __name__ == '__main__':
    unittest.main()
