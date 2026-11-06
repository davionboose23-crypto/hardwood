"""Integer boom line the app shows.

The event is not changed. A boom is still a whole-number stat at least

    ceil(max(1.5 * projection, projection + ADD[stat]) - 1e-9)

where `projection` is the model median before the card rounds it to one decimal.
That rounding moves the whole number by 1 often enough to contradict the formula
(about 27% of archived 3PM rows in Oct 24-Nov 5 2026). `display_mid` returns the
coarsest decimal of the same median that still produces the stored line, so the
boom sentence can show a projection the formula reproduces.

Probabilities are intentionally not adjusted here.
"""
import math

MULT = 1.5
ADD = {"PTS": 8, "REB": 4, "AST": 3, "FG3M": 2}


def threshold(mid, stat):
    mid = float(mid)
    if not math.isfinite(mid):
        raise ValueError("projection must be finite")
    if mid < 0:
        mid = 0.0
    return max(MULT * mid, mid + ADD[stat])


def need_int(mid, stat):
    """Smallest integer stat that counts as a boom. Matches boom.need for one row."""
    return int(math.ceil(threshold(mid, stat) - 1e-9))


def display_mid(mid, stat):
    """Coarsest 1-to-4 decimal rounding of `mid` that keeps need_int unchanged.

    One decimal is preferred so the boom line matches the card whenever that is honest.
    """
    mid = float(mid)
    if not math.isfinite(mid):
        raise ValueError("projection must be finite")
    target = need_int(mid, stat)
    for d in (1, 2, 3, 4):
        m = round(mid, d)
        if m >= 0 and need_int(m, stat) == target:
            return float(m)
    # Banker's rounding at 4 decimals crossed an integer boundary. Step back by 0.0001.
    m = round(mid, 4)
    direction = 1.0 if need_int(m, stat) < target else -1.0
    for k in range(1, 200):
        cand = round(m + direction * 0.0001 * k, 4)
        if cand < 0:
            continue
        if need_int(cand, stat) == target:
            return float(cand)
    return float(mid)
