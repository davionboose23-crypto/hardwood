#!/usr/bin/env python3
"""Read-only score of archived pregame boom chances against box scores.

Does not write projections, calibration, postgame markers, or historical CSVs.
A path under projections_archive/, data/, or output/ is refused.

This is the archived 2026-27 pregame record (morning projections_archive/YYYY-MM-DD.csv,
kept only for dates that already have a postgame marker). It is not the simulated
2025-26 holdout in output/boom_metrics.json. Pass --simulated to print that file's
stored Brier numbers beside the live record, clearly labeled.

Boom event scored here is the archived integer line (*_boom_need), which is what the
app printed. The 0.1 card projection does not always reproduce that line; the report
counts those rows. Players are counted only if the morning archive projected them to
play and the box score has minutes > 0.

Usage:
  python boom_score.py --root /path/to/nba-model
  python boom_score.py --root /path/to/nba-model --out /tmp/boom_score.json
"""
import argparse, json, math, os, glob
import numpy as np
import pandas as pd
from boom_line import ADD, need_int

STATS = ["PTS", "REB", "AST", "FG3M"]
LAB = {"PTS": "PTS", "REB": "REB", "AST": "AST", "FG3M": "3PM"}
U = np.array([0, .05, .15, .5, .85, .95, 1.0])


