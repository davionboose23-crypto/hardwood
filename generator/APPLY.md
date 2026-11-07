# Boom chance: apply on the local generator

This does not deploy the site and does not change stored boom probabilities.
The live page at the Nov 6, 2026 5:14 PM CT refresh (commit `66652d4`) stays as it is until you rebuild locally.

## What changed

The integer boom line was sometimes not the line you get by applying
`max(1.5 × projection, projection + add)` to the 0.1 projection on the card.
On archived pregame rows from 2026-10-24 through 2026-11-05 that disagreement is
4.6% of PTS, 6.4% of REB, 8.4% of AST, and 27.4% of 3PM. Example: a shown 2.0
three-point projection with a printed line of 5+ (the formula on 2.0 is 4+).

The event definition is unchanged:

`actual >= ceil(max(1.5 × model median, model median + add) − 1e-9)`

with add = PTS 8, REB 4, AST 3, 3PM 2. The next build stores `bmid`, a decimal
of that same median which reproduces the integer, and the boom sentence uses it.
The percentage is still the existing model or quantile chance for that integer.

Not changed: boom probabilities, which stat uses the classifier (REB only),
confidence labels, calibration scales, REB High range protection, historical
CSVs, postgame markers.

Held-out checks did not support a new probability. See the PR for Brier, log loss,
AUC, and the role-player slice. `boom_score.py` reprints that archived-pregame
record without writing operational files.

## Apply

From the `nba-model` directory (the folder that contains `boom.py`):

```bash
# dry run first
patch -p1 --dry-run -t < /path/to/boom-chance.patch
patch -p1 -t < /path/to/boom-chance.patch
python3 -m unittest test_boom_line.py test_boom_score.py -q
```

`patch` updates `boom.py`, `precompute.py`, and `build_html.py`, and adds
`boom_line.py`, `boom_score.py`, `test_boom_line.py`, and `test_boom_score.py`.

Do not copy `nba-model-dev/calib.py` into this tree. Do not rerun a completed
`postgame.py`. Do not replace files under `projections_archive/` or
`data/calibration.json`.

## Score the archive you already have

```bash
python3 boom_score.py --root . --out /tmp/boom_score.json
```

`--out` must sit outside `projections_archive/`, `data/`, `output/`, and `models/`.
The script reads morning archives, box scores, and postgame markers. It skips any
date that has no postgame marker, so an in-progress slate is not treated as a result.
It only joins players with minutes > 0.

The `simulated_2025_26` block is the old out-of-fold holdout in
`output/boom_metrics.json`. The `live` block is archived pregame versus box scores.
Those are different experiments.

## Rebuild

Use the normal local refresh after the patch. A morning or pregame run will emit
`bmid` on new projections and the corrected boom sentence. That run uses the
current calibration file and the current injury report; it does not roll those back
and it does not rewrite a locked archive from a night that has already tipped.

This cloud review did not run that rebuild and did not publish HTML.
