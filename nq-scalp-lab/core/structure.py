"""Structure de marché : swings MMM, CDL/CDS (MSB), orderblocks & breakers (Warren),
gaps UDG/ULG/UAG (FVG), dealing range Prime/Décote, OTE, liquidité (EQH/EQL)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# ===================================================================== swings
def mmm_swings(cdf: pd.DataFrame, dedup: int = 5) -> pd.DataFrame:
    """Machine à états MMM : état +1 suit les plus hauts ; une BeBC verrouille le
    haut suivi comme SH et bascule à -1 (et inversement). Déduplication 5 bougies."""
    h, l, fam = cdf["High"].values, cdf["Low"].values, cdf["family"].values
    state, th_i, tl_i = 1, 0, 0
    piv = []
    for i in range(1, len(cdf)):
        if state == 1:
            if h[i] >= h[th_i]:
                th_i = i
            if fam[i] == "BeBC" and i != th_i:
                piv.append((th_i, "SH", h[th_i], i)); state, tl_i = -1, i
        else:
            if l[i] <= l[tl_i]:
                tl_i = i
            if fam[i] == "BuBC" and i != tl_i:
                piv.append((tl_i, "SL", l[tl_i], i)); state, th_i = 1, i
    # déduplication : deux swings du même type à <= dedup barres -> le plus extrême
    out = []
    for p in piv:
        if out and out[-1][1] == p[1] and p[0] - out[-1][0] <= dedup:
            better = p[2] > out[-1][2] if p[1] == "SH" else p[2] < out[-1][2]
            if better:
                out[-1] = p
            continue
        out.append(p)
    sw = pd.DataFrame(out, columns=["i", "type", "price", "ci"])
    if len(sw):
        sw["time"] = cdf.index[sw["i"].values]
    return sw


def fractal_swings(df: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Pivots fractals classiques (n barres de chaque côté) – utilisés pour la liquidité."""
    h, l = df["High"].values, df["Low"].values
    rows = []
    for i in range(n, len(df) - n):
        if h[i] == h[i - n:i + n + 1].max():
            rows.append((i, "SH", h[i], i + n))
        if l[i] == l[i - n:i + n + 1].min():
            rows.append((i, "SL", l[i], i + n))
    sw = pd.DataFrame(rows, columns=["i", "type", "price", "ci"])
    if len(sw):
        sw["time"] = df.index[sw["i"].values]
    return sw


def trend_from_swings(sw: pd.DataFrame) -> str:
    shs = sw[sw["type"] == "SH"]["price"].tail(2).values
    sls = sw[sw["type"] == "SL"]["price"].tail(2).values
    if len(shs) < 2 or len(sls) < 2:
        return "indéterminée"
    if shs[1] > shs[0] and sls[1] > sls[0]:
        return "haussière (HH/HL)"
    if shs[1] < shs[0] and sls[1] < sls[0]:
        return "baissière (LH/LL)"
    return "range / transition"


# ==================================================================== CDL/CDS
def cdl_cds(cdf: pd.DataFrame, sw: pd.DataFrame) -> pd.DataFrame:
    """Système 1 MMM : CDL = clôture au-dessus du dernier SH confirmé,
    CDS = clôture sous le dernier SL confirmé (= MSB de Warren).
    Retourne les événements avec ancre (stop structurel) et invalidation."""
    c = cdf["Close"].values
    events = []
    if sw.empty:
        return pd.DataFrame(columns=["i", "time", "signal", "level", "anchor"])
    sw = sw.sort_values("ci")
    last_sh = last_sl = None
    ptr = 0
    swl = sw.to_dict("records")
    active = 0
    leg = 0
    for i in range(len(cdf)):
        while ptr < len(swl) and swl[ptr]["ci"] <= i:
            if swl[ptr]["type"] == "SH":
                last_sh = swl[ptr]
            else:
                last_sl = swl[ptr]
            ptr += 1
        if last_sh is not None and c[i] > last_sh["price"] and last_sh.get("used") is None:
            last_sh["used"] = True
            leg = leg + 1 if active == 1 else 0
            active = 1
            sig = "CDL" if leg == 0 else f"LD{min(leg, 3)}"
            events.append((i, cdf.index[i], sig, last_sh["price"], last_sl["price"] if last_sl else np.nan))
        if last_sl is not None and c[i] < last_sl["price"] and last_sl.get("used") is None:
            last_sl["used"] = True
            leg = leg + 1 if active == -1 else 0
            active = -1
            sig = "CDS" if leg == 0 else f"SD{min(leg, 3)}"
            events.append((i, cdf.index[i], sig, last_sl["price"], last_sh["price"] if last_sh else np.nan))
    return pd.DataFrame(events, columns=["i", "time", "signal", "level", "anchor"])


