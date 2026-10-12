"""Meilleur jour, meilleure heure : backtest MMM publié + mesures sur les données chargées."""
import numpy as np
import pandas as pd
import streamlit as st

from core import candles, charts, timing, ui
from core.config import MMM_DAY, MMM_H1_UTC, MMM_H4_UTC, PARIS_TZ

ui.setup_page("Meilleur jour & heure", "⏰")
opts = ui.sidebar()
B = ui.bundle(opts)
ctx = B["ctx"]
mk = B["mk"]
ui.header("⏰ Meilleur jour & meilleure heure", "Tables du backtest MMM (17 758 configurations) + profil mesuré sur NQ – heures converties en Paris", ctx)

tm = ctx["timing"]
now = ctx["last_ts"]
st.markdown('<div class="card">' + " ".join([
    ui.light(tm["ict"][0], tm["ict"][1]),
    ui.light(tm["jour"]["feu"], f"Aujourd'hui {tm['jour']['jour']}"),
    ui.light(tm["h4"]["feu"], f"H4 {tm['h4']['signal_utc']} UTC"),
    ui.light(tm["h1"]["feu"], f"H1 {tm['h1']['signal_utc']} UTC"),
    ui.light(tm["m15"]["feu"], "M15")]) + "</div>", unsafe_allow_html=True)

off = int((now.tz_convert(PARIS_TZ).utcoffset()).total_seconds() // 3600)   # UTC -> Paris
c1, c2 = st.columns(2)
with c1:
    st.markdown("#### Jour de trading (signal daily de la veille)")
    jd = pd.DataFrame(MMM_DAY).reset_index().rename(columns={"index": "Jour de trading", "BuBC": "BuBC %", "BeBC": "BeBC %"})
    jd["Statut"] = ["ÉVITER short" if b < 50 else "MEILLEUR" if a >= 76 else "FEU VERT" if a >= 71 else "PRUDENCE"
                    for a, b in zip(jd["BuBC %"], jd["BeBC %"])]
    st.markdown(ui.table_html(jd, num_cols=("BuBC %", "BeBC %")), unsafe_allow_html=True)
    st.caption("Clôture jeudi → trade vendredi = meilleur couple (76,2 % long, 68,9 % short). BeBC lundi → mardi : 46 %. "
               "Warren : ne pas trader le lundi lui-même, utiliser son haut/bas comme liquidité de la semaine.")
with c2:
    st.markdown("#### Fenêtres H4 (bougie signal → fenêtre de trade)")
    rows = []
    for u, (bu, be, feu) in sorted(MMM_H4_UTC.items(), key=lambda x: -(x[1][0] + x[1][1])):
        s, e = (u + 4 + off) % 24, (u + 8 + off) % 24
        rows.append({"Signal UTC": f"{u:02d}-{(u + 4) % 24:02d}", "Trade (Paris)": f"{s:02d}:00-{e:02d}:00",
                     "BuBC %": bu, "BeBC %": be, "Feu": feu})
    st.markdown(ui.table_html(pd.DataFrame(rows), num_cols=("BuBC %", "BeBC %")), unsafe_allow_html=True)

st.markdown("#### Heures H1 du backtest (heure du trade, Paris)")
h1 = []
for u, (bu, be) in MMM_H1_UTC.items():
    h1.append({"Trade Paris": f"{(u + 1 + off) % 24:02d}:00", "BuBC %": bu, "BeBC %": be,
               "Combo": np.nanmean([v for v in (bu, be) if v is not None])})
h1 = pd.DataFrame(h1).sort_values("Combo", ascending=False)
st.plotly_chart(charts.bars(h1["Trade Paris"], h1["Combo"], "Taux de réussite MMM moyen (BuBC/BeBC) par heure de trade",
                            color=["#22c55e" if v >= 72 else "#f5b041" if v >= 66 else "#ef4444" for v in h1["Combo"]], ref=70,
                            ytitle="%"), width="stretch")

st.markdown("#### Mesuré sur vos données NQ")
h = mk["1h"].iloc[-24 * 120:]
c1, c2 = st.columns(2)
with c1:
    hp = h.copy(); hp.index = hp.index.tz_convert(PARIS_TZ)
    st.plotly_chart(charts.heatmap(timing.weekday_hour_heatmap(hp, "range"), "Range moyen (pts) – jour × heure de Paris"), width="stretch")
with c2:
    st.plotly_chart(charts.heatmap(timing.weekday_hour_heatmap(hp, "rendement"), "Rendement moyen (pb) – jour × heure de Paris",
                                   fmt=".1f", diverging=True), width="stretch")
bt = candles.backtest_configs(candles.classify(mk["1h"].iloc[-3000:]))
bw = timing.best_windows(mk["1h"].iloc[-3000:], bt)
bw.index = [(i + int((now.tz_convert(PARIS_TZ).utcoffset() - now.utcoffset()).total_seconds() // 3600)) % 24 for i in bw.index]
show = bw.head(10).reset_index().rename(columns={"index": "Heure Paris", "range_moy": "Range moy (pts)", "abs_ret": "|Rdt| (pb)",
                                                  "pct_hausse": "% hausse", "volume": "Volume moy", "win_bc": "Win BC mesuré %", "n_bc": "N BC", "score": "Score"})
show = show.drop(columns=["n"], errors="ignore").round(1)
show["Heure Paris"] = show["Heure Paris"].map(lambda x: f"{int(x):02d}:00")
if "N BC" in show:
    show["N BC"] = show["N BC"].fillna(0).astype(int)
st.markdown("Top 10 des heures (opportunité = range × qualité du signal BC mesurée)")
st.markdown(ui.table_html(show, num_cols=tuple(c for c in show.columns if c != "Heure Paris")), unsafe_allow_html=True)

wd = timing.weekday_stats(mk["1d"].iloc[-500:])
st.plotly_chart(charts.bars(wd.index, wd["range_moy"], "Range journalier moyen par jour (pts, ~2 ans)", ref=wd["range_moy"].mean()), width="stretch")
st.markdown("""<div class="card comment"><p><b>Synthèse pour un scalpeur MNQ depuis Paris</b> : la fenêtre principale est
<b>14:00-17:30</b> (Fenêtre d'Or NY 8h-11h30), avec l'IB 15:30-16:30 – attendre 15:45 pour la 1re BC directionnelle,
puis le sweet spot 16:30-17:30 (cassure-retest de l'IB). Seconde option : <b>09:00-11:00</b> (ouverture de Londres).
<b>Zone morte 17:30-19:30</b> : aucune entrée. Les jours à privilégier : mercredi-jeudi-vendredi après une BC daily ;
prudence le lundi (pas de lecture de semaine) et sur les shorts du mardi.</p></div>""", unsafe_allow_html=True)
ui.footer()
