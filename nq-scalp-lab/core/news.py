"""Actualités & conditions de marché.

Sources :
  * Flux RSS : Fed, BCE, Google News (BoJ, Powell/FOMC, Maison-Blanche, géopolitique), CNBC.
  * FinancialJuice : flux RSS public (feed.ashx) et, si le site bloque l'accès automatique,
    COPIER-COLLER de la page financialjuice.com/home (calendrier + titres), analysé ici.
  * ForexFactory : calendrier de la semaine en cours et de la semaine suivante (JSON public).
  * FRED (Réserve fédérale de Saint-Louis) : taux, taux réels, courbe, spreads de crédit,
    conditions financières, liquidité nette de la Fed, dollar, VIX, inscriptions au chômage.

Le score de news est un RÉSUMÉ du ton des titres, pas un signal prédictif. Le régime FRED
décrit le vent de fond (taux, crédit, liquidité) ; il pèse sur les horizons longs.
"""
from __future__ import annotations

import io
import os
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import CALENDAR_URL, MACRO_REACTION, NEWS_FEEDS, NY_TZ, PARIS_TZ

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 NQScalpLab"}

FINANCIALJUICE_RSS = ["https://www.financialjuice.com/feed.ashx?xy=rss",
                      "https://www.financialjuice.com/feed.ashx"]
CALENDAR_NEXT_URL = "https://nfs.faireconomy.media/ff_calendar_nextweek.json"

LEXICON = {
    # mot-clé (regex, minuscules) : score pour le Nasdaq
    r"rate cut|cuts? rates|dovish|easing|lower rates|pause hikes|baisse des taux": 1.0,
    r"rate hike|raise rates|rate increase|interest-rate increases|hawkish|tighten|higher for longer|hausse des taux": -1.0,
    r"hot inflation|inflation (rose|accelerat|surg)|cpi (beat|hotter)|sticky inflation|higher than expected": -1.0,
    r"inflation (cool|eas|slow)|disinflation|cpi (miss|cooler)|lower than expected": 1.0,
    r"tariff|trade war|sanction|export control|ban on chips|embargo|safeguard measures": -0.8,
    r"trade deal|truce|ceasefire|agreement reached|consensus|tariff (pause|relief|exemption)": 0.8,
    r"\bwar\b|missile|attack|strikes? (on|by)|houthi|escalat|invasion|tensions": -0.8,
    r"shutdown|default|downgrade|debt ceiling": -0.6,
    r"recession|layoffs|job cuts|unemployment (rose|jump)": -0.5,
    r"record high|all-time high|rall(y|ies)|rebound|advance[sd]?|surge|soar|beats? (estimates|expectations)": 0.6,
    r"sell-?off|plunge|tumble|slump|rout|misses? (estimates|expectations)|ai concerns": -0.6,
    r"\bai\b demand|nvidia (beat|record)|strong guidance|buyback|concerns ease": 0.5,
    r"stimulus|liquidity injection|qe\b|balance sheet expansion": 0.7,
    r"quantitative tightening|\bqt\b|balance sheet runoff": -0.4,
    r"oil (retreat|fall|declin|drop|slide)|brent (declin|fell|drop)|crude (fell|declin|drop)": 0.4,
    r"oil (surge|jump|spike|soar|rall)|brent (rose|jump|surge)|crude (rose|jump|surge)": -0.5,
    r"yields? (rise|rose|jump|climb|surge)": -0.5,
    r"yields? (fall|fell|drop|declin|ease)": 0.5,
}

CB_PAT = re.compile(r"fed|fomc|powell|warsh|federal reserve|ecb|lagarde|boj|ueda|bank of japan|boe|bailey|pboc|snb|rba|boc", re.I)
POL_PAT = re.compile(r"trump|white house|congress|senate|tariff|election|treasury|bessent|xi jinping|china|eu said|kremlin", re.I)
GEO_PAT = re.compile(r"war|missile|attack|strike|houthi|iran|israel|russia|ukraine|saudi|taiwan|middle east|ceasefire", re.I)


def score_text(text: str) -> float:
    t = text.lower()
    s = 0.0
    for pat, w in LEXICON.items():
        if re.search(pat, t):
            s += w
    return float(np.clip(s, -2, 2))


