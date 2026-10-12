# NQ Scalp Lab — aide à la décision MNQ (MMM · ICT · Warren)

Laboratoire Streamlit pour scalper le Nasdaq (MNQ) sur un compte Apex : il analyse le marché toutes les 15 min,
lit les bougies selon le **Max Maserati Model**, repère les zones **ICT / Warren**, vérifie le **timing**
(jour, session, killzone), les **partenaires ICT** (ES, YM, DXY, taux, VIX) et le **flux macro / banques centrales /
politique**, puis donne un biais, une note de setup, un plan MNQ et une **probabilité de hausse à 1, 3, 5, 15, 60
et 240 min**.

> Outil éducatif. Ce n'est pas un conseil en investissement. Yahoo Finance diffuse NQ=F avec ~10-15 min de retard.

## Pages

| Page | Contenu |
|---|---|
| 🎯 **Cockpit** (`views/0_cockpit.py`) | Verdict LONG/SHORT/ATTENDRE, note A+ → NO TRADE, probabilités par horizon, feux de timing, checklist MMM 5/5, « tempête parfaite », plan MNQ avec taille Apex, commentaire de marché, décomposition du score |
| 📍 Plan de séance | Niveaux NQ classés (PDH/PDL, cash, overnight, minuit NY, boîte asiatique, Londres, IB, semaine, lundi, mois, trimestre, année), ATR, range implicite VXN, killzones en heure de Paris, calendrier + réaction historique |
| 🕯️ Bougies MMM | Alphabet MMMFCB multi-TF (BuBC±, BeBC±, C2±, AFs±, CI, S&D), swings MMM, CDL/CDS + LD/SD, PCX, mur du momentum, backtest sur vos données vs backtest publié |
| 🧱 ICT & Warren | Orderblocks (méthodes A/B/C), breakers, UDG/ULG/UAG, OTE 0,705, dealing range Prime/Décote, range & déviation, pools BSL/SSL, stats de comblement FVG |
| 🌐 Intermarché | Partenaires ICT : SMT NQ/ES et NQ/YM, DXY, TNX, VIX/VXN, RTY, or, poids lourds du Nasdaq-100 |
| 📰 Macro & News | Flux Fed, BCE, BoJ, Maison-Blanche, géopolitique (RSS), ton hawkish/dovish & risk-on/off, calendrier ForexFactory, risque d'événement |
| ⏰ Meilleur jour & heure | Tables du backtest MMM converties en heure de Paris + heatmaps jour × heure mesurées sur NQ |
| 🔬 Labo statistique | Asie → Londres → NY, balayages PDH/PDL, heure des extrêmes, extrême des 30 premières minutes, avec IC 95 % |
| 🔮 Prévisions | Métriques hors échantillon (AUC, précision vs référence, Brier, calibration) et moteurs de la prévision |
| 🛡️ Risque Apex & Journal | Drawdown suiveur, calculateur de lots MNQ, espérance, règles MMM/Warren, journal CSV |
| 📘 Méthode | Synthèse Max + Warren + ICT, routine horaire du scalpeur, fiche d'identité de trading |

## Installation locale

