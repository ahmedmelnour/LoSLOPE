# LoSLOPE — Landslide Slope Monitoring & Early-Warning Dashboard

Full-stack dashboard for the **LoSLOPE** IoT system (UTM engineering final
project). Field nodes (ESP32 DevKit V1) read slope sensors and transmit over
**LoRa 433 MHz** to a base station (**XIAO ESP32-S3**), which forwards readings
to this dashboard's backend — over **MQTT (HiveMQ Cloud)** as the primary path,
or plain HTTP on the LAN.

```
[ESP32 field nodes] --LoRa 433MHz--> [XIAO ESP32-S3 base]
                                            |  publish (MQTT/TLS 8883)
                                            v
                                   [HiveMQ Cloud broker]
                                            |  subscribe
                                            v
        SQLite + scikit-learn  <----  [FastAPI backend]  ----> serves built React SPA
        (anomaly/risk/forecast)             |  WebSocket / REST
                                            v
                          [browser dashboard]  (local, or public via Cloudflare Tunnel)
```

Two transport options for getting readings into the backend:
- **MQTT via HiveMQ Cloud** (recommended, works from any network): the base
  station *publishes* to your broker; the backend *subscribes*. No
  port-forwarding, no firewall rule — both ends connect outbound.
- **HTTP POST on the LAN** (`/api/ingest`): direct, but only works while the
  ESP and the backend share a network.

## Features

- **FastAPI + SQLite** backend: ingest, history, node CRUD, per-node status.
- **Machine learning** (`backend/app/ml/`):
  - *Anomaly detection* — per-node `IsolationForest` over
    `[tiltDev, tiltRate, soil, soilRate, vib]`, score 0–1.
  - *Risk classification* — `RandomForest` trained on real + **synthetic**
    threshold-spanning samples, output continuous **risk score 0–100**.
  - *Short-term forecast* — linear regression projecting tilt/soil 15/30/60 min
    ahead and an **ML time-to-critical** compared to the firmware's estimate.
  - Auto-retrains every `N` readings; `/api/ml/retrain` endpoint; models
    persisted to `backend/models/*.joblib`.
- **React + Vite** dashboard: Leaflet/OSM map with editable node locations,
  live per-node cards (risk gauge, anomaly badge, forecast TTC), Recharts trend
  charts with threshold lines + forecast overlay, and an alert log.
- **Live updates** over WebSocket, with automatic **5 s polling fallback**.

---

## 1. Backend

Requires **Python 3.11+** (developed/tested on 3.11 and 3.14).

```powershell
cd dashboard\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate           # macOS / Linux
pip install -r requirements.txt
```

### Seed demo data (recommended first run)

Inserts 4 demo nodes at Malaysian slope coordinates near UTM Skudai plus ~6 h
of synthetic readings (node 3 escalates to CRITICAL), then trains the models:

```powershell
python seed.py
python -c "from app.ml import pipeline; pipeline.retrain()"
```

### Run the API

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API docs (Swagger): http://localhost:8000/docs
- Use `--host 0.0.0.0` so the XIAO base station on your LAN can reach it.
- If the frontend has been built (`npm run build`), the backend also serves the
  dashboard itself at http://localhost:8000 — handy for exposing one port.

### Connect HiveMQ (MQTT data path)

Copy `.env.example` to `.env` and fill in your HiveMQ Cloud cluster details:

```
MQTT_HOST=abcd1234.s1.eu.hivemq.cloud
MQTT_PORT=8883
MQTT_USER=your_broker_username
MQTT_PASS=your_broker_password
MQTT_TOPIC=loslope/readings
MQTT_TLS=true
```

On the next start, the backend connects to the broker and ingests every reading
the base station publishes (look for `[mqtt] connected; subscribed to ...` in
the log; MQTT health also appears in `GET /api/overview`). Leave `MQTT_HOST`
blank to disable MQTT and use HTTP only.

### Optional: live feed simulator

Streams fresh readings so nodes show **online** and the dashboard updates live
without hardware:

```powershell
python simulate.py --interval 2 --escalate 3   # drive node 3 toward CRITICAL
```

> Nodes are marked **offline** if no reading arrives within 60 s, so run the
> simulator (or the real base station) to keep them live after seeding.

---

## 2. Frontend

Requires **Node 18+**.

```powershell
cd dashboard\frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` and `/ws` to the
backend on port 8000 (see `vite.config.js`).

Production build: `npm run build` → static files in `dist/`. Once built, the
FastAPI backend serves them, so the whole dashboard is reachable on port 8000.

---

## 2b. Put the dashboard online (Cloudflare Tunnel)

To make the site reachable from the internet (e.g. for a demo or your phone),
build the frontend, run the backend, then expose port 8000 with a quick tunnel —
no account, no port-forwarding:

```powershell
cd dashboard\frontend ; npm run build          # backend then serves the SPA
cd ..\backend ; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
cloudflared tunnel --url http://localhost:8000  # prints a https://*.trycloudflare.com URL
```

Open the printed URL. The React app, the `/api` routes, and the `/ws`
WebSocket all run on the same origin, so everything (including live updates)
works through the one tunnel. The URL lives only while `cloudflared` and the
backend are running; for a permanent URL, deploy the backend to a host like
Render/Railway/Fly instead.

> The device data path is independent of the tunnel: with HiveMQ configured,
> the base station keeps publishing to the broker regardless of where the
> dashboard is hosted.

---

