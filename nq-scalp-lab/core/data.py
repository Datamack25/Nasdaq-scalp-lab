"""Acquisition et préparation des données de marché.

Sources :
  * Yahoo Finance (yfinance) – différé d'environ 10-15 min sur les futures CME.
  * Fichier CSV importé (export TradingView / NinjaTrader / Tradovate) pour des
    données plus fraîches.
  * Mode DÉMO : série synthétique réaliste, uniquement si les deux premières
    sources sont indisponibles (aucune décision ne doit être prise dessus).
"""
from __future__ import annotations

import io
import zlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import NY_TZ

# période maximale autorisée par Yahoo pour chaque intervalle
YF_PERIOD = {"1m": "7d", "2m": "60d", "5m": "60d", "15m": "60d", "30m": "60d",
             "1h": "730d", "1d": "10y", "1wk": "max"}

OHLCV = ["Open", "High", "Low", "Close", "Volume"]


@dataclass
class MarketData:
    df: pd.DataFrame
    source: str          # "yahoo", "csv", "demo"
    ticker: str
    interval: str

    @property
    def is_demo(self) -> bool:
        return self.source == "demo"

    @property
    def last_ts(self):
        return self.df.index[-1] if len(self.df) else None


# ----------------------------------------------------------------- utilitaires
def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.title)
    keep = [c for c in OHLCV if c in df.columns]
    df = df[keep].copy()
    if "Volume" not in df.columns:
        df["Volume"] = 0.0
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    idx = pd.DatetimeIndex(df.index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx
    df.index = idx.tz_convert(NY_TZ)
    # impressions aberrantes : barre dont le range > 12 x médiane et qui revient aussitôt
    rng = (df["High"] - df["Low"])
    med = rng.rolling(200, min_periods=20).median()
    bad = rng > 12 * med
    if bad.any():
        df.loc[bad, "High"] = df.loc[bad, ["Open", "Close"]].max(axis=1)
        df.loc[bad, "Low"] = df.loc[bad, ["Open", "Close"]].min(axis=1)
    return df.astype(float)


def fetch_yahoo(ticker: str, interval: str, period: str | None = None) -> pd.DataFrame:
    """Télécharge depuis Yahoo. Retourne un DataFrame vide en cas d'échec."""
    try:
        import yfinance as yf
        raw = yf.download(ticker, period=period or YF_PERIOD.get(interval, "60d"),
                          interval=interval, progress=False, auto_adjust=False,
                          prepost=True, threads=False)
        return _clean(raw)
    except Exception:  # réseau, quota, changement d'API…
        return pd.DataFrame(columns=OHLCV)


def resample(df: pd.DataFrame, rule: str, offset: str | None = None,
             tz: str | None = None) -> pd.DataFrame:
    """Rééchantillonne de l'OHLCV. `tz` permet d'aligner les barres (ex. H4 UTC)."""
    if df.empty:
        return df
    src = df.tz_convert(tz) if tz else df
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    out = src.resample(rule, offset=offset, label="left", closed="left").agg(agg).dropna()
    return out.tz_convert(NY_TZ)


def to_h4(df_1h: pd.DataFrame) -> pd.DataFrame:
    """H4 aligné sur le backtest MMM : bougies 02-06, 06-10, 10-14… UTC."""
    return resample(df_1h, "4h", offset="2h", tz="UTC")


def cme_daily(df_intraday: pd.DataFrame) -> pd.DataFrame:
    """Barres journalières « journée CME » (18:00 NY la veille -> 17:00 NY)."""
    if df_intraday.empty:
        return df_intraday
    d = df_intraday.copy()
    shifted = d.index + pd.Timedelta(hours=6)          # 18:00 -> 00:00 du jour J
    d["cme_day"] = shifted.normalize().tz_localize(None)
    agg = d.groupby("cme_day").agg(Open=("Open", "first"), High=("High", "max"),
                                   Low=("Low", "min"), Close=("Close", "last"),
                                   Volume=("Volume", "sum"))
    agg.index = pd.DatetimeIndex(agg.index).tz_localize(NY_TZ)
    return agg[agg.index.dayofweek < 5]


def load_csv(file) -> pd.DataFrame:
    """Lit un export CSV (TradingView: time,open,high,low,close,Volume)."""
    raw = file.read() if hasattr(file, "read") else open(file, "rb").read()
    df = pd.read_csv(io.BytesIO(raw) if isinstance(raw, bytes) else io.StringIO(raw))
    cols = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=cols)
    tcol = next((c for c in df.columns if c in ("time", "datetime", "date", "timestamp")), df.columns[0])
    t = df[tcol]
    if np.issubdtype(t.dtype, np.number):
        idx = pd.to_datetime(t, unit="s" if t.iloc[0] < 1e11 else "ms", utc=True)
    else:
        idx = pd.to_datetime(t, utc=True, errors="coerce")
    df.index = idx
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close",
                            "volume": "Volume", "vol": "Volume"})
    return _clean(df)


# -------------------------------------------------------------- données DÉMO
_HOUR_VOL = np.array([  # profil de volatilité par heure NY (0..23), NQ typique
    0.55, 0.5, 0.75, 0.9, 0.8, 0.65, 0.6, 0.7, 1.2, 1.9, 2.0, 1.4, 0.9, 0.85,
    1.1, 1.3, 0.7, 0.2, 0.6, 0.5, 0.5, 0.45, 0.45, 0.5])


