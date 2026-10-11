"""Risque Apex / MNQ : buffer de drawdown, calculateur de lots, espérance, journal de trading."""
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from core import charts, ui
from core.config import MMM_RISK, MNQ_POINT_VALUE
from core.risk import PROP_RULES, dd_buffer, expectancy, position_size, trade_plan

ui.setup_page("Risque Apex & Journal", "🛡️")
opts = ui.sidebar()
B = ui.bundle(opts)
ctx = B["ctx"]
ui.header("🛡️ Risque Apex & journal", "Taille MNQ, drawdown suiveur, règles MMM/Warren et journal de trades", ctx)

dd = dd_buffer(opts["balance"], opts["peak"], opts["start"], opts["dd"])
ui.grid([
    ui.kpi("Compte", opts["acc"], f"solde {opts['balance']:,.0f} $".replace(",", " ")),
    ui.kpi("Seuil de liquidation", f"{dd['threshold']:,.0f} $".replace(",", " "), "bloqué à départ + 100 $" if dd["locked"] else "suiveur actif"),
    ui.kpi("Buffer restant", f"{dd['buffer']:,.0f} $".replace(",", " "), f"{dd['pct_used']:.0f} % du drawdown consommé",
           "down" if dd["pct_used"] > 60 else "up"),
    ui.kpi("Perte du jour max (MMM 3 %)", f"{opts['balance'] * MMM_RISK['daily_loss_pct'] / 100:,.0f} $".replace(",", " "),
           f"≈ {opts['balance'] * .03 / MNQ_POINT_VALUE:,.0f} pts MNQ cumulés".replace(",", " ")),
], 4)

st.markdown("#### Calculateur de lots MNQ")
c1, c2, c3, c4 = st.columns(4)
p = ctx and B["dec"].plan
d = c1.selectbox("Sens", ["LONG", "SHORT"], index=0 if not p or p["direction"] > 0 else 1)
entry = c2.number_input("Entrée", value=float(p["entry"] if p else ctx["price"]), step=.25)
stop = c3.number_input("Stop", value=float(p["stop"] if p else ctx["price"] - 10), step=.25)
target = c4.number_input("Objectif", value=float(p["c1"] if p else ctx["price"] + 10), step=.25)
direc = 1 if d == "LONG" else -1
ps = position_size(abs(entry - stop), opts["balance"], dd["buffer"], opts["maxc"], opts["risk"], opts["bfrac"],
                   opts["losses"], ctx["event"].get("same_day", False))
tp = trade_plan(direc, entry, stop, target, ps["contracts"])
bad = (direc > 0 and stop >= entry) or (direc < 0 and stop <= entry)
if bad:
    st.markdown('<div class="alert">Stop du mauvais côté de l\'entrée.</div>', unsafe_allow_html=True)
ui.grid([
    ui.kpi("Contrats MNQ", str(ps["contracts"]), f"{ps['per_contract']:.0f} $ de risque par contrat"),
    ui.kpi("Risque", f"{tp['risk_usd']:.0f} $", f"{tp['risk_pts']:.2f} pts · budget {ps['risk_budget']:.0f} $", "down"),
    ui.kpi("Gain à l'objectif", f"{tp['reward_usd']:.0f} $", f"{tp['reward_pts']:.2f} pts · {tp['rr']:.2f} R", "up"),
    ui.kpi("Partiel Warren (1 R)", ui.fmt(tp["tp1"]), "encaisser, stop à breakeven"),
], 4)
for n in ps["notes"]:
    st.caption("• " + n)

c1, c2 = st.columns(2)
with c1:
    st.markdown("#### Espérance selon le taux de réussite")
    rr = st.slider("Ratio R:R", .5, 3.0, 1.0, .1)
    both = st.slider("% « les deux atteints » (0 R)", 0, 30, 6) / 100
    wins = np.arange(.35, .86, .05)
    ev = [expectancy(w, rr, both) for w in wins]
    st.plotly_chart(charts.bars([f"{w * 100:.0f} %" for w in wins], ev, f"Espérance par trade (R) à {rr:.1f} R",
                                color=["#22c55e" if e > 0 else "#ef4444" for e in ev], ref=0, ytitle="R"), width="stretch")
    st.caption("MMM : 72 % à 1:1 ⇒ ≈ +0,4 R/trade théorique ; le rapport lui-même table sur 60-70 % du théorique après "
               "glissement, commissions et erreurs.")
