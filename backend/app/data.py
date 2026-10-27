"""Elexon BMRS data access. Fetches FUELHH (WIND actuals) and WINDFOR (forecasts),
caches them as csv.gz so the deployed app does not depend on the live API."""
import datetime as dt
import functools
import os

import pandas as pd
import requests

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
ACT_FILE = os.path.join(DATA_DIR, "actuals.csv.gz")
FC_FILE = os.path.join(DATA_DIR, "forecasts.csv.gz")

# Decisions are made in January 2026 for delivery the next day -> delivery 2 Jan .. 1 Feb.
DELIVERY_FROM = dt.date(2026, 1, 2)
DELIVERY_TO = dt.date(2026, 2, 1)
MAX_HORIZON_H = 96  # keep forecasts at most this far ahead (decisions need ~15-48h)


def _get(dataset, params):
    r = requests.get(f"{BASE}/{dataset}/stream", params=params, timeout=90)
    r.raise_for_status()
    j = r.json()
    return j if isinstance(j, list) else j.get("data", [])


def fetch_actuals():
    rows, d = [], DELIVERY_FROM
    while d <= DELIVERY_TO:
        e = min(d + dt.timedelta(days=6), DELIVERY_TO)
        rows += _get("FUELHH", {"settlementDateFrom": d.isoformat(),
                                "settlementDateTo": e.isoformat(), "fuelType": "WIND"})
        d = e + dt.timedelta(days=1)
    df = pd.DataFrame(rows)
    df = df[df["fuelType"] == "WIND"]
    out = pd.DataFrame({"start": pd.to_datetime(df["startTime"], utc=True),
                        "actual": df["generation"].astype(float)})
    return out.drop_duplicates("start").sort_values("start")


def fetch_forecasts():
    rows = []
    a = dt.datetime(2025, 12, 28, tzinfo=dt.timezone.utc)
    end = dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc)  # last decision: 31 Jan
    fmt = "%Y-%m-%dT%H:%MZ"
    while a < end:
        b = min(a + dt.timedelta(days=2), end)
        rows += _get("WINDFOR", {"publishDateTimeFrom": a.strftime(fmt),
                                 "publishDateTimeTo": b.strftime(fmt)})
        a = b
    df = pd.DataFrame(rows)
    out = pd.DataFrame({"start": pd.to_datetime(df["startTime"], utc=True),
                        "publish": pd.to_datetime(df["publishTime"], utc=True),
                        "forecast": df["generation"].astype(float)})
    h = (out["start"] - out["publish"]).dt.total_seconds() / 3600
    lo = pd.Timestamp(DELIVERY_FROM, tz="UTC")
    hi = pd.Timestamp(DELIVERY_TO + dt.timedelta(days=1), tz="UTC")
    out = out[(h >= 0) & (h <= MAX_HORIZON_H) & (out["start"] >= lo) & (out["start"] < hi)]
    return out.drop_duplicates(["start", "publish"]).sort_values(["start", "publish"])


def prefetch():
    os.makedirs(DATA_DIR, exist_ok=True)
    fetch_actuals().to_csv(ACT_FILE, index=False)
    fetch_forecasts().to_csv(FC_FILE, index=False)


@functools.lru_cache(maxsize=1)
def load():
    if not (os.path.exists(ACT_FILE) and os.path.exists(FC_FILE)):
        prefetch()
    act = pd.read_csv(ACT_FILE)
    fc = pd.read_csv(FC_FILE)
    act["start"] = pd.to_datetime(act["start"], utc=True)
    fc["start"] = pd.to_datetime(fc["start"], utc=True)
    fc["publish"] = pd.to_datetime(fc["publish"], utc=True)
    return act, fc


if __name__ == "__main__":
    prefetch()
    a, f = load()
    print(f"actuals: {len(a)} rows, forecasts: {len(f)} rows")
