import { levelColor, levelName } from "../api";

export default function Header({ overview, conn, onRetrain }) {
  const worst = overview?.worst_level ?? 0;
  const ml = overview?.ml ?? {};

  const connLabel = { live: "Live (WebSocket)", poll: "Polling (5s)", connecting: "Connecting…", down: "Disconnected" }[conn] || conn;
  const connClass = conn === "live" ? "live" : conn === "poll" ? "poll" : "down";

  return (
    <header className="header">
      <div className="brand">
        <h1>Lo<span style={{ color: "var(--accent)" }}>SLOPE</span></h1>
        <span className="sub">Slope Monitoring &amp; Early Warning</span>
      </div>

      <div
        className="status-pill"
        style={{ background: levelColor(worst) }}
        title="Worst alert level across all online nodes"
      >
        <span className="dot" />
        SYSTEM: {levelName(worst)}
      </div>

      <div className="header-meta">
        <div className="item">
          <span className="k">Nodes online</span>
          <span className="v">{overview?.online_count ?? 0}/{overview?.node_count ?? 0}</span>
        </div>
        <div className="item">
          <span className="k">ML model</span>
          <span className="v">{ml.risk_ready ? "Ready" : "Cold"}</span>
        </div>
        <button className="btn" onClick={onRetrain} title="Force ML retrain">Retrain ML</button>
        <div className={`conn ${connClass}`}>
          <span className="dot" /> {connLabel}
        </div>
      </div>
    </header>
  );
}