with c2:
    st.markdown("#### Règles de risque (MMM · Warren · prop firm)")
    st.markdown(ui.table_html(pd.DataFrame(PROP_RULES, columns=["Règle", "Application"])), unsafe_allow_html=True)

st.markdown("#### Journal de trading")
st.caption("Max : « Enregistrer chaque trade ». Le journal est stocké dans data/journal.csv (local). "
           "Sur Streamlit Cloud le disque est éphémère : téléchargez-le régulièrement.")
jp = Path(__file__).resolve().parents[1] / "data" / "journal.csv"
cols = ["date", "sens", "setup", "tf", "session", "checklist_5", "entree", "stop", "sortie", "contrats", "pnl_usd", "r", "note"]
jr = pd.read_csv(jp) if jp.exists() else pd.DataFrame(columns=cols)
with st.form("add"):
    a1, a2, a3, a4, a5 = st.columns(5)
    sens = a1.selectbox("Sens", ["LONG", "SHORT"])
    setup = a2.selectbox("Setup", ["BuBC+/BeBC+", "Sweep C2", "AF au PDH/PDL", "CDLx/CDSx", "OB Warren", "Breaker", "Range+MSB", "FVG/UDG", "Autre"])
    tfj = a3.selectbox("TF", ["1m", "5m", "15m", "1h", "4h"], index=1)
    sess = a4.selectbox("Session", ["Londres", "Fenêtre d'Or NY", "IB NY", "Après-midi NY", "Asie", "Zone morte"])
    chk = a5.slider("Checklist", 0, 5, 5)
    b1, b2, b3, b4, b5 = st.columns(5)
    e_ = b1.number_input("Entrée ", value=float(ctx["price"]), step=.25)
    s_ = b2.number_input("Stop ", value=float(ctx["price"] - 10), step=.25)
    x_ = b3.number_input("Sortie", value=float(ctx["price"] + 10), step=.25)
    n_ = b4.number_input("Contrats", 1, 500, max(ps["contracts"], 1))
    note = b5.text_input("Note")
    if st.form_submit_button("➕ Ajouter au journal"):
        sg = 1 if sens == "LONG" else -1
        pnl = (x_ - e_) * sg * MNQ_POINT_VALUE * n_
        r = (x_ - e_) * sg / abs(e_ - s_) if e_ != s_ else 0
        jr = pd.concat([jr, pd.DataFrame([{"date": pd.Timestamp.now(tz="Europe/Paris").strftime("%Y-%m-%d %H:%M"), "sens": sens,
                                           "setup": setup, "tf": tfj, "session": sess, "checklist_5": chk, "entree": e_,
                                           "stop": s_, "sortie": x_, "contrats": n_, "pnl_usd": round(pnl, 2), "r": round(r, 2), "note": note}])])
        try:
            jp.parent.mkdir(exist_ok=True); jr.to_csv(jp, index=False)
            st.success("Trade enregistré.")
        except OSError:
            st.warning("Écriture impossible ici : utilisez le bouton de téléchargement.")
if len(jr):
    jr["r"] = pd.to_numeric(jr["r"], errors="coerce")
    ui.grid([
        ui.kpi("Trades", str(len(jr)), f"{(jr['r'] > 0).mean() * 100:.0f} % gagnants"),
        ui.kpi("R total", f"{jr['r'].sum():+.1f} R", f"moyenne {jr['r'].mean():+.2f} R"),
        ui.kpi("P&L", f"{pd.to_numeric(jr['pnl_usd']).sum():+,.0f} $".replace(",", " ")),
        ui.kpi("Checklist 5/5 vs <5", f"{jr[jr['checklist_5'] == 5]['r'].mean():+.2f} R / {jr[jr['checklist_5'] < 5]['r'].mean():+.2f} R",
               "exercice Max module 8"),
    ], 4)
    st.dataframe(jr, width="stretch", hide_index=True)
    st.download_button("⬇️ Télécharger le journal (CSV)", jr.to_csv(index=False).encode(), "journal_mnq.csv", "text/csv")
ui.footer()
