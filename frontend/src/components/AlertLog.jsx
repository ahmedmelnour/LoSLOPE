import { levelColor, levelName } from "../api";

const when = (ts) => {
  const d = new Date(ts);
  return d.toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

export default function AlertLog({ alerts, nodeName }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <span>Alert Log</span>
        <span className="muted" style={{ fontSize: 12 }}>WARNING &amp; CRITICAL</span>
      </div>
      <div className="alert-list">
        {(!alerts || alerts.length === 0) ? (
          <div className="empty">No warnings or critical events.</div>
        ) : (
          alerts.map((a) => (
            <div className="alert-item" key={a.id}>
              <div className="bar" style={{ background: levelColor(a.lvl) }} />
              <span className="lvl-tag" style={{ background: levelColor(a.lvl) }}>
                {levelName(a.lvl)}
              </span>
              <span>
                <b>{nodeName(a.node_id)}</b>
                <span className="muted">
                  {" "}— tilt {Number(a.tilt_dev).toFixed(1)}°, soil {Number(a.soil).toFixed(0)}%,
                  vib {a.vib}, risk {a.risk != null ? Math.round(a.risk) : "—"}
                </span>
              </span>
              <span className="when">{when(a.ts)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
