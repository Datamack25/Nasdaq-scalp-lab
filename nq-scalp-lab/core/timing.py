"""Timing : session / killzone active, feux MMM (jour, H4, H1, M15), meilleurs
jours et meilleures heures mesurés sur les données chargées."""
from __future__ import annotations

import pandas as pd

from .config import (KILLZONES, MMM_DAY, MMM_H1_UTC, MMM_H4_UTC, MMM_M15_AVOID_UTC,
                     NY_TZ, PARIS_TZ)

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def hdec(ts: pd.Timestamp) -> float:
    return ts.hour + ts.minute / 60


def active_killzones(ts: pd.Timestamp) -> list[tuple]:
    t = hdec(ts.tz_convert(NY_TZ))
    return [k for k in KILLZONES if k[1] <= t < k[2]]


def session_name(ts: pd.Timestamp) -> str:
    t = hdec(ts.tz_convert(NY_TZ))
    if 18 <= t or t < 2:
        return "Asie"
    if 2 <= t < 8:
        return "Londres"
    if 8 <= t < 17:
        return "New York"
    return "Maintenance CME (17h-18h)"


def mmm_traffic(ts: pd.Timestamp) -> dict:
    """Feux du backtest MMM pour l'instant ts (tables en UTC)."""
    u = ts.tz_convert("UTC")
    ny = ts.tz_convert(NY_TZ)
    out = {}
    # jour de trading = jour courant
    jour = JOURS[ny.dayofweek]
    bu, be = MMM_DAY["BuBC"].get(jour), MMM_DAY["BeBC"].get(jour)
    out["jour"] = {"jour": jour, "BuBC": bu, "BeBC": be,
                   "feu": "rouge" if (be is not None and be < 50) else "vert" if (bu or 0) >= 71 else "orange"}
    # H4 : la bougie signal précédente (fermée) détermine la fenêtre en cours
    h4_open = ((u.hour - 2) // 4) * 4 + 2
    prev_sig = (h4_open - 4) % 24
    bu4, be4, f4 = MMM_H4_UTC.get(prev_sig, (None, None, "orange"))
    out["h4"] = {"signal_utc": f"{prev_sig:02d}-{(prev_sig + 4) % 24:02d}", "BuBC": bu4, "BeBC": be4, "feu": f4}
    # H1 : bougie signal = heure précédente
    sig1 = (u.hour - 1) % 24
    bu1, be1 = MMM_H1_UTC.get(sig1, (None, None))
    vals = [v for v in (bu1, be1) if v]
    f1 = "vert" if vals and max(vals) >= 72 else "rouge" if vals and max(vals) < 66 else "orange"
    out["h1"] = {"signal_utc": f"{sig1:02d}:00", "BuBC": bu1, "BeBC": be1, "feu": f1}
    hu = u.hour + u.minute / 60
    avoid15 = any(a <= hu < b for a, b in MMM_M15_AVOID_UTC)
    out["m15"] = {"feu": "rouge" if avoid15 else "vert" if 8.25 <= hu < 13.5 else "orange"}
    # fenêtres ICT / MMM
    t = hdec(ny)
    if 11.5 <= t < 13.5:
        out["ict"] = ("rouge", "Zone morte NY (11h30-13h30) : NE PAS TRADER")
    elif 2.5 <= t < 3.0:
        out["ict"] = ("rouge", "Judas de Londres : NE PAS ENTRER, laisser les stops sauter")
    elif 9.5 <= t < 9.75:
        out["ict"] = ("orange", "Ouverture cash : attendre 15 min (IB en formation)")
    elif 8.0 <= t < 11.5:
        out["ict"] = ("vert", "Fenêtre d'Or NY (8h-11h30) : fenêtre principale")
    elif 3.0 <= t < 5.0:
        out["ict"] = ("vert", "Ouverture / killzone de Londres : vraie origine de tendance")
    elif 14.0 <= t < 16.0:
        out["ict"] = ("orange", "Après-midi NY : Silver Bullet PM / dernière heure, risque serré")
    elif 17 <= t < 18:
        out["ict"] = ("rouge", "Marché CME fermé (maintenance)")
    else:
        out["ict"] = ("orange", "Hors fenêtre principale : setups A+ uniquement")
    return out


def to_paris(ts: pd.Timestamp) -> str:
    return ts.tz_convert(PARIS_TZ).strftime("%a %d %b %H:%M")


def hourly_profile(df: pd.DataFrame, horizon_bars: int = 1) -> pd.DataFrame:
    """Profil par heure NY : range moyen, |rendement|, % hausse, volume — mesuré."""
    d = df.copy()
    d["ret"] = d["Close"].shift(-horizon_bars) / d["Close"] - 1
    d["rng"] = d["High"] - d["Low"]
    d["hour"] = d.index.hour
    g = d.groupby("hour").agg(range_moy=("rng", "mean"), abs_ret=("ret", lambda x: x.abs().mean() * 1e4),
                              pct_hausse=("ret", lambda x: (x > 0).mean() * 100),
                              volume=("Volume", "mean"), n=("ret", "count"))
    g.index.name = "heure NY"
    return g


def weekday_hour_heatmap(df: pd.DataFrame, value: str = "range") -> pd.DataFrame:
    d = df.copy()
    d["rng"] = d["High"] - d["Low"]
    d["ret"] = (d["Close"] / d["Open"] - 1) * 1e4
    d["jour"] = [JOURS[i] for i in d.index.dayofweek]
    d["heure"] = d.index.hour
    col = {"range": "rng", "rendement": "ret"}[value]
    pv = d.pivot_table(index="jour", columns="heure", values=col, aggfunc="mean")
    order = [j for j in JOURS if j in pv.index]
    return pv.loc[order]


def best_windows(df1h: pd.DataFrame, cfg_bt: pd.DataFrame | None = None) -> pd.DataFrame:
    """Classement des heures (NY) : range moyen (opportunité) et taux de réussite
    MMM mesuré sur les données (qualité)."""
    prof = hourly_profile(df1h)
    if cfg_bt is not None and not cfg_bt.empty:
        b = cfg_bt[cfg_bt["family"].isin(["BuBC", "BeBC"])].copy()
        b["hour"] = pd.DatetimeIndex(b["time"]).tz_convert(NY_TZ).hour
        b["w"] = (b["result"] == "win").astype(float)
        w = b.groupby("hour").agg(win_bc=("w", "mean"), n_bc=("w", "size"))
        prof = prof.join(w)
        prof["win_bc"] *= 100
    prof["score"] = (prof["range_moy"] / prof["range_moy"].max()) * 50 + \
        (prof.get("win_bc", pd.Series(60, index=prof.index)).fillna(60) - 50)
    return prof.sort_values("score", ascending=False)


def weekday_stats(dfd: pd.DataFrame) -> pd.DataFrame:
    d = dfd.copy()
    d["ret"] = (d["Close"] / d["Open"] - 1) * 100
    d["rng"] = d["High"] - d["Low"]
    d["jour"] = [JOURS[i] for i in d.index.dayofweek]
    g = d.groupby("jour").agg(range_moy=("rng", "mean"), ret_moy=("ret", "mean"),
                              pct_hausse=("ret", lambda x: (x > 0).mean() * 100), n=("ret", "size"))
    return g.reindex([j for j in JOURS[:5] if j in g.index])
