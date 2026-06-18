// Thin REST client. All paths are proxied to the backend by Vite in dev.
const J = { "Content-Type": "application/json" };

async function req(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`${res.status} ${path}: ${txt}`);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  overview: () => req("/api/overview"),
  alerts: (limit = 200) => req(`/api/alerts?limit=${limit}`),
  nodes: () => req("/api/nodes"),
  nodeStatus: (id) => req(`/api/nodes/${id}/status`),
  readings: (nodeId, from, to) => {
    const p = new URLSearchParams();
    if (nodeId != null) p.set("node_id", nodeId);
    if (from) p.set("from", from);
    if (to) p.set("to", to);
    return req(`/api/readings?${p}`);
  },
  createNode: (node) =>
    req("/api/nodes", { method: "POST", headers: J, body: JSON.stringify(node) }),
  updateNode: (id, fields) =>
    req(`/api/nodes/${id}`, { method: "PUT", headers: J, body: JSON.stringify(fields) }),
  deleteNode: (id) => req(`/api/nodes/${id}`, { method: "DELETE" }),
  retrain: () => req("/api/ml/retrain", { method: "POST" }),
};

export const LEVELS = ["NORMAL", "WATCH", "WARNING", "CRITICAL"];
export const LEVEL_COLORS = ["#2ea043", "#d6b300", "#e8800c", "#e5484d"];
export const levelColor = (lvl) => LEVEL_COLORS[lvl ?? 0] || LEVEL_COLORS[0];
export const levelName = (lvl) => LEVELS[lvl ?? 0] || "NORMAL";
