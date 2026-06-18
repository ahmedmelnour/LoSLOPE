"""Pydantic request/response models."""
from pydantic import BaseModel, Field


class ReadingIn(BaseModel):
    """Payload the base station POSTs to /api/ingest.

    Field aliases match the compact keys produced from the LoRa packet
    `L,<id>,<seq>,<tiltDev>,<tiltRate>,<soil>,<soilRate>,<vib>,<ttc>,<lvl>`
    plus `rssi` added by the base station.
    """
    id: int = Field(..., description="node id")
    seq: int = 0
    tiltDev: float = 0.0
    tiltRate: float = 0.0
    soil: float = 0.0
    soilRate: float = 0.0
    vib: int = 0
    ttc: float = -1.0
    lvl: int = 0
    rssi: float | None = None


class NodeIn(BaseModel):
    id: int
    name: str
    latitude: float | None = None
    longitude: float | None = None
    install_date: str | None = None
    notes: str | None = None


class NodeUpdate(BaseModel):
    name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    install_date: str | None = None
    notes: str | None = None
