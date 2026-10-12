"""Moteur MMM : alphabet des bougies multi-TF, structure CDL/CDS, PCX, momentum, backtest."""
import numpy as np
import pandas as pd
import streamlit as st

from core import candles, charts, ui
from core.candles import CODE_INFO, momentum_phase, volume_read
from core.config import MMM_BY_TF, MMM_GLOBAL

ui.setup_page("Bougies MMM", "🕯️")
opts = ui.sidebar()
B = ui.bundle(opts)
ctx = B["ctx"]
ui.header("🕯️ Moteur Max Maserati (MMM)", "Classification MMMFCB des bougies CLÔTURÉES, swings, CDL/CDS, PCX, mur du momentum", ctx)

st.markdown("#### Dernière bougie clôturée par unité de temps")
cards = []
for tf in ("1d", "4h", "1h", "15m", "5m", "1m"):
    r = ctx["tf"][tf].iloc[-2]
    code = r["mmm"]
    desc, action, sens, _ = CODE_INFO.get(code, ("", "", "neutre", 0))
    tone = "up" if sens == "long" else "down" if sens == "short" else "flat"
    vr = volume_read(r["vol_ratio"])[0]
    wick = "" if r["dir"] == 0 else (" · mèche OK" if r["wick_ok"] else " · ⚠ sans mèche")
    cards.append(ui.kpi(f"{tf.upper()} · {r.name:%d/%m %H:%M} NY", code, f"{desc}<br>{action}<br>vol. {vr}{wick}", tone))
ui.grid(cards, 6)

tf = st.radio("Graphique", ["5m", "15m", "1h", "4h", "1d", "1m"], horizontal=True)
cdf = ctx["tf"][tf]
ev = ctx["events"].get(tf)
st.plotly_chart(charts.candles(cdf, n=150, levels=None, zones=None, events=ev,
                               title=f"NQ {tf} – bougies MMM (▲ Bu+, ▼ Be+, ★ PCX) et cassures CDL/CDS"), width="stretch")

c1, c2 = st.columns(2)
with c1:
    st.markdown("#### Structure (Système 1 : CDL/CDS + LD/SD)")
    rows = []
    for k in ("4h", "1h", "15m", "5m"):
        s = ctx["struct"][k]
        rows.append({"TF": k.upper(), "Tendance swings": s.get("trend"), "État": s.get("label"),
                     "Biais": {1: "▲ haussier", -1: "▼ baissier", 0: "neutre"}[s.get("bias", 0)]})
    st.markdown(ui.table_html(pd.DataFrame(rows)), unsafe_allow_html=True)
    if ev is not None and len(ev):
        e = ev.tail(8).copy()
        e["Heure NY"] = e["time"].dt.strftime("%d/%m %H:%M")
        e = e[["Heure NY", "signal", "level", "anchor"]].rename(columns={"signal": "Signal", "level": "Niveau cassé", "anchor": "Ancre (stop structurel)"})
        st.markdown(f"Derniers signaux {tf.upper()}")
        st.markdown(ui.table_html(e.round(2)), unsafe_allow_html=True)
with c2:
    st.markdown("#### Momentum & PCX")
    d = cdf.iloc[:-1]
    bc = int(d["build_count"].iloc[-1])
    wall = 4 if bc > 0 else 3
    msg = ("MUR atteint : sortir 75 % (haussier) / 100 % (baissier)" if abs(bc) >= wall else
           f"{abs(bc)} BC consécutives – mur à {wall}")
    pcx = d[d["pcx"] != ""].tail(5)
    last_sig = d[d["strong"] & d["is_bc"]].tail(1)
    ph = momentum_phase(d, d.index.get_loc(last_sig.index[0]), int(last_sig["dir"].iloc[0])) if len(last_sig) else {"phase": "n.d.", "builds": 0, "touches": 0}
    ui.grid([
        ui.kpi("Compte de construction", f"{bc:+d}", msg, "up" if bc > 0 else "down" if bc < 0 else ""),
        ui.kpi("Phase depuis la dernière BC+", ph["phase"].split("–")[0], f"{ph['builds']} construction(s), {ph['touches']} touche(s)"),
    ], 2)
    if len(pcx):
        p = pd.DataFrame({"Heure NY": pcx.index.strftime("%d/%m %H:%M"), "Signal": pcx["pcx"], "Clôture": pcx["Close"].round(2)})
        st.markdown("Power closes BC-sur-BC (Système 4) – une BC+ opposée annule tous les biais précédents")
        st.markdown(ui.table_html(p), unsafe_allow_html=True)
    else:
        st.caption("Aucun PCX récent.")

st.markdown("#### Backtest MMM sur les données chargées vs backtest publié")
max_bars = st.slider("Horizon de validation (barres)", 1, 4, 2, help="Le backtest MMM sort si l'objectif n'est pas atteint en 2 barres")
rows = []
for k, pub_tf in (("15m", "15m"), ("1h", "1h"), ("4h", "4h"), ("5m", None)):
    bt = candles.backtest_configs(ctx["tf"][k] if k != "5m" else candles.classify(B["mk"]["5m"].iloc[-3000:]), max_bars)
    if bt.empty:
        continue
    for fam, g in bt.groupby("family"):
        n = len(g)
        w = (g["result"] == "win").mean() * 100
        inv = (g["result"] == "invalid").mean() * 100
        both = (g["result"] == "les deux").mean() * 100
        se = np.sqrt(w / 100 * (1 - w / 100) / n) * 100 * 1.96
        pub = MMM_BY_TF.get(pub_tf, {}).get(fam) if pub_tf else MMM_GLOBAL[fam]["win"]
        rows.append({"TF": k, "Config": fam, "N": n, "Win %": f"{w:.1f} ± {se:.1f}", "Invalid %": f"{inv:.1f}",
                     "Les deux %": f"{both:.1f}", "Publié MMM %": pub, "R moyen": f"{(g['reward_pts'] / g['risk_pts'].replace(0, np.nan)).median():.2f}"})
st.markdown(ui.table_html(pd.DataFrame(rows), num_cols=("N", "Win %", "Invalid %", "Les deux %", "Publié MMM %", "R moyen")),
            unsafe_allow_html=True)
st.caption("Règle de validation identique au rapport : entrée à l'ouverture suivante, objectif = extrême de la bougie signal, "
           "stop = extrême opposé. Attention : l'objectif C1 est souvent très proche (R moyen < 1), d'où des taux élevés "
           "qui ne se traduisent pas automatiquement en espérance positive après coûts.")

with st.expander("📖 Alphabet MMMFCB – rappel des règles"):
    t = pd.DataFrame([{"Code": k, "Description": v[0], "Exécution": v[1], "Sens": v[2]} for k, v in CODE_INFO.items() if k != "—"])
    st.markdown(ui.table_html(t), unsafe_allow_html=True)
    st.markdown("**Règle de mèche** : pas d'entrée sur BuX sans mèche basse, ni sur BeX sans mèche haute. "
                "**Jamais sur BC-Moins** : le Mur a résisté. **CI / S&D** : attendre la BC qui sort du range.")
ui.footer()
