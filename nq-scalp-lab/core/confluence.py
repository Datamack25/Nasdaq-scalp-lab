"""Moteur de décision : confluence MMM + ICT + Warren + intermarché + news + timing.

Produit : biais directionnel (-100..+100), checklist 5/5 (Masterclass module 8),
note du setup (A+ … NO TRADE), alignement « tempête parfaite », plan de trade
MNQ, probabilités par horizon et commentaire de marché en français.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .candles import CODE_INFO, sweep_grade, volume_read
from .config import MMM_ALIGNMENT
from .structure import Zone


@dataclass
class Component:
    name: str
    score: float          # -1 .. +1 (positif = haussier)
    weight: float
    tag: str              # HTF / MTF / LTF / CTX
    comment: str

    @property
    def pts(self) -> float:
        return self.score * self.weight


@dataclass
class Decision:
    bias: float
    direction: int
    grade: str
    components: list[Component]
    checklist: dict
    alignment: dict
    plan: dict | None
    horizon_probs: dict
    commentary: list[str]
    warnings: list[str] = field(default_factory=list)
    timing: dict = field(default_factory=dict)


HORIZON_TAG_W = {  # poids des familles de composantes par horizon
    1: {"LTF": 1.0, "MTF": .35, "HTF": .15, "CTX": .4},
    3: {"LTF": 1.0, "MTF": .5, "HTF": .2, "CTX": .5},
    5: {"LTF": .9, "MTF": .6, "HTF": .25, "CTX": .6},
    15: {"LTF": .7, "MTF": .9, "HTF": .4, "CTX": .7},
    60: {"LTF": .35, "MTF": 1.0, "HTF": .8, "CTX": .8},
    240: {"LTF": .15, "MTF": .7, "HTF": 1.0, "CTX": .9},
}


def _closed(cdf: pd.DataFrame, k: int = 1) -> pd.Series:
    """Dernière bougie CLÔTURÉE (la dernière ligne est supposée en formation)."""
    return cdf.iloc[-1 - k] if len(cdf) > k else cdf.iloc[-1]


def candle_score(row: pd.Series) -> float:
    code = row.get("mmm", "—")
    base = {"BuC2+": 1, "BuBC+": .9, "BuAFs+": .6, "BuC2-": .5, "BuBC-": .25, "BuAFs-": .3,
            "BeC2+": -1, "BeBC+": -.9, "BeAFs+": -.6, "BeC2-": -.5, "BeBC-": -.25, "BeAFs-": -.3}.get(code, 0)
    if base and not row.get("wick_ok", True):
        base *= .5   # règle de mèche
    return base


def decide(ctx: dict) -> Decision:
    """ctx : dictionnaire préparé par l'app (voir app_engine.build_context)."""
    comps: list[Component] = []
    warn: list[str] = []
    tfc = ctx["tf"]                      # {"1d": cdf, "4h": cdf, "1h": cdf, "15m": cdf, "5m": cdf}
    struct = ctx["struct"]               # {"4h": dict, "1h": dict, "15m": dict, "5m": dict}
    price = ctx["price"]
    lv = ctx["levels"]["meta"]

    # 1. Biais HTF : bougie daily clôturée + structure 4H
    d_row = _closed(tfc["1d"])
    d_sc = candle_score(d_row)
    comps.append(Component("Bougie daily (MMM)", d_sc, 10, "HTF",
                           f"Dernière daily clôturée : {d_row['mmm']} – {CODE_INFO.get(d_row['mmm'], ('',))[0]}"))
    s4 = struct.get("4h", {})
    comps.append(Component("Structure 4H (CDL/CDS)", s4.get("bias", 0), 12, "HTF", s4.get("label", "n.d.")))
    h4_row = _closed(tfc["4h"])
    comps.append(Component("Bougie 4H (MMM)", candle_score(h4_row), 6, "HTF", f"4H clôturée : {h4_row['mmm']}"))
    # 2. MTF
    s1 = struct.get("1h", {})
    comps.append(Component("Structure 1H", s1.get("bias", 0), 10, "MTF", s1.get("label", "n.d.")))
    s15 = struct.get("15m", {})
    comps.append(Component("Structure 15m", s15.get("bias", 0), 8, "MTF", s15.get("label", "n.d.")))
    h1_row = _closed(tfc["1h"])
    comps.append(Component("Bougie 1H (MMM)", candle_score(h1_row), 6, "MTF", f"1H clôturée : {h1_row['mmm']}"))
    # 3. LTF déclencheur
    m15_row, m5_row = _closed(tfc["15m"]), _closed(tfc["5m"])
    comps.append(Component("Déclencheur 15m", candle_score(m15_row), 8, "LTF",
                           f"{m15_row['mmm']} – {CODE_INFO.get(m15_row['mmm'], ('', ''))[1]}"))
    comps.append(Component("Déclencheur 5m", candle_score(m5_row), 9, "LTF",
                           f"{m5_row['mmm']} (volume {m5_row['vol_ratio']:.2f}×)" if not np.isnan(m5_row["vol_ratio"]) else m5_row["mmm"]))
    s5 = struct.get("5m", {})
    comps.append(Component("Structure 5m", s5.get("bias", 0), 6, "LTF", s5.get("label", "n.d.")))
    # momentum / mur
    bc = int(_closed(tfc["5m"])["build_count"])
    if bc >= 4 or bc <= -3:
        comps.append(Component("Mur du momentum 5m", -np.sign(bc) * .7, 6, "LTF",
                               f"{abs(bc)} BC consécutives : épuisement statistique (mur {4 if bc > 0 else 3})"))
    # 4. Prime / Décote
    mo = lv.get("mid_open", np.nan)
    if not np.isnan(mo):
        dist_atr = (price - mo) / max(lv.get("atr14", 300) * .25, 1)
        sc = float(np.clip(-dist_atr, -1, 1))     # sous l'ouverture = biais long
        comps.append(Component("Ouverture de minuit (Prime/Décote)", sc, 6, "CTX",
                               f"Prix {'au-dessus' if price > mo else 'sous'} l'ouverture de minuit ({mo:,.2f}) → "
                               f"{'Prime : chercher des shorts sur rejet' if price > mo else 'Décote : chercher des longs sur rebond'}"))
    dr = ctx.get("dealing", {})
    if dr and not np.isnan(dr.get("pos", np.nan)):
        sc = float(np.clip((50 - dr["pos"]) / 35, -1, 1))
        comps.append(Component("Dealing range 15m", sc, 6, "MTF", f"{dr['zone']} ({dr['pos']:.0f} %)"))
    # 5. Liquidité : sweep récent d'un niveau clé + réintégration
    liq_sc, liq_txt = _liquidity_read(tfc["5m"], lv)
    comps.append(Component("Balayage de liquidité", liq_sc, 10, "MTF", liq_txt))
    # 6. Gaps / zones (défense)
    z_sc, z_txt = _zones_read(ctx.get("zones", []), price, ctx.get("prox", 25))
    comps.append(Component("Zones (OB / breaker / UDG)", z_sc, 7, "MTF", z_txt))
    # 7. Intermarché + SMT
    im = ctx.get("intermarket", {})
    comps.append(Component("Intermarché (ES, DXY, taux, VIX)", im.get("score", 0), 8, "CTX",
                           "; ".join(im.get("notes", [])[:3]) or "Partenaires sans signal marqué"))
    smt = ctx.get("smt", {})
    comps.append(Component("Divergence SMT (NQ/ES)", smt.get("signal", 0), 7, "MTF", smt.get("label", "n.d.")))
    br = ctx.get("breadth", {})
    if br.get("n"):
        comps.append(Component("Poids lourds Nasdaq", (br["pct_up"] - 50) / 50, 5, "CTX",
                               f"{br['up']}/{br['n']} poids lourds en hausse sur la séance"))
    # 8. Régime macro FRED (taux réels, crédit, liquidité, dollar) – vent de fond
    fr = ctx.get("fred", {})
    if fr.get("label") not in (None, "indisponible"):
        comps.append(Component("Régime macro FRED", float(np.clip(fr.get("score", 0), -1, 1)), 6, "HTF",
                               f"{fr['label']} – " + ("; ".join(fr.get("notes", [])[:1]) or "taux, crédit, liquidité, dollar")))
    # 9. News (faible poids, information)
    nb = ctx.get("news", {})
    comps.append(Component("Flux de news (info)", float(np.clip(nb.get("score", 0), -1, 1)), 3, "CTX",
                           f"Biais du flux : {nb.get('label', 'NEUTRE')} ({nb.get('n', 0)} articles) – non prédictif"))

    total_w = sum(c.weight for c in comps)
    bias = 100 * sum(c.pts for c in comps) / total_w
    direction = 1 if bias > 8 else -1 if bias < -8 else 0

    # --- checklist 5 étapes (module 8) pour la direction dominante
    chk = _checklist(direction or (1 if bias >= 0 else -1), struct, dr, ctx, m5_row, m15_row)
    # --- alignement tempête parfaite (BC des 4 TF dans le même sens)
    align = _alignment(tfc)
    # --- timing
    tm = ctx.get("timing", {})
    reds = [k for k in ("h1", "m15") if tm.get(k, {}).get("feu") == "rouge"]
    ict_feu = tm.get("ict", ("orange", ""))[0]
    ev = ctx.get("event", {})
    if ev.get("level") == "critique":
        warn.append(f"⚠️ Publication majeure imminente : {ev.get('msg')} – rester à plat")
    if ict_feu == "rouge":
        warn.append(f"⛔ {tm['ict'][1]}")
    if reds:
        warn.append("Feu rouge MMM sur " + ", ".join(r.upper() for r in reds))
    if ctx.get("demo"):
        warn.append("MODE DÉMO : données synthétiques – aucune décision réelle")
    if ctx.get("stale_min", 0) > 25:
        warn.append(f"Données vieilles de {ctx['stale_min']:.0f} min – marché fermé ou flux interrompu")

    passed = sum(chk["steps"].values())
    if direction == 0:
        grade = "NO TRADE"
    elif passed == 5 and ict_feu != "rouge" and not reds and align["count"] >= 2 and align["dir"] == direction:
        grade = "A+"
    elif passed == 5 and ict_feu != "rouge":
        grade = "A"
    elif passed == 4 and ict_feu != "rouge":
        grade = "B (4/5 : ne suffit pas selon MMM)"
    elif passed >= 3:
        grade = "C – surveiller"
    else:
        grade = "NO TRADE"
    if ev.get("level") == "critique" or ict_feu == "rouge":
        grade = "NO TRADE (timing)"

    plan = _plan(direction, ctx, m5_row, m15_row) if direction else None

    # --- probabilités par horizon : confluence pondérée par horizon ⊕ ML rétréci
    hp = {}
    ml = ctx.get("ml", {})
    for h, tw in HORIZON_TAG_W.items():
        num = sum(c.pts * tw[c.tag] for c in comps)
        den = sum(c.weight * tw[c.tag] for c in comps)
        sc = num / den if den else 0
        amp = {1: .08, 3: .10, 5: .12, 15: .16, 60: .20, 240: .22}[h]   # moins de confiance à très court terme
        p_conf = 0.5 + amp * np.tanh(2.2 * sc)
        m = ml.get(h, {})
        if m.get("ok"):
            w = 0.25 + 0.5 * m["skill"]             # le ML pèse plus s'il a prouvé une compétence
            p = (1 - w) * p_conf + w * m["p_up"]
        else:
            p = p_conf
        hp[h] = {"p_up": float(p), "p_conf": float(p_conf), "p_ml": m.get("p_up"), "skill": m.get("skill"),
                 "auc": m.get("auc"), "acc": m.get("acc"), "base": m.get("base")}

    commentary = _commentary(ctx, comps, bias, direction, grade, chk, align, hp, plan, warn)
    return Decision(bias, direction, grade, comps, chk, align, plan, hp, commentary, warn, tm)


