"""Full online path test:
   publish to HiveMQ  ->  backend subscriber  ->  WS broadcast over the
   public Cloudflare tunnel (wss://...trycloudflare.com/ws).

Usage:  python online_e2e_test.py <tunnel-host>
   e.g.  python online_e2e_test.py sandwich-duck-raising-wellington.trycloudflare.com
"""
import asyncio
import json
import ssl
import sys

import paho.mqtt.client as mqtt
import websockets

from app import config

HOST = sys.argv[1] if len(sys.argv) > 1 else None
if not HOST:
    print("pass the trycloudflare host as arg")
    sys.exit(1)

WS_URL = f"wss://{HOST}/ws"
payload = {"id": 2, "seq": 8002, "tiltDev": 2.1, "tiltRate": 0.4,
           "soil": 58.0, "soilRate": 1.1, "vib": 2, "ttc": 22.0, "lvl": 1, "rssi": -77}


def publish():
    c = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                    client_id="loslope-online-test")
    c.username_pw_set(config.MQTT_USER, config.MQTT_PASS)
    c.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
    c.connect(config.MQTT_HOST, config.MQTT_PORT, 60)
    c.loop_start()
    c.publish(config.MQTT_TOPIC, json.dumps(payload), qos=1)
    import time; time.sleep(1.5)
    c.loop_stop(); c.disconnect()


async def main():
    async with websockets.connect(WS_URL) as ws:
        print("connected to", WS_URL)
        publish()
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(msg)
            if data.get("type") == "reading" and data["data"]["seq"] == 8002:
                d = data["data"]
                print(f"RECEIVED over public WS: node {d['node_id']} seq {d['seq']} "
                      f"risk {d['risk']} anomaly {d['anomaly']}")
                return
    print("did not receive broadcast")


asyncio.run(main())
