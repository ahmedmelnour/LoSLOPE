"""Publish one reading to HiveMQ to verify the MQTT -> backend path.

Acts as the base station would. Reads broker creds from the same .env the
backend uses. Run while the backend is running:  python mqtt_test.py
"""
import json
import ssl
import time

import paho.mqtt.client as mqtt

from app import config

payload = {
    "id": 1, "seq": 7001, "tiltDev": 6.8, "tiltRate": 1.2,
    "soil": 84.0, "soilRate": 2.6, "vib": 7, "ttc": 5.0, "lvl": 3, "rssi": -88,
}

done = {"published": False}


def on_connect(client, userdata, flags, reason_code, properties=None):
    print("publisher connected:", reason_code)
    client.publish(config.MQTT_TOPIC, json.dumps(payload), qos=1)


def on_publish(client, userdata, mid, *args):
    print(f"published to {config.MQTT_TOPIC}: {payload}")
    done["published"] = True


c = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id="loslope-test-pub")
c.username_pw_set(config.MQTT_USER, config.MQTT_PASS)
c.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
c.on_connect = on_connect
c.on_publish = on_publish
c.connect(config.MQTT_HOST, config.MQTT_PORT, 60)
c.loop_start()

t0 = time.time()
while not done["published"] and time.time() - t0 < 10:
    time.sleep(0.2)
time.sleep(1)
c.loop_stop()
c.disconnect()
print("done." if done["published"] else "FAILED to publish")
