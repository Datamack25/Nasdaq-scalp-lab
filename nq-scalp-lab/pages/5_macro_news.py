"""Banques centrales, politique, géopolitique, calendrier : biais du flux et risque d'événement."""
import streamlit as st

from core import charts, ui
from core.config import MACRO_REACTION, PARIS_TZ

ui.setup_page("Macro & News", "📰")
opts = ui.sidebar()
B = ui.bundle(opts)
ctx = B["ctx"]
ui.header("📰 Macro, banques centrales & politique", "Flux RSS (Fed, BCE, BoJ, Maison-Blanche, géopolitique), calendrier et réaction historique de NQ", ctx)

nd = B["news"]
nb = ctx["news"]
ev = ctx["event"]
ui.grid([
    ui.kpi("Biais du flux", nb.get("label", "NEUTRE"), f"score {nb.get('score', 0):+.2f} · {nb.get('n', 0)} articles",
           "up" if nb.get("score", 0) > .25 else "down" if nb.get("score", 0) < -.25 else ""),
    ui.kpi("Banques centrales", f"{nb.get('by_cat', {}).get('Banque centrale', 0):+.2f}", "hawkish < 0 < dovish"),
    ui.kpi("Politique", f"{nb.get('by_cat', {}).get('Politique', 0):+.2f}", "tarifs, Maison-Blanche, Chine"),
    ui.kpi("Risque d'événement", ev.get("level", "n.d.").upper(), ev.get("msg", ""),
           "down" if ev.get("level") in ("critique", "élevé") else ""),
], 4)
st.markdown('<div class="warn">Ce score résume le ton des titres (lexique hawkish/dovish, risk-on/off). '
            'Il n\'a pas de pouvoir prédictif démontré à court terme (Leversens : ~54 % à 0-30 min, non '
            'significatif). Il sert à <b>filtrer</b> (éviter de shorter un flux très dovish, réduire la taille un '
            'jour de FOMC), pas à déclencher un trade.</div>', unsafe_allow_html=True)

if nd is None or nd.empty:
    st.markdown('<div class="alert">Flux d\'actualités indisponible (réseau bloqué ou sources hors ligne). '
                'Sur Streamlit Cloud / en local, les flux RSS Fed, BCE, Google News et CNBC se chargent automatiquement.</div>',
                unsafe_allow_html=True)
else:
    cat = st.multiselect("Catégories", ["Banque centrale", "Politique", "Marché"], default=["Banque centrale", "Politique", "Marché"])
    f = nd[nd["catégorie"].isin(cat)].head(60).copy()
    f["Paris"] = f["date"].dt.tz_convert(PARIS_TZ).dt.strftime("%d/%m %H:%M")
    rows = []
    for _, r in f.iterrows():
        tone = "up" if r["score"] > 0 else "down" if r["score"] < 0 else "flat"
        rows.append(f'<tr><td>{r["Paris"]}</td><td>{ui.esc(r["catégorie"])}</td><td>{ui.esc(r["source"])}</td>'
                    f'<td><a href="{ui.esc(r["lien"])}" target="_blank" style="color:#c9d2e3">{ui.esc(r["titre"])}</a></td>'
                    f'<td class="n {tone}">{r["score"]:+.1f}</td></tr>')
    st.markdown('<table class="t"><thead><tr><th>Paris</th><th>Catégorie</th><th>Source</th><th>Titre</th><th>Ton</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table>', unsafe_allow_html=True)

st.markdown("#### Calendrier de la semaine")
cal = B["cal"]
if cal is None or cal.empty:
    st.caption("Calendrier ForexFactory indisponible.")
else:
    c = cal.copy()
    c["Paris"] = c["date"].dt.tz_convert(PARIS_TZ).dt.strftime("%a %d/%m %H:%M")
    st.markdown(ui.table_html(c[["Paris", "country", "title", "impact", "forecast", "previous", "réaction_hist"]]
                              .rename(columns={"country": "Pays", "title": "Publication", "impact": "Impact",
                                               "forecast": "Prévision", "previous": "Précédent", "réaction_hist": "Réaction NQ (1 h)"})),
                unsafe_allow_html=True)

st.markdown("#### Réaction médiane de NQ aux publications (amplitude 1 h, sans direction)")
keys = ["CPI", "NFP", "PPI", "JOLTS", "GDP", "PCE", "Retail Sales", "FOMC"]
st.plotly_chart(charts.bars(keys, [MACRO_REACTION[k][0] for k in keys], "Publication vs jour ordinaire (pts NQ, source Leversens)",
                            color="#f5b041", ref=86, ytitle="pts en 1 h"), width="stretch")
st.markdown("""<div class="card comment">
<p><b>Conduite à tenir (MNQ, Apex)</b> : à plat 2 min avant CPI/NFP/PPI (14:30 Paris) et FOMC (20:00 Paris, conférence 20:30).
Laisser passer la 1re bougie 5 min : le premier mouvement est souvent un Judas. Entrer seulement sur une BC+ qui clôture
au-delà du range de la publication, risque réduit à 0,5 % (MMM).</p>
<p><b>Banques centrales</b> : un ton hawkish (hausse des taux, inflation tenace) pèse sur la tech ; un ton dovish (baisse, pause)
la soutient. Les discours BCE/BoJ comptent via le dollar et les taux (carry trade yen).</p>
<p><b>Politique</b> : annonces de tarifs, contrôles à l'export de puces, shutdowns = risque de gap. Pas de position ouverte
pendant les conférences annoncées de la Maison-Blanche.</p></div>""", unsafe_allow_html=True)
ui.footer()
