import { useMemo } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, Legend,
} from "recharts";

const TILT_WARN = 3, TILT_CRIT = 6;
const SOIL_WARN = 60, SOIL_CRIT = 80;

const tickTime = (ms) =>
  new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

function buildSeries(readings, forecast, key, fkey) {
  const data = readings.map((r) => ({
    t: new Date(r.ts).getTime(),
    [key]: r[key === "tilt" ? "tilt_dev" : "soil"],
  }));
  if (!data.length) return data;

  // Anchor the dashed forecast line to the last real sample, then project.
  const last = data[data.length - 1];
  last[fkey] = last[key];
  if (forecast?.ready && forecast.projections) {
    for (const p of forecast.projections) {
      data.push({
        t: last.t + p.horizon_min * 60000,
        [fkey]: key === "tilt" ? p.tilt_dev : p.soil,
      });
    }
  }
  return data;
}

function Chart({ title, unit, data, dkey, fkey, warn, crit, color }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>{title}</div>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 6, right: 12, left: -8, bottom: 0 }}>
          <CartesianGrid stroke="#2a323d" strokeDasharray="3 3" />
          <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]}
            scale="time" tickFormatter={tickTime} stroke="#8b949e" fontSize={11} />
          <YAxis stroke="#8b949e" fontSize={11} unit={unit} />
          <Tooltip
            contentStyle={{ background: "#161b22", border: "1px solid #2a323d", borderRadius: 8 }}
            labelFormatter={(ms) => new Date(ms).toLocaleString()}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine y={warn} stroke="#e8800c" strokeDasharray="4 4"
            label={{ value: "WARNING", fill: "#e8800c", fontSize: 10, position: "insideTopLeft" }} />
          <ReferenceLine y={crit} stroke="#e5484d" strokeDasharray="4 4"
            label={{ value: "CRITICAL", fill: "#e5484d", fontSize: 10, position: "insideTopLeft" }} />
          <Line type="monotone" dataKey={dkey} name="measured" stroke={color}
            dot={false} strokeWidth={2} isAnimationActive={false} connectNulls />
          <Line type="monotone" dataKey={fkey} name="ML forecast" stroke={color}
            strokeDasharray="5 4" dot={false} strokeWidth={2}
            isAnimationActive={false} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function TrendCharts({ nodes, selectedId, onSelect, readings, forecast }) {
  const tiltData = useMemo(() => buildSeries(readings, forecast, "tilt", "tiltF"), [readings, forecast]);
  const soilData = useMemo(() => buildSeries(readings, forecast, "soil", "soilF"), [readings, forecast]);

  return (
    <div className="panel">
      <div className="panel-head">
        <span>Trend Charts &amp; ML Forecast</span>
        <select className="btn" value={selectedId ?? ""} onChange={(e) => onSelect(+e.target.value)}>
          {nodes.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
        </select>
      </div>
      <div className="panel-body">
        {readings.length === 0 ? (
          <div className="empty">No readings yet for this node.</div>
        ) : (
          <>
            <Chart title="Tilt deviation (°)" unit="°" data={tiltData}
              dkey="tilt" fkey="tiltF" warn={TILT_WARN} crit={TILT_CRIT} color="#2f81f7" />
            <Chart title="Soil moisture (%)" unit="%" data={soilData}
              dkey="soil" fkey="soilF" warn={SOIL_WARN} crit={SOIL_CRIT} color="#3fb950" />
          </>
        )}
      </div>
    </div>
  );
}
