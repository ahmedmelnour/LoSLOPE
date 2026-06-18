"""HiveMQ / MQTT ingestor.

Subscribes to the broker the base station publishes to, and runs every received
message through the same ingest core as the HTTP route. New readings are pushed
to dashboard WebSocket clients by scheduling the broadcast coroutine onto the
FastAPI event loop (paho callbacks run in their own thread).
"""
import asyncio
import json
import ssl
import uuid

import paho.mqtt.client as mqtt

from . import config
from .ingest import ingest_reading
from .schemas import ReadingIn


class MqttIngestor:
    def __init__(self):
        self.client: mqtt.Client | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._broadcast = None
        self.connected = False

    def start(self, loop, broadcast):
        if not config.MQTT_ENABLED:
            print("[mqtt] disabled (set MQTT_HOST to enable)")
            return
        self._loop = loop
        self._broadcast = broadcast

        # Unique client id so multiple backends (e.g. local + Render) don't
        # kick each other off the broker by reusing the same id.
        c = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"loslope-backend-{uuid.uuid4().hex[:8]}",
        )
        if config.MQTT_USER:
            c.username_pw_set(config.MQTT_USER, config.MQTT_PASS)
        if config.MQTT_TLS:
            c.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)  # HiveMQ Cloud = valid certs
        c.on_connect = self._on_connect
        c.on_message = self._on_message
        c.on_disconnect = self._on_disconnect
        self.client = c
        try:
            c.connect(config.MQTT_HOST, config.MQTT_PORT, keepalive=60)
            c.loop_start()
            print(f"[mqtt] connecting to {config.MQTT_HOST}:{config.MQTT_PORT} "
                  f"topic={config.MQTT_TOPIC}")
        except Exception as e:
            print(f"[mqtt] connect failed: {e}")

    def stop(self):
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass

    # --- callbacks (run in paho's network thread) -------------------------
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        ok = not getattr(reason_code, "is_failure", reason_code != 0)
        if ok:
            self.connected = True
            client.subscribe(config.MQTT_TOPIC, qos=1)
            print(f"[mqtt] connected; subscribed to {config.MQTT_TOPIC}")
        else:
            print(f"[mqtt] connection refused: {reason_code}")

    def _on_disconnect(self, client, userdata, *args):
        self.connected = False
        print("[mqtt] disconnected; paho will auto-reconnect")

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            reading = ReadingIn(**data)
        except Exception as e:
            print(f"[mqtt] dropping bad payload on {msg.topic}: {e}")
            return

        out = ingest_reading(reading)
        if self._loop and self._broadcast:
            asyncio.run_coroutine_threadsafe(
                self._broadcast(
                    {"type": "reading", "data": out, "retrained": out["retrained"]}
                ),
                self._loop,
            )

    def status(self) -> dict:
        return {
            "enabled": config.MQTT_ENABLED,
            "connected": self.connected,
            "host": config.MQTT_HOST,
            "topic": config.MQTT_TOPIC,
        }


mqtt_ingestor = MqttIngestor()
