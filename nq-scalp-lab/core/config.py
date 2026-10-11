"""Configuration centrale de NQ Scalp Lab.

Toutes les heures internes sont en America/New_York (heure de référence ICT / MMM).
L'affichage est doublé en heure de Paris.
"""
from __future__ import annotations

NY_TZ = "America/New_York"
PARIS_TZ = "Europe/Paris"
UTC_TZ = "UTC"

# ---------------------------------------------------------------- instruments
MAIN_TICKER = "NQ=F"          # Nasdaq-100 E-mini (prix identique au MNQ)
MNQ_POINT_VALUE = 2.0          # $ par point pour 1 MNQ
NQ_POINT_VALUE = 20.0          # $ par point pour 1 NQ
TICK_SIZE = 0.25

# Les « partenaires » ICT : marchés corrélés utilisés pour la divergence SMT
# et le contexte intermarché (ICT : ES/YM pour SMT, DXY & taux en inverse, VIX).
PARTNERS = {
    "ES=F": {"nom": "S&P 500 E-mini (ES)", "role": "SMT – partenaire principal", "relation": +1},
    "YM=F": {"nom": "Dow Jones E-mini (YM)", "role": "SMT – triade indices", "relation": +1},
    "RTY=F": {"nom": "Russell 2000 E-mini (RTY)", "role": "Appétit pour le risque", "relation": +1},
    "DX-Y.NYB": {"nom": "Dollar Index (DXY)", "role": "Corrélation inverse ICT", "relation": -1},
    "^TNX": {"nom": "Taux US 10 ans", "role": "Taux – pression sur la tech", "relation": -1},
    "^VIX": {"nom": "VIX", "role": "Peur / régime de volatilité", "relation": -1},
    "^VXN": {"nom": "VXN (vol. Nasdaq-100)", "role": "Range implicite NQ", "relation": -1},
    "GC=F": {"nom": "Or (GC)", "role": "Valeur refuge", "relation": 0},
}

# Les poids lourds du Nasdaq-100 (≈ 45-50 % de l'indice) : breadth « Mag 7 + »
HEAVYWEIGHTS = ["NVDA", "MSFT", "AAPL", "AMZN", "META", "GOOGL", "AVGO", "TSLA"]

# --------------------------------------------------------------- sessions (NY)
# (début, fin) en heures décimales NY. Source : Masterclass MMM module 3 + Leversens.
SESSIONS = {
    "Asie": (18.0, 26.0),          # 18h-2h (traverse minuit)
    "Londres": (2.0, 8.0),
    "New York": (8.0, 17.0),
}
KILLZONES = [
    # nom, début NY, fin NY, rôle, couleur
    ("Killzone Asie", 19.0, 22.0, "Accumulation – boîte asiatique", "#5b6c8f"),
    ("Francfort", 2.0, 2.5, "Balayage pré-Londres des extrêmes asiatiques", "#7a6c9c"),
    ("Judas Londres", 2.5, 3.0, "Manipulation – NE PAS ENTRER", "#b45a5a"),
    ("Killzone Londres", 2.0, 5.0, "Vraie origine de tendance (3h-4h)", "#3f7cac"),
    ("Silver Bullet Londres", 3.0, 4.0, "Fenêtre FVG", "#2f9e8f"),
    ("Killzone ouverture NY", 7.0, 9.0, "Pré-ouverture, stats 8h30", "#c08a2d"),
    ("Fenêtre d'Or NY", 8.0, 11.5, "FENÊTRE PRINCIPALE MMM", "#d4a72c"),
    ("IB NY", 9.5, 10.5, "Initial Balance – attendre 15 min", "#e07b39"),
    ("Silver Bullet AM", 10.0, 11.0, "Fenêtre FVG", "#2f9e8f"),
    ("Sweet Spot NY", 10.5, 11.5, "Cassure-retest de l'IB", "#4caf50"),
    ("Zone morte", 11.5, 13.5, "Déjeuner – NE PAS TRADER", "#8a8a8a"),
    ("Silver Bullet PM", 14.0, 15.0, "Fenêtre FVG", "#2f9e8f"),
    ("Dernière heure", 15.0, 16.0, "Rééquilibrage de clôture", "#9c6ade"),
]