def _categorise(df: pd.DataFrame) -> pd.DataFrame:
    txt = df["titre"].fillna("") + " " + df["résumé"].fillna("")
    df["catégorie"] = np.where(txt.str.contains(CB_PAT), "Banque centrale",
                               np.where(txt.str.contains(GEO_PAT), "Géopolitique",
                                        np.where(txt.str.contains(POL_PAT), "Politique", "Marché")))
    df["score"] = [score_text(t) for t in txt]
    return df


# ===================================================================== RSS
def _parse_feed(content, src: str, per_feed: int) -> list[dict]:
    import feedparser
    f = feedparser.parse(content)
    rows = []
    for e in f.entries[:per_feed]:
        title = re.sub(r"<[^>]+>", "", e.get("title", "")).strip()
        summ = re.sub(r"<[^>]+>", "", e.get("summary", ""))[:400]
        t = e.get("published_parsed") or e.get("updated_parsed")
        ts = pd.Timestamp(datetime(*t[:6], tzinfo=timezone.utc)) if t else pd.NaT
        rows.append({"source": src, "titre": title, "résumé": summ, "lien": e.get("link", ""), "date": ts})
    return rows


def fetch_feeds(feeds: dict | None = None, per_feed: int = 15) -> pd.DataFrame:
    try:
        import feedparser  # noqa: F401
    except ImportError:
        return pd.DataFrame()
    rows = []
    for src, url in (feeds or NEWS_FEEDS).items():
        try:
            rows += _parse_feed(url, src, per_feed)
        except Exception:
            continue
    rows += fetch_financialjuice_rss()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df[df["titre"].str.len() > 0].drop_duplicates("titre")
    return _categorise(df).sort_values("date", ascending=False)


def fetch_financialjuice_rss(per_feed: int = 60) -> list[dict]:
    """Flux RSS public de FinancialJuice (titres de marché en continu, souvent différés
    pour les comptes gratuits). Retourne [] si le site refuse l'accès automatique."""
    try:
        import requests
    except ImportError:
        return []
    for url in FINANCIALJUICE_RSS:
        try:
            r = requests.get(url, headers=UA, timeout=8)
            if r.ok and b"<item" in r.content[:200000]:
                rows = _parse_feed(r.content, "FinancialJuice", per_feed)
                for x in rows:   # les titres FJ commencent souvent par « FinancialJuice: »
                    x["titre"] = re.sub(r"^FinancialJuice:\s*", "", x["titre"])
                return rows
        except Exception:
            continue
    return []


# ========================================================== FinancialJuice (collé)
_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                       "august", "september", "october", "november", "december"], 1)}
_MON3 = {k[:3]: v for k, v in _MONTHS.items()}
_TOKEN = re.compile(r"-?\d[\d,]*\.?\d*[%KMBTkmb]?|-")
HIGH_PAT = re.compile(r"\bCPI\b|\bPPI\b|Retail Sales|Non-Farm|\bNFP\b|Payrolls|FOMC|Fed Interest Rate|"
                      r"Fed's Chair|Powell|Warsh|\bGDP\b|\bPCE\b|\bISM\b|Jobless Claims|Unemployment Rate", re.I)
MED_PAT = re.compile(r"Fed's|JOLTS|Philly Fed|NY Fed|Industrial Production|Consumer Sentiment|"
                     r"Existing Home|New Home|Durable|NVIDIA|Microsoft|Apple|Amazon|Alphabet|Meta|Tesla|Broadcom|"
                     r"Lagarde|ECB|BoJ|Earnings", re.I)


def _split_values(raw: str) -> tuple[str, str, str]:
    """Ligne de valeurs FJ « actuel prévision précédent » collées sans séparateur
    (ex. ' -3.3%3.3%' = actuel vide, prévision 3,3 %, précédent 3,3 %). Un « - » suivi
    d'un caractère non numérique (ou en fin de ligne) est une case vide."""
    s = raw.strip()
    num = re.compile(r"-?\d[\d,]*\.?\d*[%KMBTkmb]?")
    out = []
    while s and len(out) < 3:
        if s[0] == "-" and (len(s) == 1 or not s[1].isdigit()):
            out.append("-"); s = s[1:]
            continue
        if len(out) == 0 and s[0] == "-":          # 1re case : « - » = actuel vide…
            rest = [t for t in _TOKEN.findall(s[1:]) if t != "-"]
            if len(rest) < 3:                       # …sauf si 3 valeurs suivent (actuel négatif)
                out.append("-"); s = s[1:]
                continue
        m = num.match(s)
        if not m:
            break
        out.append(m.group()); s = s[m.end():]
    short = len(out) == 2                          # une seule valeur après l'actuel = précédent
    while len(out) < 3:
        out.append("-")
    a, f, p = out
    if short and f != "-":
        f, p = "-", f
    return a, f, p


