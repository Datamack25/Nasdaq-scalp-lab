"""NQ Scalp Lab – Cockpit de décision (page d'accueil).

Lancer : streamlit run app.py
"""
import numpy as np
import pandas as pd
import streamlit as st

from core import charts, ui
from core.risk import dd_buffer, position_size, trade_plan

ui.setup_page("Cockpit", "🎯")
opts = ui.sidebar()
B = ui.bundle(opts)
ctx, dec = B["ctx"], B["dec"]

ui.header("🎯 Cockpit de décision MNQ", "Confluence Max Maserati (MMM) · ICT · Warren · intermarché · macro — "
          "décision toutes les 15 min", ctx)

# ---------------------------------------------------------------- alertes
for w in dec.warnings:
    cls = "alert" if any(k in w for k in ("⛔", "imminente", "DÉMO")) else "warn"
    st.markdown(f'<div class="{cls}">{ui.esc(w)}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- verdict
st.markdown(ui.verdict_block(dec), unsafe_allow_html=True)
st.write("")
st.markdown("#### Probabilité de hausse du Nasdaq par horizon")
ui.grid([ui.horizon_card(h, v) for h, v in dec.horizon_probs.items()], 6)

# ---------------------------------------------------------------- ligne KPI
lv = ctx["levels"]["meta"]
tm = dec.timing
price = ctx["price"]
mo = lv.get("mid_open", np.nan)
items = [
    ui.kpi("Prix NQ / MNQ", ui.fmt(price), f"Session : {ctx['session']}"),
    ui.kpi("Ouverture de minuit", ui.fmt(mo), "Prime → biais short" if price > mo else "Décote → biais long",
           "down" if price > mo else "up"),
    ui.kpi("ATR 14 j", ui.fmt(lv.get("atr14"), 0) + " pts",
           f"Parcouru : {ui.fmt(lv.get('done_today'), 0)} pts"),
    ui.kpi("Range implicite (VXN)", "±" + ui.fmt(lv.get("implied_1sd"), 0) + " pts",
           f"VXN {ui.fmt(lv.get('vxn'), 1)}" if lv.get("vxn") else "VXN indisponible"),
]
ui.grid(items, 4)
st.write("")

c1, c2 = st.columns([1.55, 1])
with c1:
    tf_choice = st.radio("Unité de temps du graphique", ["5m", "15m", "1h", "1m"], horizontal=True, index=0)
    cdf = ctx["tf"][tf_choice]
    fig = charts.candles(cdf, n=160, levels=ctx["levels"]["table"], zones=ctx["zones"],
                         events=ctx["events"].get(tf_choice), title=f"NQ {tf_choice} – niveaux, zones, signaux MMM (heure de Paris)")
    st.plotly_chart(fig, width="stretch")
with c2:
    st.markdown("#### Feux de timing")
    jl = tm["jour"]
    lights = [
        ui.light(tm["ict"][0], tm["ict"][1]),
        ui.light(jl["feu"], f"Jour {jl['jour']} : BuBC {jl['BuBC'] or '–'} % / BeBC {jl['BeBC'] or '–'} %"),
        ui.light(tm["h4"]["feu"], f"H4 signal {tm['h4']['signal_utc']} UTC : BuBC {tm['h4']['BuBC']} % / BeBC {tm['h4']['BeBC']} %"),
        ui.light(tm["h1"]["feu"], f"H1 signal {tm['h1']['signal_utc']} UTC : BuBC {tm['h1']['BuBC'] or '–'} % / BeBC {tm['h1']['BeBC'] or '–'} %"),
        ui.light(tm["m15"]["feu"], "M15 : fenêtre " + {"vert": "favorable", "orange": "neutre", "rouge": "à éviter"}[tm["m15"]["feu"]]),
    ]
    kz = ", ".join(k[0] for k in ctx["killzones"]) or "aucune"
    ev = ctx["event"]
    lights.append(ui.light({"critique": "rouge", "élevé": "orange", "modéré": "orange", "faible": "vert"}.get(ev.get("level"), "gris"),
                           f"Annonces : {ev.get('msg', 'n.d.')}"))
    st.markdown('<div class="card">' + "<br>".join(lights) + f'<div class="ks" style="margin-top:8px">Killzone(s) active(s) : {ui.esc(kz)}</div></div>',
                unsafe_allow_html=True)
    st.markdown(f"#### Checklist MMM 5/5 – {'LONG' if dec.checklist['dir'] > 0 else 'SHORT'}")
    st.markdown('<div class="card">' + ui.checklist_html(dec.checklist) +
                f'<div class="ks" style="margin-top:6px">{dec.checklist["passed"]}/5 · règle : 4/5 ne suffit pas</div></div>',
                unsafe_allow_html=True)
    a = dec.alignment
    sym = {1: "▲", -1: "▼", 0: "·"}
    al = " ".join(f'<span class="{"up" if v > 0 else "down" if v < 0 else "flat"}">{tf.upper()} {sym[v]}</span>'
                  for tf, v in a["dirs"].items())
    rng = f"{a['range'][0]}-{a['range'][1]} %" if a["range"][0] else "–"
    st.markdown(f'<div class="card" style="margin-top:12px"><h4>Tempête parfaite (BC clôturées)</h4>'
                f'<div class="mono">{al}</div><div class="ks">{a["count"]}/4 alignés · proba historique MMM {rng}</div></div>',
                unsafe_allow_html=True)

# ---------------------------------------------------------------- plan + taille
st.markdown("#### Plan de trade MNQ")
p = dec.plan
dd = dd_buffer(opts["balance"], opts["peak"], opts["start"], opts["dd"])
news_day = ctx["event"].get("same_day", False)
if p:
    ps = position_size(p["risk_pts"], opts["balance"], dd["buffer"], opts["maxc"], opts["risk"],
                       opts["bfrac"], opts["losses"], news_day)
    tp = trade_plan(p["direction"], p["entry"], p["stop"], p["c1"], ps["contracts"])
    tone = "up" if p["direction"] > 0 else "down"
    items = [
        ui.kpi("Sens / déclencheur", ("LONG" if p["direction"] > 0 else "SHORT"), f"{p['trigger']} à {p['trigger_time']:%H:%M} NY", tone),
        ui.kpi("Entrée", ui.fmt(p["entry"]), f"OTE 0,705 : {ui.fmt(p.get('ote'))}"),
        ui.kpi("Stop", ui.fmt(p["stop"]), f"{p['risk_pts']:.1f} pts · {ps['per_contract']:.0f} $/MNQ", "down"),
        ui.kpi("C1 / C2", f"{ui.fmt(p['c1'])}", f"C2 {ui.fmt(p['c2'])} · {p['rr1']:.1f} R / {p['rr2']:.1f} R", "up"),
        ui.kpi("Taille conseillée", f"{ps['contracts']} MNQ", f"risque {ps['risk_usd']:.0f} $ · budget {ps['risk_budget']:.0f} $"),
        ui.kpi("Buffer drawdown", f"{dd['buffer']:,.0f} $".replace(",", " "), f"seuil {dd['threshold']:,.0f} $ · utilisé {dd['pct_used']:.0f} %".replace(",", " "),
               "down" if dd["pct_used"] > 60 else ""),
    ]
    ui.grid(items, 6)
    for n in ps["notes"]:
        st.caption("• " + n)
    if not dec.grade.startswith(("A", "B")):
        st.markdown('<div class="warn">Plan indicatif uniquement : la note du setup ne justifie pas d\'entrée. '
                    'Max : « Pas toutes les cases cochées = pas de trade. Attendre le prochain setup. »</div>',
                    unsafe_allow_html=True)
else:
    st.markdown('<div class="card">Pas de biais exploitable : aucune entrée proposée. Marquer les niveaux, attendre '
                'la BC qui sort du range (« Bougez avec le Marteau, ne combattez jamais le Mur »).</div>',
                unsafe_allow_html=True)

# ---------------------------------------------------------------- commentaire
c1, c2 = st.columns([1.1, 1])
with c1:
    st.markdown("#### Commentaire de marché")
    st.markdown('<div class="card comment">' + "".join(f"<p>{ui.md(t)}</p>" for t in dec.commentary) + "</div>",
                unsafe_allow_html=True)
with c2:
    st.markdown("#### Décomposition du score")
    comp = pd.DataFrame([{"Composante": c.name, "Famille": c.tag, "Points": f"{c.pts:+.1f}",
                          "Lecture": c.comment[:110]} for c in sorted(dec.components, key=lambda c: -abs(c.pts))])
    st.markdown(ui.table_html(comp, num_cols=("Points",)), unsafe_allow_html=True)

st.plotly_chart(charts.horizons_bar(dec.horizon_probs), width="stretch")
ui.footer()