# ------------------------------------------------- statistiques MMM (backtest)
# Max Maserati Model, 17 758 configurations, mai 2019 - janv. 2026 (ES/NQ).
MMM_GLOBAL = {
    "BuBC": {"win": 72.1, "n": 11317, "note": "A+", "bars": 1.2},
    "BeBC": {"win": 67.5, "n": 6441, "note": "A", "bars": 1.3},
    "BuAF": {"win": 61.6, "n": 2698, "note": "B+", "bars": 1.1},
    "BeAF": {"win": 58.9, "n": 2920, "note": "B", "bars": 1.2},
}
MMM_BY_TF = {  # taux de réussite par horizon
    "1d": {"BuBC": 75.1, "BeBC": 65.9, "BuAF": 63.1, "BeAF": 59.3},
    "4h": {"BuBC": 69.3, "BeBC": 64.3, "BuAF": 58.7, "BeAF": 60.8},
    "1h": {"BuBC": 72.3, "BeBC": 69.3, "BuAF": 62.6, "BeAF": 58.5},
    "15m": {"BuBC": 71.8, "BeBC": 70.3, "BuAF": 61.9, "BeAF": 57.6},
}
# Jour de trading (jour qui suit la clôture daily) -> win %
MMM_DAY = {
    "BuBC": {"Lundi": 65.4, "Mardi": 71.1, "Mercredi": 69.8, "Jeudi": 74.9, "Vendredi": 76.2},
    "BeBC": {"Lundi": 65.6, "Mardi": 46.0, "Mercredi": 58.9, "Jeudi": 57.1, "Vendredi": 68.9},
}
# H4 : heure UTC d'ouverture de la bougie signal -> (BuBC, BeBC, feu)
MMM_H4_UTC = {
    2: (78.1, 68.3, "vert"), 6: (78.0, 69.5, "vert"), 10: (68.2, 70.7, "vert"),
    22: (64.9, 55.9, "orange"), 18: (58.2, 41.6, "orange"), 14: (55.1, 52.2, "rouge"),
}
# H1 : heure UTC d'ouverture de la bougie signal -> (BuBC, BeBC)
MMM_H1_UTC = {
    9: (80.4, 68.6), 8: (79.1, 67.5), 11: (78.0, 76.2), 4: (76.3, 69.5), 2: (74.1, 74.1),
    18: (76.2, 64.4), 20: (75.6, 72.0), 10: (75.2, 70.8), 3: (72.9, 74.6), 0: (74.2, 71.4),
    1: (None, 67.7), 5: (58.5, None), 6: (59.7, None), 15: (65.3, 56.4),
}
# M15 : fenêtres UTC à éviter
MMM_M15_AVOID_UTC = [(15, 16), (0, 1), (5, 6)]
MMM_M15_BEST_UTC = {"long": (9.25, 9.5, 79), "short": (12.25, 12.5, 76)}
# Alignement multi-TF -> probabilité (tempête parfaite)
MMM_ALIGNMENT = {1: (69, 78), 2: (75, 80), 3: (80, 85), 4: (85, 90)}

# ----------------------------------------------------------- règles de risque
MMM_RISK = {
    "risk_per_trade_pct": 1.0, "max_risk_pct": 2.0, "daily_loss_pct": 3.0,
    "weekly_loss_pct": 8.0, "after_3_losses_pct": 0.5, "news_day_pct": 0.5,
    "bull_wall_count": 4, "bear_wall_count": 3,
}

# Apex Trader Funding – valeurs PAR DÉFAUT, modifiables dans l'app.
# Les règles Apex évoluent : vérifier sur apextraderfunding.com avant usage.
APEX_ACCOUNTS = {
    "25K": {"balance": 25000, "trailing_dd": 1500, "max_contracts_mnq": 40},
    "50K": {"balance": 50000, "trailing_dd": 2500, "max_contracts_mnq": 100},
    "75K": {"balance": 75000, "trailing_dd": 2750, "max_contracts_mnq": 120},
    "100K": {"balance": 100000, "trailing_dd": 3000, "max_contracts_mnq": 140},
    "150K": {"balance": 150000, "trailing_dd": 5000, "max_contracts_mnq": 170},
    "250K": {"balance": 250000, "trailing_dd": 6500, "max_contracts_mnq": 270},
    "300K": {"balance": 300000, "trailing_dd": 7500, "max_contracts_mnq": 350},
}

# --------------------------------------------------------- horizons de prévision
# horizon (min) -> (intervalle de base, nb de barres en avant)
FORECAST_HORIZONS = {
    1: ("1m", 1), 3: ("1m", 3), 5: ("5m", 1), 15: ("5m", 3), 60: ("15m", 4), 240: ("1h", 4),
}

# ------------------------------------------------------- flux d'actualités (RSS)
NEWS_FEEDS = {
    "Réserve fédérale (Fed)": "https://www.federalreserve.gov/feeds/press_all.xml",
    "Fed – discours": "https://www.federalreserve.gov/feeds/speeches.xml",
    "BCE": "https://www.ecb.europa.eu/rss/press.html",
    "Banque du Japon (via Google News)": "https://news.google.com/rss/search?q=Bank+of+Japan+rate&hl=en-US&gl=US&ceid=US:en",
    "Nasdaq / marchés": "https://news.google.com/rss/search?q=Nasdaq+futures&hl=en-US&gl=US&ceid=US:en",
    "Fed / Powell": "https://news.google.com/rss/search?q=Powell+OR+FOMC+OR+%22Federal+Reserve%22&hl=en-US&gl=US&ceid=US:en",
    "Politique US / tarifs": "https://news.google.com/rss/search?q=Trump+tariffs+OR+White+House+economy&hl=en-US&gl=US&ceid=US:en",
    "Géopolitique": "https://news.google.com/rss/search?q=geopolitical+markets+risk&hl=en-US&gl=US&ceid=US:en",
    "CNBC Markets": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
}
CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Réaction médiane historique NQ aux publications (Leversens Labo ICT, pts, 1 h)
MACRO_REACTION = {
    "CPI": (122, 86), "NFP": (134, 86), "Non-Farm": (134, 86), "PPI": (69, 86),
    "JOLTS": (130, 81), "GDP": (124, 86), "PCE": (112, 86), "Retail Sales": (89, 86),
    "FOMC": (159, 36), "Federal Funds Rate": (159, 36), "Powell": (120, 36),
}

# Statistiques descriptives de référence (Leversens, NQ) affichées pour comparaison
LEVERSENS_REF = {
    "fvg5_full_5bars": 55, "fvg1h_full_5bars": 52, "ny_high_share": 71, "ny_low_share": 60,
    "cash_extreme_first30": 67, "asia_other_side_ny": 55,
    "pdh_taken_ny": 30, "pdl_taken_ny": 22,
}