def active_structure(ev: pd.DataFrame, last_close: float) -> dict:
    if ev.empty:
        return {"bias": 0, "label": "Aucune cassure de structure", "anchor": np.nan, "since": None}
    last = ev.iloc[-1]
    bull = last["signal"].startswith(("CDL", "LD"))
    invalid = (last_close < last["anchor"]) if bull else (last_close > last["anchor"])
    if invalid:
        return {"bias": 0, "label": f"{last['signal']} invalidé (ancre {last['anchor']:.2f} violée)",
                "anchor": last["anchor"], "since": last["time"]}
    return {"bias": 1 if bull else -1,
            "label": f"{last['signal']} actif – cassure de {last['level']:.2f}, ancre {last['anchor']:.2f}",
            "anchor": last["anchor"], "since": last["time"], "signal": last["signal"]}


# ============================================================= orderblocks
@dataclass
class Zone:
    kind: str              # "OB+", "OB-", "BRK+", "BRK-", "UDG+", "UDG-", "ULG+", "ULG-", "UAG+", "UAG-"
    top: float
    bottom: float
    start: pd.Timestamp
    i: int
    status: str = "intacte"     # intacte / testée / comblée / invalidée
    method: str = ""
    ote: float = np.nan
    target: float = np.nan
    extra: dict = field(default_factory=dict)

    @property
    def direction(self) -> int:
        return 1 if self.kind.endswith("+") else -1

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2


def orderblocks(cdf: pd.DataFrame, ev: pd.DataFrame, sw: pd.DataFrame, max_n: int = 12) -> list[Zone]:
    """Orderblocks Warren : dernière bougie opposée avant l'impulsion qui a cassé la
    structure. Méthode C si un swing a été « couru » juste avant (liquidité).
    Un OB invalidé (clôture au-delà) devient un breaker de sens opposé."""
    o, h, l, c = (cdf[k].values for k in ("Open", "High", "Low", "Close"))
    zones: list[Zone] = []
    sl_prices = sw[sw["type"] == "SL"][["i", "price"]].values if len(sw) else np.empty((0, 2))
    sh_prices = sw[sw["type"] == "SH"][["i", "price"]].values if len(sw) else np.empty((0, 2))
    for _, e in ev.tail(max_n * 2).iterrows():
        i = int(e["i"])
        bull = e["signal"].startswith(("CDL", "LD"))
        lo = max(0, i - 40)
        if bull:
            leg_start = lo + int(np.argmin(l[lo:i + 1]))
            j = leg_start
            while j > lo and not (c[j] < o[j]):
                j -= 1
            if not c[j] < o[j]:
                continue
            leg_hi = h[leg_start:i + 1].max()
            ran = any((sl_i < leg_start) and (l[leg_start] < p) for sl_i, p in sl_prices[-3:])
            z = Zone("OB+", h[j], l[j], cdf.index[j], j, method="C (liquidité courue)" if ran else "A/B",
                     ote=leg_hi - 0.705 * (leg_hi - l[leg_start]), target=leg_hi)
        else:
            leg_start = lo + int(np.argmax(h[lo:i + 1]))
            j = leg_start
            while j > lo and not (c[j] > o[j]):
                j -= 1
            if not c[j] > o[j]:
                continue
            leg_lo = l[leg_start:i + 1].min()
            ran = any((sh_i < leg_start) and (h[leg_start] > p) for sh_i, p in sh_prices[-3:])
            z = Zone("OB-", h[j], l[j], cdf.index[j], j, method="C (liquidité courue)" if ran else "A/B",
                     ote=leg_lo + 0.705 * (h[leg_start] - leg_lo), target=leg_lo)
        # statut après formation
        after = slice(i + 1, len(cdf))
        if z.kind == "OB+":
            if (c[after] < z.bottom).any():
                z.kind, z.status = "BRK-", "breaker (OB+ échoué)"
            elif (l[after] <= z.top).any():
                z.status = "testée"
        else:
            if (c[after] > z.top).any():
                z.kind, z.status = "BRK+", "breaker (OB- échoué)"
            elif (h[after] >= z.bottom).any():
                z.status = "testée"
        zones.append(z)
    # dédoublonnage par bougie
    seen, uniq = set(), []
    for z in zones:
        if z.i not in seen:
            uniq.append(z); seen.add(z.i)
    return uniq[-max_n:]


