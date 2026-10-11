"""Labo : les concepts ICT/MMM passés au banc d'essai sur l'historique NQ chargé."""
import numpy as np
import pandas as pd
import streamlit as st

from core import charts, levels, ui
from core.config import LEVERSENS_REF, PARIS_TZ

ui.setup_page("Labo statistique", "🔬")
opts = ui.sidebar()
B = ui.bundle(opts)
ctx = B["ctx"]
mk = B["mk"]
ui.header("🔬 Labo statistique NQ", "Fréquences observées, avec effectif et intervalle de confiance à 95 % – descriptif, pas prévisionnel", ctx)


def ci(k, n):
    if n == 0:
        return "n.d."
    p = k / n
    z = 1.96
    den = 1 + z ** 2 / n
    c = (p + z ** 2 / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return f"{p * 100:.0f} % (IC {max(0, c - h) * 100:.0f}-{min(1, c + h) * 100:.0f}) · N={n}"


h1 = mk["1h"]
a = levels.asia_london_ny_stats(h1)
sw = levels.pdh_pdl_sweep_stats(h1)
ex = levels.extreme_hour_stats(h1)

ui.grid([
    ui.kpi("NY prend l'autre côté de l'Asie", ci(a["ny_other"], a["ny_other_n"]).split(" ·")[0],
           f"quand Londres n'en a pris qu'un · réf. Leversens {LEVERSENS_REF['asia_other_side_ny']} %"),
    ui.kpi("Londres prend 1 seul côté", ci(a["london_one"], a["n"]).split(" ·")[0], f"N = {a['n']} jours"),
    ui.kpi("PDH pris pendant NY (s'il était intact)",
           ci(int((sw["pdh_ny"] & ~sw["pdh_pre"]).sum()), int((~sw["pdh_pre"]).sum())).split(" ·")[0] if len(sw) else "n.d.",
           f"réf. {LEVERSENS_REF['pdh_taken_ny']} %"),
    ui.kpi("PDL pris pendant NY (s'il était intact)",
           ci(int((sw["pdl_ny"] & ~sw["pdl_pre"]).sum()), int((~sw["pdl_pre"]).sum())).split(" ·")[0] if len(sw) else "n.d.",
           f"réf. {LEVERSENS_REF['pdl_taken_ny']} %"),
], 4)

st.markdown("#### Heure du plus haut et du plus bas de la journée CME")
if len(ex):
    off = int((ctx["last_ts"].tz_convert(PARIS_TZ).utcoffset() - ctx["last_ts"].utcoffset()).total_seconds() // 3600)
    hh = ((ex["h_hour"] + off) % 24).value_counts(normalize=True).sort_index() * 100
    ll = ((ex["l_hour"] + off) % 24).value_counts(normalize=True).sort_index() * 100
    st.plotly_chart(charts.hour_hist(hh, ll, f"Répartition horaire des extrêmes (N = {len(ex)} jours)"), width="stretch")
    ny = ex["h_hour"].between(8, 16).mean() * 100, ex["l_hour"].between(8, 16).mean() * 100
    st.caption(f"Plus haut formé pendant New York (8h-17h NY) : {ny[0]:.0f} % · plus bas : {ny[1]:.0f} % "
               f"(Leversens : {LEVERSENS_REF['ny_high_share']} % / {LEVERSENS_REF['ny_low_share']} % pour 39 % de la journée).")

c1, c2 = st.columns(2)
with c1:
    st.markdown("#### Balayage PDH / PDL pendant New York (1 h)")
    if len(sw):
        rows = []
        for side, pre, ny, out in (("PDH", "pdh_pre", "pdh_ny", "pdh_outcome"), ("PDL", "pdl_pre", "pdl_ny", "pdl_outcome")):
            n = len(sw); k_pre = int(sw[pre].sum())
            intact = sw[~sw[pre]]
            k_ny = int(intact[ny].sum())
            o = sw[out].dropna() if out in sw else pd.Series(dtype=str)
            rows.append({"Niveau": side, "Déjà pris avant NY": ci(k_pre, n), "Pris pendant NY (si intact)": ci(k_ny, len(intact)),
                         "Continuation": ci(int((o == "continuation").sum()), len(o)),
                         "Retour dans le range": ci(int((o == "retour range").sum()), len(o))})
        st.markdown(ui.table_html(pd.DataFrame(rows)), unsafe_allow_html=True)
with c2:
    st.markdown("#### Range asiatique → Londres → New York")
    t = pd.DataFrame([
        {"Événement": "Londres prend un seul côté", "Fréquence": ci(a["london_one"], a["n"])},
        {"Événement": "Londres prend les deux côtés", "Fréquence": ci(a["london_both"], a["n"])},
        {"Événement": "Londres ne prend aucun côté", "Fréquence": ci(a["london_none"], a["n"])},
        {"Événement": "NY prend l'autre côté (si Londres un seul)", "Fréquence": ci(a["ny_other"], a["ny_other_n"])},
    ])
    st.markdown(ui.table_html(t), unsafe_allow_html=True)

st.markdown("#### Séance cash : extrême dans les 30 premières minutes")
d5 = mk["5m"].copy()
d5["day"] = d5.index.normalize()
k = n = 0
for day, g in d5.groupby("day"):
    cash = g.between_time("09:30", "15:55")
    if len(cash) < 70:
        continue
    n += 1
    first = cash.between_time("09:30", "09:55")
    k += (first["High"].max() >= cash["High"].max()) or (first["Low"].min() <= cash["Low"].min())
st.markdown(f'<div class="card">Plus haut OU plus bas de la séance cash formé entre 15:30 et 16:00 Paris : '
            f'<b>{ci(k, n)}</b> (Leversens : {LEVERSENS_REF["cash_extreme_first30"]} %). Une tranche de 30 min = 7,7 % '
            f'de la séance : l\'ouverture fixe très souvent un extrême → ne pas chasser l\'ouverture, attendre la BC de 15:45.</div>',
            unsafe_allow_html=True)
st.caption("Ces fréquences décrivent le passé de NQ ; aucune ne dit dans quel sens le marché va partir. "
           "Elles servent à calibrer les cibles et les fenêtres, pas à prédire.")
ui.footer()
