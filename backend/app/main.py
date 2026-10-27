import datetime as dt
import os
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import analytics as an

app = FastAPI(title="Wind Forecast Monitor")


def _day(s):
    try:
        d = dt.date.fromisoformat(s)
    except ValueError:
        raise HTTPException(400, f"Invalid date '{s}', expected YYYY-MM-DD")
    if not an.D_MIN <= d <= an.D_MAX:
        raise HTTPException(400, f"Delivery date must be between {an.D_MIN} and {an.D_MAX}")
    return d


def _cutoff(s):
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", s):
        raise HTTPException(400, "cutoff must be HH:MM (London time)")
    return s


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/config")
def config():
    return {"delivery_min": an.D_MIN.isoformat(), "delivery_max": an.D_MAX.isoformat(),
            "default_cutoff": "09:00", "timezone": an.TZ}


@app.get("/api/decision")
def decision(date: str, cutoff: str = "09:00"):
    out = an.decision(_day(date), _cutoff(cutoff))
    if out is None:
        raise HTTPException(404, "No forecast and actual data for that delivery day")
    return out


@app.get("/api/accuracy")
def accuracy(date_from: str, date_to: str, cutoff: str = "09:00"):
    a, b = _day(date_from), _day(date_to)
    if a > b:
        raise HTTPException(400, "date_from must not be after date_to")
    out = an.accuracy(a, b, _cutoff(cutoff))
    if out is None:
        raise HTTPException(404, "No data for that range")
    return out


STATIC = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(STATIC):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC, "assets")), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = os.path.join(STATIC, path)
        return FileResponse(f if path and os.path.isfile(f) else os.path.join(STATIC, "index.html"))
