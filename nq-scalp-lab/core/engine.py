"""Orchestration : charge toutes les données, exécute les moteurs, construit le contexte
et la décision. Indépendant de Streamlit (testable en script)."""
from __future__ import annotations

import pandas as pd

from . import candles, confluence, forecast, intermarket, levels, news, structure, timing
from .config import FORECAST_HORIZONS, HEAVYWEIGHTS, MAIN_TICKER, PARTNERS
from .data import get_data, to_h4


def load_market(csv_df: pd.DataFrame | None = None) -> dict:
    """Charge NQ multi-TF. Source cohérente : CSV/Yahoo ou DÉMO pour tout l'univers."""
    out = {}
    src = None
    for iv in ("1m", "5m", "15m", "1h", "1d"):
        md = get_data(MAIN_TICKER, iv, csv_df)
        out[iv] = md.df
        src = src or md.source
        if md.source == "demo":
            src = "demo"
    out["4h"] = to_h4(out["1h"])
    out["source"] = src
    return out


def load_partners(demo: bool, tickers=None, interval: str = "5m", period: str = "5d") -> dict:
    res = {}
    for tk in tickers or list(PARTNERS):
        md = get_data(tk, interval, allow_demo=demo, period=period)
        if md.source in ("yahoo", "demo"):
            res[tk] = md.df
    return res


def analyse(mk: dict, partners: dict, heavy: dict, news_df: pd.DataFrame, cal: pd.DataFrame,
            ml: dict | None = None, fred_reg: dict | None = None) -> tuple[dict, confluence.Decision]:
    tf = {k: candles.classify(mk[k].iloc[-600:]) for k in ("1d", "4h", "1h", "15m", "5m")}
    tf["1m"] = candles.classify(mk["1m"].iloc[-600:]) if not mk["1m"].empty else tf["5m"]
    price = float(mk["5m"]["Close"].iloc[-1])
    last_ts = mk["5m"].index[-1]

    struct, swings, events = {}, {}, {}
    for k in ("4h", "1h", "15m", "5m"):
        sw = structure.mmm_swings(tf[k])
        ev = structure.cdl_cds(tf[k], sw)
        swings[k], events[k] = sw, ev
        st_ = structure.active_structure(ev, price)
        st_["trend"] = structure.trend_from_swings(sw)
        struct[k] = st_

    vxn = partners.get("^VXN")
    vxn_last = float(vxn["Close"].iloc[-1]) if vxn is not None and not vxn.empty else None
    lv = levels.compute_levels(mk["5m"], mk["1d"], vxn_last)
    dealing = structure.dealing_range(swings["15m"], price)
    zones = structure.orderblocks(tf["15m"], events["15m"], swings["15m"]) + \
        structure.orderblocks(tf["5m"], events["5m"], swings["5m"]) + \
        [z for z in structure.gaps(tf["15m"], 200) if z.kind.startswith("UDG")] + \
        [z for z in structure.gaps(tf["5m"], 150) if z.kind.startswith("UDG")]
    pools = structure.liquidity_pools(mk["5m"], price)
    rng_info = structure.ranges_and_deviation(tf["15m"])

    closes = {tk: df["Close"] for tk, df in partners.items()}
    closes[MAIN_TICKER] = mk["5m"]["Close"].iloc[-1500:]
    snap = intermarket.partner_snapshot(closes)
    im_score, im_notes = intermarket.intermarket_score(snap, PARTNERS)
    smt = {"signal": 0, "label": "ES indisponible"}
    if "ES=F" in partners:
        smt = intermarket.smt_divergence(mk["5m"], partners["ES=F"])
    br = intermarket.breadth({tk: d["Close"] for tk, d in heavy.items()})

    nb = news.news_bias(news_df)
    ev_risk = news.event_risk(cal, last_ts)
    fred_reg = fred_reg or {"score": 0.0, "label": "indisponible", "rows": [], "notes": []}
    conditions = news.market_conditions(nb, fred_reg, cal, news_df, last_ts)
    atr15 = (mk["15m"]["High"] - mk["15m"]["Low"]).rolling(14).mean().iloc[-1]
    stale = (pd.Timestamp.now(tz=last_ts.tz) - last_ts).total_seconds() / 60

    ctx = {"tf": tf, "struct": struct, "swings": swings, "events": events, "price": price,
           "levels": lv, "dealing": dealing, "zones": zones, "pools": pools, "range": rng_info,
           "intermarket": {"score": im_score, "notes": im_notes, "snap": snap},
           "smt": smt, "breadth": br, "news": nb, "event": ev_risk,
           "fred": fred_reg, "conditions": conditions,
           "timing": timing.mmm_traffic(last_ts), "killzones": timing.active_killzones(last_ts),
           "session": timing.session_name(last_ts), "prox": float(max(10, 0.6 * atr15)),
           "ml": ml or {}, "demo": mk.get("source") == "demo", "stale_min": stale,
           "last_ts": last_ts, "source": mk.get("source")}
    dec = confluence.decide(ctx)
    return ctx, dec


def run_forecasts(mk: dict, partners: dict, horizons=None) -> dict:
    res = {}
    for h, (iv, bars) in (horizons or FORECAST_HORIZONS).items():
        df = mk.get(iv)
        if df is None or df.empty:
            res[h] = {"ok": False, "msg": "pas de données"}
            continue
        try:
            res[h] = forecast.forecast_horizon(df, bars, partners if iv != "1d" else None)
        except Exception as e:  # robustesse : un horizon en échec ne bloque pas les autres
            res[h] = {"ok": False, "msg": str(e)[:120]}
    return res


def load_heavy(demo: bool) -> dict:
    return load_partners(demo, HEAVYWEIGHTS, "5m", "5d")
