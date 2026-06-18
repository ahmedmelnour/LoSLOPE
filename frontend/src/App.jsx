import { useEffect, useMemo, useState } from "react";
import { api, levelName } from "./api";
import { useLiveData, usePolledData } from "./useLiveData";
import Header from "./components/Header";
import MapView from "./components/MapView";
import NodeCard from "./components/NodeCard";
import TrendCharts from "./components/TrendCharts";
import AlertLog from "./components/AlertLog";

export default function App() {
  const { conn, tick, lastReading } = useLiveData();
  const [editMode, setEditMode] = useState(false);
  const [selectedId, setSelectedId] = useState(null);

  // System overview drives the header, map, and node cards.
  const { data: overview } = usePolledData(api.overview, [], tick);
  const { data: alerts } = usePolledData(() => api.alerts(100), [], tick);

  const summaries = overview?.nodes ?? [];
  const nodes = summaries.map((s) => s.node);

  // Default the chart selection to the first node.
  useEffect(() => {
    if (selectedId == null && nodes.length) setSelectedId(nodes[0].id);
  }, [nodes, selectedId]);

  // Readings + forecast for the selected node (chart panel).
  const { data: readings } = usePolledData(
    () => (selectedId != null ? api.readings(selectedId) : Promise.resolve([])),
    [selectedId], tick
  );
  const { data: nodeStatus } = usePolledData(
    () => (selectedId != null ? api.nodeStatus(selectedId) : Promise.resolve(null)),
    [selectedId], tick
  );

  // forecast per node for the cards (status calls would be N requests; we
  // reuse the selected node's forecast and let cards show the firmware ttc).
  const forecastById = useMemo(() => {
    const m = {};
    if (nodeStatus?.node) m[nodeStatus.node.id] = nodeStatus.forecast;
    return m;
  }, [nodeStatus]);

  const nodeName = (id) => nodes.find((n) => n.id === id)?.name || `Node ${id}`;

  const handleRetrain = async () => {
    await api.retrain();
  };

  return (
    <div className="app">
      <Header overview={overview} conn={conn} onRetrain={handleRetrain} />

      {lastReading && (
        <div className="edit-banner" style={{ display: "none" }}>{/* hook for debug */}</div>
      )}

      <div className="layout">
        <div className="col">
          <MapView
            summaries={summaries}
            editMode={editMode}
            onToggleEdit={() => setEditMode((e) => !e)}
            onCreate={(n) => api.createNode(n)}
            onUpdate={(id, f) => api.updateNode(id, f)}
            onDelete={(id) => api.deleteNode(id)}
          />
          <TrendCharts
            nodes={nodes}
            selectedId={selectedId}
            onSelect={setSelectedId}
            readings={readings ?? []}
            forecast={nodeStatus?.forecast}
          />
        </div>

        <div className="col">
          <div className="panel">
            <div className="panel-head">
              <span>Live Node Status</span>
              <span className="muted" style={{ fontSize: 12 }}>
                {overview ? `System: ${levelName(overview.worst_level)}` : ""}
              </span>
            </div>
            <div className="panel-body">
              {summaries.length === 0 ? (
                <div className="empty">No nodes yet. Use “Add / Edit Nodes” on the map.</div>
              ) : (
                <div className="cards">
                  {summaries.map((s) => (
                    <NodeCard key={s.node.id} summary={s} forecast={forecastById[s.node.id]} />
                  ))}
                </div>
              )}
            </div>
          </div>

          <AlertLog alerts={alerts} nodeName={nodeName} />
        </div>
      </div>
    </div>
  );
}