# ---------------------------------------------------------------- helpers
def _liquidity_read(c5: pd.DataFrame, lv: dict) -> tuple[float, str]:
    last = c5.iloc[-13:-1]       # ~1 h de bougies 5m clôturées
    levels = {"PDH": lv.get("pdh"), "PDL": lv.get("pdl"), "haut asiatique": lv.get("asia_h"),
              "bas asiatique": lv.get("asia_l")}
    best = (0.0, "Aucun balayage récent d'un niveau clé (PDH/PDL/Asie) sur la dernière heure")
    for name, lvl in levels.items():
        if lvl is None or np.isnan(lvl):
            continue
        side = "high" if name in ("PDH", "haut asiatique") else "low"
        for _, r in last.iterrows():
            g = sweep_grade(r["Open"], r["High"], r["Low"], r["Close"], lvl, side)
            if g:
                vr = volume_read(r["vol_ratio"])[0]
                strength = {"X": .4, "X+": .7, "X++": 1.0}[g]
                if vr == "Chasse aux stops":
                    strength *= .4
                sc = -strength if side == "high" else strength
                if abs(sc) >= abs(best[0]):
                    best = (sc, f"Sweep {g} du {name} ({lvl:,.2f}) à {r.name:%H:%M} NY, volume : {vr} → "
                                f"{'retournement baissier possible' if sc < 0 else 'retournement haussier possible'}")
    return best


