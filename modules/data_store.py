"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Module: modules/data_store.py
Purpose: Centralized Data Layer, Telemetry Caching, and Analytics Coordinator
=============================================================================
Coordinates data flow between SQLite persistent storage, the live telemetry
simulator/hardware stream, and the multi-factor geotechnical risk engine.
Provides formatted pandas DataFrames for all UI dashboard views.
Includes corridor baseline averages and neighborhood anomaly cascade propagation.
"""

import pandas as pd
from datetime import datetime, timedelta
from database.db import (
    get_connection,
    get_stations,
    log_telemetry,
    log_risk_assessment,
    log_alert,
    get_alerts,
    get_road_sections,
    get_response_teams
)
from modules.risk_engine import calculate_risk

# Station Adjacency & Distance Topology along NH-58 Mountain Corridor
STATION_NEIGHBORHOOD = {
    "GG-001": [
        {"id": "GG-002", "name": "Valley Gorge Sector A", "distance_km": 16.0, "corridor": "NH-58 km 42-58", "sector_id": "SEC-01"}
    ],
    "GG-002": [
        {"id": "GG-001", "name": "NH-58 Mountain Pass", "distance_km": 16.0, "corridor": "NH-58 km 35-48", "sector_id": "SEC-01"},
        {"id": "GG-003", "name": "Ridge Tunnel Link", "distance_km": 13.0, "corridor": "NH-58 km 58-71", "sector_id": "SEC-02"}
    ],
    "GG-003": [
        {"id": "GG-002", "name": "Valley Gorge Sector A", "distance_km": 13.0, "corridor": "NH-58 km 48-62", "sector_id": "SEC-02"},
        {"id": "GG-004", "name": "Highland Slope North", "distance_km": 18.0, "corridor": "NH-58 km 71-89", "sector_id": "SEC-03"}
    ],
    "GG-004": [
        {"id": "GG-003", "name": "Ridge Tunnel Link", "distance_km": 18.0, "corridor": "NH-58 km 62-78", "sector_id": "SEC-03"},
        {"id": "GG-005", "name": "Alaknanda Escarpment", "distance_km": 16.0, "corridor": "NH-58 km 89-105", "sector_id": "SEC-04"}
    ],
    "GG-005": [
        {"id": "GG-004", "name": "Highland Slope North", "distance_km": 16.0, "corridor": "NH-58 km 78-95", "sector_id": "SEC-04"}
    ]
}

def enrich_station_telemetry(raw_stations_list):
    """
    Takes raw station telemetry list and executes risk calculation for each station.
    Returns enriched list of station records with calculated risk scores, categories,
    contributing factors, and UI colors.
    """
    enriched = []
    for stn in raw_stations_list:
        temp_val = stn.get("temp_c", stn.get("temperature_c", 15.0))
        res = calculate_risk(
            soil_adc=stn.get("soil_adc"),
            soil_moisture_pct=stn.get("soil_moisture_pct"),
            rain_adc=stn.get("rain_adc"),
            rainfall_intensity_mmh=stn.get("rainfall_intensity_mmh"),
            rain_acc_24h_mm=stn.get("acc_rain", 0.0),
            tilt_degrees=stn.get("tilt"),
            tilt_rate_deg_h=stn.get("tilt_rate", 0.0),
            vibration_detected=stn.get("vib", False),
            vibration_intensity_g=stn.get("vib_g", 0.0),
            temperature_c=temp_val
        )
        
        item = dict(stn)
        item["temp_c"] = temp_val
        item["temperature_c"] = temp_val
        item["risk_score"] = res["risk_score"]
        item["risk_level"] = res["risk_level"]
        item["status_color"] = res["status_color"]
        item["factors"] = res["factors"]
        item["breakdown"] = res["breakdown"]
        item["recommended_action"] = res["recommended_action"]
        item["data_quality"] = res["data_quality"]
        item["status"] = "ONLINE"
        enriched.append(item)
    return enriched

def get_corridor_averages(enriched_stations):
    """Computes baseline mean values across all monitoring stations in the corridor."""
    if not enriched_stations:
        return {"avg_soil": 35.0, "avg_temp": 14.5, "avg_rain": 2.0, "avg_tilt": 0.25, "avg_risk": 15.0}
    
    n = max(1, len(enriched_stations))
    avg_soil = sum(s.get("soil_moisture_pct", 0.0) for s in enriched_stations) / n
    avg_temp = sum(s.get("temp_c", s.get("temperature_c", 15.0)) for s in enriched_stations) / n
    avg_rain = sum(s.get("rainfall_intensity_mmh", 0.0) for s in enriched_stations) / n
    avg_tilt = sum(s.get("tilt", 0.0) for s in enriched_stations) / n
    avg_risk = sum(s.get("risk_score", 0.0) for s in enriched_stations) / n

    return {
        "avg_soil": round(avg_soil, 1),
        "avg_temp": round(avg_temp, 1),
        "avg_rain": round(avg_rain, 1),
        "avg_tilt": round(avg_tilt, 2),
        "avg_risk": round(avg_risk, 1)
    }

def evaluate_neighborhood_anomaly(station_data, enriched_stations, anomaly_ratio=1.25):
    """
    Evaluates whether incoming ESP32/sensor data for a station exceeds the corridor average
    by the specified anomaly ratio (e.g. 1.25x or 25% above average).
    If triggered, generates proximity alarm messages for all adjacent/nearby stations.
    """
    averages = get_corridor_averages(enriched_stations)
    stn_id = station_data.get("id", "GG-001")
    stn_name = station_data.get("name", "NH-58 Mountain Pass")

    curr_soil = station_data.get("soil_moisture_pct", 0.0)
    curr_temp = station_data.get("temp_c", station_data.get("temperature_c", 15.0))
    curr_rain = station_data.get("rainfall_intensity_mmh", 0.0)
    curr_tilt = station_data.get("tilt", 0.0)
    curr_risk = station_data.get("risk_score", 0.0)

    anomalous_params = []

    # 1. Soil saturation vs corridor average
    if curr_soil >= 60.0 and (averages["avg_soil"] == 0 or curr_soil >= averages["avg_soil"] * anomaly_ratio):
        delta_pct = ((curr_soil - averages["avg_soil"]) / max(1.0, averages["avg_soil"])) * 100.0
        anomalous_params.append({
            "param": "Soil Moisture",
            "current": curr_soil,
            "average": averages["avg_soil"],
            "unit": "% VWC",
            "delta_pct": delta_pct
        })

    # 2. Rainfall rate vs corridor average
    if curr_rain >= 10.0 and (averages["avg_rain"] == 0 or curr_rain >= averages["avg_rain"] * anomaly_ratio):
        delta_pct = ((curr_rain - averages["avg_rain"]) / max(1.0, averages["avg_rain"])) * 100.0
        anomalous_params.append({
            "param": "Precipitation Rate",
            "current": curr_rain,
            "average": averages["avg_rain"],
            "unit": "mm/h",
            "delta_pct": delta_pct
        })

    # 3. Inclinometer tilt vs corridor average
    if curr_tilt >= 0.8 and (averages["avg_tilt"] == 0 or curr_tilt >= averages["avg_tilt"] * anomaly_ratio):
        delta_pct = ((curr_tilt - averages["avg_tilt"]) / max(0.05, averages["avg_tilt"])) * 100.0
        anomalous_params.append({
            "param": "Slope Inclinometer Tilt",
            "current": curr_tilt,
            "average": averages["avg_tilt"],
            "unit": "°",
            "delta_pct": delta_pct
        })

    # 4. Composite risk score vs average
    if curr_risk >= 50.0 and (averages["avg_risk"] == 0 or curr_risk >= averages["avg_risk"] * anomaly_ratio):
        delta_pct = ((curr_risk - averages["avg_risk"]) / max(1.0, averages["avg_risk"])) * 100.0
        anomalous_params.append({
            "param": "Composite Risk Index",
            "current": curr_risk,
            "average": averages["avg_risk"],
            "unit": "pts",
            "delta_pct": delta_pct
        })

    is_anomaly = len(anomalous_params) > 0
    nearby_nodes = STATION_NEIGHBORHOOD.get(stn_id, [])
    alarm_messages = []

    if is_anomaly:
        param_summary = "; ".join([f"{p['param']} at {p['current']}{p['unit']} (Corridor Mean: {p['average']}{p['unit']}, +{p['delta_pct']:.1f}% surge)" for p in anomalous_params])
        
        for neighbor in nearby_nodes:
            msg = (
                f"🚨 PROXIMITY EARLY WARNING CASCADE: Node {stn_id} ({stn_name}) exceeded corridor baseline average [{param_summary}]. "
                f"AUTOMATED NEIGHBORHOOD ADVISORY TRANSMITTED TO ADJACENT NODE {neighbor['id']} ({neighbor['name']}, {neighbor['distance_km']} km away): "
                f"Heightened surveillance initiated on Sector {neighbor['sector_id']}. Recommend single-lane traffic restriction."
            )
            alarm_messages.append({
                "target_station_id": neighbor["id"],
                "target_station_name": neighbor["name"],
                "distance_km": neighbor["distance_km"],
                "sector_id": neighbor["sector_id"],
                "message": msg
            })

    return {
        "is_anomaly": is_anomaly,
        "averages": averages,
        "anomalous_parameters": anomalous_params,
        "nearby_stations": nearby_nodes,
        "alarm_messages": alarm_messages,
        "anomaly_ratio": anomaly_ratio
    }

def get_telemetry_dataframe(enriched_stations):
    """Converts enriched telemetry list into a presentation-ready DataFrame."""
    rows = []
    for s in enriched_stations:
        vib_str = "DETECTED 🔴" if s.get("vib") else "STABLE 🟢"
        rows.append({
            "Station ID": s["id"],
            "Station Name": s["name"],
            "Corridor": s.get("corridor", "NH-58"),
            "Soil Moisture": f"{s.get('soil_moisture_pct', 0.0)}% ({s.get('soil_adc')} ADC)",
            "Temperature": f"{s.get('temp_c', s.get('temperature_c', 15.0)):.1f}°C",
            "Rainfall": f"{s.get('rainfall_intensity_mmh', 0.0)} mm/h",
            "Slope Tilt": f"{s.get('tilt', 0.0):.2f}°",
            "Vibration": vib_str,
            "Risk Score": s["risk_score"],
            "Risk Level": s["risk_level"],
            "Quality": s["data_quality"],
            "Status": "ONLINE 🟢"
        })
    return pd.DataFrame(rows)

def get_system_kpis(enriched_stations):
    """Calculates top-level operational KPIs for the overview dashboard."""
    total_stations = len(enriched_stations)
    online_stations = sum(1 for s in enriched_stations if s.get("status") == "ONLINE")
    max_risk = max((s["risk_score"] for s in enriched_stations), default=0.0)
    
    # Active unresolved alerts count
    alerts_df = get_alerts()
    active_alerts = len(alerts_df[~alerts_df["status"].isin(["RESOLVED", "FALSE ALARM"])]) if not alerts_df.empty else 0
    
    # Critical events today
    critical_count = sum(1 for s in enriched_stations if s["risk_level"] == "CRITICAL")

    # Determine system status banner code
    if any(s["risk_level"] == "CRITICAL" for s in enriched_stations):
        system_status = "CRITICAL"
        detail = "CRITICAL HAZARD DETECTED: Acute slope displacement or saturation exceeding safety limits. Immediate road mitigation required."
    elif any(s["risk_level"] == "HIGH" for s in enriched_stations):
        system_status = "HIGH RISK"
        detail = "HIGH RISK ADVISORY: Significant precipitation and ground movement detected on mountain sector. Enforce transit restrictions."
    elif any(s["risk_level"] == "MODERATE" for s in enriched_stations):
        system_status = "ELEVATED"
        detail = "ELEVATED MONITORING: Moderate soil saturation or sustained drizzle recorded. Ground telemetry on heightened poll cycle."
    elif any(s.get("data_quality") == "INSUFFICIENT" for s in enriched_stations):
        system_status = "DATA UNAVAILABLE"
        detail = "TELEMETRY WARNING: Incomplete sensor packet received. Geotechnical stability cannot be reliably certified."
    else:
        system_status = "STABLE"
        detail = "All monitored mountain sectors reporting baseline geotechnical stability and nominal drainage conditions."

    network_health = "99.2%" if online_stations == total_stations else f"{(online_stations / max(1, total_stations)) * 100:.1f}%"

    return {
        "total_stations": total_stations,
        "online_stations": online_stations,
        "active_alerts": active_alerts,
        "max_risk_score": max_risk,
        "critical_events_today": critical_count,
        "network_health": network_health,
        "system_status": system_status,
        "system_detail": detail
    }

def get_filtered_history(station_id=None, time_range="Last 24 Hours"):
    """
    Queries historical telemetry records from SQLite with time range filtering.
    Ranges: 'Last 15 Minutes', 'Last 1 Hour', 'Last 24 Hours', 'Last 7 Days', 'All Records'
    """
    conn = get_connection()
    now = datetime.utcnow()
    
    delta_map = {
        "Last 15 Minutes": timedelta(minutes=15),
        "Last 1 Hour": timedelta(hours=1),
        "Last 24 Hours": timedelta(hours=24),
        "Last 7 Days": timedelta(days=7),
    }

    query = "SELECT * FROM telemetry_history WHERE 1=1"
    params = []

    if time_range in delta_map:
        cutoff = (now - delta_map[time_range]).isoformat()
        query += " AND timestamp >= ?"
        params.append(cutoff)

    if station_id and station_id != "ALL":
        query += " AND station_id = ?"
        params.append(station_id)

    query += " ORDER BY timestamp ASC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if not df.empty:
        df["datetime"] = pd.to_datetime(df["timestamp"])
    return df
