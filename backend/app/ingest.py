"""Shared ingest core, used by both the HTTP route and the MQTT subscriber.

Keeps a single code path for: validate -> ML enrich -> store -> auto-register
node -> note retrain. WebSocket broadcasting is handled by the caller, since
the HTTP and MQTT entry points reach the event loop differently.
"""
from . import alerts, db
from .ml import pipeline
from .schemas import ReadingIn


def reading_to_packet(reading: ReadingIn) -> dict:
    """Map the validated aliased payload to DB column names."""
    return {
        "node_id": reading.id,
        "seq": reading.seq,
        "ts": db.utcnow_iso(),
        "tilt_dev": reading.tiltDev,
        "tilt_rate": reading.tiltRate,
        "soil": reading.soil,
        "soil_rate": reading.soilRate,
        "vib": reading.vib,
        "ttc": reading.ttc,
        "lvl": reading.lvl,
        "rssi": reading.rssi,
    }


def ingest_reading(reading: ReadingIn) -> dict:
    """Enrich, store, auto-register the node, and note a possible retrain.

    Returns a dict describing the stored+enriched reading plus a `retrained`
    flag, ready to be broadcast over WebSocket by the caller.
    """
    packet = reading_to_packet(reading)

    enrichment = pipeline.enrich(packet)
    packet["anomaly"] = enrichment["anomaly"]
    packet["risk"] = enrichment["risk"]
    row_id = db.insert_reading(packet)

    # Auto-register an unknown node so its readings are not orphaned.
    if db.get_node(packet["node_id"]) is None:
        db.create_node({
            "id": packet["node_id"],
            "name": f"Node {packet['node_id']}",
            "latitude": None, "longitude": None,
            "install_date": db.utcnow_iso()[:10], "notes": "auto-registered",
        })

    retrained = pipeline.note_new_reading()
    out = {**packet, "id": row_id, **enrichment, "retrained": retrained}

    # Fire a Telegram alert on WARNING/CRITICAL (non-blocking; no-op if unset).
    alerts.maybe_alert(out)
    return out
