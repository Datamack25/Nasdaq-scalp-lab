"""Moteur MMM – alphabet des bougies (MMMFCB), sweeps, volume, momentum, PCX.

Références : Masterclass MMM module 1, 6, 7 ; backtest 17 758 configurations.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NEAR = 0.70  # « clôture près du sommet » = dans le tiers haut de son propre range

# description courte de chaque code (affichage)
CODE_INFO = {
    "BuBC+": ("Clôture de corps haussière forte", "ENTRER à la clôture, C1 = sommet", "long", 3),
    "BuBC-": ("Clôture de corps haussière – friction", "NE PAS ENTRER (rechargement)", "long", 1),
    "BeBC+": ("Clôture de corps baissière forte", "ENTRER à la clôture, C1 = bas", "short", 3),
    "BeBC-": ("Clôture de corps baissière – friction", "NE PAS ENTRER (rechargement)", "short", 1),
    "BuC2+": ("Sweep souverain haussier", "ENTRER à la clôture, stop 1 tick sous la mèche", "long", 4),
    "BuC2-": ("Sweep haussier + BC avec mèche de retour", "Entrée 50 % clôture-bas", "long", 2),
    "BeC2+": ("Sweep souverain baissier", "ENTRER à la clôture, stop 1 tick au-dessus de la mèche", "short", 4),
    "BeC2-": ("Sweep baissier + BC avec mèche de retour", "Entrée 50 % clôture-haut", "short", 2),
    "BuAFs+": ("Affinité haussière (rejet du Mur)", "Entrée clôture, C1 = sommet", "long", 2),
    "BuAFs-": ("Affinité haussière faible", "Entrée 50 % de la mèche", "long", 1),
    "BeAFs+": ("Affinité baissière (rejet du Mur)", "Entrée clôture, C1 = bas", "short", 2),
    "BeAFs-": ("Affinité baissière faible", "Entrée 50 % de la mèche", "short", 1),
    "CI BuAF": ("Inside bar – moitié haute", "ÉVITER, attendre la BC de sortie", "neutre", 0),
    "CI BeAF": ("Inside bar – moitié basse", "ÉVITER, attendre la BC de sortie", "neutre", 0),
    "S&D BuAF": ("Cherche & Détruit – clôture haute", "ATTENDRE la 1re BC sortante", "neutre", 0),
    "S&D BeAF": ("Cherche & Détruit – clôture basse", "ATTENDRE la 1re BC sortante", "neutre", 0),
    "—": ("Indéterminé", "", "neutre", 0),
}


def classify(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les colonnes MMM à un OHLCV : code, family, direction, quality, wick_ok."""
    o, h, l, c = (df[k].values for k in ("Open", "High", "Low", "Close"))
    ph, pl = np.r_[np.nan, h[:-1]], np.r_[np.nan, l[:-1]]
    rng = np.where(h - l > 0, h - l, np.nan)
    pos = (c - l) / rng
    up_break, dn_break = h > ph, l < pl
    bu_bc, be_bc = c > ph, c < pl
    low_wick = np.minimum(o, c) - l
    up_wick = h - np.maximum(o, c)

    code = np.full(len(df), "—", dtype=object)
    near_top, near_bot = pos >= NEAR, pos <= 1 - NEAR

    # ordre de priorité : sweeps souverains > BC > S&D > AF > CI
    c2u = dn_break & bu_bc
    c2d = up_break & be_bc
    code[c2u] = np.where(near_top[c2u], "BuC2+", "BuC2-")
    code[c2d] = np.where(near_bot[c2d], "BeC2+", "BeC2-")
    m = (code == "—") & bu_bc
    code[m] = np.where(near_top[m], "BuBC+", "BuBC-")
    m = (code == "—") & be_bc
    code[m] = np.where(near_bot[m], "BeBC+", "BeBC-")
    m = (code == "—") & up_break & dn_break
    code[m] = np.where(pos[m] >= .5, "S&D BuAF", "S&D BeAF")
    m = (code == "—") & dn_break
    code[m] = np.where(near_top[m], "BuAFs+", "BuAFs-")
    m = (code == "—") & up_break
    code[m] = np.where(near_bot[m], "BeAFs+", "BeAFs-")
    m = (code == "—") & ~up_break & ~dn_break & ~np.isnan(ph)
    code[m] = np.where(pos[m] >= .5, "CI BuAF", "CI BeAF")

    fam = np.full(len(df), "", dtype=object)
    for k, v in (("BuBC", "BuBC"), ("BuC2", "BuBC"), ("BeBC", "BeBC"), ("BeC2", "BeBC"),
                 ("BuAFs", "BuAF"), ("BeAFs", "BeAF"), ("CI", "CI"), ("S&D", "SD")):
        fam[np.char.startswith(code.astype(str), k)] = v
    direction = np.select([np.isin(fam, ["BuBC", "BuAF"]), np.isin(fam, ["BeBC", "BeAF"])], [1, -1], 0)
    # règle de mèche : pas d'entrée BuX sans mèche basse, BeX sans mèche haute
    tick = 0.25
    wick_ok = np.where(direction > 0, low_wick >= tick, np.where(direction < 0, up_wick >= tick, False))
    out = df.copy()
    out["mmm"] = code
    out["family"] = fam
    out["dir"] = direction
    out["strong"] = np.char.endswith(code.astype(str), "+")
    out["wick_ok"] = wick_ok
    out["close_pos"] = pos
    out["is_bc"] = np.isin(fam, ["BuBC", "BeBC"])
    out["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20, min_periods=5).mean().replace(0, np.nan)
    out["build_count"] = _build_count(out)
    out["pcx"] = _pcx(out)
    return out


def _build_count(cdf: pd.DataFrame) -> np.ndarray:
    """Nombre de BC consécutives dans la même direction (les NBC n'interrompent pas,
    une BC opposée remet à zéro). Mur du momentum : 4 haussier / 3 baissier."""
    cnt = np.zeros(len(cdf), dtype=int)
    cur = 0
    for i, (bc, d) in enumerate(zip(cdf["is_bc"].values, cdf["dir"].values)):
        if bc:
            cur = cur + d if np.sign(cur) == d or cur == 0 else d
        cnt[i] = cur
    return cnt


def _pcx(cdf: pd.DataFrame, look: int = 5) -> np.ndarray:
    """Système 4 : CDLx+ (BuBC clôture au-dessus de l'ouverture d'une BeBC récente)
    et CDSx+ (BeBC clôture sous le BAS d'une BuBC récente)."""
    out = np.full(len(cdf), "", dtype=object)
    fam, o, l, c = cdf["family"].values, cdf["Open"].values, cdf["Low"].values, cdf["Close"].values
    last_be_open, last_bu_low, last_be_i, last_bu_i = np.nan, np.nan, -99, -99
    for i in range(len(cdf)):
        if fam[i] == "BuBC" and i - last_be_i <= look and c[i] > last_be_open:
            out[i] = "CDLx+"
        if fam[i] == "BeBC" and i - last_bu_i <= look and c[i] < last_bu_low:
            out[i] = "CDSx+"
        if fam[i] == "BeBC":
            last_be_open, last_be_i = o[i], i
        if fam[i] == "BuBC":
            last_bu_low, last_bu_i = l[i], i
    return out


def sweep_grade(o: float, h: float, l: float, c: float, level: float, side: str) -> str | None:
    """Grade X / X+ / X++ d'un sweep. side='high' (sweep d'un SH) ou 'low'."""
    mid = (h + l) / 2
    if side == "high":
        if not (h > level and c < level):
            return None
        if c < mid:
            return "X++"
        return "X+" if c < o else "X"
    if not (l < level and c > level):
        return None
    if c > mid:
        return "X++"
    return "X+" if c > o else "X"


def volume_read(ratio: float) -> tuple[str, str]:
    """Lecture du ratio de volume (Masterclass module 7)."""
    if ratio is None or np.isnan(ratio):
        return "n.d.", "Volume indisponible"
    if ratio >= 1.5:
        return "Épuisement", "≥1,5× : retournement à conviction maximale sur bougie confirmatrice"
    if ratio >= 1.2:
        return "Absorption", "≥1,2× : rejet institutionnel à haute conviction"
    if ratio > 0.8:
        return "Défense", "0,8-1,2× : niveau défendu sans violence, attendre la BC suivante"
    return "Chasse aux stops", "≤0,8× : sweep mince, le mouvement continue souvent dans le sens du sweep"


def momentum_phase(cdf: pd.DataFrame, entry_idx: int, direction: int) -> dict:
    """Cycle de vie du momentum après une entrée : construction / touche / échec."""
    if entry_idx >= len(cdf) - 1:
        return {"phase": "En attente", "builds": 0, "touches": 0}
    entry = cdf["Close"].iloc[entry_idx]
    after = cdf.iloc[entry_idx + 1:]
    builds = touches = 0
    for _, r in after.iterrows():
        if direction > 0:
            if r["Close"] < entry:
                return {"phase": "ÉCHEC – sortir", "builds": builds, "touches": touches}
            if r["Low"] <= entry:
                touches += 1
            elif r["dir"] > 0 and r["is_bc"]:
                builds += 1
        else:
            if r["Close"] > entry:
                return {"phase": "ÉCHEC – sortir", "builds": builds, "touches": touches}
            if r["High"] >= entry:
                touches += 1
            elif r["dir"] < 0 and r["is_bc"]:
                builds += 1
    wall = 4 if direction > 0 else 3
    if builds >= wall:
        ph = "MUR DU MOMENTUM – sortir 75-100 %"
    elif touches:
        ph = f"TOUCHE n°{touches} – resserrer le stop"
    else:
        ph = "CONSTRUCTION – tenir"
    return {"phase": ph, "builds": builds, "touches": touches}


def backtest_configs(cdf: pd.DataFrame, max_bars: int = 2) -> pd.DataFrame:
    """Backtest MMM sur les données chargées : entrée ouverture suivante,
    objectif = extrême de la bougie signal, stop = extrême opposé, horizon `max_bars`.
    Résultat : win / invalid / both (atteints dans la même barre) / expiré."""
    o, h, l = cdf["Open"].values, cdf["High"].values, cdf["Low"].values
    fam, hours = cdf["family"].values, cdf.index
    rows = []
    for i in range(1, len(cdf) - max_bars - 1):
        f = fam[i]
        if f not in ("BuBC", "BeBC", "BuAF", "BeAF"):
            continue
        long = f in ("BuBC", "BuAF")
        tgt, stp = (h[i], l[i]) if long else (l[i], h[i])
        entry = o[i + 1]
        if (long and entry >= tgt) or (not long and entry <= tgt):
            res = "win"
        else:
            res = "expiré"
            for j in range(i + 1, i + 1 + max_bars):
                hit_t = h[j] >= tgt if long else l[j] <= tgt
                hit_s = l[j] <= stp if long else h[j] >= stp
                if hit_t and hit_s:
                    res = "les deux"; break
                if hit_t:
                    res = "win"; break
                if hit_s:
                    res = "invalid"; break
        rows.append((hours[i], f, cdf["mmm"].values[i], res, abs(tgt - entry), abs(entry - stp)))
    return pd.DataFrame(rows, columns=["time", "family", "code", "result", "reward_pts", "risk_pts"])