```bash
git clone https://github.com/<vous>/nq-scalp-lab.git
cd nq-scalp-lab
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Test sans réseau (mode démo) : `python tests/smoke_test.py`

## Déploiement Streamlit Community Cloud

1. Pousser le dépôt sur GitHub.
2. share.streamlit.io → *New app* → choisir le dépôt, branche `main`, fichier `app.py`.
3. Aucun secret n'est requis.

## Données

* **Yahoo Finance** (`yfinance`) : NQ=F en 1 min (7 j), 5 et 15 min (60 j), 1 h (2 ans), journalier (10 ans) ; partenaires en 5 min.
* **CSV** (barre latérale) : un export 1 min TradingView / NinjaTrader (`time, open, high, low, close, volume`) remplace Yahoo pour NQ, pour des données plus fraîches.
* **Mode DÉMO** : si ni Yahoo ni CSV ne répondent, une série synthétique permet de tester l'interface. Un bandeau orange le signale ; aucune décision ne doit être prise dessus.
* **Actualités** : RSS Fed, BCE, Google News (BoJ, Powell/FOMC, tarifs/Maison-Blanche, géopolitique), CNBC ; calendrier `nfs.faireconomy.media` (ForexFactory).

Toutes les heures internes sont en heure de New York (référence ICT/MMM) ; l'affichage est en heure de Paris.

## Comment la décision est construite

1. **Bougies clôturées uniquement** : la dernière barre est supposée en formation (règle Max).
2. **Score de confluence** (-100 à +100) : bougies MMM D/4H/1H/15m/5m, structure CDL/CDS par TF, mur du momentum,
   Prime/Décote (ouverture de minuit + dealing range), sweep X/X+/X++ de PDH/PDL/Asie qualifié par le volume,
   zones OB/breaker/UDG proches, intermarché, SMT, poids lourds, ton des news (poids faible).
3. **Checklist 5/5** (Masterclass module 8) : structure HTF, localisation, zone, bougie LTF, volume. 4/5 ne suffit pas.
4. **Note** : A+ exige 5/5, un timing non rouge et ≥ 2 clôtures de corps alignées sur D/4H/1H/15m ; zone morte,
   Judas de Londres ou publication imminente → NO TRADE.
5. **Probabilités** : confluence pondérée par horizon ⊕ modèle walk-forward (régression logistique + gradient boosting,
   TimeSeriesSplit avec écart = horizon). La probabilité ML est **rétrécie vers 50 %** selon sa compétence hors
   échantillon (AUC) : un modèle sans compétence n'influence pas le résultat.
6. **Plan MNQ** : entrée à la clôture de la BC+ (ou limite sur la zone / OTE), stop 1 tick au-delà de la mèche,
   C1 = extrême de la bougie (≥ 1 R), C2 = prochaine liquidité ; taille = min(1 % du compte, 10 % du buffer Apex, plafond de contrats).

## Paramètres à vérifier

* Les règles Apex (drawdown suiveur, nombre de contrats) sont des **valeurs par défaut modifiables** dans la barre
  latérale et dans `core/config.py` : vérifiez-les sur le site d'Apex, elles changent.
* Les statistiques MMM viennent du rapport de backtest de l'auteur (ES/NQ, mai 2019 - janv. 2026). La page Bougies MMM
  les compare à ce que donnent vos propres données.

## Structure

```
app.py                 navigation (titres + icônes des pages)
views/0_cockpit.py     Cockpit
views/                 pages Streamlit (noms ASCII ; dossier « views » et non « pages » pour que la navigation st.navigation reste prioritaire)
core/config.py         paramètres, tables MMM, killzones, partenaires, flux
core/data.py           Yahoo / CSV / démo, rééchantillonnage, H4 aligné UTC
core/candles.py        moteur MMM (MMMFCB, PCX, momentum, sweeps, backtest)
core/structure.py      swings MMM, CDL/CDS, OB/breakers, gaps, dealing range, liquidité
core/levels.py         niveaux de séance + statistiques Asie/PDH/extrêmes
core/timing.py         sessions, killzones, feux MMM, profils horaires
core/intermarket.py    SMT, partenaires, poids lourds
core/news.py           RSS, ton, calendrier, risque d'événement
core/forecast.py       features + modèles walk-forward multi-horizon
core/confluence.py     moteur de décision, plan, commentaire
core/risk.py           Apex, taille de position, espérance
core/ui.py, charts.py  thème HTML/CSS et graphiques Plotly
tests/smoke_test.py    test de bout en bout en mode démo
```

## Sources

Max Maserati Model : résultats de backtesting (17 758 configurations) · MMM Trading Masterclass (8 modules) ·
Stratégie de trade Warren (ESLSCA) · Leversens Trading : Plan de séance et Labo ICT.
