"""Méthode : synthèse Max Maserati + Warren + ICT et routine du scalpeur MNQ (heure de Paris)."""
import streamlit as st

from core import ui

ui.setup_page("Méthode & bonnes pratiques", "📘")
ui.sidebar()
st.markdown('<div class="hdr"><div><h1>📘 Méthode & bonnes pratiques</h1><div class="sub">Ce que disent Max Maserati, '
            'Warren et l\'ICT – traduit en routine pour un scalpeur MNQ sur Apex, en heure de Paris</div></div></div>',
            unsafe_allow_html=True)

st.markdown("""<div class="card comment">
<p><b>Le principe (Max)</b> : chaque mouvement oppose des <b>Murs</b> (ordres limites passifs) à des <b>Marteaux</b> (ordres au
marché). La clôture du corps au-delà du range précédent (BC) prouve que le Marteau a gagné. Pas de BC = pas de momentum =
pas de trade. « Bougez avec le Marteau, ne combattez jamais le Mur. Tradez uniquement dans les zones de valeur. »</p>
<p><b>Le principe (Warren)</b> : la smart money a besoin de liquidité. On attend qu'un swing soit « couru », puis une cassure
de structure (MSB) sur clôture ; l'origine du mouvement (orderblock) devient la zone d'entrée, idéalement à l'OTE 0,705 ;
la cible est la liquidité non touchée de l'autre côté.</p>
<p><b>Le principe (ICT)</b> : le temps compte autant que le prix. Asie accumule, Londres manipule (Judas), New York
distribue. On trade dans les killzones, au-delà de l'ouverture de minuit dans le bon sens (Décote pour acheter, Prime pour
vendre), en confirmant avec les partenaires (SMT ES/YM, DXY).</p></div>""", unsafe_allow_html=True)

