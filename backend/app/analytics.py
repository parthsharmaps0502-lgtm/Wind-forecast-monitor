import datetime as dt
import functools

import numpy as np
import pandas as pd

from . import data

TZ = "Europe/London"
D_MIN, D_MAX = data.DELIVERY_FROM, data.DELIVERY_TO
HORIZON_BINS = [0, 6, 12, 18, 24, 30, 36, 48, 96]


def _limit(start, cutoff):
    """Decision deadline for each target time: cutoff (London clock) on the day before delivery."""
    h, m = map(int, cutoff.split(":"))
    local = start.dt.tz_convert(TZ)
    day = local.dt.normalize().dt.tz_localize(None) - pd.Timedelta(days=1)
    lim = (day + pd.Timedelta(hours=h, minutes=m)).dt.tz_localize(TZ, ambiguous="NaT", nonexistent="NaT")
    return lim.dt.tz_convert("UTC")


@functools.lru_cache(maxsize=64)
def selected(cutoff):
    """For each target half-hour: the latest forecast published at or before the decision deadline."""
    _, fc = data.load()
    fc = fc.copy()
    fc["limit"] = _limit(fc["start"], cutoff)
    fc = fc[fc["publish"] <= fc["limit"]].sort_values("publish").drop_duplicates("start", keep="last")
    return fc.drop(columns="limit")


def _decorate(df):
    df["date"] = df["start"].dt.tz_convert(TZ).dt.date
    df["error"] = df["actual"] - df["forecast"]  # negative = wind under-delivered vs forecast
    df["horizon"] = (df["start"] - df["publish"]).dt.total_seconds() / 3600
    return df


def frame(cutoff, d0, d1):
    act, _ = data.load()
    df = _decorate(act.merge(selected(cutoff), on="start", how="inner"))
    return df[(df["date"] >= d0) & (df["date"] <= d1)].sort_values("start")


def r(x, n=1):
    return None if x is None or pd.isna(x) else round(float(x), n)


def metrics(df):
    if df.empty:
        return None
    e, ae = df["error"], df["error"].abs()
    short = -e  # shortfall = forecast - actual (positive when wind under-delivers)
    return {
        "n": int(len(df)), "mae": r(ae.mean()), "rmse": r(np.sqrt((e ** 2).mean())),
        "bias": r(e.mean()),
        "wape": r(ae.sum() / df["actual"].sum() * 100) if df["actual"].sum() > 0 else None,
        "p50_abs": r(ae.quantile(.5)), "p90_abs": r(ae.quantile(.9)),
        "p90_shortfall": r(short.quantile(.9)), "max_shortfall": r(short.max()),
        "max_surplus": r(-short.min()), "mean_actual": r(df["actual"].mean()),
        "mean_horizon_h": r(df["horizon"].mean()),
    }


def _iso(s):
    return s.dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def decision(day, cutoff):
    df = frame(cutoff, day, day)
    if df.empty:
        return None
    prior = frame(cutoff, D_MIN, day - dt.timedelta(days=1))
    if prior["date"].nunique() >= 3:
        basis = f"errors from the {prior['date'].nunique()} previous delivery days"
    else:
        prior, basis = frame(cutoff, D_MIN, D_MAX), "full January backtest (too few earlier days)"
    q10, q90 = prior["error"].quantile(.1), prior["error"].quantile(.9)
    df = df.assign(low=(df["forecast"] + q10).clip(lower=0), high=df["forecast"] + q90)
    pts = pd.DataFrame({"t": _iso(df["start"]), "forecast": df["forecast"], "actual": df["actual"],
                        "low": df["low"], "high": df["high"], "publish": _iso(df["publish"]),
                        "horizon": df["horizon"].round(1)})
    return {
        "date": day.isoformat(), "cutoff": cutoff,
        "decision_deadline": str(_limit(df["start"].iloc[:1], cutoff).iloc[0]),
        "points": pts.to_dict("records"), "band_basis": basis,
        "q10_error": r(q10), "q90_error": r(q90),
        "summary": {
            "avg_forecast": r(df["forecast"].mean()), "min_forecast": r(df["forecast"].min()),
            "peak_forecast": r(df["forecast"].max()), "avg_low": r(df["low"].mean()),
            "avg_high": r(df["high"].mean()),
            "published_first": _iso(df["publish"]).min(), "published_last": _iso(df["publish"]).max(),
            "n_publications": int(df["publish"].nunique()),
        },
        "day_metrics": metrics(df),
    }


def accuracy(d0, d1, cutoff):
    df = frame(cutoff, d0, d1)
    if df.empty:
        return None
    df = df.assign(hour=df["start"].dt.tz_convert(TZ).dt.hour)
    by_hour = df.groupby("hour").agg(mae=("error", lambda s: s.abs().mean()), bias=("error", "mean")).round(1)
    daily = df.groupby("date").agg(mae=("error", lambda s: s.abs().mean()), bias=("error", "mean"),
                                   actual=("actual", "mean")).round(1)
    # Error vs how far ahead the forecast was made (all publications, not only the decision-time one)
    act, fc = data.load()
    allf = _decorate(act.merge(fc, on="start", how="inner"))
    allf = allf[(allf["date"] >= d0) & (allf["date"] <= d1)].copy()
    allf["bin"] = pd.cut(allf["horizon"], HORIZON_BINS, right=False)
    hz = allf.groupby("bin", observed=True)["error"].agg(mae=lambda s: s.abs().mean(), bias="mean").round(1)
    hist, edges = np.histogram(df["error"], bins=24)
    return {
        "from": d0.isoformat(), "to": d1.isoformat(), "cutoff": cutoff, "metrics": metrics(df),
        "by_hour": [{"hour": int(h), **v} for h, v in by_hour.to_dict("index").items()],
        "daily": [{"date": str(k), **v} for k, v in daily.to_dict("index").items()],
        "by_horizon": [{"label": f"{int(b.left)}–{int(b.right)}h", **v} for b, v in hz.to_dict("index").items()],
        "histogram": [{"bin": r((edges[i] + edges[i + 1]) / 2, 0), "count": int(c)} for i, c in enumerate(hist)],
        "series": pd.DataFrame({"t": _iso(df["start"]), "actual": df["actual"],
                                "forecast": df["forecast"]}).to_dict("records"),
    }
