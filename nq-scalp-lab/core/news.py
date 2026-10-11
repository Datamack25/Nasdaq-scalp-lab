"""Actualités : banques centrales, politique, géopolitique, calendrier macro.

Le score de news est un RÉSUMÉ du flux (lexique hawkish/dovish, risk-on/off),
pas un signal prédictif. Leversens a mesuré qu'un tel score ne bat pas le hasard
à 0-30 min : il sert de filtre de contexte et de risque, pas de déclencheur.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import CALENDAR_URL, MACRO_REACTION, NEWS_FEEDS, NY_TZ

LEXICON = {
    # mot-clé (regex, minuscules) : score pour le Nasdaq
    r"rate cut|cuts? rates|dovish|easing|lower rates|pause hikes|baisse des taux": 1.0,
    r"rate hike|raise rates|hawkish|tighten|higher for longer|hausse des taux": -1.0,
    r"hot inflation|inflation (rose|accelerat|surg)|cpi (beat|hotter)|sticky inflation": -1.0,
    r"inflation (cool|eas|slow)|disinflation|cpi (miss|cooler)": 1.0,
    r"tariff|trade war|sanction|export control|ban on chips|embargo": -0.8,
    r"trade deal|truce|ceasefire|agreement reached|tariff (pause|relief|exemption)": 0.8,
    r"war|missile|attack|escalat|invasion|strike on": -0.8,
    r"shutdown|default|downgrade|debt ceiling": -0.6,
    r"recession|layoffs|job cuts|unemployment (rose|jump)": -0.5,
    r"record high|all-time high|rall(y|ies)|surge|soar|beats? (estimates|expectations)": 0.6,
    r"sell-?off|plunge|tumble|slump|rout|misses? (estimates|expectations)": -0.6,
    r"\bai\b demand|nvidia (beat|record)|strong guidance|buyback": 0.5,
    r"stimulus|liquidity injection|qe\b|balance sheet expansion": 0.7,
    r"quantitative tightening|\bqt\b|balance sheet runoff": -0.4,
}

CB_PAT = re.compile(r"fed|fomc|powell|federal reserve|ecb|lagarde|boj|ueda|bank of japan|boe|bailey|pboc|snb", re.I)
POL_PAT = re.compile(r"trump|white house|congress|senate|tariff|election|treasury|bessent|biden|xi jinping|china", re.I)


def score_text(text: str) -> float:
    t = text.lower()
    s = 0.0
    for pat, w in LEXICON.items():
        if re.search(pat, t):
            s += w
    return float(np.clip(s, -2, 2))


def fetch_feeds(feeds: dict | None = None, per_feed: int = 15) -> pd.DataFrame:
    try:
        import feedparser
    except ImportError:
        return pd.DataFrame()
    rows = []
    for src, url in (feeds or NEWS_FEEDS).items():
        try:
            f = feedparser.parse(url)
        except Exception:
            continue
        for e in f.entries[:per_feed]:
            title = re.sub(r"<[^>]+>", "", e.get("title", ""))
            summ = re.sub(r"<[^>]+>", "", e.get("summary", ""))[:300]
            t = e.get("published_parsed") or e.get("updated_parsed")
            ts = pd.Timestamp(datetime(*t[:6], tzinfo=timezone.utc)) if t else pd.NaT
            rows.append({"source": src, "titre": title, "résumé": summ, "lien": e.get("link", ""),
                         "date": ts})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates("titre")
    df["score"] = [score_text(f"{a} {b}") for a, b in zip(df["titre"], df["résumé"])]
    df["catégorie"] = np.where(df["titre"].str.contains(CB_PAT), "Banque centrale",
                               np.where(df["titre"].str.contains(POL_PAT), "Politique", "Marché"))
    return df.sort_values("date", ascending=False)


def news_bias(df: pd.DataFrame, now: pd.Timestamp | None = None, half_life_h: float = 6) -> dict:
    if df is None or df.empty:
        return {"score": 0.0, "label": "NEUTRE", "n": 0}
    now = now or pd.Timestamp.now(tz="UTC")
    age = (now.tz_convert("UTC") - df["date"].dt.tz_convert("UTC")).dt.total_seconds() / 3600
    w = np.exp(-np.log(2) * age.clip(lower=0).fillna(48) / half_life_h)
    s = float((df["score"] * w).sum() / max(w.sum(), 1e-9))
    lab = "HAUSSIER" if s > .25 else "BAISSIER" if s < -.25 else "NEUTRE"
    by_cat = df.assign(w=w).groupby("catégorie").apply(
        lambda g: float((g["score"] * g["w"]).sum() / max(g["w"].sum(), 1e-9)), include_groups=False).to_dict()
    return {"score": s, "label": lab, "n": len(df), "by_cat": by_cat}


def fetch_calendar(url: str = CALENDAR_URL) -> pd.DataFrame:
    try:
        import requests
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0 NQScalpLab"})
        r.raise_for_status()
        js = r.json()
    except Exception:
        return pd.DataFrame()
    df = pd.DataFrame(js)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(NY_TZ)
    df = df[df["country"].isin(["USD", "EUR", "JPY", "CNY", "GBP"])]
    df = df[df["impact"].isin(["High", "Medium"])]
    df["réaction_hist"] = df["title"].map(_reaction)
    return df.sort_values("date")[["date", "country", "title", "impact", "forecast", "previous", "réaction_hist"]]


def _reaction(title: str) -> str:
    for k, (pub, ordi) in MACRO_REACTION.items():
        if k.lower() in str(title).lower():
            return f"{pub} pts/1h (jour ordinaire {ordi})"
    return ""


def event_risk(cal: pd.DataFrame, now: pd.Timestamp) -> dict:
    """Risque d'événement : prochaine publication USD à fort impact."""
    if cal is None or cal.empty:
        return {"level": "inconnu", "msg": "Calendrier indisponible – vérifier ForexFactory"}
    hi = cal[(cal["impact"] == "High") & (cal["country"] == "USD")]
    nxt = hi[hi["date"] >= now - pd.Timedelta(minutes=5)]
    if nxt.empty:
        return {"level": "faible", "msg": "Aucune publication USD à fort impact à venir cette semaine"}
    e = nxt.iloc[0]
    mins = (e["date"] - now).total_seconds() / 60
    same_day = e["date"].date() == now.tz_convert(NY_TZ).date()
    if -5 <= mins <= 15:
        lvl = "critique"
    elif same_day:
        lvl = "élevé"
    else:
        lvl = "modéré"
    return {"level": lvl, "minutes": mins, "event": e["title"], "time": e["date"],
            "msg": f"{e['title']} dans {mins / 60:.1f} h" if mins > 0 else f"{e['title']} vient de sortir",
            "same_day": same_day}
