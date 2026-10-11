"""Test de fumée : exécute toute la chaîne en mode démo (aucun réseau requis)."""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pandas as pd
from core import engine, candles, structure, levels

t0 = time.time()
mk = engine.load_market()
print("source:", mk["source"], {k: len(v) for k, v in mk.items() if k != "source"})
partners = engine.load_partners(mk["source"] == "demo")
heavy = engine.load_heavy(mk["source"] == "demo")
ml = engine.run_forecasts(mk, partners)
for h, r in ml.items():
    print(h, "ok" if r.get("ok") else r.get("msg"), {k: round(r[k], 3) for k in ("p_up", "auc", "acc", "base", "skill")} if r.get("ok") else "")
ctx, dec = engine.analyse(mk, partners, heavy, pd.DataFrame(), pd.DataFrame(), ml)
print("bias", round(dec.bias, 1), "dir", dec.direction, "grade", dec.grade)
for c in dec.components:
    print(f"  {c.name:40s} {c.pts:+6.2f}  {c.comment[:90]}")
print(dec.checklist)
print(dec.alignment)
print(dec.plan)
print("\n".join(dec.commentary))
print(ctx["levels"]["table"].head(30).to_string())
bt = candles.backtest_configs(ctx["tf"]["15m"])
print(bt.groupby("family")["result"].value_counts(normalize=True).unstack().round(3))
print("zones", len(ctx["zones"]), [ (z.kind, z.status) for z in ctx["zones"][:6]])
print("pools", ctx["pools"][:3])
print(levels.asia_london_ny_stats(mk["1h"]))
print(structure.fvg_fill_stats(candles.classify(mk["5m"])).mean(numeric_only=True).round(3))
print("elapsed", round(time.time() - t0, 1), "s")
