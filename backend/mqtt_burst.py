"""Publish a short burst of readings for all demo nodes via HiveMQ, mimicking
the base station forwarding live LoRa packets. For demos/screenshots."""
import json
import random
import ssl
import time

import paho.mqtt.client as mqtt

from app import config

c = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id="loslope-burst")
c.username_pw_set(config.MQTT_USER, config.MQTT_PASS)
c.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
c.connect(config.MQTT_HOST, config.MQTT_PORT, 60)
c.loop_start()

# Per-node target profiles: (tilt, soil, vib, lvl)
profiles = {
    1: (0.6, 38, 0, 0),    # NORMAL
    2: (2.2, 55, 2, 1),    # WATCH
    3: (6.8, 84, 7, 3),    # CRITICAL
    4: (3.4, 66, 4, 2),    # WARNING
}

for rnd in range(6):
    for nid, (tilt, soil, vib, lvl) in profiles.items():
        payload = {
            "id": nid, "seq": 9000 + rnd,
            "tiltDev": round(tilt + random.uniform(-0.1, 0.1), 3),
            "tiltRate": round(random.uniform(0.02, 0.12), 3),
            "soil": round(soil + random.uniform(-1, 1), 2),
            "soilRate": round(random.uniform(0.1, 0.6), 3),
            "vib": vib, "ttc": (8.0 if lvl >= 2 else -1.0), "lvl": lvl,
            "rssi": round(random.uniform(-100, -72), 1),
        }
        c.publish(config.MQTT_TOPIC, json.dumps(payload), qos=1)
    time.sleep(1)

time.sleep(1)
c.loop_stop()
c.disconnect()
print("burst done")
