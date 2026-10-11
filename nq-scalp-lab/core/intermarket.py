"""Intermarché ICT : divergence SMT (NQ vs ES/YM), dollar, taux, VIX, poids lourds."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .structure import fractal_swings


def smt_divergence(a: pd.DataFrame, b: pd.DataFrame, n: int = 3, look: int = 120) -> dict:
    """SMT (Smart Money Technique) : le marché A fait un nouveau plus haut (bas) que
    B ne confirme pas. Retourne le signal le plus récent."""
    a, b = a.iloc[-look:], b.iloc[-look:]
    idx = a.index.intersection(b.index)
    if len(idx) < 30:
        return {"signal": 0, "label": "Données insuffisantes"}
    a, b = a.loc[idx], b.loc[idx]
    sa = fractal_swings(a, n)
    out = {"signal": 0, "label": "Pas de divergence SMT"}
    for t in ("SH", "SL"):
        xa = sa[sa["type"] == t].tail(2)
        if len(xa) < 2:
            continue
        i0, i1 = xa["i"].values
        pa0, pa1 = xa["price"].values
        col = "High" if t == "SH" else "Low"
        # valeurs de B autour des mêmes pivots (±n barres)
        pb0 = b[col].iloc[max(0, i0 - n):i0 + n + 1].agg("max" if t == "SH" else "min")
        pb1 = b[col].iloc[max(0, i1 - n):i1 + n + 1].agg("max" if t == "SH" else "min")
        if t == "SH" and ((pa1 > pa0) != (pb1 > pb0)):
            leader = "NQ" if pa1 > pa0 else "partenaire"
            out = {"signal": -1, "time": a.index[i1],
                   "label": f"SMT baissière : {'NQ fait un plus haut, le partenaire non' if leader == 'NQ' else 'le partenaire fait un plus haut, NQ non'}"}
        if t == "SL" and ((pa1 < pa0) != (pb1 < pb0)):
            leader = "NQ" if pa1 < pa0 else "partenaire"
            sig = {"signal": 1, "time": a.index[i1],
                   "label": f"SMT haussière : {'NQ fait un plus bas, le partenaire non' if leader == 'NQ' else 'le partenaire fait un plus bas, NQ non'}"}
            if out["signal"] == 0 or sig["time"] > out.get("time", sig["time"]):
                out = sig
    return out


def partner_snapshot(closes: dict[str, pd.Series], ref: str = "NQ=F", window: int = 288) -> pd.DataFrame:
    """Variation du jour, corrélation glissante avec NQ et tendance courte de chaque partenaire."""
    rows = []
    nq = closes.get(ref)
    if nq is None or nq.empty:
        return pd.DataFrame()
    rnq = np.log(nq).diff()
    for tk, s in closes.items():
        if s is None or s.empty:
            continue
        r = np.log(s).diff()
        j = pd.concat([rnq, r], axis=1, join="inner").dropna().iloc[-window:]
        corr = j.corr().iloc[0, 1] if len(j) > 20 else np.nan
        day = s[s.index >= s.index[-1].normalize()]
        chg = (s.iloc[-1] / day.iloc[0] - 1) * 100 if len(day) > 1 else (s.iloc[-1] / s.iloc[-79] - 1) * 100 if len(s) > 80 else np.nan
        mom = (s.iloc[-1] / s.iloc[-13] - 1) * 100 if len(s) > 13 else np.nan   # 1 h en 5 min
        rows.append({"ticker": tk, "dernier": s.iloc[-1], "var_jour_%": chg, "mom_1h_%": mom, "corr_NQ": corr})
    return pd.DataFrame(rows).set_index("ticker")


def intermarket_score(snap: pd.DataFrame, relations: dict) -> tuple[float, list[str]]:
    """Score de -1 à +1 pour NQ à partir des partenaires (signe x relation x momentum)."""
    if snap.empty:
        return 0.0, ["Intermarché indisponible"]
    notes, s, w = [], 0.0, 0.0
    weights = {"ES=F": 1.0, "YM=F": .5, "RTY=F": .4, "DX-Y.NYB": .8, "^TNX": .8, "^VIX": 1.0, "^VXN": .6}
    for tk, wt in weights.items():
        if tk not in snap.index or tk not in relations:
            continue
        m = snap.loc[tk, "mom_1h_%"]
        if np.isnan(m):
            continue
        rel = relations[tk]["relation"]
        scale = {"^VIX": 3.0, "^VXN": 3.0, "^TNX": 0.6, "DX-Y.NYB": 0.15}.get(tk, 0.25)
        contrib = np.tanh(m / scale) * rel
        s += contrib * wt; w += wt
        if abs(contrib) > .4:
            sens = "soutient" if contrib > 0 else "pèse sur"
            notes.append(f"{relations[tk]['nom']} {m:+.2f} % sur 1 h → {sens} le Nasdaq")
    return (s / w if w else 0.0), notes


def breadth(closes: dict[str, pd.Series]) -> dict:
    up, chg = 0, []
    for tk, s in closes.items():
        if s is None or len(s) < 2:
            continue
        day = s[s.index >= s.index[-1].normalize()]
        base = day.iloc[0] if len(day) > 1 else s.iloc[-2]
        c = (s.iloc[-1] / base - 1) * 100
        chg.append((tk, c)); up += c > 0
    n = len(chg)
    return {"n": n, "up": up, "pct_up": up / n * 100 if n else np.nan,
            "detail": sorted(chg, key=lambda x: -x[1])}
