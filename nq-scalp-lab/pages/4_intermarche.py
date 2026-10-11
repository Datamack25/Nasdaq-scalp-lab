"""Partenaires ICT : ES/YM (SMT), DXY & taux (inverse), VIX/VXN, poids lourds du Nasdaq-100."""
import numpy as np
import streamlit as st

from core import charts, intermarket, ui
from core.config import PARTNERS

ui.setup_page("Intermarché", "🌐")
opts = ui.sidebar()
B = ui.bundle(opts)
ctx = B["ctx"]
ui.header("🌐 Intermarché & partenaires ICT", "Divergence SMT, dollar, taux, volatilité et poids lourds du Nasdaq-100", ctx)

im = ctx["intermarket"]
snap = im["snap"]
br = ctx["breadth"]
smt_es = ctx["smt"]
smt_ym = intermarket.smt_divergence(B["mk"]["5m"], B["partners"]["YM=F"]) if "YM=F" in B["partners"] else {"signal": 0, "label": "YM indisponible"}
ui.grid([
    ui.kpi("Score intermarché", f"{im['score']:+.2f}", "−1 vendeur … +1 acheteur", "up" if im["score"] > .15 else "down" if im["score"] < -.15 else ""),
    ui.kpi("SMT NQ / ES", {1: "Haussière", -1: "Baissière", 0: "Aucune"}[smt_es["signal"]], smt_es["label"],
           "up" if smt_es["signal"] > 0 else "down" if smt_es["signal"] < 0 else ""),
    ui.kpi("SMT NQ / YM", {1: "Haussière", -1: "Baissière", 0: "Aucune"}[smt_ym["signal"]], smt_ym["label"],
           "up" if smt_ym["signal"] > 0 else "down" if smt_ym["signal"] < 0 else ""),
    ui.kpi("Poids lourds en hausse", f"{br.get('up', 0)}/{br.get('n', 0)}", "NVDA, MSFT, AAPL, AMZN, META, GOOGL, AVGO, TSLA",
           "up" if br.get("pct_up", 50) > 60 else "down" if br.get("pct_up", 50) < 40 else ""),
], 4)

st.markdown("#### Tableau des partenaires")
if not snap.empty:
    t = snap.copy()
    t.insert(0, "Marché", [PARTNERS.get(i, {}).get("nom", "Nasdaq-100 E-mini (NQ)") for i in t.index])
    t.insert(1, "Rôle ICT", [PARTNERS.get(i, {}).get("role", "Référence") for i in t.index])
    t["Lecture pour NQ"] = [
        "—" if i == "NQ=F" or np.isnan(r["mom_1h_%"]) else
        ("favorable" if np.sign(r["mom_1h_%"]) * PARTNERS.get(i, {}).get("relation", 0) > 0 else
         "défavorable" if np.sign(r["mom_1h_%"]) * PARTNERS.get(i, {}).get("relation", 0) < 0 else "neutre")
        for i, r in t.iterrows()]
    show = t.reset_index().rename(columns={"ticker": "Ticker", "dernier": "Dernier", "var_jour_%": "Var. séance %",
                                           "mom_1h_%": "Momentum 1 h %", "corr_NQ": "Corr. NQ (24 h, 5m)"})
    for c in ("Dernier", "Var. séance %", "Momentum 1 h %", "Corr. NQ (24 h, 5m)"):
        show[c] = show[c].map(lambda x: ui.fmt(x, 2))
    st.markdown(ui.table_html(show, num_cols=("Dernier", "Var. séance %", "Momentum 1 h %", "Corr. NQ (24 h, 5m)")),
                unsafe_allow_html=True)
for n in im["notes"]:
    st.caption("• " + n)

closes = {"NQ=F": B["mk"]["5m"]["Close"]}
for tk in ("ES=F", "YM=F", "RTY=F"):
    if tk in B["partners"]:
        closes[tk] = B["partners"][tk]["Close"]
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(charts.normalized_lines(closes, "Triade des indices – base de la divergence SMT"), width="stretch")
with c2:
    inv = {"NQ=F": B["mk"]["5m"]["Close"]}
    for tk in ("DX-Y.NYB", "^TNX", "^VIX"):
        if tk in B["partners"]:
            inv[tk] = B["partners"][tk]["Close"]
    st.plotly_chart(charts.normalized_lines(inv, "NQ vs dollar, taux 10 ans, VIX (relations inverses)"), width="stretch")

if br.get("detail"):
    det = br["detail"]
    st.plotly_chart(charts.bars([d[0] for d in det], [d[1] for d in det], "Poids lourds – variation de la séance (%)",
                                color=["#22c55e" if d[1] > 0 else "#ef4444" for d in det], ref=0), width="stretch")

with st.expander("📖 Les partenaires de l'ICT – comment les lire"):
    st.markdown("""
- **SMT (Smart Money Technique)** : NQ, ES et YM sont normalement synchrones. Quand l'un fait un nouveau plus haut (bas) que l'autre ne confirme pas, la liquidité vient d'être prise d'un côté sans conviction de l'autre → indice de retournement. À combiner avec un sweep de PDH/PDL ou d'un extrême de killzone, jamais seul.
- **DXY** : relation inverse avec les indices actions US. Un dollar qui casse à la hausse pendant la killzone de Londres/NY pèse sur le Nasdaq.
- **Taux 10 ans (TNX)** : la tech est une duration longue ; des taux qui montent compressent les multiples → pression baissière sur NQ.
- **VIX / VXN** : régime de peur. VXN fournit le range implicite du jour (±σ = prix × VXN / √252).
- **Poids lourds** : 8 valeurs ≈ la moitié de l'indice. Si NQ monte avec seulement 2-3 poids lourds en hausse, le mouvement est fragile.
""")
ui.footer()