# ======================================================================= gaps
def gaps(cdf: pd.DataFrame, lookback: int = 300) -> list[Zone]:
    """UDG (FVG 3 bougies), ULG (corps séparés, mèches connectées), UAG (gap absolu)."""
    df = cdf.iloc[-lookback:]
    off = len(cdf) - len(df)
    o, h, l, c = (df[k].values for k in ("Open", "High", "Low", "Close"))
    fam = df["family"].values if "family" in df else np.array([""] * len(df))
    zs: list[Zone] = []
    for k in range(2, len(df)):
        level = {"BuBC": 1, "BeBC": 1, "CI": 2, "BuAF": 3, "BeAF": 3}.get(fam[k], 0)
        if l[k] > h[k - 2]:
            zs.append(Zone("UDG+", l[k], h[k - 2], df.index[k], off + k, extra={"niveau": level}))
        elif h[k] < l[k - 2]:
            zs.append(Zone("UDG-", l[k - 2], h[k], df.index[k], off + k, extra={"niveau": level}))
    for k in range(1, len(df)):
        bt1, bb1 = max(o[k - 1], c[k - 1]), min(o[k - 1], c[k - 1])
        bt2, bb2 = max(o[k], c[k]), min(o[k], c[k])
        if l[k] > h[k - 1]:
            zs.append(Zone("UAG+", l[k], h[k - 1], df.index[k], off + k))
        elif h[k] < l[k - 1]:
            zs.append(Zone("UAG-", l[k - 1], h[k], df.index[k], off + k))
        elif bb2 > bt1 and l[k] <= h[k - 1]:
            zs.append(Zone("ULG+", bb2, bt1, df.index[k], off + k))
        elif bt2 < bb1 and h[k] >= l[k - 1]:
            zs.append(Zone("ULG-", bb1, bt2, df.index[k], off + k))
    # statut de comblement
    H, L, C = cdf["High"].values, cdf["Low"].values, cdf["Close"].values
    for z in zs:
        a = slice(z.i + 1, len(cdf))
        if z.direction > 0:
            if (C[a] < z.bottom).any():
                z.status = "violée"
            elif (L[a] <= z.bottom).any():
                z.status = "comblée"
            elif (L[a] <= z.top).any():
                z.status = "partielle"
        else:
            if (C[a] > z.top).any():
                z.status = "violée"
            elif (H[a] >= z.top).any():
                z.status = "comblée"
            elif (H[a] >= z.bottom).any():
                z.status = "partielle"
    return zs


def fvg_fill_stats(cdf: pd.DataFrame, horizons=(1, 5, 20)) -> pd.DataFrame:
    """Taux de comblement des FVG (partiel / total) dans les k bougies suivantes."""
    h, l = cdf["High"].values, cdf["Low"].values
    rows = []
    for k in range(2, len(cdf) - max(horizons)):
        if l[k] > h[k - 2]:
            top, bot, d = l[k], h[k - 2], 1
        elif h[k] < l[k - 2]:
            top, bot, d = l[k - 2], h[k], -1
        else:
            continue
        r = {"time": cdf.index[k], "dir": d, "size": top - bot}
        for n in horizons:
            seg = slice(k + 1, k + 1 + n)
            if d > 0:
                r[f"partiel_{n}"] = (l[seg] <= top).any(); r[f"total_{n}"] = (l[seg] <= bot).any()
            else:
                r[f"partiel_{n}"] = (h[seg] >= bot).any(); r[f"total_{n}"] = (h[seg] >= top).any()
        rows.append(r)
    return pd.DataFrame(rows)