def _zones_read(zones: list[Zone], price: float, prox: float) -> tuple[float, str]:
    near = [z for z in zones if z.status in ("intacte", "testée", "partielle") or "breaker" in z.status]
    near = [z for z in near if z.bottom - prox <= price <= z.top + prox]
    if not near:
        return 0.0, f"Aucune zone institutionnelle à ±{prox:.0f} pts"
    z = sorted(near, key=lambda z: abs(z.mid - price))[0]
    sc = .8 * z.direction
    return sc, f"{z.kind} {z.bottom:,.2f}-{z.top:,.2f} ({z.status}) à proximité → {'support' if sc > 0 else 'résistance'}"


def _checklist(d: int, struct, dr, ctx, m5, m15) -> dict:
    htf = struct.get("4h", {}).get("bias", 0) == d or struct.get("1h", {}).get("bias", 0) == d
    pos = dr.get("pos", 50) if dr else 50
    loc = (pos <= 35) if d > 0 else (pos >= 65)
    prox = ctx.get("prox", 25)
    zones = [z for z in ctx.get("zones", []) if z.direction == d and z.status in ("intacte", "testée", "partielle")]
    price = ctx["price"]
    zone_ok = any(z.bottom - prox <= price <= z.top + prox for z in zones)
    good = {1: ("BuBC+", "BuAFs+", "BuC2+"), -1: ("BeBC+", "BeAFs+", "BeC2+")}[d]
    trig = (m5["mmm"] in good and m5["wick_ok"]) or (m15["mmm"] in good and m15["wick_ok"])
    vr = m5["vol_ratio"] if m5["mmm"] in good else m15["vol_ratio"]
    vol_ok = bool(vr >= 1.0) if not np.isnan(vr) else False
    steps = {"1 · Structure HTF (CDL/CDS 4H ou 1H)": bool(htf),
             "2 · Localisation (Décote ≤35 % long / Prime ≥65 % short)": bool(loc),
             "3 · Zone de déséquilibre proche (UDG/OB)": bool(zone_ok),
             "4 · Bougie LTF de déclenchement (+, mèche OK)": bool(trig),
             "5 · Volume ≥ 1,0× la moyenne": vol_ok}
    return {"dir": d, "steps": steps, "passed": sum(steps.values())}


