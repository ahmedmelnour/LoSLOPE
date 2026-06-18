"""LoSLOPE FastAPI application.

Routes:
  POST   /api/ingest             ingest a reading from the base station
  GET    /api/readings           historical readings for charts
  GET    /api/nodes              list nodes
  POST   /api/nodes              create a node
  PUT    /api/nodes/{id}         update a node (location, name, notes ...)
  DELETE /api/nodes/{id}         delete a node
  GET    /api/nodes/{id}/status  latest reading + ML + online/offline
  GET    /api/overview           system-wide status for the header
  GET    /api/alerts             WARNING/CRITICAL alert log
  POST   /api/ml/retrain         force a model retrain
  GET    /api/ml/status          model status
  WS     /ws                     live reading push
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dateutil import parser as dtparser
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import config, db
from .config import LEVEL_NAMES, OFFLINE_SECONDS
from .ingest import ingest_reading
from .ml import pipeline
from .mqtt_client import mqtt_ingestor
from .schemas import NodeIn, NodeUpdate, ReadingIn
from .ws import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    # Populate a fresh (e.g. cloud) database so the dashboard isn't empty.
    if config.AUTO_SEED and not db.list_nodes():
        try:
            import seed
            seed.main()
        except Exception as e:
            print(f"[seed] auto-seed skipped: {e}")
    pipeline.load_or_train()
    # Start the HiveMQ subscriber (no-op unless MQTT_HOST is configured),
    # bridging received readings onto this event loop for WS broadcast.
    mqtt_ingestor.start(asyncio.get_running_loop(), manager.broadcast)
    print("[loslope] backend ready")
    yield
    mqtt_ingestor.stop()


app = FastAPI(title="LoSLOPE API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- helpers ---------------------------------------------------------------

def _is_online(ts: str | None) -> bool:
    if not ts:
        return False
    age = (datetime.now(timezone.utc) - dtparser.isoparse(ts)).total_seconds()
    return age <= OFFLINE_SECONDS


# --- ingest ----------------------------------------------------------------
# HTTP path (LAN). The MQTT subscriber uses the same ingest_reading() core.

@app.post("/api/ingest")
async def ingest(reading_in: ReadingIn):
    out = ingest_reading(reading_in)
    await manager.broadcast(
        {"type": "reading", "data": out, "retrained": out["retrained"]}
    )
    return {"status": "ok", **out}


# --- readings --------------------------------------------------------------

# `from` is a Python keyword, so the query param is bound via an alias.
@app.get("/api/readings")
def readings(node_id: int | None = None,
             frm: str | None = Query(None, alias="from"),
             to: str | None = Query(None, alias="to")):
    return db.get_readings(node_id, frm, to)


# --- nodes -----------------------------------------------------------------

@app.get("/api/nodes")
def get_nodes():
    return db.list_nodes()


@app.post("/api/nodes")
def post_node(node: NodeIn):
    if db.get_node(node.id):
        raise HTTPException(409, f"Node {node.id} already exists")
    return db.create_node(node.model_dump())


@app.put("/api/nodes/{node_id}")
def put_node(node_id: int, update: NodeUpdate):
    if db.get_node(node_id) is None:
        raise HTTPException(404, "Node not found")
    fields = {k: v for k, v in update.model_dump().items() if v is not None}
    return db.update_node(node_id, fields)


@app.delete("/api/nodes/{node_id}")
def remove_node(node_id: int):
    if db.get_node(node_id) is None:
        raise HTTPException(404, "Node not found")
    db.delete_node(node_id)
    return {"status": "deleted", "id": node_id}


@app.get("/api/nodes/{node_id}/status")
def node_status(node_id: int):
    node = db.get_node(node_id)
    if node is None:
        raise HTTPException(404, "Node not found")
    latest = db.latest_reading(node_id)
    online = _is_online(latest["ts"]) if latest else False
    forecast = pipeline.forecast_for_node(node_id) if latest else {"ready": False}
    risk = pipeline.risk.predict(latest) if latest else {"risk": 0.0, "level": 0}
    return {
        "node": node,
        "online": online,
        "latest": latest,
        "risk": risk,
        "forecast": forecast,
    }


# --- system overview & alerts ---------------------------------------------

@app.get("/api/overview")
def overview():
    nodes = db.list_nodes()
    worst = 0
    online_count = 0
    summaries = []
    for node in nodes:
        latest = db.latest_reading(node["id"])
        online = _is_online(latest["ts"]) if latest else False
        if online:
            online_count += 1
        lvl = latest["lvl"] if (latest and online) else 0
        worst = max(worst, lvl)
        summaries.append({
            "node": node,
            "online": online,
            "latest": latest,
        })
    return {
        "worst_level": worst,
        "worst_level_name": LEVEL_NAMES[worst],
        "node_count": len(nodes),
        "online_count": online_count,
        "nodes": summaries,
        "ml": pipeline.status(),
        "mqtt": mqtt_ingestor.status(),
    }


@app.get("/api/alerts")
def alerts(limit: int = 200):
    return db.alert_log(limit)


# --- ML control ------------------------------------------------------------

@app.post("/api/ml/retrain")
def ml_retrain():
    return pipeline.retrain()


@app.get("/api/ml/status")
def ml_status():
    return pipeline.status()


# --- WebSocket -------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # We don't expect client messages; keep the socket alive.
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:
        await manager.disconnect(ws)


# --- health + frontend serving --------------------------------------------
# When the frontend has been built (`npm run build`), FastAPI serves it so a
# single port (and therefore a single tunnel) exposes the whole dashboard.

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "LoSLOPE API"}


if config.FRONTEND_DIST.exists():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    _assets = config.FRONTEND_DIST / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/")
    def spa_index():
        return FileResponse(config.FRONTEND_DIST / "index.html")

    # SPA fallback: serve real static files, otherwise index.html. Registered
    # last so it never shadows /api/* or /ws.
    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        candidate = config.FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(config.FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    def root():
        return {"service": "LoSLOPE API", "docs": "/docs",
                "note": "frontend not built; run `npm run build` to serve it here"}