## 3. API reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ingest` | Ingest one reading from the base station |
| GET | `/api/readings?node_id=&from=&to=` | Historical readings (charts) |
| GET | `/api/nodes` | List nodes |
| POST | `/api/nodes` | Create a node |
| PUT | `/api/nodes/{id}` | Update a node (location, name, notes) |
| DELETE | `/api/nodes/{id}` | Delete a node |
| GET | `/api/nodes/{id}/status` | Latest reading + ML risk + online/offline + forecast |
| GET | `/api/overview` | System-wide status (worst level, per-node summary) |
| GET | `/api/alerts?limit=` | WARNING/CRITICAL alert log |
| POST | `/api/ml/retrain` | Force a model retrain |
| GET | `/api/ml/status` | Model status |
| WS | `/ws` | Live reading push |

### `POST /api/ingest` example payload

```json
{
  "id": 3,
  "seq": 1024,
  "tiltDev": 7.2,
  "tiltRate": 1.4,
  "soil": 88.0,
  "soilRate": 3.1,
  "vib": 8,
  "ttc": 4.0,
  "lvl": 3,
  "rssi": -91
}
```

Field meaning: `id` node id · `seq` sequence · `tiltDev` tilt deviation (°) ·
`tiltRate` °/min · `soil` saturation % (high = wet/dangerous) · `soilRate` %/min
· `vib` vibration events / 10 s · `ttc` firmware minutes-to-critical (`-1` none)
· `lvl` 0 NORMAL / 1 WATCH / 2 WARNING / 3 CRITICAL · `rssi` LoRa dBm.

### curl test

```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"id":3,"seq":1024,"tiltDev":7.2,"tiltRate":1.4,"soil":88.0,"soilRate":3.1,"vib":8,"ttc":4.0,"lvl":3,"rssi":-91}'
```

PowerShell:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/ingest -Method Post `
  -ContentType "application/json" `
  -Body '{"id":3,"seq":1024,"tiltDev":7.2,"tiltRate":1.4,"soil":88.0,"soilRate":3.1,"vib":8,"ttc":4.0,"lvl":3,"rssi":-91}'
```

Response includes the ML enrichment:

```json
{ "status": "ok", "id": 2881, "anomaly": 0.80, "risk": 100.0,
  "risk_level": 3, "risk_probabilities": {"0":0,"1":0,"2":0,"3":1.0}, "retrained": false }
```

---

## 4. Base station firmware (XIAO ESP32-S3)

`firmware/base_station_post.ino` contains an `HTTPClient` + `ArduinoJson` helper
`postReading(...)` plus a call site to paste into your existing base station
`loop()` right after `parsePacket()`. Set `WIFI_SSID`, `WIFI_PASSWORD`, and
`INGEST_URL` (the backend machine's LAN IP, e.g.
`http://192.168.1.42:8000/api/ingest`).

---

## 5. Deploy online for free (Render, from GitHub)

The repo ships a multi-stage `Dockerfile` (builds the frontend, runs the backend
that serves it) and a `render.yaml` Blueprint, so the whole app runs as one free
Render web service. Because the backend **subscribes to HiveMQ**, your physical
base station feeds the cloud dashboard with no port-forwarding or PC required.

1. **Push to GitHub** (one time):
   ```powershell
   # create an empty repo on github.com first (no README), then:
   git remote add origin https://github.com/<your-username>/loslope.git
   git push -u origin main
   ```
2. **Create the Render service:** Render → **New > Blueprint** → connect the repo.
   It reads `render.yaml` and prompts for the secret env vars — enter your
   **MQTT_HOST**, **MQTT_USER**, **MQTT_PASS** (HiveMQ cluster + credentials).
3. Render builds the image and gives you a stable URL like
   `https://loslope-xxxx.onrender.com`. Pushing to `main` auto-redeploys.

**Free-tier notes:**
- The service **sleeps after ~15 min idle** and cold-starts (~30–60 s) on the
  next visit. `AUTO_SEED=true` reseeds an empty DB so it's always populated.
- The SQLite DB + trained models live on an **ephemeral disk** — they reset on
  each redeploy/restart (fine for a demo; add a paid disk or external DB for
  permanent history).
- Secrets stay in Render's env settings, never in the repo (`.env` is gitignored).

---

## Project layout

```
dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, routes, WebSocket
│   │   ├── db.py              SQLite layer (nodes, readings)
│   │   ├── schemas.py         Pydantic models
│   │   ├── config.py          thresholds, paths, retrain cadence
│   │   ├── ws.py              WebSocket connection manager
│   │   └── ml/
│   │       ├── pipeline.py    orchestrator + persistence + retrain
│   │       ├── anomaly.py     IsolationForest (per node)
│   │       ├── risk.py        RandomForest risk classifier
│   │       ├── forecast.py    regression + ML time-to-critical
│   │       ├── synthetic.py   synthetic training-sample generator
│   │       └── features.py    feature vector definition
│   ├── seed.py                demo nodes + synthetic readings
│   ├── simulate.py            live feed simulator
│   ├── e2e_test.py            ingest -> WS -> status smoke test
│   └── requirements.txt
├── frontend/                  React + Vite + Leaflet + Recharts
│   └── src/
│       ├── App.jsx
│       ├── api.js, useLiveData.js
│       └── components/        Header, MapView, NodeCard, TrendCharts, AlertLog, RiskGauge
└── firmware/
    └── base_station_post.ino  XIAO ESP32-S3 HTTP POST snippet
```

## End-to-end smoke test

With the backend running:

```powershell
cd dashboard\backend
.\.venv\Scripts\python.exe e2e_test.py
```

Subscribes to the WebSocket, POSTs a CRITICAL reading, and confirms the enriched
reading (anomaly + risk) is broadcast and reflected by `/api/nodes/3/status`.
