import React, { useEffect, useState } from "react";
import {
  ResponsiveContainer, ComposedChart, LineChart, BarChart, Line, Bar, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from "recharts";

const fmt = (v, d = 0) => (v == null ? "–" : Number(v).toLocaleString("en-GB", { maximumFractionDigits: d }));
const tz = { timeZone: "Europe/London" };
const hhmm = (t) => new Date(t).toLocaleTimeString("en-GB", { ...tz, hour: "2-digit", minute: "2-digit" });
const dayTime = (t) => new Date(t).toLocaleString("en-GB", { ...tz, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

function useApi(url) {
  const [s, set] = useState({ data: null, error: null, loading: true });
  useEffect(() => {
    let live = true;
    set((x) => ({ ...x, loading: true, error: null }));
    fetch(url)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Request failed (${r.status})`);
        return r.json();
      })
      .then((d) => live && set({ data: d, error: null, loading: false }))
      .catch((e) => live && set({ data: null, error: e.message, loading: false }));
    return () => { live = false; };
  }, [url]);
  return s;
}

const Kpi = ({ v, label }) => <div className="kpi"><b>{v}</b><span>{label}</span></div>;
const Status = ({ s }) =>
  s.loading ? <p className="note">Loading…</p> : s.error ? <div className="callout err">{s.error}</div> : null;

function Decision({ cfg, cutoff }) {
  const [day, setDay] = useState("2026-01-15");
  const s = useApi(`/api/decision?date=${day}&cutoff=${cutoff}`);
  const d = s.data;
  const pts = d?.points.map((p) => ({ ...p, band: [p.low, p.high] }));
  return (
    <>
      <div className="bar">
        <label>Delivery day
          <input type="date" value={day} min={cfg.delivery_min} max={cfg.delivery_max} onChange={(e) => e.target.value && setDay(e.target.value)} />
        </label>
      </div>
      <Status s={s} />
      {d && (
        <>
          <div className="callout">
            For delivery on <b>{d.date}</b>, using the latest forecast published before <b>{dayTime(d.decision_deadline)}</b> (decision deadline, day before).
            Expected wind averages <b>{fmt(d.summary.avg_forecast)} MW</b>. Historically it has landed between{" "}
            <b>{fmt(d.summary.avg_low)}</b> and <b>{fmt(d.summary.avg_high)} MW</b> on average (P10–P90), so plan thermal cover against the lower figure to stay protected.
          </div>
          <div className="kpis">
            <Kpi v={`${fmt(d.summary.avg_forecast)} MW`} label="Average forecast wind" />
            <Kpi v={`${fmt(d.summary.min_forecast)} MW`} label="Lowest forecast half-hour" />
            <Kpi v={`${fmt(d.summary.peak_forecast)} MW`} label="Highest forecast half-hour" />
            <Kpi v={`${fmt(-d.q10_error)} MW`} label="Typical downside (P10 shortfall)" />
            <Kpi v={dayTime(d.summary.published_last)} label={`Forecast published (${d.summary.n_publications} run${d.summary.n_publications > 1 ? "s" : ""} used)`} />
          </div>
          <div className="card">
            <h2>Forecast at decision time vs actual wind</h2>
            <p className="note">Shaded band: P10–P90 range based on {d.band_basis}. Actuals are shown so you can see how the forecast turned out.</p>
            <ResponsiveContainer width="100%" height={360}>
              <ComposedChart data={pts}>
                <CartesianGrid stroke="#e3e9eb" />
                <XAxis dataKey="t" tickFormatter={hhmm} minTickGap={40} />
                <YAxis tickFormatter={(v) => fmt(v)} width={60} unit="" label={{ value: "MW", angle: -90, position: "insideLeft" }} />
                <Tooltip labelFormatter={dayTime} formatter={(v) => (Array.isArray(v) ? `${fmt(v[0])} – ${fmt(v[1])} MW` : `${fmt(v)} MW`)} />
                <Legend />
                <Area dataKey="band" name="P10–P90 range" stroke="none" fill="#b9d3f7" fillOpacity={0.6} />
                <Line dataKey="forecast" name="Forecast (latest at deadline)" stroke="#1f6feb" dot={false} strokeWidth={2} />
                <Line dataKey="actual" name="Actual" stroke="#0f2230" dot={false} strokeWidth={2} strokeDasharray="5 3" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="card">
            <h2>How accurate was this day?</h2>
            <div className="kpis">
              <Kpi v={`${fmt(d.day_metrics.mae)} MW`} label="Mean absolute error" />
              <Kpi v={`${fmt(d.day_metrics.bias)} MW`} label="Bias (actual − forecast)" />
              <Kpi v={`${fmt(d.day_metrics.max_shortfall)} MW`} label="Worst shortfall" />
              <Kpi v={`${fmt(d.day_metrics.mean_horizon_h)} h`} label="Average forecast lead time" />
            </div>
          </div>
        </>
      )}
    </>
  );
}

function Accuracy({ cfg, cutoff }) {
  const [from, setFrom] = useState(cfg.delivery_min);
  const [to, setTo] = useState(cfg.delivery_max);
  const s = useApi(`/api/accuracy?date_from=${from}&date_to=${to}&cutoff=${cutoff}`);
  const d = s.data, m = d?.metrics;
  return (
    <>
      <div className="bar">
        <label>From (delivery day)<input type="date" value={from} min={cfg.delivery_min} max={cfg.delivery_max} onChange={(e) => e.target.value && setFrom(e.target.value)} /></label>
        <label>To<input type="date" value={to} min={cfg.delivery_min} max={cfg.delivery_max} onChange={(e) => e.target.value && setTo(e.target.value)} /></label>
      </div>
      <Status s={s} />
      {d && (
        <>
          <div className="kpis">
            <Kpi v={`${fmt(m.mae)} MW`} label="Mean absolute error (MAE)" />
            <Kpi v={`${fmt(m.rmse)} MW`} label="RMSE (penalises large misses)" />
            <Kpi v={`${fmt(m.bias)} MW`} label="Bias (negative = over-forecast)" />
            <Kpi v={`${fmt(m.wape, 1)} %`} label="Error as % of wind generated" />
            <Kpi v={`${fmt(m.p90_abs)} MW`} label="90% of errors are below" />
            <Kpi v={`${fmt(m.p90_shortfall)} MW`} label="90th-percentile shortfall" />
            <Kpi v={`${fmt(m.max_shortfall)} MW`} label="Worst shortfall" />
          </div>
          <div className="card">
            <h2>Actual vs forecast over the period</h2>
            <p className="note">{fmt(m.n)} half-hours. Forecast = latest run published before the {cutoff} decision deadline on the previous day.</p>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={d.series}>
                <CartesianGrid stroke="#e3e9eb" />
                <XAxis dataKey="t" tickFormatter={(t) => new Date(t).toLocaleDateString("en-GB", { ...tz, day: "numeric", month: "short" })} minTickGap={50} />
                <YAxis tickFormatter={(v) => fmt(v)} width={60} />
                <Tooltip labelFormatter={dayTime} formatter={(v) => `${fmt(v)} MW`} />
                <Legend />
                <Line dataKey="forecast" name="Forecast" stroke="#1f6feb" dot={false} strokeWidth={1.5} />
                <Line dataKey="actual" name="Actual" stroke="#0f2230" dot={false} strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="grid2">
            <div className="card"><h2>Error by forecast lead time</h2>
              <p className="note">All forecast runs, grouped by how far ahead they were made. Shows what a later or earlier decision would cost.</p>
              <ResponsiveContainer width="100%" height={250}><BarChart data={d.by_horizon}><CartesianGrid stroke="#e3e9eb" /><XAxis dataKey="label" /><YAxis width={50} /><Tooltip formatter={(v) => `${fmt(v)} MW`} /><Legend /><Bar dataKey="mae" name="MAE" fill="#1f6feb" /><Bar dataKey="bias" name="Bias" fill="#c2410c" /></BarChart></ResponsiveContainer></div>
            <div className="card"><h2>Error by hour of delivery day</h2>
              <p className="note">Local time. Find the hours where forecasts are least reliable.</p>
              <ResponsiveContainer width="100%" height={250}><BarChart data={d.by_hour}><CartesianGrid stroke="#e3e9eb" /><XAxis dataKey="hour" /><YAxis width={50} /><Tooltip formatter={(v) => `${fmt(v)} MW`} /><Legend /><Bar dataKey="mae" name="MAE" fill="#1f6feb" /><Bar dataKey="bias" name="Bias" fill="#c2410c" /></BarChart></ResponsiveContainer></div>
            <div className="card"><h2>Daily mean absolute error</h2>
              <ResponsiveContainer width="100%" height={250}><BarChart data={d.daily}><CartesianGrid stroke="#e3e9eb" /><XAxis dataKey="date" tickFormatter={(x) => x.slice(5)} minTickGap={20} /><YAxis width={50} /><Tooltip formatter={(v) => `${fmt(v)} MW`} /><Bar dataKey="mae" name="MAE" fill="#1f6feb" /></BarChart></ResponsiveContainer></div>
            <div className="card"><h2>Distribution of errors (actual − forecast)</h2>
              <p className="note">Left of zero: wind under-delivered, extra power to buy.</p>
              <ResponsiveContainer width="100%" height={250}><BarChart data={d.histogram}><CartesianGrid stroke="#e3e9eb" /><XAxis dataKey="bin" tickFormatter={(v) => fmt(v)} minTickGap={20} /><YAxis width={40} /><Tooltip /><ReferenceLine x={0} stroke="#0f2230" /><Bar dataKey="count" name="Half-hours" fill="#1f6feb" /></BarChart></ResponsiveContainer></div>
          </div>
        </>
      )}
    </>
  );
}

export default function App() {
  const cfg = useApi("/api/config");
  const [tab, setTab] = useState("decision");
  const [cutoff, setCutoff] = useState("09:00");
  return (
    <div className="wrap">
      <h1>UK wind forecast monitor</h1>
      <p className="sub">What the day-ahead wind forecast says when you buy, and how far it can be trusted. National wind generation, Elexon data, January 2026 decisions.</p>
      <Status s={cfg} />
      {cfg.data && (
        <>
          <div className="bar">
            <label>Decision deadline on day before delivery (London time)
              <input type="time" value={cutoff} onChange={(e) => e.target.value && setCutoff(e.target.value)} />
            </label>
          </div>
          <div className="tabs" role="tablist">
            <button role="tab" aria-selected={tab === "decision"} onClick={() => setTab("decision")}>Forecast for a delivery day</button>
            <button role="tab" aria-selected={tab === "accuracy"} onClick={() => setTab("accuracy")}>Forecast accuracy</button>
          </div>
          {tab === "decision" ? <Decision cfg={cfg.data} cutoff={cutoff} /> : <Accuracy cfg={cfg.data} cutoff={cutoff} />}
        </>
      )}
    </div>
  );
}
