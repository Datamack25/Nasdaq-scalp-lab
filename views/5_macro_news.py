"""Macro & News : FinancialJuice, ForexFactory, FRED (Saint-Louis), banques centrales, politique,
géopolitique → sentiment, régime macro et recommandations."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import charts, ui
from core.config import MACRO_REACTION, PARIS_TZ
from core.news import FRED_SERIES

ui.setup_page("Macro & News", "📰")
opts = ui.sidebar()
B = ui.bundle(opts)
ctx = B["ctx"]
ui.header("📰 Macro, banques centrales & géopolitique",
          "FinancialJuice · ForexFactory · FRED Saint-Louis · Fed/BCE/BoJ · Maison-Blanche · géopolitique", ctx)

nd = B["news"]
nb = ctx["news"]
ev = ctx["event"]
fr = B["fred_reg"]
src = B["sources"]

# ------------------------------------------------------------ synthèse
ui.grid([
    ui.kpi("Sentiment des actualités", nb.get("label", "NEUTRE"), f"score {nb.get('score', 0):+.2f} · {nb.get('n', 0)} titres",
           "up" if nb.get("score", 0) > .25 else "down" if nb.get("score", 0) < -.25 else ""),
    ui.kpi("Régime macro FRED", fr.get("label", "n.d."), f"score {fr.get('score', 0):+.2f} (taux, crédit, liquidité, dollar)",
           "up" if fr.get("score", 0) > .2 else "down" if fr.get("score", 0) < -.2 else ""),
    ui.kpi("Géopolitique", f"{nb.get('by_cat', {}).get('Géopolitique', 0):+.2f}", "guerres, pétrole, sanctions",
           "down" if nb.get("by_cat", {}).get("Géopolitique", 0) < -.3 else ""),
    ui.kpi("Banques centrales", f"{nb.get('by_cat', {}).get('Banque centrale', 0):+.2f}", "hawkish < 0 < dovish"),
    ui.kpi("Risque d'événement", ev.get("level", "n.d.").upper(), ev.get("msg", ""),
           "down" if ev.get("level") in ("critique", "élevé") else ""),
    ui.kpi("Sources actives", f"{sum(1 for v in src.values() if v)}/5",
           f"RSS {src['rss']} · FJ {src['fj_rss'] + src['fj_paste']} · FF {src['ff']} · FRED {src['fred']}"),
], 6)

st.markdown("#### Recommandations selon les conditions de marché")
conds = ctx.get("conditions", [])
if conds:
    st.markdown('<div class="card">' + "<br>".join(ui.light(l, t) for l, t in conds) + "</div>", unsafe_allow_html=True)
else:
    st.caption("Aucune condition particulière détectée (ou sources indisponibles).")
st.markdown('<div class="warn">Le sentiment résume le ton des titres (lexique hawkish/dovish, risk-on/off, pétrole, '
            'taux, géopolitique) : c\'est un <b>filtre</b>, pas un déclencheur. Le régime FRED décrit le vent de fond '
            '(jours/semaines) et pèse surtout sur les horizons 60-240 min. La décision reste la checklist MMM 5/5.</div>',
            unsafe_allow_html=True)

tabs = st.tabs(["🗞️ Fil d'actualités", "⚡ FinancialJuice", "📅 Calendrier (FF + FJ)", "🏛️ FRED Saint-Louis", "📊 Réactions NQ"])

# ------------------------------------------------------------ fil
with tabs[0]:
    if nd is None or nd.empty:
        st.markdown('<div class="alert">Aucun titre chargé (réseau bloqué ou sources hors ligne). Collez la page '
                    'FinancialJuice dans la barre latérale pour l\'analyser quand même.</div>', unsafe_allow_html=True)
    else:
        by_src = nb.get("by_src", {})
        if by_src:
            s = pd.Series(by_src).sort_values()
            st.plotly_chart(charts.bars(list(s.index), list(s.values), "Sentiment pondéré par source (récence)",
                                        color=["#22c55e" if v > 0 else "#ef4444" for v in s.values], ref=0, ytitle="score"),
                            width="stretch")
        c1, c2 = st.columns([1, 3])
        cats = sorted(nd["catégorie"].dropna().unique())
        cat = c1.multiselect("Catégories", cats, default=cats)
        srcs = sorted(nd["source"].dropna().unique())
        sel = c2.multiselect("Sources", srcs, default=srcs)
        f = nd[nd["catégorie"].isin(cat) & nd["source"].isin(sel)].head(80).copy()
        f["Paris"] = pd.to_datetime(f["date"], utc=True).dt.tz_convert(PARIS_TZ).dt.strftime("%d/%m %H:%M")
        rows = []
        for _, r in f.iterrows():
            tone = "up" if r["score"] > 0 else "down" if r["score"] < 0 else "flat"
            rows.append(f'<tr><td>{r["Paris"]}</td><td>{ui.esc(r["catégorie"])}</td><td>{ui.esc(r["source"])}</td>'
                        f'<td><a href="{ui.esc(r["lien"])}" target="_blank" style="color:#c9d2e3">{ui.esc(r["titre"])}</a></td>'
                        f'<td class="n {tone}">{r["score"]:+.1f}</td></tr>')
        st.markdown('<table class="t"><thead><tr><th>Paris</th><th>Catégorie</th><th>Source</th><th>Titre</th><th>Ton</th></tr></thead>'
                    f'<tbody>{"".join(rows)}</tbody></table>', unsafe_allow_html=True)

# ------------------------------------------------------------ FinancialJuice
with tabs[1]:
    fjh = nd[nd["source"].astype(str).str.startswith("FinancialJuice")] if nd is not None and not nd.empty else pd.DataFrame()
    st.markdown(f"Titres FinancialJuice chargés : **{len(fjh)}** (RSS {src['fj_rss']}, collés {len(B['fj_heads'])}) · "
                f"événements du calendrier FJ : **{len(B['fj_cal'])}**")
    if fjh.empty and B["fj_cal"].empty:
        st.markdown('<div class="warn">Le flux RSS FinancialJuice n\'a rien renvoyé (le site bloque souvent les accès '
                    'automatiques et diffuse en différé aux comptes gratuits). Ouvrez <b>financialjuice.com/home</b>, '
                    'faites <b>Ctrl+A</b> puis <b>Ctrl+C</b> et collez dans « 📋 FinancialJuice : coller la page » '
                    '(barre latérale) : le calendrier avec les valeurs publiées et les titres seront analysés.</div>',
                    unsafe_allow_html=True)
    if not fjh.empty:
        for _, r in fjh.head(25).iterrows():
            tone = "up" if r["score"] > 0 else "down" if r["score"] < 0 else "flat"
            t = pd.to_datetime(r["date"], utc=True).tz_convert(PARIS_TZ).strftime("%d/%m %H:%M")
            body = f'<div class="ks">{ui.esc(r["résumé"])[:400]}</div>' if isinstance(r.get("résumé"), str) and r["résumé"] else ""
            st.markdown(f'<div class="card" style="margin-bottom:6px"><span class="ks">{t} · {ui.esc(r["catégorie"])}</span> '
                        f'<span class="{tone}" style="float:right">{r["score"]:+.1f}</span><br><b>{ui.esc(r["titre"])}</b>{body}</div>',
                        unsafe_allow_html=True)
    fjc = B["fj_cal"]
    if not fjc.empty:
        pub = fjc[fjc["actual"] != "-"]
        if len(pub):
            st.markdown("Valeurs déjà publiées (FinancialJuice)")
            p = pub.copy()
            p["Paris"] = p["date"].dt.tz_convert(PARIS_TZ).dt.strftime("%a %d/%m %H:%M")
            p["Surprise"] = p["surprise"].map(lambda x: "" if pd.isna(x) else f"{x:+.2f}")
            st.markdown(ui.table_html(p[["Paris", "title", "actual", "forecast", "previous", "Surprise"]]
                                      .rename(columns={"title": "Publication", "actual": "Publié", "forecast": "Prévu", "previous": "Précédent"})),
                        unsafe_allow_html=True)

# ------------------------------------------------------------ calendrier
with tabs[2]:
    cal = B["cal"]
    if cal is None or cal.empty:
        st.caption("Calendrier indisponible : ni ForexFactory ni FinancialJuice (collé).")
    else:
        c1, c2 = st.columns(2)
        imp = c1.multiselect("Impact", ["High", "Medium", "Low"], default=["High", "Medium"])
        pays = c2.multiselect("Pays", sorted(cal["country"].dropna().unique()),
                              default=[p for p in ("USD",) if p in set(cal["country"])] or sorted(cal["country"].dropna().unique()))
        c = cal[cal["impact"].isin(imp) & cal["country"].isin(pays)].copy()
        now = ctx["last_ts"]
        c = c[c["date"] >= now.normalize() - pd.Timedelta(days=1)]
        c["Paris"] = c["date"].dt.tz_convert(PARIS_TZ).dt.strftime("%a %d/%m %H:%M")
        for col in ("actual", "forecast", "previous", "réaction_hist", "source"):
            if col not in c:
                c[col] = ""
        st.markdown(ui.table_html(c[["Paris", "country", "title", "impact", "actual", "forecast", "previous", "réaction_hist", "source"]]
                                  .fillna("").rename(columns={"country": "Pays", "title": "Publication", "impact": "Impact",
                                                              "actual": "Publié", "forecast": "Prévu", "previous": "Précédent",
                                                              "réaction_hist": "Réaction NQ (1 h)", "source": "Source"})),
                    unsafe_allow_html=True)
        st.caption("ForexFactory : semaine en cours + suivante (USD, EUR, JPY, CNY, GBP – impact moyen/fort). "
                   "FinancialJuice (collé) ajoute les discours Fed/BCE, les résultats d'entreprises et les valeurs publiées. "
                   "Impact FJ estimé par mots-clés (CPI, PPI, NFP, FOMC, Fed Chair… = fort).")

# ------------------------------------------------------------ FRED
with tabs[3]:
    rows = fr.get("rows", [])
    if not rows:
        st.markdown('<div class="alert">FRED indisponible. L\'app utilise le CSV public fred.stlouisfed.org (sans clé) ; '
                    'pour l\'API officielle, ajoutez <code>FRED_API_KEY</code> dans les secrets Streamlit '
                    '(clé gratuite sur fredaccount.stlouisfed.org).</div>', unsafe_allow_html=True)
    else:
        t = pd.DataFrame(rows)
        t["Dernier"] = t["Dernier"].map(lambda x: ui.fmt(x, 2))
        t["Variation"] = t["Variation"].map(lambda x: ui.fmt(x, 2, True))
        t["Effet NQ"] = t["Effet NQ"].map(lambda x: "" if pd.isna(x) else f"{x:+.2f}")
        st.markdown(ui.table_html(t[["Série", "Dernier", "Variation", "Effet NQ", "Lecture", "Date"]],
                                  num_cols=("Dernier", "Variation", "Effet NQ")), unsafe_allow_html=True)
        st.caption("Variations : 30 jours (taux réels, 2 ans, point mort, spread HY, dollar en %), 7 jours (10 ans, VIX), "
                   "4 semaines (liquidité nette, NFCI). Effet NQ : -1 = vent contraire, +1 = vent porteur.")
        fred = B["fred"]
        choix = st.multiselect("Séries à tracer", [k for k in FRED_SERIES if k in fred],
                               default=[k for k in ("DFII10", "DGS10", "BAMLH0A0HYM2") if k in fred],
                               format_func=lambda k: FRED_SERIES[k])
        if choix:
            fig = go.Figure()
            for k in choix:
                s = fred[k].iloc[-260:]
                fig.add_trace(go.Scatter(x=s.index, y=s.values, name=FRED_SERIES[k], mode="lines"))
            st.plotly_chart(charts._style(fig, 380, "FRED – séries sélectionnées (≈ 1 an)"), width="stretch")

# ------------------------------------------------------------ réactions
with tabs[4]:
    keys = ["CPI", "NFP", "PPI", "JOLTS", "GDP", "PCE", "Retail Sales", "FOMC"]
    st.plotly_chart(charts.bars(keys, [MACRO_REACTION[k][0] for k in keys], "Publication vs jour ordinaire (pts NQ en 1 h, Leversens)",
                                color="#f5b041", ref=86, ytitle="pts en 1 h"), width="stretch")
    st.markdown("""<div class="card comment">
<p><b>Conduite à tenir (MNQ, Apex)</b> : à plat 2 min avant CPI/NFP/PPI (14:30 Paris) et FOMC (20:00 Paris, conférence 20:30).
Laisser passer la 1re bougie 5 min : le premier mouvement est souvent un Judas. Entrer seulement sur une BC+ qui clôture
au-delà du range de la publication, risque réduit à 0,5 % (MMM).</p>
<p><b>Lecture des surprises</b> : inflation (CPI, PPI, PCE) au-dessus du prévu → taux en hausse → pression sur NQ ;
en dessous → soutien. Emploi/activité au-dessus du prévu : positif si l'inflation est calme, négatif si la Fed est en mode hausse.</p>
<p><b>Pétrole & géopolitique</b> : un Brent au-dessus de 100 $ qui accélère nourrit l'inflation et les taux ; une détente
(cessez-le-feu, accord) soutient la tech. Pas de position ouverte pendant les conférences annoncées de la Maison-Blanche.</p></div>""",
                unsafe_allow_html=True)
ui.footer()