def _to_float(s: str) -> float:
    try:
        m = re.match(r"-?[\d,]*\.?\d+", s.replace(",", ""))
        return float(m.group()) if m else np.nan
    except Exception:
        return np.nan


def parse_financialjuice_paste(text: str, year: int | None = None, tz: str = PARIS_TZ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Analyse le texte copié depuis financialjuice.com/home (Ctrl+A, Ctrl+C).
    Retourne (calendrier, titres). Les heures affichées par FJ sont celles de votre
    navigateur (Paris par défaut)."""
    if not text or not text.strip():
        return pd.DataFrame(), pd.DataFrame()
    year = year or pd.Timestamp.now(tz=tz).year
    lines = [l.rstrip("\n") for l in text.splitlines()]
    cal, heads = [], []
    day = None
    buf: list[str] = []
    i = 0
    date_hdr = re.compile(r"^\s*(" + "|".join(m.title() for m in _MONTHS) + r")\s+(\d{1,2})\s*$")
    ev_line = re.compile(r"^(\d{2}):(\d{2})(\S.*)$")                    # « 08:00German CPI… »
    head_ts = re.compile(r"^(?:\d+:)?(\d{2}):(\d{2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2})(.*)$")
    while i < len(lines):
        ln = lines[i]
        m = date_hdr.match(ln)
        if m:
            day = (_MONTHS[m.group(1).lower()], int(m.group(2)))
            i += 1
            continue
        m = ev_line.match(ln)
        if m and day:
            title = m.group(3).strip()
            act = fc = prev = "-"
            if i + 1 < len(lines) and lines[i + 1].startswith(" ") and _TOKEN.search(lines[i + 1] or ""):
                act, fc, prev = _split_values(lines[i + 1])
                i += 1
            ts = pd.Timestamp(year, day[0], day[1], int(m.group(1)), int(m.group(2)), tz=tz)
            cal.append({"date": ts.tz_convert(NY_TZ), "title": title, "actual": act, "forecast": fc, "previous": prev})
            i += 1
            continue
        m = head_ts.match(ln.strip())
        if m:
            mon, d = _MON3[m.group(3).lower()], int(m.group(4))
            ts = pd.Timestamp(year, mon, d, int(m.group(1)), int(m.group(2)), tz=tz)
            body = [b for b in buf if len(b) > 25]
            if body:
                heads.append({"source": "FinancialJuice (collé)", "titre": body[0][:220],
                              "résumé": " ".join(body[1:])[:600], "lien": "https://www.financialjuice.com/home",
                              "date": ts.tz_convert("UTC"), "tags": m.group(5).strip()})
            buf = []
            i += 1
            continue
        s = ln.strip()
        if s and not ev_line.match(s):
            buf.append(s)
            buf = buf[-8:]
        i += 1
    cdf = pd.DataFrame(cal)
    if not cdf.empty:
        cdf["country"] = np.where(cdf["title"].str.match(r"^(US |Fed|FOMC)") | cdf["title"].str.contains(r"Fed's|Warsh|Powell"),
                                  "USD", "AUTRE")
        cdf["impact"] = np.where(cdf["title"].str.contains(HIGH_PAT) & (cdf["country"] == "USD"), "High",
                                 np.where(cdf["title"].str.contains(MED_PAT), "Medium", "Low"))
        a, f = cdf["actual"].map(_to_float), cdf["forecast"].map(_to_float)
        cdf["surprise"] = np.where(a.notna() & f.notna(), a - f, np.nan)
        cdf["réaction_hist"] = cdf["title"].map(_reaction)
        cdf["source"] = "FinancialJuice"
    hdf = pd.DataFrame(heads)
    if not hdf.empty:
        hdf = _categorise(hdf.drop_duplicates("titre"))
    return cdf, hdf


# ================================================================ ForexFactory
def fetch_calendar(url: str = CALENDAR_URL) -> pd.DataFrame:
    """Calendrier ForexFactory : semaine en cours + semaine suivante (si publiée)."""
    try:
        import requests
    except ImportError:
        return pd.DataFrame()
    frames = []
    for u in (url, CALENDAR_NEXT_URL):
        try:
            r = requests.get(u, timeout=8, headers=UA)
            r.raise_for_status()
            frames.append(pd.DataFrame(r.json()))
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(NY_TZ)
    df = df[df["country"].isin(["USD", "EUR", "JPY", "CNY", "GBP"])]
    df = df[df["impact"].isin(["High", "Medium"])]
    df["réaction_hist"] = df["title"].map(_reaction)
    df["source"] = "ForexFactory"
    for c in ("actual",):
        if c not in df:
            df[c] = ""
    return df.drop_duplicates(["date", "title"]).sort_values("date")[
        ["date", "country", "title", "impact", "actual", "forecast", "previous", "réaction_hist", "source"]]


def merge_calendars(ff: pd.DataFrame, fj: pd.DataFrame) -> pd.DataFrame:
    """Fusionne ForexFactory et FinancialJuice (FJ apporte les valeurs publiées et les
    discours ; doublons supprimés à ±15 min sur un titre proche)."""
    frames = [f for f in (ff, fj) if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True, sort=False)
    df["key"] = df["title"].str.lower().str.replace(r"[^a-z]", "", regex=True).str[:14]
    df["slot"] = df["date"].dt.floor("15min")
    df = df.sort_values("source", ascending=False).drop_duplicates(["slot", "key"])  # FJ prioritaire
    return df.drop(columns=["key", "slot"]).sort_values("date")


def _reaction(title: str) -> str:
    for k, (pub, ordi) in MACRO_REACTION.items():
        if k.lower() in str(title).lower():
            return f"{pub} pts/1h (jour ordinaire {ordi})"
    return ""


# ===================================================================== FRED
FRED_SERIES = {
    "DGS10": "Taux US 10 ans (%)",
    "DGS2": "Taux US 2 ans (%)",
    "DFII10": "Taux réel 10 ans (TIPS, %)",
    "T10Y2Y": "Pente 10 ans - 2 ans (pts)",
    "T10YIE": "Point mort d'inflation 10 ans (%)",
    "BAMLH0A0HYM2": "Spread high yield (OAS, %)",
    "NFCI": "Conditions financières (NFCI Chicago Fed)",
    "WALCL": "Bilan de la Fed (M$)",
    "WTREGEN": "Compte du Trésor TGA (M$)",
    "RRPONTSYD": "Reverse repo ON (Md$)",
    "DTWEXBGS": "Dollar large (indice)",
    "VIXCLS": "VIX (clôture)",
    "DFF": "Fed funds effectif (%)",
    "ICSA": "Inscriptions hebdo au chômage",
}


def fetch_fred(series=None, start: str | None = None) -> dict[str, pd.Series]:
    """Télécharge les séries FRED. Avec la variable FRED_API_KEY (ou st.secrets), utilise
    l'API officielle ; sinon le CSV public fredgraph (sans clé)."""
    try:
        import requests
    except ImportError:
        return {}
    start = start or (pd.Timestamp.today() - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    key = os.environ.get("FRED_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("FRED_API_KEY")
        except Exception:
            key = None
    out = {}
    for sid in (series or FRED_SERIES):
        try:
            if key:
                r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                                 params={"series_id": sid, "api_key": key, "file_type": "json",
                                         "observation_start": start}, timeout=10, headers=UA)
                r.raise_for_status()
                obs = pd.DataFrame(r.json()["observations"])
                s = pd.Series(pd.to_numeric(obs["value"], errors="coerce").values,
                              index=pd.to_datetime(obs["date"]), name=sid)
            else:
                r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv",
                                 params={"id": sid, "cosd": start}, timeout=10, headers=UA)
                r.raise_for_status()
                s = parse_fred_csv(r.text, sid)
            s = s.dropna()
            if len(s):
                out[sid] = s
        except Exception:
            continue
    return out


def parse_fred_csv(text: str, sid: str) -> pd.Series:
    df = pd.read_csv(io.StringIO(text))
    dcol = df.columns[0]
    vcol = sid if sid in df.columns else df.columns[1]
    return pd.Series(pd.to_numeric(df[vcol], errors="coerce").values, index=pd.to_datetime(df[dcol]), name=sid)


def _chg(s: pd.Series | None, days: int) -> float:
    if s is None or len(s) < 2:
        return np.nan
    ref = s[s.index <= s.index[-1] - pd.Timedelta(days=days)]
    return float(s.iloc[-1] - ref.iloc[-1]) if len(ref) else np.nan


def fred_regime(fred: dict[str, pd.Series]) -> dict:
    """Vent de fond macro pour le Nasdaq (score -1 … +1) à partir de FRED."""
    if not fred:
        return {"score": 0.0, "label": "indisponible", "rows": [], "notes": ["FRED indisponible (réseau)"]}
    rows, comps, notes = [], [], []

    def add(sid, val, chg, sc, why):
        rows.append({"Série": FRED_SERIES.get(sid, sid), "Code": sid, "Dernier": val, "Variation": chg,
                     "Effet NQ": sc, "Lecture": why, "Date": fred[sid].index[-1].strftime("%d/%m/%Y")})
        if not np.isnan(sc):
            comps.append(sc)

    last = {k: float(v.iloc[-1]) for k, v in fred.items()}
    if "DFII10" in fred:
        c = _chg(fred["DFII10"], 30)
        sc = float(np.tanh(-c / 0.25)) if not np.isnan(c) else np.nan
        add("DFII10", last["DFII10"], c, sc, "Taux réels en hausse = pression sur les valorisations tech" if c > 0 else "Taux réels en baisse = soutien à la tech")
    if "DGS10" in fred:
        c = _chg(fred["DGS10"], 7)
        sc = float(np.tanh(-c / 0.15)) if not np.isnan(c) else np.nan
        add("DGS10", last["DGS10"], c, sc, "10 ans en hausse sur 1 semaine" if c > 0 else "10 ans en baisse sur 1 semaine")
    if "DGS2" in fred:
        c = _chg(fred["DGS2"], 30)
        add("DGS2", last["DGS2"], c, float(np.tanh(-c / 0.3)) if not np.isnan(c) else np.nan,
            "Le marché price plus de hausses Fed" if c > 0 else "Le marché price moins de resserrement")
    if "T10Y2Y" in fred:
        add("T10Y2Y", last["T10Y2Y"], _chg(fred["T10Y2Y"], 30), np.nan,
            "Courbe inversée (signal récession)" if last["T10Y2Y"] < 0 else "Courbe positive")
    if "T10YIE" in fred:
        c = _chg(fred["T10YIE"], 30)
        add("T10YIE", last["T10YIE"], c, float(np.tanh(-c / 0.2)) if not np.isnan(c) else np.nan,
            "Anticipations d'inflation en hausse" if c > 0 else "Anticipations d'inflation stables/en baisse")
    if "BAMLH0A0HYM2" in fred:
        c = _chg(fred["BAMLH0A0HYM2"], 30)
        add("BAMLH0A0HYM2", last["BAMLH0A0HYM2"], c, float(np.tanh(-c / 0.4)) if not np.isnan(c) else np.nan,
            "Crédit qui se tend (risk-off)" if c > 0 else "Crédit détendu (risk-on)")
    if "NFCI" in fred:
        v = last["NFCI"]
        c = _chg(fred["NFCI"], 28)
        add("NFCI", v, c, float(np.tanh(-(v + 2 * (c if not np.isnan(c) else 0)) / 0.3)),
            "Conditions financières souples (< 0)" if v < 0 else "Conditions financières restrictives (> 0)")
    if all(k in fred for k in ("WALCL", "WTREGEN", "RRPONTSYD")):
        nl = (fred["WALCL"] / 1000).resample("W-WED").last().ffill() \
            - (fred["WTREGEN"] / 1000).resample("W-WED").last().ffill() \
            - fred["RRPONTSYD"].resample("W-WED").last().ffill()
        nl = nl.dropna()
        if len(nl) > 5:
            c = float(nl.iloc[-1] - nl.iloc[-5])
            sc = float(np.tanh(c / 150))
            rows.append({"Série": "Liquidité nette Fed (bilan - TGA - RRP, Md$)", "Code": "NETLIQ", "Dernier": float(nl.iloc[-1]),
                         "Variation": c, "Effet NQ": sc, "Date": nl.index[-1].strftime("%d/%m/%Y"),
                         "Lecture": "Liquidité injectée (soutien aux actifs risqués)" if c > 0 else "Liquidité drainée (vent contraire)"})
            comps.append(sc)
    if "DTWEXBGS" in fred:
        s = fred["DTWEXBGS"]
        c = _chg(s, 30) / s.iloc[-1] * 100
        add("DTWEXBGS", last["DTWEXBGS"], c, float(np.tanh(-c / 1.5)) if not np.isnan(c) else np.nan,
            "Dollar en hausse (resserrement des conditions)" if c > 0 else "Dollar en baisse (soutien)")
    if "VIXCLS" in fred:
        v = last["VIXCLS"]
        add("VIXCLS", v, _chg(fred["VIXCLS"], 7), float(np.tanh(-(v - 18) / 8)),
            "Volatilité élevée : réduire la taille" if v > 22 else "Volatilité contenue")
    if "DFF" in fred:
        add("DFF", last["DFF"], _chg(fred["DFF"], 90), np.nan, "Niveau directeur effectif")
    if "ICSA" in fred:
        s = fred["ICSA"]
        c = float(s.iloc[-4:].mean() - s.iloc[-8:-4].mean()) if len(s) >= 8 else np.nan
        add("ICSA", last["ICSA"], c, np.nan, "Marché du travail qui se dégrade" if c > 15000 else "Marché du travail stable")
    score = float(np.mean(comps)) if comps else 0.0
    label = "Vent porteur (risk-on)" if score > .2 else "Vent contraire (risk-off)" if score < -.2 else "Neutre / mitigé"
    neg = sorted([r for r in rows if not pd.isna(r["Effet NQ"])], key=lambda r: r["Effet NQ"])
    if neg and neg[0]["Effet NQ"] < -.4:
        notes.append(f"Principal vent contraire : {neg[0]['Série']} – {neg[0]['Lecture']}")
    if neg and neg[-1]["Effet NQ"] > .4:
        notes.append(f"Principal soutien : {neg[-1]['Série']} – {neg[-1]['Lecture']}")
    return {"score": score, "label": label, "rows": rows, "notes": notes}


# ============================================================ synthèse / reco
def news_bias(df: pd.DataFrame, now: pd.Timestamp | None = None, half_life_h: float = 6) -> dict:
    if df is None or df.empty:
        return {"score": 0.0, "label": "NEUTRE", "n": 0, "by_cat": {}, "by_src": {}}
    now = now or pd.Timestamp.now(tz="UTC")
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"], utc=True)
    age = (now.tz_convert("UTC") - d["date"]).dt.total_seconds() / 3600
    d["w"] = np.exp(-np.log(2) * age.clip(lower=0).fillna(48) / half_life_h)
    s = float((d["score"] * d["w"]).sum() / max(d["w"].sum(), 1e-9))
    lab = "HAUSSIER" if s > .25 else "BAISSIER" if s < -.25 else "NEUTRE"

    def agg(col):
        return {k: float((g["score"] * g["w"]).sum() / max(g["w"].sum(), 1e-9)) for k, g in d.groupby(col)}

    return {"score": s, "label": lab, "n": len(d), "by_cat": agg("catégorie"), "by_src": agg("source")}


def event_risk(cal: pd.DataFrame, now: pd.Timestamp) -> dict:
    """Risque d'événement : prochaine publication USD à fort impact."""
    if cal is None or cal.empty:
        return {"level": "inconnu", "msg": "Calendrier indisponible – vérifier ForexFactory / FinancialJuice"}
    hi = cal[(cal["impact"] == "High") & (cal["country"] == "USD")]
    nxt = hi[hi["date"] >= now - pd.Timedelta(minutes=5)]
    if nxt.empty:
        return {"level": "faible", "msg": "Aucune publication USD à fort impact à venir"}
    e = nxt.iloc[0]
    mins = (e["date"] - now).total_seconds() / 60
    same_day = e["date"].date() == now.tz_convert(NY_TZ).date()
    lvl = "critique" if -5 <= mins <= 15 else "élevé" if same_day else "modéré"
    paris = e["date"].tz_convert(PARIS_TZ).strftime("%a %d/%m %H:%M")
    return {"level": lvl, "minutes": mins, "event": e["title"], "time": e["date"],
            "msg": f"{e['title']} – {paris} Paris ({mins / 60:.1f} h)" if mins > 0 else f"{e['title']} vient de sortir",
            "same_day": same_day}


def market_conditions(nb: dict, fred_reg: dict, cal: pd.DataFrame, heads: pd.DataFrame,
                      now: pd.Timestamp) -> list[tuple[str, str]]:
    """Recommandations textuelles (niveau, texte) à partir des news, de FRED et du calendrier."""
    out: list[tuple[str, str]] = []
    fs = fred_reg.get("score", 0)
    if fred_reg.get("label") != "indisponible":
        lvl = "vert" if fs > .2 else "rouge" if fs < -.2 else "orange"
        out.append((lvl, f"Régime macro FRED : {fred_reg['label']} ({fs:+.2f}). "
                         + ("Privilégier les longs sur repli dans la Décote." if fs > .2 else
                            "Privilégier les shorts sur rejet en Prime, cibles courtes sur les longs." if fs < -.2 else
                            "Pas de vent dominant : laisser parler la structure intraday.")))
        out += [("orange", n) for n in fred_reg.get("notes", [])]
    s = nb.get("score", 0)
    if nb.get("n"):
        out.append(("vert" if s > .25 else "rouge" if s < -.25 else "orange",
                    f"Ton des actualités : {nb['label']} ({s:+.2f}, {nb['n']} titres). "
                    + ("Éviter de shorter contre un flux très favorable." if s > .25 else
                       "Éviter les longs agressifs contre un flux négatif." if s < -.25 else "Flux équilibré.")))
    geo = nb.get("by_cat", {}).get("Géopolitique")
    if geo is not None and geo < -.3:
        out.append(("rouge", "Tensions géopolitiques dans le flux : risque de gap et de spike pétrole → taille réduite, stops hors des pools évidents."))
    cb = nb.get("by_cat", {}).get("Banque centrale")
    if cb is not None and abs(cb) > .3:
        out.append(("rouge" if cb < 0 else "vert", f"Banques centrales : ton {'hawkish' if cb < 0 else 'dovish'} ({cb:+.2f})."))
    if heads is not None and not heads.empty:
        txt = " ".join(heads["titre"].head(40).str.lower())
        if re.search(r"brent|crude|oil", txt) and re.search(r"\$1[0-9]{2}|surge|jump|spike", txt):
            out.append(("orange", "Pétrole au-dessus de 100 $ ou en forte hausse dans les titres : risque inflation → taux → pression sur NQ."))
    if cal is not None and not cal.empty:
        now_ny = now.tz_convert(NY_TZ)
        today = cal[(cal["date"].dt.date == now_ny.date()) & (cal["impact"].isin(["High", "Medium"])) & (cal["country"] == "USD")]
        for _, e in today.head(6).iterrows():
            t = e["date"].tz_convert(PARIS_TZ).strftime("%H:%M")
            if e["impact"] == "High":
                out.append(("rouge", f"{t} Paris – {e['title']} : être à plat 2 min avant, laisser passer la 1re bougie 5 min."))
            else:
                out.append(("orange", f"{t} Paris – {e['title']} : volatilité possible, pas de nouvelle entrée juste avant."))
        sp = cal[cal.get("surprise", pd.Series(dtype=float)).notna()] if "surprise" in cal else pd.DataFrame()
        for _, e in sp.tail(4).iterrows():
            if e["country"] == "USD" and abs(e["surprise"]) > 0:
                infl = re.search(r"CPI|PPI|PCE|Price", e["title"], re.I)
                hot = e["surprise"] > 0
                eff = ("haussier pour les taux → négatif NQ" if hot else "baissier pour les taux → positif NQ") if infl else \
                      ("économie plus forte" if hot else "économie plus faible")
                out.append(("orange", f"Surprise {e['title']} : publié {e['actual']} vs prévu {e['forecast']} → {eff}."))
    return out
