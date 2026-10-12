"""Zones ICT / Warren : orderblocks (A/B/C), breakers, gaps UDG/ULG/UAG, OTE, range & déviation,
dealing range Prime/Décote, pools de liquidité."""
import numpy as np
import pandas as pd
import streamlit as st

from core import candles, charts, structure, ui

ui.setup_page("ICT & Warren", "🧱")
opts = ui.sidebar()
B = ui.bundle(opts)
ctx = B["ctx"]
price = ctx["price"]
ui.header("🧱 Zones ICT & Warren", "Orderblocks, breakers, FVG/UDG, OTE 0,705, ranges & déviations, liquidité", ctx)

tf = st.radio("Unité de temps d'analyse", ["15m", "5m", "1h", "4h"], horizontal=True)
cdf = ctx["tf"][tf]
sw = structure.mmm_swings(cdf)
ev = structure.cdl_cds(cdf, sw)
obs = structure.orderblocks(cdf, ev, sw, max_n=15)
gz = structure.gaps(cdf, 250)
dr = structure.dealing_range(sw, price)
rg = structure.ranges_and_deviation(cdf)
pools = structure.liquidity_pools(cdf, price)

ui.grid([
    ui.kpi("Dealing range", f"{dr['pos']:.0f} %" if not np.isnan(dr["pos"]) else "n.d.", dr["zone"],
           "up" if dr["pos"] <= 35 else "down" if dr["pos"] >= 65 else ""),
    ui.kpi("Équilibre (EQ 50 %)", ui.fmt(dr.get("eq")), f"range {ui.fmt(dr.get('low'))} – {ui.fmt(dr.get('high'))}"),
    ui.kpi("OTE 0,705 long", ui.fmt(dr.get("ote_long")), "zone dorée 0,618-0,786", "up"),
    ui.kpi("OTE 0,705 short", ui.fmt(dr.get("ote_short")), "zone dorée 0,618-0,786", "down"),
], 4)

st.plotly_chart(charts.candles(cdf, n=170, levels=None, zones=obs + gz, events=ev, max_zones=10,
                               title=f"NQ {tf} – orderblocks, breakers, gaps (zones actives les plus proches)"), width="stretch")

c1, c2 = st.columns(2)
with c1:
    st.markdown("#### Orderblocks & breakers (Warren)")
    rows = []
    for z in reversed(obs):
        rows.append({"Type": {"OB+": "OB haussier (demande)", "OB-": "OB baissier (supply)",
                              "BRK+": "Breaker haussier", "BRK-": "Breaker baissier"}[z.kind],
                     "Zone": f"{z.bottom:,.2f} – {z.top:,.2f}", "Formé (NY)": f"{z.start:%d/%m %H:%M}",
                     "Méthode": z.method, "OTE 0,705": ui.fmt(z.ote), "Cible": ui.fmt(z.target), "Statut": z.status,
                     "Dist.": ui.fmt(z.mid - price, 1, True)})
    st.markdown(ui.table_html(pd.DataFrame(rows)) if rows else "Aucun orderblock détecté.", unsafe_allow_html=True)
    st.caption("Méthode C (Warren) : un swing a été « couru » (liquidité prise) juste avant l'OB – sa méthode préférée. "
               "Invalidation : clôture au-delà de l'OB, qui devient alors un breaker de sens opposé.")
with c2:
    st.markdown("#### Gaps MMM (prix injustes)")
    act = [z for z in gz if z.status in ("intacte", "partielle")]
    act = sorted(act, key=lambda z: abs(z.mid - price))[:14]
    rows = [{"Type": z.kind, "Zone": f"{z.bottom:,.2f} – {z.top:,.2f}", "Taille": f"{z.top - z.bottom:.2f}",
             "Formé (NY)": f"{z.start:%d/%m %H:%M}", "3e bougie": {1: "N1 continuation", 2: "N2 recharge 50 %", 3: "N3 épuisement"}.get(z.extra.get("niveau"), "–"),
             "Statut": z.status, "Dist.": ui.fmt(z.mid - price, 1, True)} for z in act]
    st.markdown(ui.table_html(pd.DataFrame(rows)) if rows else "Aucun gap ouvert.", unsafe_allow_html=True)
    st.caption("UDG = FVG 3 bougies (aimant principal) · ULG = corps séparés, mèches connectées (TGV) · UAG = gap absolu. "
               "Défense : AF/BC au bord → continuation. Violation : BC au-delà de l'origine → retournement. "
               "Ne jamais entrer à l'aveugle sur le bord : attendre la BC de confirmation.")

c1, c2 = st.columns(2)
with c1:
    st.markdown("#### Range & déviation (Warren, méthode 30 min)")
    st.markdown(f"""<div class="card comment">
<p>Range des 48 dernières barres : <b>{ui.fmt(rg['low'])} – {ui.fmt(rg['high'])}</b>, EQ {ui.fmt(rg['eq'])} – le prix est <b>{rg['side']}</b>.</p>
<p>Marché en range : <b>{'oui' if rg['is_range'] else 'non (tendance)'}</b> · Déviation récente : <b>{rg['deviation']}</b>.</p>
<p>Setup Warren en 5 étapes : 1) deux pivots forment le range 2) sweep / déviation d'une extrémité 3) MSB sur clôture
4) la supply/demande formée avant la cassure devient la zone d'entrée 5) TP sur l'extrémité opposée. Jamais à l'EQ.</p></div>""",
                unsafe_allow_html=True)
with c2:
    st.markdown("#### Pools de liquidité non pris (BSL / SSL)")
    if pools:
        st.markdown(ui.table_html(pd.DataFrame([{"Pool": p["type"], "Prix": ui.fmt(p["price"]), "Distance": ui.fmt(p["dist"], 1, True)} for p in pools]),
                                  num_cols=("Prix", "Distance")), unsafe_allow_html=True)
    else:
        st.caption("Aucun haut/bas égal non pris détecté.")
    smt = ctx["smt"]
    st.markdown(f'<div class="card" style="margin-top:10px"><h4>SMT NQ / ES (5m)</h4>{ui.esc(smt.get("label"))}</div>',
                unsafe_allow_html=True)

st.markdown("#### FVG : statistiques de comblement mesurées sur vos données")
rows = []
for k, n in (("5m", 4000), ("15m", 3000), ("1h", 5000)):
    st_ = structure.fvg_fill_stats(candles.classify(B["mk"][k].iloc[-n:]))
    if st_.empty:
        continue
    rows.append({"TF": k, "N FVG": len(st_), "Partiel 1 b.": f"{st_['partiel_1'].mean() * 100:.0f} %",
                 "Total 1 b.": f"{st_['total_1'].mean() * 100:.0f} %", "Partiel 5 b.": f"{st_['partiel_5'].mean() * 100:.0f} %",
                 "Total 5 b.": f"{st_['total_5'].mean() * 100:.0f} %", "Total 20 b.": f"{st_['total_20'].mean() * 100:.0f} %",
                 "Taille médiane": f"{st_['size'].median():.2f} pts"})
st.markdown(ui.table_html(pd.DataFrame(rows)), unsafe_allow_html=True)
st.caption("Référence Leversens (NQ) : 55 % des FVG 5 min totalement comblés en 5 bougies, 52 % en 1 h. Plus le gap est grand, "
           "moins il est comblé totalement : utiliser les grands FVG comme zones de rechargement, pas comme cibles.")
ui.footer()
