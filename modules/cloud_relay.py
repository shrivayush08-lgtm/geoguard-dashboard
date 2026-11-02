"""
=============================================================================
GEOGUARD AI — CLOUD IOT TELEMETRY RELAY
Module: modules/cloud_relay.py
Purpose: Bridges physical local ESP32 USB telemetry to the Streamlit Cloud website
=============================================================================
"""

import time
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any

CLOUD_RELAY_ENDPOINT = "https://api.restful-api.dev/objects/ff808181a09d98f701a19b381ba40808"
_LAST_FETCH_TIME = 0.0
_CACHED_PACKET: Optional[Dict[str, Any]] = None


def send_telemetry_to_cloud(packet: Dict[str, Any]) -> bool:
    """
    Pushes a live ESP32 telemetry packet to the public cloud relay channel.
    Called by the local forwarder running on the developer/operator laptop.
    """
    try:
        payload = {
            "name": "GeoGuard_Live_Telemetry",
            "data": {
                "station_id": packet.get("station_id", "GG-002"),
                "soil_moisture_pct": packet.get("soil_moisture_pct", 35.0),
                "soil_adc": packet.get("soil_adc"),
                "temperature_c": packet.get("temperature_c", 15.0),
                "tilt_degrees": packet.get("tilt_degrees", 0.3),
                "vibration_pga": packet.get("vibration_pga", 0.02),
                "rain_intensity_mmh": packet.get("rain_intensity_mmh", 0.0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "forwarded_at": time.time()
            }
        }
        res = requests.put(CLOUD_RELAY_ENDPOINT, json=payload, timeout=2.5)
        return res.status_code == 200
    except Exception:
        return False


def fetch_telemetry_from_cloud(max_age_seconds: float = 60.0) -> Optional[Dict[str, Any]]:
    """
    Retrieves the latest physical telemetry packet from the cloud relay channel.
    Called by Streamlit Cloud when local USB hardware is not physically present.
    Rate-limited to 1 request per 1.5 seconds to conserve latency.
    """
    global _LAST_FETCH_TIME, _CACHED_PACKET
    now = time.time()
    
    # Return cached packet if called within 1.2s to prevent excessive HTTP calls on Streamlit reruns
    if _CACHED_PACKET is not None and (now - _LAST_FETCH_TIME) < 1.2:
        return _CACHED_PACKET

    try:
        res = requests.get(CLOUD_RELAY_ENDPOINT, timeout=2.5)
        _LAST_FETCH_TIME = now
        if res.status_code == 200:
            item = res.json()
            data = item.get("data", {})
            fwd_time = float(data.get("forwarded_at", 0.0))
            age = now - fwd_time
            if age <= max_age_seconds:
                data["is_relay"] = True
                data["relay_age_sec"] = round(age, 1)
                _CACHED_PACKET = data
                return data
    except Exception:
        pass

    return None
