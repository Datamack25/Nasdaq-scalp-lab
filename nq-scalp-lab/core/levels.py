"""Niveaux clés NQ (plan de séance) : PDH/PDL, séance cash, overnight, ouverture de
minuit, ouvertures macro (semaine/mois/trimestre/année), range du lundi, boîte
asiatique, IB, ATR, range implicite VXN."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import NY_TZ


def cme_day_start(ts: pd.Timestamp) -> pd.Timestamp:
    """Début de la journée CME (18:00 NY la veille) contenant ts."""
    ts = ts.tz_convert(NY_TZ)
    base = ts.normalize() + pd.Timedelta(hours=18)
    return base if ts >= base else base - pd.Timedelta(days=1)


def _between(df, a, b):
    return df[(df.index >= a) & (df.index < b)]


def _hl(seg):
    if seg.empty:
        return np.nan, np.nan, None, None
    return seg["High"].max(), seg["Low"].min(), seg["High"].idxmax(), seg["Low"].idxmin()


def compute_levels(df5: pd.DataFrame, dfd: pd.DataFrame, vxn: float | None = None) -> dict:
    """df5 : barres 5 min (≥ 10 jours) ; dfd : barres journalières (≥ 1 an)."""
    now = df5.index[-1]
    price = df5["Close"].iloc[-1]
    day0 = cme_day_start(now)
    # si on est le week-end / avant réouverture, day0 peut ne contenir aucune barre
    if _between(df5, day0, day0 + pd.Timedelta(hours=23)).empty:
        day0 = cme_day_start(df5.index[-1] - pd.Timedelta(minutes=1))
    prev0 = day0 - pd.Timedelta(days=1)
    while _between(df5, prev0, prev0 + pd.Timedelta(hours=23)).empty and prev0 > df5.index[0]:
        prev0 -= pd.Timedelta(days=1)
    cal_day = (day0 + pd.Timedelta(hours=6)).normalize()        # date civile de la séance
    prev_cal = (prev0 + pd.Timedelta(hours=6)).normalize()

    L = []

    def add(name, p, t=None, group="jour"):
        if p is not None and not (isinstance(p, float) and np.isnan(p)):
            L.append({"niveau": name, "prix": float(p), "heure": t, "groupe": group})

    # --- veille
    prev = _between(df5, prev0, prev0 + pd.Timedelta(hours=23))
    ph, pl, pht, plt = _hl(prev)
    add("PDH – plus haut de la veille", ph, pht, "veille")
    add("PDL – plus bas de la veille", pl, plt, "veille")
    pcash = _between(df5, prev_cal + pd.Timedelta(hours=9.5), prev_cal + pd.Timedelta(hours=16))
    if not pcash.empty:
        a, b, at, bt = _hl(pcash)
        add("Plus haut cash veille", a, at, "veille"); add("Plus bas cash veille", b, bt, "veille")
        add("Clôture cash veille (16:00)", pcash["Close"].iloc[-1], pcash.index[-1], "veille")
    if not prev.empty:
        add("Settlement veille (17:00)", prev["Close"].iloc[-1], prev.index[-1], "veille")

    # --- séance en cours
    today = _between(df5, day0, now + pd.Timedelta(minutes=5))
    on = _between(df5, day0, cal_day + pd.Timedelta(hours=9.5))
    a, b, at, bt = _hl(on)
    add("Plus haut overnight", a, at, "jour"); add("Plus bas overnight", b, bt, "jour")
    asia = _between(df5, day0 + pd.Timedelta(hours=2), day0 + pd.Timedelta(hours=6))   # 20:00-00:00
    asia_h, asia_l, _, _ = _hl(asia)
    add("Haut boîte asiatique (20h-0h)", asia_h, None, "jour"); add("Bas boîte asiatique", asia_l, None, "jour")
    lon = _between(df5, cal_day + pd.Timedelta(hours=2), cal_day + pd.Timedelta(hours=5))
    a, b, _, _ = _hl(lon)
    add("Haut Londres (2h-5h)", a, None, "jour"); add("Bas Londres", b, None, "jour")
    mid = df5[df5.index >= cal_day]
    mid_open = mid["Open"].iloc[0] if not mid.empty else np.nan
    add("Ouverture de minuit NY", mid_open, cal_day, "jour")
    o830 = df5[df5.index >= cal_day + pd.Timedelta(hours=8.5)]
    if not o830.empty and o830.index[0] < cal_day + pd.Timedelta(hours=9):
        add("Ouverture 8:30", o830["Open"].iloc[0], o830.index[0], "jour")
    o930 = df5[df5.index >= cal_day + pd.Timedelta(hours=9.5)]
    if not o930.empty and o930.index[0] < cal_day + pd.Timedelta(hours=10):
        add("Ouverture cash 9:30", o930["Open"].iloc[0], o930.index[0], "jour")
    ib = _between(df5, cal_day + pd.Timedelta(hours=9.5), cal_day + pd.Timedelta(hours=10.5))
    if len(ib) >= 12:
        a, b, _, _ = _hl(ib)
        add("IB haut (9:30-10:30)", a, None, "jour"); add("IB bas", b, None, "jour")

    # --- semaine / mois / macro
    wk_start = day0 - pd.Timedelta(days=(cal_day.dayofweek))  # dimanche 18:00
    wk = _between(df5, wk_start, now + pd.Timedelta(minutes=5))
    if not wk.empty:
        add("Ouverture hebdo (dim. 18:00)", wk["Open"].iloc[0], wk.index[0], "semaine")
    mon = _between(df5, wk_start, wk_start + pd.Timedelta(hours=23))
    if not mon.empty and now > wk_start + pd.Timedelta(hours=23):
        a, b, _, _ = _hl(mon)
        add("Haut du lundi (Warren)", a, None, "semaine"); add("Bas du lundi (Warren)", b, None, "semaine")
    pwk = _between(df5, wk_start - pd.Timedelta(days=7), wk_start)
    a, b, at, bt = _hl(pwk)
    add("Plus haut semaine précédente", a, at, "semaine"); add("Plus bas semaine précédente", b, bt, "semaine")
    if dfd is not None and not dfd.empty:
        d = dfd.copy()
        cur = d[d.index.month == cal_day.month]
        cur = cur[cur.index.year == cal_day.year]
        if not cur.empty:
            add("Ouverture du mois", cur["Open"].iloc[0], cur.index[0], "macro")
        q0 = (cal_day.month - 1) // 3 * 3 + 1
        q = d[(d.index.year == cal_day.year) & (d.index.month >= q0) & (d.index.month <= cal_day.month)]
        if not q.empty:
            add("Ouverture du trimestre", q["Open"].iloc[0], q.index[0], "macro")
        y = d[d.index.year == cal_day.year]
        if not y.empty:
            add("Ouverture annuelle", y["Open"].iloc[0], y.index[0], "macro")

    lv = pd.DataFrame(L)
    if not lv.empty:
        lv["distance"] = lv["prix"] - price
        lv = lv.sort_values("prix", ascending=False).reset_index(drop=True)

    # --- volatilité attendue
    meta = {"price": price, "now": now, "cal_day": cal_day, "day0": day0, "mid_open": mid_open,
            "asia_h": asia_h, "asia_l": asia_l, "pdh": ph, "pdl": pl}
    if dfd is not None and len(dfd) > 20:
        tr = pd.concat([dfd["High"] - dfd["Low"], (dfd["High"] - dfd["Close"].shift()).abs(),
                        (dfd["Low"] - dfd["Close"].shift()).abs()], axis=1).max(axis=1)
        meta["atr14"] = tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-2]
        rngs = (dfd["High"] - dfd["Low"]).iloc[-61:-1]
        meta["range_q"] = rngs.quantile([.25, .5, .75]).values
    if vxn and not np.isnan(vxn):
        sigma = price * vxn / 100 / np.sqrt(252)
        meta["vxn"] = vxn
        meta["implied_1sd"] = sigma
        meta["implied_range"] = sigma * 1.596    # E[range] ≈ 1,6 σ (Parkinson)
    meta["done_today"] = (today["High"].max() - today["Low"].min()) if not today.empty else np.nan
    if not np.isnan(mid_open):
        meta["premium"] = price > mid_open
    return {"table": lv, "meta": meta}


def asia_london_ny_stats(df1h: pd.DataFrame) -> dict:
    """Balayage du range asiatique (20:00-00:00 NY) par Londres (2-8) puis NY (8-16)."""
    res = {"london_one": 0, "london_both": 0, "london_none": 0, "ny_other": 0, "n": 0, "ny_other_n": 0}
    days = sorted(set((df1h.index + pd.Timedelta(hours=6)).normalize()))
    for d in days:
        asia = _between(df1h, d - pd.Timedelta(hours=4), d)
        lon = _between(df1h, d + pd.Timedelta(hours=2), d + pd.Timedelta(hours=8))
        ny = _between(df1h, d + pd.Timedelta(hours=8), d + pd.Timedelta(hours=16))
        if len(asia) < 3 or len(lon) < 4 or len(ny) < 6:
            continue
        ah, al = asia["High"].max(), asia["Low"].min()
        th, tl = lon["High"].max() > ah, lon["Low"].min() < al
        res["n"] += 1
        if th and tl:
            res["london_both"] += 1
        elif th or tl:
            res["london_one"] += 1
            res["ny_other_n"] += 1
            if (th and ny["Low"].min() < al) or (tl and ny["High"].max() > ah):
                res["ny_other"] += 1
        else:
            res["london_none"] += 1
    return res


def pdh_pdl_sweep_stats(df1h: pd.DataFrame) -> pd.DataFrame:
    """Pour chaque jour : PDH/PDL pris avant NY, pendant NY (9-16), issue après balayage."""
    out = []
    days = sorted(set((df1h.index + pd.Timedelta(hours=6)).normalize()))
    for k in range(1, len(days)):
        d, p = days[k], days[k - 1]
        prev = _between(df1h, p - pd.Timedelta(hours=6), p + pd.Timedelta(hours=17))
        pre = _between(df1h, d - pd.Timedelta(hours=6), d + pd.Timedelta(hours=9))
        ny = _between(df1h, d + pd.Timedelta(hours=9), d + pd.Timedelta(hours=16))
        if prev.empty or ny.empty or pre.empty:
            continue
        pdh, pdl = prev["High"].max(), prev["Low"].min()
        r = {"day": d, "pdh_pre": pre["High"].max() > pdh, "pdl_pre": pre["Low"].min() < pdl,
             "pdh_ny": ny["High"].max() > pdh, "pdl_ny": ny["Low"].min() < pdl}
        close = ny["Close"].iloc[-1]
        if r["pdh_ny"] and not r["pdh_pre"]:
            r["pdh_outcome"] = "continuation" if close > pdh else "retour range"
        if r["pdl_ny"] and not r["pdl_pre"]:
            r["pdl_outcome"] = "continuation" if close < pdl else "retour range"
        out.append(r)
    return pd.DataFrame(out)


def extreme_hour_stats(df1h: pd.DataFrame) -> pd.DataFrame:
    """Heure (NY) de formation du plus haut et du plus bas de chaque journée CME."""
    d = df1h.copy()
    d["day"] = (d.index + pd.Timedelta(hours=6)).normalize()
    rows = []
    for day, g in d.groupby("day"):
        if len(g) < 18:
            continue
        rows.append({"day": day, "h_hour": g["High"].idxmax().hour, "l_hour": g["Low"].idxmin().hour})
    return pd.DataFrame(rows)