def _alignment(tfc: dict) -> dict:
    dirs = {}
    for tf in ("1d", "4h", "1h", "15m"):
        r = _closed(tfc[tf])
        dirs[tf] = int(r["dir"]) if r["is_bc"] else 0
    bull, bear = sum(v > 0 for v in dirs.values()), sum(v < 0 for v in dirs.values())
    d = 1 if bull > bear else -1 if bear > bull else 0
    cnt = max(bull, bear)
    rng = MMM_ALIGNMENT.get(cnt, (None, None))
    return {"dirs": dirs, "count": cnt, "dir": d, "range": rng}


def _plan(d: int, ctx: dict, m5, m15) -> dict:
    """Plan MNQ. 1) Bougie déclencheur MMM valide (5m puis 15m) : entrée clôture, stop
    1 tick au-delà de la mèche, C1 = extrême de la bougie. 2) Sinon : ordre limite sur la
    zone institutionnelle la plus proche dans le sens (OB / breaker / UDG) ou l'OTE 0,705.
    C2 = prochaine liquidité (niveau clé / pool)."""
    price = ctx["price"]
    tick = .25
    atr5 = float((ctx["tf"]["5m"]["High"] - ctx["tf"]["5m"]["Low"]).rolling(14).mean().iloc[-2])
    min_stop = max(4.0, 0.6 * atr5)
    good = {1: ("BuBC+", "BuAFs+", "BuC2+"), -1: ("BeBC+", "BeAFs+", "BeC2+")}[d]
    trig = next((r for r in (m5, m15) if r["mmm"] in good and r["wick_ok"]), None)
    if trig is not None:
        mode = "marché"
        label = f"{trig['mmm']} ({'5m' if trig is m5 else '15m'})"
        when = trig.name
        entry = float(trig["Close"])
        stop = float(trig["Low"]) - tick if d > 0 else float(trig["High"]) + tick
        c1 = float(trig["High"]) if d > 0 else float(trig["Low"])
    else:
        mode = "limite"
        when = ctx["last_ts"]
        zs = [z for z in ctx.get("zones", []) if z.direction == d and z.status in ("intacte", "testée", "partielle")]
        zs = [z for z in zs if (price - z.top >= 0 if d > 0 else z.bottom - price >= 0)
              and abs(z.mid - price) <= 3 * ctx.get("prox", 25)]
        if zs:
            z = min(zs, key=lambda z: abs(z.mid - price))
            entry = z.top if d > 0 else z.bottom
            stop = z.bottom - tick if d > 0 else z.top + tick
            label = f"Limite sur {z.kind} {z.bottom:,.2f}-{z.top:,.2f}"
        else:
            ote = ctx.get("dealing", {}).get("ote_long" if d > 0 else "ote_short")
            entry = float(ote) if ote and abs(ote - price) < 3 * ctx.get("prox", 25) else price
            stop = entry - d * min_stop
            label = "Limite OTE 0,705" if entry != price else "Pas de déclencheur MMM – attendre la BC+"
        c1 = entry + d * abs(entry - stop)
    risk = abs(entry - stop)
    if risk < min_stop:
        stop = entry - d * min_stop
        risk = min_stop
    tbl = ctx["levels"]["table"]
    cands = tbl[(tbl["prix"] - entry) * d > risk * .8]["prix"].tolist() if not tbl.empty else []
    cands += [p["price"] for p in ctx.get("pools", []) if (p["price"] - entry) * d > risk * .8]
    c2 = min(cands, key=lambda x: abs(x - entry)) if cands else entry + d * 2 * risk
    if abs(c1 - entry) < risk * .8:
        c1 = entry + d * risk           # 1 R minimum (backtest = 1:1)
    return {"direction": d, "trigger": label, "mode": mode, "trigger_time": when, "entry": entry,
            "stop": stop, "c1": c1, "c2": float(c2), "risk_pts": risk,
            "rr1": abs(c1 - entry) / risk, "rr2": abs(c2 - entry) / risk,
            "ote": ctx.get("dealing", {}).get("ote_long" if d > 0 else "ote_short")}


