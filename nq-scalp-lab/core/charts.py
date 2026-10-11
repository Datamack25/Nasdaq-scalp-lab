"""Graphiques Plotly (thème sombre cohérent avec le CSS)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import KILLZONES, PARIS_TZ

UP, DOWN, AMBER, BLUE, MUT, GRID = "#22c55e", "#ef4444", "#f5b041", "#5b9cff", "#8b97b0", "#1d2740"
LAYOUT = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0e1420",
              font=dict(family="IBM Plex Sans, Inter, Segoe UI, Arial, sans-serif", color="#c9d2e3", size=12),
              margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified",
              legend=dict(orientation="h", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"))

ZONE_COL = {"OB+": "rgba(34,197,94,.16)", "OB-": "rgba(239,68,68,.16)", "BRK+": "rgba(91,156,255,.16)",
            "BRK-": "rgba(167,139,250,.18)", "UDG+": "rgba(34,197,94,.09)", "UDG-": "rgba(239,68,68,.09)"}


def _style(fig, h=520, title=None):
    fig.update_layout(**LAYOUT, height=h, title=dict(text=title, x=0, font=dict(size=14)) if title else None)
    fig.update_xaxes(gridcolor=GRID, showspikes=True, spikecolor=MUT, spikethickness=1)
    fig.update_yaxes(gridcolor=GRID, side="right", showspikes=True, spikecolor=MUT, spikethickness=1)
    return fig


def candles(cdf: pd.DataFrame, n: int = 180, levels: pd.DataFrame | None = None, zones=None,
            show_mmm: bool = True, killzones: bool = True, title: str = "", h: int = 560,
            events: pd.DataFrame | None = None, paris: bool = True, max_zones: int = 6):
    d = cdf.iloc[-n:].copy()
    x = d.index.tz_convert(PARIS_TZ) if paris else d.index
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.82, .18], vertical_spacing=.02)
    fig.add_trace(go.Candlestick(x=x, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"],
                                 increasing=dict(line=dict(color=UP), fillcolor=UP),
                                 decreasing=dict(line=dict(color=DOWN), fillcolor=DOWN), name="NQ"), 1, 1)
    vc = np.where(d["Close"] >= d["Open"], "rgba(34,197,94,.45)", "rgba(239,68,68,.45)")
    fig.add_trace(go.Bar(x=x, y=d["Volume"], marker_color=vc, name="Volume", showlegend=False), 2, 1)
    lo, hi = d["Low"].min(), d["High"].max()
    pad = (hi - lo) * .15
    if levels is not None and not levels.empty:
        vis = levels[(levels["prix"] >= lo - pad) & (levels["prix"] <= hi + pad)].sort_values("prix")
        merged = []
        for _, r in vis.iterrows():
            name = r["niveau"].split("–")[0].strip()
            if merged and abs(r["prix"] - merged[-1][0]) < (hi - lo) * .018:
                merged[-1][1].append(name)
                continue
            merged.append([r["prix"], [name], r["groupe"]])
        for prix, names, grp in merged:
            col = {"veille": AMBER, "jour": BLUE, "semaine": "#a78bfa", "macro": "#e879f9"}.get(grp, MUT)
            fig.add_hline(y=prix, line=dict(color=col, width=1, dash="dot"), row=1, col=1,
                          annotation_text=" / ".join(names[:2]) + (" …" if len(names) > 2 else ""),
                          annotation_position="top left", annotation_font=dict(size=9, color=col))
    if zones:
        x0_lim = d.index[0]
        last = d["Close"].iloc[-1]
        live = [z for z in zones if z.kind in ZONE_COL and z.status not in ("comblée", "violée")
                and z.start >= x0_lim - pd.Timedelta(days=3) and lo - pad <= z.mid <= hi + pad]
        live = sorted(live, key=lambda z: abs(z.mid - last))[:max_zones]
        for z in live:
            xs = max(z.start, x0_lim)
            xp = xs.tz_convert(PARIS_TZ) if paris else xs
            fig.add_shape(type="rect", x0=xp, x1=x[-1], y0=z.bottom, y1=z.top, fillcolor=ZONE_COL[z.kind],
                          line=dict(width=1, color=ZONE_COL[z.kind].replace(".16", ".5").replace(".09", ".35").replace(".18", ".5")),
                          row=1, col=1)
            fig.add_annotation(x=x[-1], y=z.mid, text=f"{z.kind} {z.status[:8]}", showarrow=False,
                               font=dict(size=9, color="#c9d2e3"), xanchor="right", row=1, col=1)
    if show_mmm and "mmm" in d:
        strong = d[d["mmm"].isin(["BuBC+", "BuC2+", "BuAFs+"])]
        weak = d[d["mmm"].isin(["BeBC+", "BeC2+", "BeAFs+"])]
        xs_ = strong.index.tz_convert(PARIS_TZ) if paris else strong.index
        xw_ = weak.index.tz_convert(PARIS_TZ) if paris else weak.index
        fig.add_trace(go.Scatter(x=xs_, y=strong["Low"] - (hi - lo) * .012, mode="markers",
                                 marker=dict(symbol="triangle-up", size=8, color=UP), name="Bu+ (MMM)",
                                 text=strong["mmm"], hovertemplate="%{text}<extra></extra>"), 1, 1)
        fig.add_trace(go.Scatter(x=xw_, y=weak["High"] + (hi - lo) * .012, mode="markers",
                                 marker=dict(symbol="triangle-down", size=8, color=DOWN), name="Be+ (MMM)",
                                 text=weak["mmm"], hovertemplate="%{text}<extra></extra>"), 1, 1)
        pcx = d[d["pcx"] != ""].tail(4)
        if len(pcx):
            fig.add_trace(go.Scatter(x=pcx.index.tz_convert(PARIS_TZ) if paris else pcx.index, y=pcx["Close"],
                                     mode="markers", marker=dict(symbol="star", size=11, color=AMBER),
                                     name="PCX", text=pcx["pcx"], hovertemplate="%{text}<extra></extra>"), 1, 1)
    if events is not None and len(events):
        ev = events[events["time"] >= d.index[0]].tail(6)
        for _, e in ev.iterrows():
            bull = e["signal"].startswith(("CDL", "LD"))
            fig.add_annotation(x=e["time"].tz_convert(PARIS_TZ) if paris else e["time"], y=e["level"],
                               text=e["signal"], showarrow=True, arrowhead=2, ay=-25 if bull else 25,
                               font=dict(size=10, color=UP if bull else DOWN), arrowcolor=UP if bull else DOWN,
                               row=1, col=1)
    if killzones and len(d) > 2:
        step = d.index[1] - d.index[0]
        if step <= pd.Timedelta(minutes=15):
            for day in sorted(set(d.index.normalize())):
                for name, a, b, _, col in KILLZONES:
                    if name not in ("Killzone Londres", "Fenêtre d'Or NY", "Zone morte"):
                        continue
                    x0, x1 = day + pd.Timedelta(hours=a), day + pd.Timedelta(hours=b)
                    if x1 < d.index[0] or x0 > d.index[-1]:
                        continue
                    fig.add_vrect(x0=x0.tz_convert(PARIS_TZ) if paris else x0, x1=x1.tz_convert(PARIS_TZ) if paris else x1,
                                  fillcolor=col, opacity=.07, line_width=0, row=1, col=1)
    fig.update_layout(xaxis_rangeslider_visible=False)
    fig.update_yaxes(range=[lo - pad, hi + pad], row=1, col=1)
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])] if step_gt_daily(d) else [])
    return _style(fig, h, title)


def step_gt_daily(d):
    return len(d) > 2 and (d.index[1] - d.index[0]) >= pd.Timedelta(days=1)


def horizons_bar(hp: dict):
    hs = list(hp)
    p = [hp[h]["p_up"] * 100 for h in hs]
    lab = [f"{h} min" if h < 60 else f"{h // 60} h" for h in hs]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=lab, y=[v - 50 for v in p], base=50,
                         marker_color=[UP if v >= 50 else DOWN for v in p],
                         text=[f"{v:.0f} %" for v in p], textposition="outside", name="P(hausse)"))
    conf = [hp[h]["p_conf"] * 100 for h in hs]
    fig.add_trace(go.Scatter(x=lab, y=conf, mode="markers", marker=dict(symbol="diamond", size=9, color=AMBER),
                             name="Confluence seule"))
    ml = [hp[h]["p_ml"] * 100 if hp[h]["p_ml"] is not None else None for h in hs]
    fig.add_trace(go.Scatter(x=lab, y=ml, mode="markers", marker=dict(symbol="circle-open", size=10, color=BLUE),
                             name="ML seul (rétréci)"))
    fig.add_hline(y=50, line=dict(color=MUT, dash="dot"))
    fig.update_yaxes(range=[25, 75], title="Probabilité de hausse (%)")
    return _style(fig, 330, "Probabilité directionnelle par horizon")


def heatmap(pv: pd.DataFrame, title: str, fmt: str = ".0f", diverging=False):
    fig = go.Figure(go.Heatmap(z=pv.values, x=[f"{c}h" for c in pv.columns], y=pv.index,
                               colorscale="RdYlGn" if diverging else "Viridis", zmid=0 if diverging else None,
                               texttemplate="%{z:" + fmt + "}", textfont=dict(size=9)))
    fig = _style(fig, 330, title)
    fig.update_yaxes(side="left", automargin=True)
    return fig


def bars(x, y, title, color=BLUE, ref=None, ytitle=""):
    fig = go.Figure(go.Bar(x=x, y=y, marker_color=color))
    if ref is not None:
        fig.add_hline(y=ref, line=dict(color=AMBER, dash="dot"))
    fig.update_yaxes(title=ytitle)
    return _style(fig, 320, title)


def normalized_lines(closes: dict, title: str):
    fig = go.Figure()
    for tk, s in closes.items():
        if s is None or len(s) < 5:
            continue
        s = s.iloc[-288:]
        fig.add_trace(go.Scatter(x=s.index.tz_convert(PARIS_TZ), y=(s / s.iloc[0] - 1) * 100, name=tk, mode="lines",
                                 line=dict(width=2.5 if tk == "NQ=F" else 1.2)))
    fig.update_yaxes(title="% depuis le début de la fenêtre")
    return _style(fig, 400, title)


def calibration(calib: pd.DataFrame, title: str):
    x = [str(i) for i in calib.index]
    fig = go.Figure(go.Bar(x=x, y=calib["mean"] * 100, text=calib["size"], textposition="outside",
                           marker_color=BLUE))
    fig.add_hline(y=50, line=dict(color=MUT, dash="dot"))
    fig.update_yaxes(title="% de hausses réalisées", range=[0, 100])
    fig.update_xaxes(title="Tranche de probabilité prédite (hors échantillon)")
    return _style(fig, 300, title)


def hour_hist(counts_h: pd.Series, counts_l: pd.Series, title: str):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=counts_h.index, y=counts_h.values, name="Plus haut", marker_color=UP))
    fig.add_trace(go.Bar(x=counts_l.index, y=counts_l.values, name="Plus bas", marker_color=DOWN))
    fig.add_hline(y=100 / 23, line=dict(color=AMBER, dash="dot"), annotation_text="uniforme")
    fig.update_layout(barmode="group")
    fig.update_xaxes(title="Heure de Paris", dtick=1)
    fig.update_yaxes(title="% des jours")
    return _style(fig, 340, title)
