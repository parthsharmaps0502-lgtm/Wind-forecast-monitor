# UK Wind Forecast Monitor

Web app for a UK energy utility's day-ahead desk. It answers two questions about national wind generation (Elexon BMRS only):

1. **What does the latest wind forecast say at the moment I have to decide?**
2. **How wrong has that forecast been, in MW, so I can buy with the error in mind?**

React (Vite + Recharts) frontend, Python (FastAPI + pandas) backend, one Docker image.

> **AI disclosure:** this application was built with AI assistance (Claude, Anthropic). Design, code and this README were drafted with it and should be reviewed like any other code.

## Pitch (for the client)
- **Pick a delivery day, see the forecast you would actually have had.** For every half-hour, the app shows the most recent WINDFOR forecast published before your day-ahead deadline (default 09:00 London, day before), not a later, better-informed one.
- **See it against reality.** Actual wind (FUELHH) is overlaid, with a P10-P90 band built from past errors at the same deadline. Plan thermal cover against the lower edge of the band.
- **Quantified accuracy:** MAE, RMSE, bias, error as % of wind output, 90th-percentile error and shortfall, worst shortfall; broken down by hour of day, by day, by forecast lead time, plus an error histogram.
- **Direction matters:** the app reports shortfall (wind below forecast) separately, because that is the costly side for a buyer.

## Key design decisions / assumptions
- **Decision rule.** For target half-hour T on delivery day D, forecast = row with the largest `publishTime <= (D-1) at cutoff, London time`. Cutoff is user-adjustable; 09:00 is a conservative default ahead of GB day-ahead auction gate closures (confirm with the desk).
- **"Decisions made in January 2026"** is read as decisions taken 1-31 Jan, i.e. delivery days **2 Jan - 1 Feb 2026**. Change `DELIVERY_FROM/TO` in `backend/app/data.py` to shift this.
- **Error** = actual - forecast (MW). Negative = over-forecast = extra power to buy.
- **Uncertainty band** = forecast + P10/P90 of past errors at the same cutoff, using only *earlier* delivery days (no look-ahead) once 3+ exist; otherwise the full-month backtest, labelled as in-sample in the UI.
- **Lead-time chart** uses all forecast runs, so it shows what an earlier/later decision would cost.
- Times are stored in UTC and displayed in Europe/London.

## Architecture
```
backend/app/data.py       Elexon fetch (FUELHH WIND, WINDFOR) -> csv.gz cache -> pandas frames
backend/app/analytics.py  forecast-at-deadline selection, metrics, breakdowns
backend/app/main.py       FastAPI: /api/config, /api/decision, /api/accuracy; serves built UI
frontend/src/App.jsx      two views: delivery-day forecast, accuracy
Dockerfile                multi-stage: node build -> python runtime (UI served by FastAPI)
```
The deployed app reads a committed cache so it does not depend on Elexon being reachable at runtime.

## Run
```bash
# 1. fetch real data (needs internet) and commit the cache
cd backend && pip install -r requirements.txt && python -m app.data   # writes backend/data/*.csv.gz
# (offline smoke test only: DATA_DIR=./data python make_synthetic.py  -> SYNTHETIC data)

# 2. docker
docker compose up --build        # http://localhost:8000

# or dev: uvicorn app.main:app --reload (backend/), npm install && npm run dev (frontend/)
```

## Deploy (Heroku, container stack)
```bash
heroku create <name> && heroku stack:set container
git add -A && git commit -m "deploy" && git push heroku main
```
(`heroku.yml` is included. Vercel does not run Docker images, so Heroku is the simpler fit.)

## Known limitations
- Elexon endpoint parameters (`settlementDateFrom/To`, `publishDateTimeFrom/To`, `fuelType`) were written from the public API schema and **not yet run against the live API**; the logic was tested on synthetic data only. Run `python -m app.data` first and check row counts.
- Wind only, national level, per the brief. No demand, prices or thermal costs, so the app does not compute a purchase volume.
- Band is empirical and pooled across hours; it does not condition on wind level or weather regime.
