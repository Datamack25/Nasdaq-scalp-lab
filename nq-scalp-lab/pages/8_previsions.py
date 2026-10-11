"""Prévisions directionnelles 1, 3, 5, 15, 60, 240 min – transparence complète sur la compétence."""
import numpy as np
import pandas as pd
import streamlit as st

from core import charts, ui
from core.config import FORECAST_HORIZONS

ui.setup_page("Prévisions", "🔮")
opts = ui.sidebar()
B = ui.bundle(opts)
ctx, dec = B["ctx"], B["dec"]
ui.header("🔮 Pronostics multi-horizon", "Confluence (règles MMM/ICT) ⊕ apprentissage walk-forward, rétréci vers 50 % selon la compétence prouvée", ctx)

ui.grid([ui.horizon_card(h, v) for h, v in dec.horizon_probs.items()], 6)
st.plotly_chart(charts.horizons_bar(dec.horizon_probs), width="stretch")

if not B["ml"]:
    st.info("Le moteur ML est désactivé (barre latérale). Les probabilités affichées viennent de la seule confluence.")
else:
    st.markdown("#### Qualité hors échantillon par horizon")
    rows = []
    for h, r in B["ml"].items():
        iv, bars = FORECAST_HORIZONS[h]
        if not r.get("ok"):
            rows.append({"Horizon": f"{h} min", "Base": f"{iv} × {bars}", "Statut": r.get("msg", "échec")})
            continue
        edge = (r["acc"] - r["base"]) * 100
        rows.append({"Horizon": f"{h} min", "Base": f"{iv} × {bars}", "N entraînement": r["n_train"], "N test": r["n_oos"],
                     "AUC": f"{r['auc']:.3f}", "Précision": f"{r['acc'] * 100:.1f} %", "Référence (classe maj.)": f"{r['base'] * 100:.1f} %",
                     "Avantage": f"{edge:+.1f} pts", "Précision si |p-50|>8": f"{r['acc_conf'] * 100:.1f} %" if not np.isnan(r["acc_conf"]) else "n.d.",
                     "Brier vs réf.": f"{r['brier']:.4f} / {r['brier_ref']:.4f}", "Compétence": f"{r['skill'] * 100:.0f} %",
                     "P brute": f"{r['p_raw'] * 100:.0f} %", "P rétrécie": f"{r['p_up'] * 100:.0f} %"})
    st.markdown(ui.table_html(pd.DataFrame(rows)), unsafe_allow_html=True)
    st.caption("Walk-forward TimeSeriesSplit (5 plis) avec un écart égal à l'horizon pour éviter toute fuite. "
               "Compétence = (AUC − 0,50) / 0,08, bornée 0-100 % : un modèle à AUC 0,50 affiche 50 % quoi qu'il calcule.")

    h_sel = st.select_slider("Détail de l'horizon", options=list(B["ml"]), value=15)
    r = B["ml"][h_sel]
    if r.get("ok"):
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(charts.calibration(r["calib"], f"Calibration hors échantillon – {h_sel} min"), width="stretch")
        with c2:
            st.markdown("#### Moteurs de la prévision actuelle")
            drv = pd.DataFrame([{"Variable": k, "Contribution (logit)": f"{v:+.3f}", "Pousse vers": "hausse" if v > 0 else "baisse"} for k, v in r["drivers"]])
            st.markdown(ui.table_html(drv), unsafe_allow_html=True)
            st.caption(f"Dernière barre utilisée : {r['last_bar']:%d/%m %H:%M} NY.")

st.markdown("#### Comment lire ces pronostics")
st.markdown("""<div class="card comment">
<p><b>Délai Yahoo</b> : NQ=F est différé d'environ 10-15 min. Les horizons <b>1, 3 et 5 min</b> portent donc sur une barre déjà
ancienne au moment où vous la lisez : utilisez-les comme lecture du micro-momentum, pas comme signal d'exécution. Pour un vrai
usage scalping, importez un CSV 1 min récent (barre latérale) ou branchez un flux temps réel.</p>
<p><b>15 et 60 min</b> sont les horizons les plus exploitables avec une décision toutes les 15 min ; <b>240 min</b> donne le contexte
de la session.</p>
<p><b>Ordre de grandeur honnête</b> : sur un indice liquide, un modèle robuste dépasse rarement 53-56 % de précision hors
échantillon. Les taux de 70-80 % du backtest MMM mesurent autre chose (atteinte d'un objectif C1 très proche avant le stop),
pas la direction du prix à horizon fixe.</p>
<p><b>Règle d'usage</b> : la probabilité sert à confirmer ou refuser un setup MMM/ICT déjà présent. Un 60 % contre votre setup = on passe.
Un 50 % = pas d'information, on s'en remet à la checklist 5/5.</p></div>""", unsafe_allow_html=True)
ui.footer()