def nkey(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", str(s)) if c.isalnum() and not unicodedata.combining(c)).lower()


def _refuse(path, root):
    """Refuse writes into the operational tree."""
    ap = os.path.realpath(path)
    root = os.path.realpath(root)
    banned = [os.path.join(root, p) for p in ("projections_archive", "data", "output", "models")]
    for b in banned:
        if ap == b or ap.startswith(b + os.sep):
            raise SystemExit(f"refusing to write inside {b}")
    base = os.path.basename(ap)
    if base in {"calibration.json", "calibration_log.json", "results.json", "projections.json", "boom_metrics.json"}:
        raise SystemExit(f"refusing to overwrite {base}")


def knots(pr):
    pr = np.asarray(pr, float)
    if pr.ndim == 1:
        pr = pr.reshape(1, -1)
    lo70, mid, hi70, lo90, hi90 = [pr[:, i] for i in range(5)]
    v = np.column_stack([
        np.maximum(0, 2 * lo90 - lo70), lo90, lo70, mid, hi70, hi90, hi90 + 1.5 * (hi90 - hi70)
    ])
    v = np.maximum.accumulate(v, axis=1)
    return v + np.arange(7) * 1e-6


def q_prob(pr, y):
    """P(integer outcome >= y), same continuity correction as boom.q_prob / the app shade."""
    v = knots(np.asarray(pr, float))
    y = np.atleast_1d(np.asarray(y, float))
    seg = np.clip((v < (y - 0.5)[:, None]).sum(1) - 1, 0, 5)
    a = v[np.arange(len(y)), seg]
    b = v[np.arange(len(y)), seg + 1]
    w = np.clip(((y - 0.5) - a) / np.maximum(b - a, 1e-9), 0, 1)
    u = U[seg] + w * (U[seg + 1] - U[seg])
    yy = y - 0.5
    F = np.where(yy <= v[:, 0], 0.0, np.where(yy >= v[:, -1], 1.0, u))
    out = 1 - F
    return float(out[0]) if out.size == 1 else out


# Same floor the boom model uses (boom.py clips probabilities to [1e-4, 1-1e-4]).
# A displayed 0.0% is the card rounding a smaller positive chance, not a hard zero.
_PCLIP = 1e-4


def brier(y, p):
    y = np.asarray(y, float)
    p = np.clip(np.asarray(p, float), _PCLIP, 1 - _PCLIP)
    return float(np.mean((p - y) ** 2))


def logloss(y, p):
    y = np.asarray(y, float)
    p = np.clip(np.asarray(p, float), _PCLIP, 1 - _PCLIP)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def auc(y, p):
    y = np.asarray(y, int)
    p = np.asarray(p, float)
    pos = p[y == 1]
    neg = p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    # Mann-Whitney, average ranks for ties
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), float)
    i = 0
    ps = p[order]
    while i < len(p):
        j = i
        while j + 1 < len(p) and ps[j + 1] == ps[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1
        i = j + 1
    rpos = ranks[y == 1].sum()
    return float((rpos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def metrics(y, p):
    y = np.asarray(y, int)
    p = np.asarray(p, float)
    m = np.isfinite(p)
    y, p = y[m], p[m]
    if len(y) == 0:
        return None
    k = max(1, int(round(len(y) * 0.1)))
    top = np.argsort(-p)[:k]
    return dict(
        n=int(len(y)), events=int(y.sum()), rate=round(float(y.mean()), 4),
        mean_p=round(float(p.mean()), 4), brier=round(brier(y, p), 5),
        logloss=round(logloss(y, p), 5), auc=None if auc(y, p) is None else round(auc(y, p), 4),
        top10_n=int(k), top10_rate=round(float(y[top].mean()), 4),
    )


def load_rows(root):
    arch = os.path.join(root, "projections_archive")
    markers = {}
    for f in glob.glob(os.path.join(arch, "postgame", "*.json")):
        with open(f) as fh:
            m = json.load(fh)
        if isinstance(m, dict) and m.get("date"):
            markers[m["date"]] = True
    frames = []
    for f in sorted(glob.glob(os.path.join(arch, "20*.csv"))):
        d = pd.read_csv(f)
        if "date" not in d.columns:
            continue
        d["date"] = d["date"].astype(str)
        d = d[d["date"].isin(markers)]
        if not len(d):
            continue
        frames.append(d)
    if not frames:
        return pd.DataFrame(), sorted(markers)
    A = pd.concat(frames, ignore_index=True)
    role = A.projected_role.astype(str)
    A = A[~role.str.startswith(("OUT", "DNP", "DOUBTFUL", "QUESTIONABLE")) & A["PTS_proj"].notna()].copy()
    box = pd.read_csv(os.path.join(root, "data", "P_2026-27.csv"))
    box["date"] = pd.to_datetime(box.GAME_DATE).dt.date.astype(str)
    box["k"] = box.PLAYER_NAME.map(nkey) + "|" + box.TEAM_ABBREVIATION + "|" + box.date
    A["k"] = A.player.map(nkey) + "|" + A.team + "|" + A.date.astype(str)
    A = A.drop_duplicates("k", keep="last")
    J = A.merge(box[["k", "MIN", "PTS", "REB", "AST", "FG3M"]], on="k", how="inner")
    J = J[J.MIN > 0].copy()
    return J, sorted(markers)


def score_frame(J):
    rows = []
    for d in J.to_dict("records"):
        pts = float(d["PTS_proj"])
        role = str(d.get("projected_role") or "")
        model = d.get("model")
        minutes = float(d["projected_min"])
        watch = model == "main" and pts < 20 and minutes > 0
        role_player = watch and (not role.startswith("Starter") or minutes < 28)
        for t in STATS:
            lab = LAB[t]
            need = d.get(f"{lab}_boom_need")
            pct = d.get(f"{lab}_boom_pct")
            if need is None or pct is None or (isinstance(need, float) and math.isnan(need)) or (isinstance(pct, float) and math.isnan(pct)):
                continue
            proj = float(d[f"{lab}_proj"])
            shown = [float(d[f"{lab}_{k}"]) for k in ("low70", "proj", "high70", "low90", "high90")]
            act = float(d["FG3M"] if t == "FG3M" else d[t])
            line = float(need)
            line_from_card = float(need_int(proj, t))
            rows.append(dict(
                date=str(d["date"]), stat=t, y=int(act + 1e-9 >= line),
                p_arch=float(pct) / 100.0, p_tail=q_prob(shown, line),
                line_mismatch=int(abs(line - line_from_card) > 0.1),
                watch=bool(watch), role=bool(role_player),
                min_jump=bool(float(d["MIN"]) >= float(d["projected_min"]) * 1.3),
            ))
    return pd.DataFrame(rows)


def _block(df):
    if df is None or not len(df):
        return None
    return dict(archived=metrics(df.y, df.p_arch), shaded_tail=metrics(df.y, df.p_tail),
                line_mismatch_rate=round(float(df.line_mismatch.mean()), 4),
                line_mismatch_n=int(df.line_mismatch.sum()))


def simulated(root):
    f = os.path.join(root, "output", "boom_metrics.json")
    if not os.path.exists(f):
        return None
    with open(f) as fh:
        raw = json.load(fh)
    out = {"label": "simulated_2025_26_holdout_not_archived_pregame", "splits": raw.get("splits"), "stats": {}}
    for t, s in (raw.get("stats") or {}).items():
        ch, bq = s.get("chosen") or {}, s.get("baseline_quantile") or {}
        out["stats"][t] = dict(ship=s.get("ship"), variant=s.get("variant"),
                                model_brier=ch.get("brier"), quantile_brier=bq.get("brier"),
                                model_logloss=ch.get("logloss"), quantile_logloss=bq.get("logloss"),
                                model_auc=ch.get("auc"), quantile_auc=bq.get("auc"))
    return out


def report(root, dev_end="2026-10-31"):
    J, markers = load_rows(root)
    R = score_frame(J) if len(J) else pd.DataFrame()
    live = {"label": "archived_morning_pregame_vs_box_score", "postgame_markers": markers,
            "played_rows_with_boom": int(len(R)), "note": "Morning archive only. Late pregame/ injury snapshots are not in this bundle. Dates without a postgame marker are excluded. MIN>0."}
    if len(R):
        R["split"] = np.where(R.date <= dev_end, "dev", "hold")
        live["dates"] = [str(R.date.min()), str(R.date.max())]
        live["by_stat"] = {}
        for t in STATS:
            x = R[R.stat == t]
            jump = x[x.watch & x.min_jump]
            near = x[x.watch & ~x.min_jump]
            live["by_stat"][t] = dict(
                all=_block(x), dev=_block(x[x.split == "dev"]), hold=_block(x[x.split == "hold"]),
                watch=_block(x[x.watch]), watch_hold=_block(x[x.watch & (x.split == "hold")]),
                role=_block(x[x.role]),
                watch_minutes=dict(
                    near_n=int(len(near)), near_rate=None if not len(near) else round(float(near.y.mean()), 4),
                    near_mean_p=None if not len(near) else round(float(near.p_arch.mean()), 4),
                    jump30_n=int(len(jump)), jump30_rate=None if not len(jump) else round(float(jump.y.mean()), 4),
                    jump30_mean_p=None if not len(jump) else round(float(jump.p_arch.mean()), 4),
                ),
            )
    return dict(live=live, simulated_2025_26=simulated(root), definition={t: f"actual >= ceil(max(1.5*proj, proj+{ADD[t]}) - 1e-9)" for t in STATS})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--out", help="optional JSON path outside projections_archive/, data/, output/, models/")
    ap.add_argument("--dev-end", default="2026-10-31")
    a = ap.parse_args()
    rep = report(a.root, a.dev_end)
    text = json.dumps(rep, indent=1)
    print(text)
    if a.out:
        _refuse(a.out, a.root)
        with open(a.out, "w") as f:
            f.write(text)
            f.write("\n")


if __name__ == "__main__":
    main()
