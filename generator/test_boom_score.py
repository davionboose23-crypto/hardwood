"""Read-only boom scorer on a synthetic slate. Does not touch real archives."""
import json, os, tempfile, unittest
import pandas as pd
import boom_score as S


def _slate(root):
    os.makedirs(os.path.join(root, "projections_archive", "postgame"), exist_ok=True)
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    os.makedirs(os.path.join(root, "output"), exist_ok=True)
    # Two players. Card proj 2.0 for 3PM would imply line 4, archived line is 5.
    rows = []
    for name, team, proj3, need3, pct3, act3, mins in (
        ("Role Player", "BOS", 2.0, 5, 9.4, 4, 22),
        ("Other Guy", "BOS", 1.5, 4, 12.0, 5, 18),
    ):
        rows.append(dict(
            date="2026-10-24", game_id="1", team=team, opponent="NYK", player=name,
            projected_role="Bench", projected_min=mins, model="main", PTS_proj=12.0,
            PTS_low70=6, PTS_high70=18, PTS_low90=2, PTS_high90=22, PTS_conf="Med",
            PTS_boom_pct=8.0, PTS_boom_need=20,
            REB_proj=3, REB_low70=1, REB_high70=5, REB_low90=0, REB_high90=7, REB_conf="Low",
            REB_boom_pct=5.0, REB_boom_need=7,
            AST_proj=2, AST_low70=0.5, AST_high70=4, AST_low90=0, AST_high90=5, AST_conf="Low",
            AST_boom_pct=6.0, AST_boom_need=5,
            **{"3PM_proj": proj3, "3PM_low70": 0.5, "3PM_high70": 3.5, "3PM_low90": 0, "3PM_high90": 4.5,
               "3PM_conf": "Med", "3PM_boom_pct": pct3, "3PM_boom_need": need3},
        ))
    pd.DataFrame(rows).to_csv(os.path.join(root, "projections_archive", "2026-10-24.csv"), index=False)
    # no marker => must be excluded
    pd.DataFrame([{**rows[0], "date": "2026-11-06", "player": "Future"}]).to_csv(
        os.path.join(root, "projections_archive", "2026-11-06.csv"), index=False)
    with open(os.path.join(root, "projections_archive", "postgame", "2026-10-24.json"), "w") as fh:
        json.dump({"date": "2026-10-24", "published": True}, fh)
    box = pd.DataFrame([
        dict(PLAYER_NAME="Role Player", TEAM_ABBREVIATION="BOS", GAME_DATE="2026-10-24", MIN=24, PTS=10, REB=4, AST=1, FG3M=4),
        dict(PLAYER_NAME="Other Guy", TEAM_ABBREVIATION="BOS", GAME_DATE="2026-10-24", MIN=20, PTS=15, REB=2, AST=3, FG3M=5),
        dict(PLAYER_NAME="Sat Out", TEAM_ABBREVIATION="BOS", GAME_DATE="2026-10-24", MIN=0, PTS=0, REB=0, AST=0, FG3M=0),
    ])
    box.to_csv(os.path.join(root, "data", "P_2026-27.csv"), index=False)
    with open(os.path.join(root, "output", "boom_metrics.json"), "w") as fh:
        json.dump({"stats": {"FG3M": {"ship": False, "variant": "residual", "chosen": {"brier": 0.07115}, "baseline_quantile": {"brier": 0.0711}}}}, fh)


class ScoreTests(unittest.TestCase):
    def test_scores_marked_nights_only_and_flags_line_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            _slate(root)
            rep = S.report(root)
            self.assertEqual(rep["live"]["postgame_markers"], ["2026-10-24"])
            fg = rep["live"]["by_stat"]["FG3M"]["all"]
            self.assertEqual(fg["archived"]["n"], 2)
            self.assertEqual(fg["line_mismatch_n"], 1)  # Role Player: card 2.0 says 4+, archive says 5
            # Role Player actual 4 is not a boom at the archived line of 5. Other Guy 5 >= 4 is a boom.
            self.assertEqual(fg["archived"]["events"], 1)
            self.assertEqual(rep["simulated_2025_26"]["label"], "simulated_2025_26_holdout_not_archived_pregame")
            self.assertEqual(rep["simulated_2025_26"]["stats"]["FG3M"]["model_brier"], 0.07115)
            # watch population is both (PTS proj 12 < 20, main, bench)
            self.assertEqual(rep["live"]["by_stat"]["FG3M"]["watch"]["archived"]["n"], 2)

    def test_refuses_operational_writes(self):
        with tempfile.TemporaryDirectory() as root:
            _slate(root)
            for rel in ("data/calibration.json", "projections_archive/2026-10-24.csv", "output/boom_metrics.json", "models/boom.joblib"):
                with self.assertRaises(SystemExit):
                    S._refuse(os.path.join(root, rel), root)

    def test_out_flag_does_not_touch_archive(self):
        with tempfile.TemporaryDirectory() as root:
            _slate(root)
            with open(os.path.join(root, "projections_archive", "2026-10-24.csv")) as fh:
                before = fh.read()
            with open(os.path.join(root, "projections_archive", "postgame", "2026-10-24.json")) as fh:
                marker = fh.read()
            out = os.path.join(root, "boom_score_report.json")
            S._refuse(out, root)
            rep = S.report(root)
            with open(out, "w") as f:
                json.dump(rep, f)
            with open(os.path.join(root, "projections_archive", "2026-10-24.csv")) as fh:
                self.assertEqual(fh.read(), before)
            with open(os.path.join(root, "projections_archive", "postgame", "2026-10-24.json")) as fh:
                self.assertEqual(fh.read(), marker)


if __name__ == "__main__":
    unittest.main()