def _commentary(ctx, comps, bias, d, grade, chk, align, hp, plan, warn) -> list[str]:
    lv = ctx["levels"]["meta"]
    price = ctx["price"]
    out = []
    sens = {1: "haussier", -1: "baissier", 0: "neutre"}[d]
    out.append(f"**Lecture d'ensemble** – NQ à {price:,.2f}. Le score de confluence est de {bias:+.0f}/100 : "
               f"biais **{sens}**. Note du setup : **{grade}**.")
    top = sorted(comps, key=lambda c: abs(c.pts), reverse=True)[:4]
    out.append("**Ce qui pèse le plus** – " + " ; ".join(
        f"{c.name} ({'+' if c.pts >= 0 else ''}{c.pts:.1f}) : {c.comment}" for c in top) + ".")
    if "atr14" in lv:
        txt = f"**Volatilité** – ATR 14 j : {lv['atr14']:.0f} pts"
        if "implied_1sd" in lv:
            txt += f", range implicite VXN ±{lv['implied_1sd']:.0f} pts (1σ)"
        if not np.isnan(lv.get("done_today", np.nan)):
            pct = lv["done_today"] / lv["atr14"] * 100
            txt += f". Déjà parcouru : {lv['done_today']:.0f} pts ({pct:.0f} % de l'ATR)"
            if pct > 85:
                txt += " → l'essentiel du range est fait, viser des cibles courtes"
        out.append(txt + ".")
    a = align
    if a["count"] >= 2 and a["dir"]:
        out.append(f"**Alignement multi-TF** – {a['count']} horizons sur 4 ont clôturé en BC "
                   f"{'haussière' if a['dir'] > 0 else 'baissière'} : probabilité historique MMM "
                   f"{a['range'][0]}-{a['range'][1]} % (« tempête parfaite » à 4/4).")
    else:
        out.append("**Alignement multi-TF** – pas d'alignement des clôtures de corps D/4H/1H/15m : "
                   "MMM recommande d'entrer sur un signal 4H et de n'utiliser le 1H/15m qu'en confirmation.")
    p = chk["passed"]
    out.append(f"**Checklist 5 étapes ({'long' if chk['dir'] > 0 else 'short'})** – {p}/5 validées. "
               + ("Toutes les cases sont cochées." if p == 5 else "Règle MMM : 4/5 ne suffit pas, on attend."))
    if plan:
        out.append(f"**Plan MNQ ({plan['mode']})** – {plan['trigger']} : entrée ~{plan['entry']:,.2f}, stop {plan['stop']:,.2f} "
                   f"({plan['risk_pts']:.1f} pts), C1 {plan['c1']:,.2f} ({plan['rr1']:.1f} R), "
                   f"C2 {plan['c2']:,.2f} ({plan['rr2']:.1f} R). Sortir 75 % à C1, stop à breakeven, "
                   f"tout couper si C1 n'est pas atteint en 2 barres.")
    hz = " · ".join(f"{h} min : {v['p_up'] * 100:.0f} %" for h, v in hp.items())
    out.append(f"**Probabilité de hausse par horizon** – {hz}. Au-delà de 45-55 %, l'avantage est réel mais "
               f"modeste ; en dessous, c'est du bruit.")
    conds = [t for lvl, t in ctx.get("conditions", []) if lvl in ("rouge", "vert")][:3]
    if conds:
        out.append("**Conditions de marché (FRED · news · calendrier)** – " + " ".join(conds))
    if warn:
        out.append("**Alertes** – " + " | ".join(warn))
    return out
