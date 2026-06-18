import RiskGauge from "./RiskGauge";
import { levelColor, levelName } from "../api";

const fmt = (v, d = 2) => (v == null ? "—" : Number(v).toFixed(d));

export default function NodeCard({ summary, forecast }) {
  const { node, online, latest } = summary;
  const lvl = online && latest ? latest.lvl : 0;
  const color = online ? levelColor(lvl) : "#6b7480";
  const anomaly = latest?.anomaly ?? 0;
  const hot = anomaly >= 0.6;

  const mlTtc = forecast?.ml_ttc;
  const fwTtc = latest?.ttc;

  return (
    <div className="card" style={{ borderLeftColor: color }}>
      <div className="card-head">
        <span className="name">{node.name}</span>
        {online ? (
          <span className="lvl-tag" style={{ background: color }}>{levelName(lvl)}</span>
        ) : (
          <span className="offline">● OFFLINE</span>
        )}
      </div>

      <div className="gauge-row">
        <RiskGauge value={latest?.risk ?? 0} />
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span className={`anomaly-badge ${hot ? "hot" : ""}`}>
            ML anomaly: {(anomaly * 100).toFixed(0)}%
          </span>
          <span className="muted" style={{ fontSize: 11 }}>
            Signal {fmt(latest?.rssi, 0)} dBm
          </span>
        </div>
      </div>

      <div className="metrics">
        <div className="metric">
          <div className="k">Tilt deviation</div>
          <div className="v">{fmt(latest?.tilt_dev)}<small> °</small></div>
        </div>
        <div className="metric">
          <div className="k">Tilt rate</div>
          <div className="v">{fmt(latest?.tilt_rate)}<small> °/min</small></div>
        </div>
        <div className="metric">
          <div className="k">Soil moisture</div>
          <div className="v">{fmt(latest?.soil, 1)}<small> %</small></div>
        </div>
        <div className="metric">
          <div className="k">Vibration</div>
          <div className="v">{latest?.vib ?? "—"}<small> /10s</small></div>
        </div>
      </div>

      <div className="ttc">
        Time-to-critical — ML: <b>{mlTtc != null && mlTtc >= 0 ? `${mlTtc} min` : "none"}</b>
        {"  ·  "}firmware: <b>{fwTtc != null && fwTtc >= 0 ? `${fwTtc} min` : "none"}</b>
      </div>
    </div>
  );
}
