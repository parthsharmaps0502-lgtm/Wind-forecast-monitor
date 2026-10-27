"""Writes SYNTHETIC cache files so the app can be run/tested offline. Not real Elexon data.
Usage: DATA_DIR=./data python make_synthetic.py"""
import os
import numpy as np, pandas as pd
rng = np.random.default_rng(1)
d = os.environ.get("DATA_DIR", "data"); os.makedirs(d, exist_ok=True)
t = pd.date_range("2026-01-02", "2026-02-02", freq="30min", inclusive="left", tz="UTC")
truth = np.clip(8000 + 4000*np.sin(np.arange(len(t))/200) + rng.normal(0, 400, len(t)).cumsum()*0.1, 0, 20000)
pd.DataFrame({"start": t, "actual": truth}).to_csv(f"{d}/actuals.csv.gz", index=False)
rows = []
for pub in pd.date_range("2025-12-28", "2026-02-01", freq="6h", tz="UTC", inclusive="left"):
    m = (t >= pub) & (t <= pub + pd.Timedelta(hours=96))
    for s, v in zip(t[m], truth[m]):
        h = (s - pub).total_seconds()/3600
        rows.append((s, pub, max(0, v + rng.normal(0, 150 + 25*h))))
pd.DataFrame(rows, columns=["start", "publish", "forecast"]).to_csv(f"{d}/forecasts.csv.gz", index=False)
