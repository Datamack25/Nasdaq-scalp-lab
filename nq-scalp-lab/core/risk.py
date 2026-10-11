"""Gestion du risque Apex / MNQ : taille de position, buffer de drawdown, règles MMM & Warren."""
from __future__ import annotations

import math

from .config import MMM_RISK, MNQ_POINT_VALUE


def dd_buffer(balance: float, peak: float, start: float, trailing_dd: float) -> dict:
    """Drawdown suiveur Apex (sur le plus haut atteint, se bloque à départ + 100 $)."""
    threshold = min(peak - trailing_dd, start + 100)
    buffer = balance - threshold
    return {"threshold": threshold, "buffer": buffer, "locked": peak - trailing_dd >= start + 100,
            "pct_used": 100 * (1 - buffer / trailing_dd) if trailing_dd else 0}


def position_size(stop_pts: float, balance: float, buffer: float, max_contracts: int,
                  risk_pct: float = MMM_RISK["risk_per_trade_pct"], buffer_frac: float = 0.10,
                  losses_in_row: int = 0, news_day: bool = False) -> dict:
    """Nombre de MNQ : min(règle MMM % du compte, fraction du buffer de DD, plafond Apex)."""
    notes = []
    if losses_in_row >= 3:
        risk_pct = min(risk_pct, MMM_RISK["after_3_losses_pct"]); notes.append("3 pertes d'affilée → risque réduit à 0,5 % (MMM)")
    if news_day:
        risk_pct = min(risk_pct, MMM_RISK["news_day_pct"]); notes.append("Jour d'annonce majeure → 0,5 % (MMM)")
    risk_mmm = balance * risk_pct / 100
    risk_buf = max(buffer, 0) * buffer_frac
    risk_usd = min(risk_mmm, risk_buf)
    if risk_buf < risk_mmm:
        notes.append(f"Plafonné par le buffer de drawdown ({buffer_frac:.0%} de {buffer:,.0f} $)")
    per_contract = max(stop_pts, 0.25) * MNQ_POINT_VALUE
    n = max(0, min(max_contracts, math.floor(risk_usd / per_contract)))
    if n == 0:
        notes.append("Stop trop large pour le risque autorisé : réduire le stop ou passer le trade")
    return {"contracts": n, "risk_usd": n * per_contract, "risk_budget": risk_usd,
            "per_contract": per_contract, "risk_pct_eff": risk_pct, "notes": notes}


def trade_plan(direction: int, entry: float, stop: float, target: float, contracts: int) -> dict:
    risk = abs(entry - stop)
    reward = abs(target - entry)
    rr = reward / risk if risk else float("nan")
    return {"risk_pts": risk, "reward_pts": reward, "rr": rr,
            "risk_usd": risk * MNQ_POINT_VALUE * contracts,
            "reward_usd": reward * MNQ_POINT_VALUE * contracts,
            "tp1": entry + direction * risk,                # Warren : partiel à 1 R
            "be_after": entry + direction * risk * 0.5}


def expectancy(win: float, rr: float = 1.0, both: float = 0.0) -> float:
    """Espérance en R (les « deux atteints » comptent 0)."""
    loss = 1 - win - both
    return win * rr - loss


PROP_RULES = [
    ("Taille", "Ne jamais dépasser 2 % du compte ni ~10-15 % du buffer de drawdown restant par trade."),
    ("Perte du jour", "Coupe la journée à 3 % (MMM) – sur Apex, bien avant le seuil de liquidation."),
    ("Série", "Après 3 pertes : risque divisé par 2 ; après 5 gains : retour à la normale (MMM)."),
    ("Annonces", "CPI, NFP, FOMC : pas de position ouverte 2 min avant la publication ; 0,5 % le jour même."),
    ("Mur du momentum", "Sortir 75 % après 4 bougies de construction haussières, 100 % après 3 baissières."),
    ("2 barres", "Objectif non atteint en 2 barres → sortie (backtest MMM)."),
    ("Partiel", "Warren : 0,5 % encaissé à 1 R, stop à breakeven sur le reste."),
    ("Une session", "Maîtriser UNE session (Londres ou Fenêtre d'Or NY) pendant 3 mois / 100 trades."),
    ("Zone morte", "Aucune entrée 11h30-13h30 NY (17h30-19h30 Paris)."),
    ("Pas de vengeance", "Le stop touché est un coût normal (15-22 % des trades). On ne double pas."),
]