st.markdown("#### Routine du jour (heure de Paris)")
routine = [
    ("Veille / 06:00", "Daily clôturée ? Noter le biais HTF (BuBC/BeBC daily, CDL/CDS 4H). Marquer PDH/PDL, ouvertures hebdo/mois, haut/bas du lundi."),
    ("06:00", "Ouverture de minuit NY : Prime / Décote du jour. Boîte asiatique (02:00-06:00) marquée, jamais tradée."),
    ("08:00-09:00", "Francfort / Judas de Londres : observer le piège, ne pas entrer."),
    ("09:00-11:00", "Ouverture de Londres : 1re fenêtre (BC+ qui casse le Judas). Optionnelle si vous êtes concentré sur NY."),
    ("14:00-14:30", "Pré-ouverture NY. Publications de 14:30 → à plat avant ; attendre la 1re bougie 5 min."),
    ("15:30-15:45", "Ouverture cash + IB : marquer, NE PAS chasser (67 % des séances font un extrême dans les 30 min)."),
    ("15:45-17:30", "FENÊTRE PRINCIPALE : checklist 5/5 sur 5m/15m, entrée à la clôture de la BC+, stop au-delà de la mèche."),
    ("17:30-19:30", "Zone morte : aucune entrée. Gérer ou clôturer."),
    ("20:00-21:00", "Silver Bullet PM / FOMC éventuel : setups A+ uniquement, taille réduite."),
    ("Après séance", "Journal : capture, setup, checklist, R. Revue hebdomadaire des stats par setup et par session."),
]
st.markdown(ui.table_html(__import__("pandas").DataFrame(routine, columns=["Heure", "Action"])), unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    st.markdown("#### Les 12 meilleures pratiques retenues")
    st.markdown("""<div class="card comment">
<p>1. <b>Une seule session, un seul setup</b> pendant 3 mois / 100 trades (Max) : Fenêtre d'Or NY + BuBC+/BeBC+ 5m dans le sens 4H.</p>
<p>2. <b>Bougie clôturée uniquement</b> : jamais d'entrée pendant la formation.</p>
<p>3. <b>Seulement les « + »</b> avec mèche : BC−, CI et S&D = attendre.</p>
<p>4. <b>Checklist 5/5</b> : structure HTF, localisation Prime/Décote, zone, bougie LTF, volume. 4/5 = pas de trade.</p>
<p>5. <b>Liquidité d'abord</b> (Warren méthode C) : un swing couru avant la zone augmente la qualité.</p>
<p>6. <b>MSB sur clôture, pas sur mèche</b>.</p>
<p>7. <b>Entrée H4/1H en biais, 5m/15m en exécution</b> : ne jamais entrer sur un 15m seul contre le 4H.</p>
<p>8. <b>Sortie</b> : 75 % à C1, reste à breakeven ; tout couper si C1 n'est pas atteint en 2 barres.</p>
<p>9. <b>Mur du momentum</b> : 4 BC haussières / 3 baissières = sortir.</p>
<p>10. <b>Risque</b> : ≤ 1 % du compte et ≤ 10 % du buffer Apex ; 3 pertes = demi-taille ; 3 % de perte = fin de journée.</p>
<p>11. <b>Annonces</b> : à plat avant, 0,5 % le jour même, laisser passer le Judas.</p>
<p>12. <b>Statistiques ≠ prédiction</b> : les fréquences calibrent cibles et fenêtres ; la décision reste la checklist.</p></div>""",
                unsafe_allow_html=True)
with c2:
    st.markdown("#### Fiche d'identité de trading (proposée)")
    fiche = [("HTF de cadrage", "4H (+ daily pour le jour)"), ("Mid TF de confirmation", "1H / 15m"), ("LTF d'entrée", "5m (1m pour affiner)"),
             ("Cadrage macro", "Ouverture de minuit + PDH/PDL + boîte asiatique"), ("Système de signal", "Système 1 (CDL/CDS) + BC+ / sweep C2"),
             ("Outil d'exécution", "OTE 0,705 dans l'OB / UDG"), ("Session", "Fenêtre d'Or NY 14:00-17:30 Paris"),
             ("Risque par trade", "0,5-1 % et ≤ 10 % du buffer"), ("Trades max / jour", "3"), ("Perte jour max", "3 % ou 2 pertes pleines"),
             ("R:R cible", "1:1 sur C1, runner vers la liquidité"), ("Drawdown d'arrêt / révision", "50 % du drawdown Apex consommé")]
    st.markdown(ui.table_html(__import__("pandas").DataFrame(fiche, columns=["Élément", "Choix"])), unsafe_allow_html=True)
    st.markdown("""<div class="warn" style="margin-top:10px">À propos des chiffres du backtest MMM : 72 % de réussite pour un
objectif égal à l'extrême de la bougie signal, donc souvent très proche. Les projections de rendement du rapport (149-446 %/an)
supposent un R:R de 1:1 sans frictions ; le rapport lui-même prévoit 60-70 % du théorique. Ne dimensionnez jamais un compte
Apex sur ces projections : mesurez votre propre taux sur 50-100 trades (page Risque & Journal).</div>""", unsafe_allow_html=True)

st.markdown("#### Comment cet outil décide")
st.markdown("""<div class="card comment">
<p>Le <b>score de confluence</b> (-100 à +100) additionne des composantes pondérées : bougies MMM clôturées (D, 4H, 1H, 15m, 5m),
structure CDL/CDS par TF, mur du momentum, Prime/Décote (ouverture de minuit et dealing range), sweep X/X+/X++ de PDH/PDL/Asie
qualifié par le volume, zones OB/breaker/UDG proches, intermarché (ES, YM, RTY, DXY, TNX, VIX), divergence SMT, poids lourds
et, avec un poids faible, le ton des actualités.</p>
<p>La <b>note</b> (A+, A, B, C, NO TRADE) exige la checklist 5/5, un timing non rouge (zone morte, Judas, annonce imminente) et,
pour A+, au moins 2 clôtures de corps alignées sur D/4H/1H/15m.</p>
<p>Les <b>probabilités par horizon</b> mélangent la confluence (pondérée différemment selon l'horizon) et un modèle
walk-forward dont le poids dépend de sa compétence mesurée hors échantillon.</p></div>""", unsafe_allow_html=True)
st.caption("Sources : Max Maserati Model – résultats de backtesting (10 janv. 2026) · MMM Trading Masterclass (8 modules) · "
           "Stratégie de trade Warren (ESLSCA) · Leversens Trading – Plan de séance et Labo ICT. Usage éducatif.")
ui.footer()
