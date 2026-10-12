"""Plan de séance : niveaux NQ, range attendu, publications, killzones (heure de Paris)."""
import numpy as np
import pandas as pd
import streamlit as st

from core import ui
from core.config import KILLZONES, PARIS_TZ

ui.setup_page("Plan de séance", "📍")
opts = ui.sidebar()
B = ui.bundle(opts)
ctx = B["ctx"]
lv = ctx["levels"]
meta = lv["meta"]
ui.header("📍 Plan de séance", "Niveaux NQ classés, range attendu, publications du jour et killzones – heure de Paris", ctx)

price = meta["price"]
q = meta.get("range_q", [np.nan] * 3)
ui.grid([
    ui.kpi("Prix de référence", ui.fmt(price), f"{ctx['last_ts'].tz_convert(PARIS_TZ):%a %d/%m %H:%M} Paris"),
    ui.kpi("Range implicite 1σ (VXN)", "±" + ui.fmt(meta.get("implied_1sd"), 0) + " pts",
           f"range équivalent {ui.fmt(meta.get('implied_range'), 0)} pts"),
    ui.kpi("ATR 14 jours", ui.fmt(meta.get("atr14"), 0) + " pts",
           f"quartiles 60 j : {ui.fmt(q[0], 0)} / {ui.fmt(q[1], 0)} / {ui.fmt(q[2], 0)}"),
    ui.kpi("Déjà parcouru", ui.fmt(meta.get("done_today"), 0) + " pts",
           f"{meta.get('done_today', np.nan) / meta.get('atr14', np.nan) * 100:.0f} % de l'ATR"
           if meta.get("atr14") else ""),
], 4)

c1, c2 = st.columns([1.2, 1])
with c1:
    st.markdown("#### Les niveaux NQ (du plus haut au plus bas)")
    t = lv["table"].copy()
    if not t.empty:
        row = pd.DataFrame([{"niveau": "▶ PRIX DE RÉFÉRENCE", "prix": price, "heure": ctx["last_ts"], "groupe": "", "distance": 0.0}])
        t = pd.concat([t, row]).sort_values("prix", ascending=False).reset_index(drop=True)
        cur = int(t.index[t["niveau"] == "▶ PRIX DE RÉFÉRENCE"][0])
        t["Heure Paris"] = [h.tz_convert(PARIS_TZ).strftime("%d/%m %H:%M") if isinstance(h, pd.Timestamp) and not pd.isna(h) else ""
                            for h in t["heure"]]
        show = pd.DataFrame({"Niveau": t["niveau"], "Groupe": t["groupe"], "Prix": t["prix"].map(lambda x: ui.fmt(x)),
                             "Distance (pts)": t["distance"].map(lambda x: ui.fmt(x, 2, True)), "Formé": t["Heure Paris"]})
        st.markdown(ui.table_html(show, num_cols=("Prix", "Distance (pts)"), highlight_row=cur), unsafe_allow_html=True)
with c2:
    st.markdown("#### Killzones (heure de Paris)")
    now = ctx["last_ts"]
    offs = (now.tz_convert(PARIS_TZ).utcoffset() - now.utcoffset()).total_seconds() / 3600
    bars, lanes = [], {}
    for i, (name, a, b, role, col) in enumerate(KILLZONES):
        pa, pb = (a + offs) % 24, (b + offs) % 24
        if pb < pa:
            pb += 24
        lane = i % 2
        bars.append(f'<div class="kz" title="{ui.esc(name)} – {ui.esc(role)}" style="left:{pa / 24 * 100:.2f}%;'
                    f'width:{(pb - pa) / 24 * 100:.2f}%;top:{6 + lane * 24}px;background:{col}">{ui.esc(name)}</div>')
    tnow = now.tz_convert(PARIS_TZ)
    hn = tnow.hour + tnow.minute / 60
    ticks = "".join(f'<div class="tick" style="left:{h / 24 * 100:.2f}%">{h:02d}h</div>' for h in range(0, 24, 3))
    st.markdown(f'<div class="timeline" style="height:76px">{"".join(bars)}<div class="now" style="left:{hn / 24 * 100:.2f}%"></div>{ticks}</div>',
                unsafe_allow_html=True)
    kz = pd.DataFrame([{"Fenêtre": n, "Paris": f"{int((a + offs) % 24):02d}:{int(((a + offs) % 1) * 60):02d}-{int((b + offs) % 24):02d}:{int(((b + offs) % 1) * 60):02d}",
                        "Rôle": r} for n, a, b, r, _ in KILLZONES])
    st.markdown(ui.table_html(kz), unsafe_allow_html=True)
    st.caption(f"Écart Paris – New York actuel : +{offs:.0f} h (+5 h les semaines de décalage des changements d'heure).")

st.markdown("#### Les publications (ForexFactory)")
cal = B["cal"]
if cal is None or cal.empty:
    st.markdown('<div class="warn">Calendrier indisponible (réseau). Vérifier ForexFactory avant la séance : '
                'CPI, NFP, PPI à 14:30 Paris ; JOLTS, ISM à 16:00 ; FOMC à 20:00.</div>', unsafe_allow_html=True)
else:
    c = cal.copy()
    c["Paris"] = c["date"].dt.tz_convert(PARIS_TZ).dt.strftime("%a %d/%m %H:%M")
    c = c[["Paris", "country", "title", "impact", "forecast", "previous", "réaction_hist"]]
    c.columns = ["Paris", "Pays", "Publication", "Impact", "Prévision", "Précédent", "Réaction NQ historique"]
    st.markdown(ui.table_html(c), unsafe_allow_html=True)
ev = ctx["event"]
st.markdown(f'<div class="card">Risque d\'événement : <b>{ui.esc(ev.get("level"))}</b> – {ui.esc(ev.get("msg"))}. '
            'Règle MMM : risque 0,5 % les jours de publication majeure ; pratique prop firm : être à plat 2 min avant.</div>',
            unsafe_allow_html=True)

st.markdown("#### Lecture des niveaux (ICT / MMM / Warren)")
st.markdown("""<div class="card comment">
<p><b>PDH / PDL</b> : pools de stops de la veille. Sweep + bougie d'affinité (BeAFs+ au PDH, BuAFs+ au PDL) = retournement vers l'extrême opposé. Fenêtre la plus probable : 15:30-16:30 Paris.</p>
<p><b>Ouverture de minuit NY</b> : au-dessus = Prime (chercher des shorts sur rejet), en dessous = Décote (longs sur rebond). Une BC englobante au niveau = conviction maximale.</p>
<p><b>Boîte asiatique</b> : ne jamais trader dedans. Londres en prend souvent un côté (Judas), New York va chercher l'autre ~55 % du temps (Leversens).</p>
<p><b>Range du lundi (Warren)</b> : à la clôture du lundi, haut et bas deviennent la liquidité de la semaine ; un côté balayé tôt rend l'autre probable.</p>
<p><b>Ouvertures hebdo / mensuelle / annuelle</b> : coût moyen institutionnel – BuAFs+/BuBC+ au retour = long premium, BeAFs+ = short premium.</p>
</div>""", unsafe_allow_html=True)
ui.footer()