# ============================================================ dealing range
def dealing_range(sw: pd.DataFrame, price: float) -> dict:
    """Range de négociation entre le dernier SH et le dernier SL : Prime / Décote / EQ."""
    if sw.empty or (sw["type"] == "SH").sum() == 0 or (sw["type"] == "SL").sum() == 0:
        return {"pos": np.nan, "zone": "n.d.", "high": np.nan, "low": np.nan, "eq": np.nan}
    hi = sw[sw["type"] == "SH"]["price"].iloc[-1]
    lo = sw[sw["type"] == "SL"]["price"].iloc[-1]
    hi, lo = max(hi, lo, price), min(hi, lo, price)
    pos = (price - lo) / (hi - lo) * 100 if hi > lo else 50
    zone = "Décote (0-35 %)" if pos <= 35 else "Prime (65-100 %)" if pos >= 65 else "Équilibre (35-65 %)"
    return {"pos": pos, "zone": zone, "high": hi, "low": lo, "eq": (hi + lo) / 2,
            "ote_long": hi - 0.705 * (hi - lo), "ote_short": lo + 0.705 * (hi - lo)}


def liquidity_pools(df: pd.DataFrame, price: float, tol_pct: float = 0.0004, n: int = 3) -> list[dict]:
    """Hauts égaux / bas égaux non pris (BSL/SSL) = pools de stops."""
    sw = fractal_swings(df.iloc[-400:], n=n)
    pools = []
    for t in ("SH", "SL"):
        s = sw[sw["type"] == t].sort_values("price")
        p = s["price"].values
        for a in range(len(p) - 1):
            if abs(p[a + 1] - p[a]) <= tol_pct * price:
                lvl = max(p[a], p[a + 1]) if t == "SH" else min(p[a], p[a + 1])
                after = df["High"].iloc[-400:] if t == "SH" else df["Low"].iloc[-400:]
                last_i = max(s["i"].values[a], s["i"].values[a + 1])
                taken = (after.iloc[last_i + 1:] > lvl).any() if t == "SH" else (after.iloc[last_i + 1:] < lvl).any()
                if not taken:
                    pools.append({"type": "BSL (hauts égaux)" if t == "SH" else "SSL (bas égaux)",
                                  "price": lvl, "dist": lvl - price})
    seen, out = set(), []
    for p in sorted(pools, key=lambda x: abs(x["dist"])):
        key = round(p["price"])
        if key not in seen:
            out.append(p); seen.add(key)
    return out[:8]


def ranges_and_deviation(df: pd.DataFrame, window: int = 48) -> dict:
    """Méthode range de Warren : range, EQ, déviation (sweep d'un bord) + MSB."""
    seg = df.iloc[-window:]
    hi, lo = seg["High"].max(), seg["Low"].min()
    eq = (hi + lo) / 2
    width = hi - lo
    atr = (df["High"] - df["Low"]).rolling(14).mean().iloc[-1]
    is_range = width < 6 * atr if atr and not np.isnan(atr) else False
    last = df.iloc[-6:]
    dev_hi = (last["High"] > hi * 0.9999).any() and last["Close"].iloc[-1] < hi
    dev_lo = (last["Low"] < lo * 1.0001).any() and last["Close"].iloc[-1] > lo
    price = df["Close"].iloc[-1]
    return {"high": hi, "low": lo, "eq": eq, "is_range": bool(is_range),
            "deviation": "haut dévié" if dev_hi else "bas dévié" if dev_lo else "aucune",
            "side": "au-dessus de l'EQ" if price > eq else "sous l'EQ"}
