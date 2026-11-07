# Trends filters: apply on the local generator

Changes the Trends screen only. It does not change projections, calibration, injuries, boom math, or confidence labels.

`build_html.py` reads the current `data/projections.json` and writes `output/NBA_Projections.html`. It does not rewrite archives, calibration, or the injury file. Do not run `precompute.py` or `postgame.py` for this patch.

## Apply

From the `nba-model` directory that already has the boom-line patch and the NBA Cup TBD skip:

```bash
patch -p1 --dry-run -t < /path/to/trends-filters.patch
patch -p1 -t < /path/to/trends-filters.patch
node test_trends_filter.js
python3 -m unittest test_trends_ui.py test_boom_line.py test_boom_score.py -q
python3 build_html.py
```

`node` is only needed for the filter test. The page itself is still the generated HTML file.

Then publish `output/NBA_Projections.html` the way the nightly job does. Headshots already on disk are embedded by `build_html.py`. A copy of the HTML built without the `data/headshots` folder will omit photos; use the real tree.

This does not deploy from the cloud review. The live site stays on the current publish until that local build is published.