def synthetic_minutes(days: int = 70, seed: int = 7, start_price: float = 21000.0,
                      end: pd.Timestamp | None = None) -> pd.DataFrame:
    """Série 1 minute réaliste (sessions CME, profil horaire, régimes, sauts macro)."""
    rng = np.random.default_rng(seed)
    end = (end or pd.Timestamp.now(tz=NY_TZ)).floor("min")
    idx = pd.date_range(end - pd.Timedelta(days=days * 7 / 5 + 3), end, freq="1min", tz=NY_TZ)
    h = idx.hour.values
    dow = idx.dayofweek.values
    open_mask = ~((h == 17) | ((dow == 4) & (h >= 17)) | (dow == 5) | ((dow == 6) & (h < 18)))
    idx = idx[open_mask]
    h = idx.hour.values
    n = len(idx)
    base = 0.00022 * _HOUR_VOL[h]
    regime = np.repeat(rng.choice([0.7, 1.0, 1.5], size=n // 1380 + 2, p=[.3, .5, .2]), 1380)[:n]
    drift_reg = np.repeat(rng.normal(0, 0.000012, size=n // 600 + 2), 600)[:n]
    shocks = rng.standard_t(df=4, size=n) / np.sqrt(2)
    macro = ((idx.hour == 8) & (idx.minute == 30)) | ((idx.hour == 14) & (idx.minute == 0))
    shocks = np.where(macro & (rng.random(n) < .5), shocks * 6, shocks)
    ret = drift_reg + base * regime * shocks
    close = start_price * np.exp(np.cumsum(ret))
    open_ = np.r_[start_price, close[:-1]]
    wick = np.abs(rng.normal(0, 1, n)) * base * regime * close * 0.6
    high = np.maximum(open_, close) + wick * rng.random(n)
    low = np.minimum(open_, close) - wick * rng.random(n)
    vol = (rng.gamma(2.0, 60, n) * _HOUR_VOL[h] ** 1.5 * (1 + 3 * macro)).round()
    df = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)
    for c in ["Open", "High", "Low", "Close"]:
        df[c] = (df[c] / 0.25).round() * 0.25
    df["High"] = df[["Open", "High", "Close"]].max(axis=1)
    df["Low"] = df[["Open", "Low", "Close"]].min(axis=1)
    return df


def synthetic_partner(nq_1m: pd.DataFrame, beta: float, noise: float, scale: float, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    r = np.log(nq_1m["Close"]).diff().fillna(0).values
    rp = beta * r + rng.normal(0, noise, len(r))
    c = scale * np.exp(np.cumsum(rp))
    o = np.r_[scale, c[:-1]]
    w = np.abs(rng.normal(0, noise, len(r))) * c
    return pd.DataFrame({"Open": o, "High": np.maximum(o, c) + w, "Low": np.minimum(o, c) - w,
                         "Close": c, "Volume": nq_1m["Volume"].values}, index=nq_1m.index)


_INTERVAL_RULE = {"1m": "1min", "2m": "2min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h"}


class DemoUniverse:
    """Génère une fois l'univers démo (NQ + partenaires) et le sert par intervalle."""

    _cache: dict = {}

    @classmethod
    def get(cls, ticker: str, interval: str) -> pd.DataFrame:
        key = "base"
        if key not in cls._cache:
            nq = synthetic_minutes()
            cls._cache[key] = {
                "NQ=F": nq,
                "ES=F": synthetic_partner(nq, 0.82, 0.00008, 5900, 11),
                "YM=F": synthetic_partner(nq, 0.6, 0.0001, 42000, 12),
                "RTY=F": synthetic_partner(nq, 0.75, 0.00015, 2200, 13),
                "DX-Y.NYB": synthetic_partner(nq, -0.12, 0.00004, 99, 14),
                "^TNX": synthetic_partner(nq, -0.3, 0.0002, 4.1, 15),
                "^VIX": synthetic_partner(nq, -3.0, 0.0008, 16, 16),
                "^VXN": synthetic_partner(nq, -2.6, 0.0008, 21, 17),
                "GC=F": synthetic_partner(nq, 0.05, 0.0001, 2600, 18),
            }
        uni = cls._cache[key]
        base = uni.get(ticker)
        if base is None:  # actions : bêta aléatoire stable
            seed = zlib.crc32(ticker.encode()) % 1000
            base = synthetic_partner(uni["NQ=F"], 1.2, 0.0003, 300, seed)
            uni[ticker] = base
        if interval == "1m":
            return base.iloc[-7 * 1380:]
        if interval in _INTERVAL_RULE:
            return resample(base, _INTERVAL_RULE[interval])
        if interval == "1d":
            return cme_daily(base)
        return resample(base, "1h")


def get_data(ticker: str, interval: str, csv_df: pd.DataFrame | None = None,
             allow_demo: bool = True, period: str | None = None) -> MarketData:
    """Point d'entrée unique : CSV > Yahoo > DÉMO."""
    if csv_df is not None and not csv_df.empty and ticker in ("NQ=F", "MNQ=F"):
        df = csv_df
        if interval in _INTERVAL_RULE:
            df = resample(csv_df, _INTERVAL_RULE[interval])
        elif interval == "1d":
            df = cme_daily(csv_df)
        return MarketData(df, "csv", ticker, interval)
    df = fetch_yahoo(ticker, interval, period)
    if not df.empty:
        return MarketData(df, "yahoo", ticker, interval)
    if allow_demo:
        return MarketData(DemoUniverse.get(ticker, interval), "demo", ticker, interval)
    return MarketData(pd.DataFrame(columns=OHLCV), "none", ticker, interval)
