/*
 * LoSLOPE — XIAO ESP32-S3 base station: POST a LoRa reading to the dashboard.
 *
 * Paste the helper + the call site into your existing base station firmware.
 * The base station already receives a LoRa packet of the form:
 *     L,<id>,<seq>,<tiltDev>,<tiltRate>,<soil>,<soilRate>,<vib>,<ttc>,<lvl>
 * After parsePacket() has filled your local variables, call
 * postReading(...) to forward them to the FastAPI backend's /api/ingest.
 *
 * Dependencies (Arduino IDE Library Manager):
 *   - WiFi      (bundled with the ESP32 core)
 *   - HTTPClient(bundled with the ESP32 core)
 *   - ArduinoJson by Benoit Blanchon  (v6/v7)
 *
 * No TLS here (plain HTTP on the LAN). For HTTPS use WiFiClientSecure and a
 * root CA / setInsecure().
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ---- Configure these for your network / server ---------------------------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// IP/host of the machine running the dashboard backend (uvicorn on :8000).
// e.g. "http://192.168.1.42:8000/api/ingest"
const char* INGEST_URL    = "http://192.168.1.42:8000/api/ingest";

// --------------------------------------------------------------------------
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi connecting");
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(300);
    Serial.print(".");
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? " connected" : " FAILED");
}

/*
 * Forward one reading to the dashboard. `rssi` is the LoRa packet RSSI you
 * read on the base station (e.g. LoRa.packetRssi()). Returns the HTTP status
 * code, or a negative HTTPClient error code.
 */
int postReading(int id, long seq, float tiltDev, float tiltRate,
                float soil, float soilRate, int vib, float ttc, int lvl,
                int rssi) {
  connectWiFi();
  if (WiFi.status() != WL_CONNECTED) return -1;

  // Build the JSON body — keys match the backend's ReadingIn schema.
  StaticJsonDocument<256> doc;
  doc["id"]       = id;
  doc["seq"]      = seq;
  doc["tiltDev"]  = tiltDev;
  doc["tiltRate"] = tiltRate;
  doc["soil"]     = soil;
  doc["soilRate"] = soilRate;
  doc["vib"]      = vib;
  doc["ttc"]      = ttc;
  doc["lvl"]      = lvl;
  doc["rssi"]     = rssi;

  String body;
  serializeJson(doc, body);

  HTTPClient http;
  http.begin(INGEST_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(4000);
  int code = http.POST(body);
  if (code > 0) {
    Serial.printf("ingest -> HTTP %d: %s\n", code, http.getString().c_str());
  } else {
    Serial.printf("ingest POST failed: %s\n", http.errorToString(code).c_str());
  }
  http.end();
  return code;
}

/* ==========================================================================
 * CALL SITE — paste inside loop() right after you parse a LoRa packet.
 * ==========================================================================
 *
 * void loop() {
 *   int packetSize = LoRa.parsePacket();
 *   if (packetSize) {
 *     String pkt = "";
 *     while (LoRa.available()) pkt += (char)LoRa.read();
 *     int rssi = LoRa.packetRssi();
 *
 *     // ---- parsePacket(): split "L,id,seq,tiltDev,...,lvl" into fields ----
 *     // (use your existing parser; example with sscanf below)
 *     int id, seq, vib, lvl;
 *     float tiltDev, tiltRate, soil, soilRate, ttc;
 *     int n = sscanf(pkt.c_str(), "L,%d,%d,%f,%f,%f,%f,%d,%f,%d",
 *                    &id, &seq, &tiltDev, &tiltRate, &soil, &soilRate,
 *                    &vib, &ttc, &lvl);
 *     if (n == 9) {
 *       postReading(id, seq, tiltDev, tiltRate, soil, soilRate,
 *                   vib, ttc, lvl, rssi);
 *     }
 *   }
 * }
 */
