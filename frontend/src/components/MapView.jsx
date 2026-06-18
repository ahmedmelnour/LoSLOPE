import { useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { levelColor, levelName } from "../api";

// Colored teardrop marker built from an inline SVG divIcon.
function pinIcon(color, online) {
  const opacity = online ? 1 : 0.45;
  const html = `
    <div style="opacity:${opacity}">
      <svg width="26" height="36" viewBox="0 0 26 36" xmlns="http://www.w3.org/2000/svg">
        <path d="M13 0C5.8 0 0 5.8 0 13c0 9.2 13 23 13 23s13-13.8 13-23C26 5.8 20.2 0 13 0z"
              fill="${color}" stroke="#0e1116" stroke-width="1.5"/>
        <circle cx="13" cy="13" r="5" fill="#0e1116"/>
      </svg>
    </div>`;
  return L.divIcon({
    html, className: "node-pin",
    iconSize: [26, 36], iconAnchor: [13, 36], popupAnchor: [0, -34],
  });
}

function ClickCapture({ onClick }) {
  useMapEvents({ click: (e) => onClick(e.latlng) });
  return null;
}

const fmt = (v, d = 2) => (v == null ? "—" : Number(v).toFixed(d));

export default function MapView({ summaries, editMode, onToggleEdit, onCreate, onUpdate, onDelete }) {
  const center = [1.5587, 103.637]; // UTM Skudai
  const [draft, setDraft] = useState(null); // {id?, name, latitude, longitude, notes}

  const nodesWithGps = summaries.filter((s) => s.node.latitude != null && s.node.longitude != null);

  const handleMapClick = (latlng) => {
    if (!editMode) return;
    setDraft((d) => ({
      id: d?.id,
      name: d?.name || "",
      notes: d?.notes || "",
      latitude: +latlng.lat.toFixed(6),
      longitude: +latlng.lng.toFixed(6),
    }));
  };

  const startEdit = (node) => {
    setDraft({
      id: node.id, name: node.name, notes: node.notes || "",
      latitude: node.latitude, longitude: node.longitude,
    });
  };

  const save = async () => {
    if (draft.id != null) {
      await onUpdate(draft.id, {
        name: draft.name, latitude: draft.latitude,
        longitude: draft.longitude, notes: draft.notes,
      });
    } else {
      const nextId = Math.max(0, ...summaries.map((s) => s.node.id)) + 1;
      await onCreate({
        id: nextId, name: draft.name || `Node ${nextId}`,
        latitude: draft.latitude, longitude: draft.longitude,
        install_date: new Date().toISOString().slice(0, 10), notes: draft.notes,
      });
    }
    setDraft(null);
  };

  return (
    <div className="panel">
      <div className="panel-head">
        <span>Field Node Map</span>
        <button className={`btn ${editMode ? "active" : ""}`} onClick={onToggleEdit}>
          {editMode ? "Done editing" : "Add / Edit Nodes"}
        </button>
      </div>

      {editMode && (
        <div className="edit-banner">
          Click anywhere on the map to place a new node, or click an existing marker’s
          “Edit” button to reposition it.
        </div>
      )}

      <div className="map-wrap">
        <MapContainer center={center} zoom={15} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickCapture onClick={handleMapClick} />

          {nodesWithGps.map(({ node, online, latest }) => {
            const lvl = online && latest ? latest.lvl : 0;
            return (
              <Marker
                key={node.id}
                position={[node.latitude, node.longitude]}
                icon={pinIcon(online ? levelColor(lvl) : "#6b7480", online)}
              >
                <Popup>
                  <div className="map-popup">
                    <b>{node.name}</b> <span style={{ color: levelColor(lvl) }}>
                      ● {online ? levelName(lvl) : "OFFLINE"}
                    </span>
                    <div className="row"><span className="k">Tilt dev</span><span>{fmt(latest?.tilt_dev)}°</span></div>
                    <div className="row"><span className="k">Soil</span><span>{fmt(latest?.soil, 1)}%</span></div>
                    <div className="row"><span className="k">Vibration</span><span>{latest?.vib ?? "—"}</span></div>
                    <div className="row"><span className="k">Risk score</span><span>{fmt(latest?.risk, 0)}</span></div>
                    <div className="row"><span className="k">RSSI</span><span>{fmt(latest?.rssi, 0)} dBm</span></div>
                    {editMode && (
                      <div className="form-actions">
                        <button className="btn" onClick={() => startEdit(node)}>Edit</button>
                        <button className="btn danger" onClick={() => onDelete(node.id)}>Delete</button>
                      </div>
                    )}
                  </div>
                </Popup>
              </Marker>
            );
          })}

          {draft && draft.latitude != null && (
            <Marker position={[draft.latitude, draft.longitude]} icon={pinIcon("#2f81f7", true)} />
          )}
        </MapContainer>
      </div>

      {editMode && draft && (
        <div className="panel-body">
          <div className="field">
            <label>{draft.id != null ? `Editing node ${draft.id}` : "New node name"}</label>
            <input value={draft.name} placeholder="e.g. N5 - West Slope"
              onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          </div>
          <div className="metrics" style={{ marginTop: 0 }}>
            <div className="field">
              <label>Latitude</label>
              <input value={draft.latitude ?? ""} type="number" step="0.000001"
                onChange={(e) => setDraft({ ...draft, latitude: parseFloat(e.target.value) })} />
            </div>
            <div className="field">
              <label>Longitude</label>
              <input value={draft.longitude ?? ""} type="number" step="0.000001"
                onChange={(e) => setDraft({ ...draft, longitude: parseFloat(e.target.value) })} />
            </div>
          </div>
          <div className="field">
            <label>Notes</label>
            <textarea rows={2} value={draft.notes}
              onChange={(e) => setDraft({ ...draft, notes: e.target.value })} />
          </div>
          <div className="form-actions">
            <button className="btn primary" onClick={save}
              disabled={draft.latitude == null || draft.longitude == null}>
              {draft.id != null ? "Save changes" : "Create node"}
            </button>
            <button className="btn" onClick={() => setDraft(null)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
