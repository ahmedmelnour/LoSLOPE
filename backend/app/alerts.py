"""Alerting: compose a WARNING/CRITICAL message and push it to Telegram.

Message text comes from Google Gemini (free tier) when GEMINI_API_KEY is set,
otherwise from a deterministic template. The template is also the automatic
fallback whenever Gemini errors, times out, or is rate-limited — so an alert
never fails to go out at the worst possible moment.

Sending happens on a background thread so it never blocks ingest.
"""
import json
import threading
import urllib.request
from datetime import datetime, timezone

from . import config, db
from .config import LEVEL_NAMES

# Per-node alert state for escalation + cooldown: node_id -> (level, ts).
_last_alert: dict[int, tuple[int, datetime]] = {}
_lock = threading.Lock()

_EMOJI = {2: "⚠️", 3: "\U0001f6a8"}  # ⚠️ , 🚨
_ACTION = {
    2: "Monitor closely; prepare to restrict access to the slope.",
    3: "Evacuate the slope area immediately and notify authorities.",
}


def _should_alert(node_id: int, level: int) -> bool:
    """Fire on escalation, or on a repeated CRITICAL past the cooldown."""
    if level < config.ALERT_MIN_LEVEL:
        return False
    now = datetime.now(timezone.utc)
    with _lock:
        prev = _last_alert.get(node_id)
        escalated = prev is None or level > prev[0]
        repeat_crit = (
            level >= 3 and prev is not None
            and (now - prev[1]).total_seconds() >= config.ALERT_COOLDOWN_SECONDS
        )
        if escalated or repeat_crit:
            _last_alert[node_id] = (level, now)
            return True
        # Keep the latest level so a drop-then-rise re-escalates correctly.
        _last_alert[node_id] = (level, prev[1] if prev else now)
        return False


def build_template_alert(out: dict, node_name: str) -> str:
    lvl = int(out.get("lvl", 0))
    emoji = _EMOJI.get(lvl, "")
    lines = [
        f"{emoji} LoSLOPE {LEVEL_NAMES[lvl]} — {node_name}",
        f"Tilt {out.get('tilt_dev', 0):.1f}° (rate {out.get('tilt_rate', 0):.2f}/min)"
        f" · Soil {out.get('soil', 0):.0f}% · Vib {out.get('vib', 0)}",
        f"ML risk {out.get('risk', 0):.0f}/100"
        + (", anomaly detected" if (out.get("anomaly") or 0) >= 0.6 else ""),
    ]
    ttc = out.get("ttc", -1)
    if ttc is not None and ttc >= 0:
        lines.append(f"Forecast: critical in ~{ttc:.0f} min")
    if lvl in _ACTION:
        lines.append(f"→ {_ACTION[lvl]}")
    return "\n".join(lines)


def _gemini_alert(out: dict, node_name: str) -> str | None:
    """Ask Gemini for the alert text; return None on any failure."""
    prompt = (
        "You are an emergency alerting assistant for a landslide early-warning "
        "system. Write a SHORT Telegram alert (2-3 sentences, urgent but clear, "
        "no markdown). Include the node, the key sensor values, the ML risk, and "
        "a concrete recommended action.\n\n"
        f"Node: {node_name}\n"
        f"Alert level: {LEVEL_NAMES[int(out.get('lvl', 0))]}\n"
        f"Tilt deviation: {out.get('tilt_dev')} deg (rate {out.get('tilt_rate')} deg/min)\n"
        f"Soil saturation: {out.get('soil')} %\n"
        f"Vibration events: {out.get('vib')}\n"
        f"ML risk score: {out.get('risk')}/100\n"
        f"Anomaly score: {out.get('anomaly')}\n"
        f"Forecast minutes-to-critical: {out.get('ttc')} (-1 = none)\n"
    )
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 256,
            "temperature": 0.4,
            # 2.5 Flash is a thinking model; disable thinking so the short alert
            # isn't truncated by reasoning tokens (ignored by non-thinking models).
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.load(resp)
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return text or None
    except Exception as e:
        print(f"[alert] Gemini failed ({e}); using template")
        return None


def _send_telegram(text: str) -> None:
    if not config.TELEGRAM_ENABLED:
        print("[alert] Telegram not configured; message:\n" + text)
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    body = json.dumps({"chat_id": config.TELEGRAM_CHAT_ID, "text": text}).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            resp.read()
        print("[alert] Telegram sent")
    except Exception as e:
        print(f"[alert] Telegram send failed: {e}")


def _dispatch(out: dict) -> None:
    node = db.get_node(out["node_id"])
    node_name = node["name"] if node else f"Node {out['node_id']}"
    text = None
    if config.GEMINI_ENABLED:
        text = _gemini_alert(out, node_name)
    if not text:
        text = build_template_alert(out, node_name)
    _send_telegram(text)


def maybe_alert(out: dict) -> None:
    """Entry point from the ingest core. Non-blocking."""
    try:
        level = int(out.get("lvl", 0))
    except (TypeError, ValueError):
        return
    if not _should_alert(out["node_id"], level):
        return
    threading.Thread(target=_dispatch, args=(out,), daemon=True).start()
