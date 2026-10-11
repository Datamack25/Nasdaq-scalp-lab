"""Couche d'affichage HTML/CSS (thème terminal) + chargement mis en cache."""
from __future__ import annotations

import hashlib
import html

import numpy as np
import pandas as pd
import streamlit as st

from . import engine, news
from .config import PARIS_TZ
from .data import load_csv

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
:root{--bg:#0b0f17;--panel:#121826;--panel2:#171f30;--line:#243049;--txt:#e6ebf5;--mut:#8b97b0;
--up:#22c55e;--down:#ef4444;--amber:#f5b041;--blue:#5b9cff;--violet:#a78bfa;}
html,body,[class*="css"]{font-family:'IBM Plex Sans',sans-serif;}
.stApp{background:radial-gradient(1200px 600px at 10% -10%,#16213a 0%,var(--bg) 55%);color:var(--txt);}
section[data-testid="stSidebar"]{background:#0e1420;border-right:1px solid var(--line);}
.block-container{padding-top:1.4rem;max-width:1500px;}
h1,h2,h3{letter-spacing:-.01em;}
.mono{font-family:'JetBrains Mono',monospace;}
.hdr{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;
 border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:14px;}
.hdr h1{font-size:1.65rem;margin:0;font-weight:700;}
.hdr .sub{color:var(--mut);font-size:.9rem;margin-top:2px;}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:.75rem;font-weight:600;
 border:1px solid var(--line);background:var(--panel2);color:var(--mut);margin-left:6px;}
.badge.live{color:#0b0f17;background:var(--up);border-color:var(--up);}
.badge.demo{color:#0b0f17;background:var(--amber);border-color:var(--amber);}
.badge.csv{color:#0b0f17;background:var(--blue);border-color:var(--blue);}
.grid{display:grid;gap:12px;margin-bottom:12px;}
.g6{grid-template-columns:repeat(6,minmax(0,1fr));} .g4{grid-template-columns:repeat(4,minmax(0,1fr));}
.g3{grid-template-columns:repeat(3,minmax(0,1fr));} .g2{grid-template-columns:repeat(2,minmax(0,1fr));}
@media(max-width:1100px){.g6{grid-template-columns:repeat(3,1fr);} .g4{grid-template-columns:repeat(2,1fr);}}
@media(max-width:700px){.g6,.g4,.g3,.g2{grid-template-columns:1fr 1fr;}}
.card{background:linear-gradient(180deg,var(--panel) 0%,#101624 100%);border:1px solid var(--line);
 border-radius:12px;padding:14px 16px;}
.card h4{margin:0 0 8px 0;font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);font-weight:600;}
.kv{font-family:'JetBrains Mono',monospace;font-size:1.45rem;font-weight:600;}
.ks{color:var(--mut);font-size:.8rem;margin-top:2px;}
.up{color:var(--up);} .down{color:var(--down);} .flat{color:var(--mut);} .amber{color:var(--amber);}
.hz{text-align:center;}
.hz .h{font-size:.75rem;color:var(--mut);letter-spacing:.08em;text-transform:uppercase;}
.hz .p{font-family:'JetBrains Mono',monospace;font-size:1.6rem;font-weight:700;margin:4px 0;}
.bar{height:8px;border-radius:6px;background:var(--down);overflow:hidden;margin:6px 0 4px 0;}
.bar>span{display:block;height:100%;background:var(--up);}
.lab{font-size:.78rem;font-weight:600;}
.verdict{border-radius:14px;padding:18px 20px;border:1px solid var(--line);display:flex;gap:22px;align-items:center;flex-wrap:wrap;}
.verdict.long{background:linear-gradient(90deg,rgba(34,197,94,.18),rgba(18,24,38,.9));border-color:rgba(34,197,94,.5);}
.verdict.short{background:linear-gradient(90deg,rgba(239,68,68,.18),rgba(18,24,38,.9));border-color:rgba(239,68,68,.5);}
.verdict.flat{background:linear-gradient(90deg,rgba(139,151,176,.14),rgba(18,24,38,.9));}
.verdict .big{font-size:2.1rem;font-weight:700;letter-spacing:-.02em;}
.verdict .grade{font-family:'JetBrains Mono',monospace;font-size:1.1rem;padding:4px 12px;border-radius:8px;
 background:#0b0f17;border:1px solid var(--line);}
.gauge{flex:1;min-width:260px;}
.gauge .track{position:relative;height:12px;border-radius:8px;
 background:linear-gradient(90deg,#ef4444 0%,#3a4357 50%,#22c55e 100%);}
.gauge .needle{position:absolute;top:-5px;width:4px;height:22px;background:#fff;border-radius:3px;box-shadow:0 0 8px #fff8;}
.gauge .scale{display:flex;justify-content:space-between;color:var(--mut);font-size:.72rem;margin-top:6px;}
.light{display:inline-flex;align-items:center;gap:6px;font-size:.82rem;margin:2px 10px 2px 0;}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block;}
.dot.vert{background:var(--up);box-shadow:0 0 6px var(--up);} .dot.orange{background:var(--amber);box-shadow:0 0 6px var(--amber);}
.dot.rouge{background:var(--down);box-shadow:0 0 6px var(--down);} .dot.gris{background:#556;}
.chk{display:flex;gap:8px;align-items:flex-start;padding:5px 0;border-bottom:1px dashed #22304a;font-size:.88rem;}
.chk:last-child{border-bottom:none;}
.ok{color:var(--up);font-weight:700;} .ko{color:var(--down);font-weight:700;}
.warn{background:rgba(245,176,65,.1);border:1px solid rgba(245,176,65,.45);border-radius:10px;padding:10px 14px;margin:6px 0;font-size:.9rem;}
.alert{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.5);border-radius:10px;padding:10px 14px;margin:6px 0;font-size:.9rem;}
.comment p{margin:0 0 8px 0;line-height:1.5;font-size:.93rem;}
table.t{width:100%;border-collapse:collapse;font-size:.85rem;}
table.t th{color:var(--mut);text-align:left;font-weight:600;border-bottom:1px solid var(--line);padding:6px 8px;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;}
table.t td{padding:6px 8px;border-bottom:1px solid #1b2538;}
table.t td.n{font-family:'JetBrains Mono',monospace;text-align:right;}
table.t tr.cur td{background:rgba(245,176,65,.12);font-weight:600;}
.timeline{position:relative;height:64px;background:var(--panel2);border-radius:10px;border:1px solid var(--line);overflow:hidden;}
.timeline .kz{position:absolute;top:8px;height:22px;border-radius:5px;font-size:.66rem;color:#fff;padding:3px 5px;white-space:nowrap;overflow:hidden;opacity:.92;}
.timeline .now{position:absolute;top:0;bottom:0;width:2px;background:#fff;box-shadow:0 0 6px #fff;}
.timeline .tick{position:absolute;bottom:4px;font-size:.62rem;color:var(--mut);}
.foot{color:var(--mut);font-size:.75rem;margin-top:24px;border-top:1px solid var(--line);padding-top:8px;}
</style>
"""


def setup_page(title: str, icon: str = "📈"):
    st.set_page_config(page_title=f"{title} · NQ Scalp Lab", page_icon=icon, layout="wide",
                       initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)


def esc(x) -> str:
    return html.escape(str(x))


def md(s: str) -> str:
    """Échappe puis convertit le **gras** markdown en <b>."""
    import re
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc(s))


def fmt(x, d=2, sign=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n.d."
    s = f"{x:+,.{d}f}" if sign else f"{x:,.{d}f}"
    return s.replace(",", " ").replace(".", ",")


def header(title: str, sub: str, ctx: dict | None = None):
    badge = ""
    if ctx:
        src = ctx.get("source")
        cls, lab = {"yahoo": ("live", "Yahoo · différé ~10-15 min"), "csv": ("csv", "CSV importé"),
                    "demo": ("demo", "MODE DÉMO")}.get(src, ("", src))
        ts = ctx["last_ts"].tz_convert(PARIS_TZ).strftime("%d/%m %H:%M")
        badge = f'<span class="badge {cls}">{esc(lab)}</span><span class="badge">Dernière barre {ts} Paris</span>'
    st.markdown(f'<div class="hdr"><div><h1>{esc(title)}</h1><div class="sub">{esc(sub)}</div></div>'
                f'<div>{badge}</div></div>', unsafe_allow_html=True)


def kpi(label, value, sub="", tone=""):
    return (f'<div class="card"><h4>{esc(label)}</h4><div class="kv {tone}">{value}</div>'
            f'<div class="ks">{sub}</div></div>')


def grid(items: list[str], cols: int = 4):
    st.markdown(f'<div class="grid g{cols}">' + "".join(items) + "</div>", unsafe_allow_html=True)


def light(feu: str, text: str) -> str:
    return f'<span class="light"><span class="dot {esc(feu)}"></span>{esc(text)}</span>'


def horizon_card(h: int, v: dict) -> str:
    p = v["p_up"]
    tone = "up" if p >= .53 else "down" if p <= .47 else "flat"
    lab = "HAUSSE" if p >= .58 else "BAISSE" if p <= .42 else "Légère hausse" if p >= .53 else \
        "Légère baisse" if p <= .47 else "NEUTRE"
    skill = v.get("skill")
    sk = f"compétence ML {skill * 100:.0f} %" if skill is not None else "ML n.d."
    hl = f"{h} min" if h < 60 else f"{h // 60} h"
    return (f'<div class="card hz"><div class="h">{hl}</div><div class="p {tone}">{p * 100:.0f}%</div>'
            f'<div class="bar"><span style="width:{p * 100:.0f}%"></span></div>'
            f'<div class="lab {tone}">{lab}</div><div class="ks">{sk}</div></div>')


def verdict_block(dec) -> str:
    d = dec.direction
    cls, word = {1: ("long", "LONG"), -1: ("short", "SHORT"), 0: ("flat", "ATTENDRE")}[d]
    pos = (dec.bias + 100) / 2
    return (f'<div class="verdict {cls}"><div><div class="ks">BIAIS DE CONFLUENCE</div>'
            f'<div class="big {"up" if d > 0 else "down" if d < 0 else "flat"}">{word}</div></div>'
            f'<div><div class="ks">NOTE DU SETUP</div><div class="grade">{esc(dec.grade)}</div></div>'
            f'<div class="gauge"><div class="ks">Score {dec.bias:+.0f} / 100</div>'
            f'<div class="track"><div class="needle" style="left:calc({pos:.1f}% - 2px)"></div></div>'
            f'<div class="scale"><span>-100 vendeur</span><span>0</span><span>acheteur +100</span></div></div></div>')


def checklist_html(chk: dict) -> str:
    rows = "".join(f'<div class="chk"><span class="{"ok" if v else "ko"}">{"✔" if v else "✘"}</span>'
                   f'<span>{esc(k)}</span></div>' for k, v in chk["steps"].items())
    return rows


def table_html(df: pd.DataFrame, num_cols=(), highlight_row=None) -> str:
    th = "".join(f"<th>{esc(c)}</th>" for c in df.columns)
    trs = []
    for i, (_, r) in enumerate(df.iterrows()):
        cls = ' class="cur"' if highlight_row is not None and i == highlight_row else ""
        tds = "".join(f'<td class="n">{esc(v)}</td>' if c in num_cols else f"<td>{esc(v)}</td>"
                      for c, v in r.items())
        trs.append(f"<tr{cls}>{tds}</tr>")
    return f'<table class="t"><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'


def footer():
    st.markdown('<div class="foot">NQ Scalp Lab · outil d\'aide à la décision à but éducatif. Les statistiques '
                'MMM proviennent des backtests de l\'auteur (ES/NQ, 2019-2026) ; les probabilités du modèle sont '
                'mesurées hors échantillon sur les données chargées et rétrécies vers 50 % selon leur compétence. '
                'Rien ici ne constitue un conseil en investissement.</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------ sidebar
def sidebar() -> dict:
    with st.sidebar:
        st.markdown("### ⚙️ Données")
        up = st.file_uploader("CSV NQ/MNQ 1 min (optionnel)", type=["csv"],
                              help="Export TradingView/NinjaTrader : time, open, high, low, close, volume. "
                                   "Remplace Yahoo pour NQ (plus frais).")
        csv_bytes = up.getvalue() if up else None
        c1, c2 = st.columns(2)
        if c1.button("🔄 Rafraîchir", width="stretch"):
            st.cache_data.clear()
        run_ml = c2.toggle("ML", value=True, help="Moteur de prévision walk-forward (≈30 s au 1er calcul)")
        news_on = st.toggle("Actualités & calendrier", value=True)
        st.caption("Yahoo est différé d'environ 10-15 min sur NQ=F. Cache : 5 min (marché), 15 min (ML).")
        st.markdown("### 🏦 Compte Apex")
        from .config import APEX_ACCOUNTS
        acc = st.selectbox("Taille", list(APEX_ACCOUNTS), index=1, key="apex_acc")
        a = APEX_ACCOUNTS[acc]
        for k, v in ((f"bal_{acc}", float(a["balance"])), (f"peak_{acc}", float(a["balance"])),
                     (f"dd_{acc}", float(a["trailing_dd"])), (f"maxc_{acc}", int(a["max_contracts_mnq"])),
                     ("riskpct", 1.0), ("bfrac", 10), ("losses", 0)):
            st.session_state.setdefault(k, v)
        bal = st.number_input("Solde actuel $", step=100.0, key=f"bal_{acc}")
        peak = st.number_input("Plus haut atteint $", step=100.0, key=f"peak_{acc}")
        dd = st.number_input("Drawdown suiveur $", step=100.0, key=f"dd_{acc}")
        maxc = st.number_input("Max contrats MNQ", step=1, key=f"maxc_{acc}")
        risk = st.slider("Risque / trade (% compte)", .25, 2.0, step=.25, key="riskpct")
        bfrac = st.slider("Risque max (% du buffer DD)", 5, 30, step=1, key="bfrac") / 100
        losses = st.number_input("Pertes d'affilée", 0, 10, key="losses")
        st.caption("Règles Apex par défaut : à vérifier sur le site d'Apex, elles évoluent.")
    return {"csv": csv_bytes, "ml": run_ml, "news": news_on, "acc": acc, "start": a["balance"],
            "balance": bal, "peak": max(peak, bal), "dd": dd, "maxc": int(maxc), "risk": risk,
            "bfrac": bfrac, "losses": int(losses)}


# ------------------------------------------------------------------ cache
@st.cache_data(ttl=300, show_spinner="Chargement du marché…")
def _market(csv_hash: str | None, csv_bytes: bytes | None):
    import io
    csv_df = load_csv(io.BytesIO(csv_bytes)) if csv_bytes else None
    mk = engine.load_market(csv_df)
    demo = mk["source"] == "demo"
    return mk, engine.load_partners(demo), engine.load_heavy(demo)


@st.cache_data(ttl=600, show_spinner="Lecture des actualités…")
def _news():
    return news.fetch_feeds(), news.fetch_calendar()


@st.cache_data(ttl=900, show_spinner="Entraînement walk-forward des modèles (1 à 240 min)…")
def _ml(csv_hash: str | None, _mk: dict, _partners: dict, last_ts):
    return engine.run_forecasts(_mk, _partners)


def bundle(opts: dict):
    h = hashlib.md5(opts["csv"]).hexdigest() if opts["csv"] else None
    mk, partners, heavy = _market(h, opts["csv"])
    nd, cal = _news() if opts["news"] else (pd.DataFrame(), pd.DataFrame())
    ml = _ml(h, mk, partners, str(mk["5m"].index[-1])) if opts["ml"] else {}
    ctx, dec = engine.analyse(mk, partners, heavy, nd, cal, ml)
    return {"mk": mk, "partners": partners, "heavy": heavy, "news": nd, "cal": cal, "ml": ml,
            "ctx": ctx, "dec": dec}
