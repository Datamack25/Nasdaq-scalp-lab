"""Moteur de prévision multi-horizon (1, 3, 5, 15, 60, 240 min).

Principe : pour chaque horizon, un ensemble (régression logistique + gradient
boosting) est entraîné en walk-forward sur les données chargées, avec un « gap »
égal à l'horizon pour éviter toute fuite d'information. La probabilité finale est
RÉTRÉCIE vers 50 % en fonction de la compétence mesurée hors échantillon (AUC) :
un modèle qui ne bat pas le hasard affiche ~50 %, quoi qu'il « pense ».
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .candles import classify

warnings.filterwarnings("ignore", category=RuntimeWarning)

FEATURE_LABELS = {
    "r1": "rendement 1 barre", "r3": "rendement 3 barres", "r6": "rendement 6 barres",
    "r12": "rendement 12 barres", "rsi": "RSI 14", "ema_spread": "écart EMA20/EMA50",
    "dist_ema20": "distance à l'EMA20", "bb_pos": "position Bollinger", "bb_width": "largeur Bollinger",
    "atr_pct": "volatilité (ATR %)", "vol_ratio": "ratio de volume", "mmm_dir": "bougie MMM",
    "mmm_strong": "bougie MMM forte", "build": "compte de construction", "dist_mid": "distance ouverture minuit",
    "day_pos": "position dans le range du jour", "h_sin": "heure (sin)", "h_cos": "heure (cos)",
    "dow": "jour de semaine", "london": "session Londres", "ny_am": "matinée NY", "lunch": "zone morte",
    "es_r3": "ES 3 barres", "vix_r3": "VIX 3 barres", "dxy_r3": "DXY 3 barres", "nq_es_gap": "écart NQ-ES",
}


def _rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _align_at_close(s: pd.Series, target_idx: pd.DatetimeIndex, target_step) -> pd.Series:
    """Aligne une série partenaire sur l'index cible SANS fuite : on compare les heures
    de CLÔTURE (index + durée de barre) et on prend la dernière valeur connue."""
    step = pd.Series(s.index).diff().median()
    left = pd.DataFrame({"t": target_idx + target_step}).reset_index()
    right = pd.DataFrame({"t": s.index + step, "v": s.values}).sort_values("t")
    m = pd.merge_asof(left.sort_values("t"), right, on="t", direction="backward",
                      tolerance=pd.Timedelta(hours=2))
    return pd.Series(m.sort_values("index")["v"].values, index=target_idx)


def build_features(df: pd.DataFrame, partners: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    c = df["Close"]
    lc = np.log(c)
    X = pd.DataFrame(index=df.index)
    for k in (1, 3, 6, 12):
        X[f"r{k}"] = lc.diff(k) * 1e4
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - c.shift()).abs(), (df["Low"] - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    ema20, ema50 = c.ewm(span=20, adjust=False).mean(), c.ewm(span=50, adjust=False).mean()
    X["rsi"] = _rsi(c)
    X["ema_spread"] = (ema20 - ema50) / atr
    X["dist_ema20"] = (c - ema20) / atr
    ma, sd = c.rolling(20).mean(), c.rolling(20).std()
    X["bb_pos"] = (c - ma) / (2 * sd)
    X["bb_width"] = (4 * sd / c * 1e4)
    X["bb_width"] = X["bb_width"] / X["bb_width"].rolling(100, min_periods=20).mean()
    X["atr_pct"] = atr / c * 1e4
    cdf = classify(df)
    X["vol_ratio"] = cdf["vol_ratio"].clip(0, 5)
    X["mmm_dir"] = cdf["dir"]
    X["mmm_strong"] = cdf["strong"].astype(float) * cdf["dir"]
    X["build"] = cdf["build_count"].clip(-6, 6)
    # contexte intrajournalier (journée CME)
    day = (df.index + pd.Timedelta(hours=6)).normalize()
    hr = pd.Series(df.index.hour, index=df.index)
    first_mid = (hr == 0) & (hr.shift() != 0)
    mid_open = df["Open"].where(first_mid).ffill()     # pas de fuite : valeur connue à t
    X["dist_mid"] = (c - mid_open) / atr
    dh = df["High"].groupby(day).cummax()
    dl = df["Low"].groupby(day).cummin()
    X["day_pos"] = (c - dl) / (dh - dl).replace(0, np.nan)
    hd = df.index.hour + df.index.minute / 60
    X["h_sin"], X["h_cos"] = np.sin(2 * np.pi * hd / 24), np.cos(2 * np.pi * hd / 24)
    X["dow"] = df.index.dayofweek
    X["london"] = ((hd >= 2) & (hd < 8)).astype(float)
    X["ny_am"] = ((hd >= 8) & (hd < 11.5)).astype(float)
    X["lunch"] = ((hd >= 11.5) & (hd < 13.5)).astype(float)
    if partners:
        nq_step = pd.Series(df.index).diff().median()
        for key, tk in (("es", "ES=F"), ("vix", "^VIX"), ("dxy", "DX-Y.NYB")):
            p = partners.get(tk)
            if p is None or p.empty:
                continue
            pc = _align_at_close(p["Close"], df.index, nq_step)
            if pc.notna().mean() < .8:
                continue
            X[f"{key}_r3"] = np.log(pc).diff(3) * 1e4
            if key == "es":
                X["nq_es_gap"] = X["r12"] - np.log(pc).diff(12) * 1e4
    return X.replace([np.inf, -np.inf], np.nan)


def _models():
    lr = make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=500))
    gb = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150,
                                        l2_regularization=1.0, min_samples_leaf=60)
    return lr, gb


def forecast_horizon(df: pd.DataFrame, bars_ahead: int, partners=None, n_splits: int = 5,
                     max_rows: int = 12000) -> dict:
    """Entraîne et évalue un horizon. Retourne proba hausse, métriques OOS, moteurs."""
    X = build_features(df, partners)
    y = (df["Close"].shift(-bars_ahead) > df["Close"]).astype(float)
    y[df["Close"].shift(-bars_ahead).isna()] = np.nan
    data = X.join(y.rename("y")).dropna(subset=["r12", "rsi"])
    train = data.dropna(subset=["y"]).iloc[-max_rows:]
    if len(train) < 400:
        return {"ok": False, "msg": f"Historique insuffisant ({len(train)} barres)"}
    feats = [f for f in X.columns if train[f].notna().mean() > .9]
    Xt = train[feats].fillna(train[feats].median())
    yt = train["y"].values
    tss = TimeSeriesSplit(n_splits=n_splits, gap=bars_ahead)
    oos_p, oos_y = [], []
    for tr_i, te_i in tss.split(Xt):
        lr, gb = _models()
        lr.fit(Xt.iloc[tr_i], yt[tr_i]); gb.fit(Xt.iloc[tr_i], yt[tr_i])
        p = 0.5 * lr.predict_proba(Xt.iloc[te_i])[:, 1] + 0.5 * gb.predict_proba(Xt.iloc[te_i])[:, 1]
        oos_p.append(p); oos_y.append(yt[te_i])
    p_oos, y_oos = np.concatenate(oos_p), np.concatenate(oos_y)
    base = max(y_oos.mean(), 1 - y_oos.mean())
    acc = ((p_oos > .5) == (y_oos > .5)).mean()
    try:
        auc = roc_auc_score(y_oos, p_oos)
    except ValueError:
        auc = .5
    brier = brier_score_loss(y_oos, p_oos)
    brier_ref = brier_score_loss(y_oos, np.full_like(p_oos, y_oos.mean()))
    conf = np.abs(p_oos - .5) > .08
    acc_conf = ((p_oos[conf] > .5) == (y_oos[conf] > .5)).mean() if conf.sum() > 30 else np.nan
    # fit final
    lr, gb = _models()
    lr.fit(Xt, yt); gb.fit(Xt, yt)
    last = data[feats].iloc[[-1]].fillna(train[feats].median())
    p_raw = float(0.5 * lr.predict_proba(last)[:, 1][0] + 0.5 * gb.predict_proba(last)[:, 1][0])
    skill = float(np.clip((auc - 0.5) / 0.08, 0, 1))
    p_final = 0.5 + (p_raw - 0.5) * skill
    # moteurs : contribution logistique standardisée
    coefs = lr[-1].coef_[0]
    z = lr[0].transform(last)[0]
    contrib = pd.Series(coefs * z, index=feats).sort_values(key=np.abs, ascending=False)
    drivers = [(FEATURE_LABELS.get(k, k), float(v)) for k, v in contrib.head(4).items()]
    # calibration par tranches
    bins = pd.cut(p_oos, [0, .4, .45, .5, .55, .6, 1])
    calib = pd.DataFrame({"bin": bins, "y": y_oos}).groupby("bin", observed=True)["y"].agg(["mean", "size"])
    return {"ok": True, "p_up": p_final, "p_raw": p_raw, "skill": skill, "acc": acc, "auc": auc,
            "base": base, "brier": brier, "brier_ref": brier_ref, "acc_conf": acc_conf,
            "n_train": len(train), "n_oos": len(y_oos), "drivers": drivers, "calib": calib,
            "last_bar": data.index[-1]}


def label(p: float) -> tuple[str, str]:
    if p >= .58:
        return "HAUSSE", "up"
    if p <= .42:
        return "BAISSE", "down"
    if p >= .53:
        return "Légère hausse", "up-soft"
    if p <= .47:
        return "Légère baisse", "down-soft"
    return "NEUTRE", "flat"
