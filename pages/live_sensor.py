"""
=============================================================================
GEOGUARD AI — OFF-GRID HIGHWAY LANDSLIDE EARLY WARNING & INTERLOCK SYSTEM
Page: pages/live_sensor.py
Purpose: Live 4-Sensor Telemetry Monitoring, Risk Normalization, Highway
         Interlock Simulation & Automated Dispatch Center
=============================================================================
COMPETITION: Smart India Hackathon (SIH)
CORRIDOR: NH-58 Himalayan Corridor (Rishikesh–Devprayag–Joshimath)

WHERE THIS CODE IS USED:
- Invoked by app.py when the user selects "2. Live Sensor Monitoring" from sidebar.
- Provides real-time ingestion, visualization, and early warning detection for:
  1. Soil Moisture Sensor (% VWC & saturation detection)
  2. Temperature Sensor (°C & freeze-thaw hazard detection)
  3. Slope/Tilt Sensor (° angular displacement & shear movement)
  4. Vibration Sensor (g Peak Ground Acceleration & micro-seismic motion)
- Normalizes raw sensor readings into 0-100 risk scores with configurable weights.
- Calculates Overall Landslide Risk Score = (Soil + Temp + Slope + Vib) / 4.
- Exact Classification:
  * < 40.0: LOW RISK (Green)
  * 40.0 - 70.0: MODERATE RISK (Yellow)
  * > 70.0: CRITICAL DANGER (Red)
- Simulated Highway Interlock Actuation (Boom Barrier, Upstream Traffic Signals).
- Automated Emergency Dispatch Incident Logger & CSV Export.
- 5 Time-series Plotly charts including Composite Risk with 40 and 70 reference lines.
=============================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import math
from datetime import datetime, timezone, timedelta
import plotly.graph_objects as go

from modules.ui import (
    render_slope_cross_section_svg,
    get_plotly_theme,
    render_html,
    COLOR_BLUE,
    COLOR_CYAN,
    COLOR_TEAL,
    COLOR_SAFE,
    COLOR_MODERATE,
    COLOR_HIGH,
    COLOR_CRITICAL,
    COLOR_BORDER
)
from modules.sms_dispatcher import (
    format_landslide_sms_message,
    send_fast2sms,
    check_and_dispatch_automatic_sms
)
from modules.risk_engine import (
    calculate_five_sensor_risk,
    calculate_four_sensor_risk,
    build_four_sensor_risk_gauge,
    normalize_soil_moisture_risk,
    normalize_temperature_risk,
    normalize_slope_tilt_risk,
    normalize_vibration_risk
)
from modules.data_store import (
    get_filtered_history,
    evaluate_neighborhood_anomaly,
    get_corridor_averages,
    STATION_NEIGHBORHOOD
)
from modules.interlock import HighwayInterlockSystem
from database.db import log_alert, get_alerts, get_config


def _hex_to_rgb(hex_code):
    """Converts a hex color code to an R,G,B string for CSS rgba() usage."""
    hex_code = hex_code.lstrip('#')
    if len(hex_code) == 6:
        return f"{int(hex_code[0:2], 16)}, {int(hex_code[2:4], 16)}, {int(hex_code[4:6], 16)}"
    return "56, 189, 248"


def _safe_float(val, default=None):
    """Safely converts a value to float, rejecting NaN, Inf, empty strings, and non-numeric values."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return default
        return float(val)
    if isinstance(val, str):
        val = val.strip()
        if not val or val.upper() in ("NONE", "NULL", "NAN", "INF", "-INF", "N/A", "UNDEFINED"):
            return default
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return default
            return f
        except (ValueError, TypeError):
            return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


def render_sparkline_chart(values, color_hex="#38BDF8", height=52):
    """Generates a compact, minimalist Plotly sparkline without axis clutter."""
    clean_vals = []
    if values:
        for v in values:
            fv = _safe_float(v, 0.0)
            clean_vals.append(fv if fv is not None else 0.0)
    if not clean_vals:
        clean_vals = [0.0] * 5
    elif len(clean_vals) < 5:
        clean_vals = list(clean_vals) + [clean_vals[-1]] * (5 - len(clean_vals))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=clean_vals,
        mode="lines",
        line=dict(color=color_hex, width=2.0),
        fill="tozeroy",
        fillcolor=f"rgba({_hex_to_rgb(color_hex)}, 0.10)",
        hoverinfo="y"
    ))
    fig.update_layout(
        height=height,
        margin=dict(l=2, r=2, t=4, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, showgrid=False, fixedrange=True),
        yaxis=dict(visible=False, showgrid=False, fixedrange=True),
        showlegend=False
    )
    return fig


def render_live_sensor_page(enriched_stations):
    """
    Renders the complete Live Sensor Monitoring dashboard:
    - 4 live sensor telemetry cards with units, status indicators, and sparklines
    - Composite Landslide Risk Gauge (<40 Low, 40-70 Moderate, >70 Critical)
    - Highway Interlock Simulation panel (Barrier, Traffic Signal, Emergency Status)
    - Automated Dispatch Incident Log & CSV export
    - 5 Real-time Plotly charts with reference thresholds
    - Corridor proximity cascade alarms
    """
    # -------------------------------------------------------------------------
    # 1. State Initialization
    # -------------------------------------------------------------------------
    if "is_monitoring" not in st.session_state:
        st.session_state.is_monitoring = True

    if "sensor_weights" not in st.session_state:
        st.session_state.sensor_weights = {
            "soil": 0.25,
            "temperature": 0.25,
            "slope": 0.25,
            "vibration": 0.25
        }

    if "interlock_system" not in st.session_state:
        st.session_state.interlock_system = HighwayInterlockSystem()

    # -------------------------------------------------------------------------
    # 2. Header & Command Bar
    # -------------------------------------------------------------------------
    st.markdown("<div class='hud-eyebrow'>FIELD TELEMETRY & HIGHWAY INTERLOCK</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Live Sensor Monitoring & Landslide Risk Detection</h2>", unsafe_allow_html=True)

    # Top Control Ribbon
    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([2.0, 1.2, 1.3, 1.5])

    with ctrl_col1:
        station_options = [s["id"] for s in enriched_stations]
        station_names = {s["id"]: f"{s['id']} — {s['name']} ({s.get('corridor', 'NH-58')})" for s in enriched_stations}
        default_stn_idx = next((i for i, sid in enumerate(station_options) if sid == "GG-002"), 0)
        selected_id = st.selectbox(
            "Target Sensor Node (ESP32 Stream)",
            station_options,
            index=default_stn_idx,
            format_func=lambda x: station_names.get(x, x),
            key="live_sensor_station_select"
        )

    with ctrl_col2:
        time_window = st.selectbox(
            "History Window",
            ["Last 15 Minutes", "Last 1 Hour", "Last 24 Hours", "Last 7 Days"],
            index=1,
            key="live_sensor_history_window"
        )

    with ctrl_col3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.session_state.is_monitoring:
            if st.button("⏸ PAUSE MONITORING", use_container_width=True, help="Temporarily pause telemetry sampling"):
                st.session_state.is_monitoring = False
                st.rerun()
        else:
            if st.button("▶ RESUME MONITORING", type="primary", use_container_width=True, help="Resume telemetry sampling"):
                st.session_state.is_monitoring = True
                st.rerun()

    with ctrl_col4:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        op_mode = st.session_state.get("operating_mode", "SIMULATION")
        if not st.session_state.is_monitoring:
            conn_html = "<span style='background: rgba(148, 163, 184, 0.12); border: 1px solid #475569; color: #94A3B8; padding: 6px 12px; border-radius: 4px; font-family: monospace; font-size: 11px; font-weight: 600; display: inline-block;'>STANDBY • PAUSED</span>"
        elif op_mode == "HARDWARE":
            gateway = st.session_state.get("serial_gateway")
            is_conn = gateway.is_connected if gateway else False
            hw_source = st.session_state.get("hardware_source")
            if is_conn:
                conn_html = "<span style='background: rgba(16, 185, 129, 0.12); border: 1px solid #10B981; color: #10B981; padding: 6px 12px; border-radius: 4px; font-family: monospace; font-size: 11px; font-weight: 600; display: inline-block;'>● ESP32 SERIAL CONNECTED</span>"
            elif hw_source == "CLOUD_RELAY":
                conn_html = "<span style='background: rgba(16, 185, 129, 0.12); border: 1px solid #10B981; color: #10B981; padding: 6px 12px; border-radius: 4px; font-family: monospace; font-size: 11px; font-weight: 600; display: inline-block;'>● CLOUD IOT RELAY ACTIVE</span>"
            else:
                conn_html = "<span style='background: rgba(56, 189, 248, 0.12); border: 1px solid #38BDF8; color: #38BDF8; padding: 6px 12px; border-radius: 4px; font-family: monospace; font-size: 11px; font-weight: 600; display: inline-block;'>● HARDWARE STANDBY (ACTIVE)</span>"
        else:
            conn_html = "<span style='background: rgba(56, 189, 248, 0.12); border: 1px solid #38BDF8; color: #38BDF8; padding: 6px 12px; border-radius: 4px; font-family: monospace; font-size: 11px; font-weight: 600; display: inline-block;'>● SIMULATION MODE ACTIVE</span>"
        
        st.markdown(f"<div style='text-align: right;'>{conn_html}</div>", unsafe_allow_html=True)

    # Hardware connection diagnostic banner
    gateway = st.session_state.get("serial_gateway")
    if op_mode == "HARDWARE" and gateway and not gateway.is_connected:
        if "locked" in gateway.status_message.lower() or "busy" in gateway.status_message.lower() or "access denied" in gateway.status_message.lower():
            st.error(
                "⚠️ **ESP32 COM Port Locked (Access Denied):** Arduino IDE Serial Monitor or another software currently has COM20 open. "
                "**Please CLOSE the Arduino IDE Serial Monitor window**, then click **'⚡ Connect ESP32'** in the sidebar to stream live geotechnical telemetry."
            )
        elif "failed" in gateway.status_message.lower():
            st.warning(f"⚠️ **Hardware Interface Notice:** {gateway.status_message}")

    with st.expander("📟 View & Copy Matched ESP32 Firmware (Receiver & Transmitter Codes)", expanded=False):
        c_tab1, c_tab2 = st.tabs(["📡 ESP32 Receiver Sketch", "🏔️ ESP32 Transmitter Sketch"])
        with c_tab1:
            try:
                with open(r"C:\Users\ayush srivastav\OneDrive\Documents\Arduino\GeoGuard_Receiver\GeoGuard_Receiver.ino", "r") as f:
                    c_rx = f.read()
            except Exception:
                c_rx = "// Could not read GeoGuard_Receiver.ino"
            st.code(c_rx, language="cpp")
        with c_tab2:
            try:
                with open(r"C:\Users\ayush srivastav\OneDrive\Documents\Arduino\GeoGuard_Transmitter\GeoGuard_Transmitter.ino", "r") as f:
                    c_tx = f.read()
            except Exception:
                c_tx = "// Could not read GeoGuard_Transmitter.ino"
            st.code(c_tx, language="cpp")

    # Locate current station record from existing station-selection logic
    if not enriched_stations:
        st.warning("⚠️ No station telemetry records available.")
        return

    current_stn = next((s for s in enriched_stations if isinstance(s, dict) and s.get("id") == selected_id), enriched_stations[0])
    if not isinstance(current_stn, dict):
        current_stn = {}

    last_update_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Fetch historical readings for charts
    hist_df = get_filtered_history(station_id=selected_id, time_range=time_window)
    if hist_df is None:
        hist_df = pd.DataFrame()

    # Telemetry values with safe numeric conversion
    soil_pct = _safe_float(current_stn.get("soil_moisture_pct"), 42.0)
    soil_adc = int(_safe_float(current_stn.get("soil_adc"), 2150))
    temp_c = _safe_float(current_stn.get("temp_c", current_stn.get("temperature_c")), 14.5)
    tilt_deg = _safe_float(current_stn.get("tilt"), 0.35)
    tilt_rate = _safe_float(current_stn.get("tilt_rate"), 0.0)
    vib_detected = bool(current_stn.get("vib", False))
    vib_g = _safe_float(current_stn.get("vib_g"), 0.04)
    batt = _safe_float(current_stn.get("battery"), 98.2)

    # -------------------------------------------------------------------------
    # 3. Node Telemetry Header Strip
    # -------------------------------------------------------------------------
    stn_id = current_stn.get('id', 'GG-001')
    stn_name = current_stn.get('name', 'Himalayan Pass')
    stn_corridor = current_stn.get('corridor', 'NH-58')
    stn_lat = _safe_float(current_stn.get('lat'), 30.1234)
    stn_lon = _safe_float(current_stn.get('lon'), 78.4321)

    render_html(f"""
    <div style='background: #111827; border: 1px solid #1F2937; border-radius: 8px; padding: 12px 18px; margin: 10px 0 16px 0; display: flex; justify-content: space-between; align-items: center;'>
        <div style='display: flex; gap: 20px; align-items: center;'>
            <div>
                <span style='font-size: 13px; color: #38BDF8; font-weight: 700;'>STATION {stn_id}</span>
                <span style='font-size: 12px; color: #94A3B8; margin-left: 8px;'>{stn_name}</span>
            </div>
            <div style='display: flex; gap: 14px; font-family: "JetBrains Mono", monospace; font-size: 11px; color: #94A3B8;'>
                <span>Corridor: <b style='color:#F8FAFC;'>{stn_corridor}</b></span>
                <span>Coordinates: <b style='color:#F8FAFC;'>{stn_lat:.4f}°N, {stn_lon:.4f}°E</b></span>
                <span>Last Updated: <b style='color:#10B981;'>{last_update_ts}</b></span>
            </div>
        </div>
        <div style='display: flex; gap: 12px; align-items: center; font-family: "JetBrains Mono", monospace; font-size: 11px;'>
            <span style='color: #10B981;'>● Power: 3.3V Regulated</span>
            <span style='color: #38BDF8;'>● Comms: USB-Serial/nRF24</span>
            <span style='color: #F8FAFC;'>Battery: <b style='color:#10B981;'>{batt:.1f}%</b></span>
        </div>
    </div>
    """)

    # -------------------------------------------------------------------------
    # 4. Automatic Landslide Risk Assessment
    # -------------------------------------------------------------------------
    # Safely retrieve rain_intensity, falling back to rainfall_intensity_mmh
    raw_rain_obj = current_stn.get("rain_intensity")
    if raw_rain_obj is None or (isinstance(raw_rain_obj, str) and raw_rain_obj.strip() == ""):
        raw_rain_obj = current_stn.get("rainfall_intensity_mmh")

    parsed_rain = _safe_float(raw_rain_obj, None)
    # Physically impossible or negative rainfall rejected to None
    rain_mmh = parsed_rain if (parsed_rain is not None and parsed_rain >= 0.0) else None
    rain_mmh_val = rain_mmh if rain_mmh is not None else 0.0

    risk_res = calculate_five_sensor_risk(
        soil_moisture_pct=soil_pct,
        rain_intensity_mmh=rain_mmh,
        temperature_c=temp_c,
        tilt_degrees=tilt_deg,
        vibration_pga=vib_g,
        vibration_detected=vib_detected,
        tilt_rate_deg_h=tilt_rate,
        weights=st.session_state.sensor_weights
    )

    overall_score = risk_res["overall_risk_score"]
    risk_level = risk_res["risk_level"]
    status_color = risk_res["status_color"]
    status_msg = risk_res["status_message"]
    sensor_scores = risk_res["sensor_scores"]

    # -------------------------------------------------------------------------
    # 5. Highway Interlock State Machine Evaluation
    # -------------------------------------------------------------------------
    interlock = st.session_state.interlock_system
    interlock_summary = interlock.evaluate(
        composite_risk=overall_score,
        is_valid_telemetry=risk_res["is_valid"],
        sensor_readings={
            "soil_moisture_pct": soil_pct,
            "temperature_c": temp_c,
            "tilt_degrees": tilt_deg,
            "vibration_pga": vib_g
        },
        risk_subscores=sensor_scores,
        station_id=selected_id,
        station_location=current_stn.get("corridor", "NH-58 Himalayan Corridor"),
        data_source=st.session_state.get("operating_mode", "SIMULATION")
    )

    # -------------------------------------------------------------------------
    # 6. Immediate Warning Banner (if single sensor exhibits critical shock)
    # -------------------------------------------------------------------------
    if risk_res["immediate_warning"]:
        triggers_joined = " • ".join(risk_res["immediate_triggers"])
        render_html(f"""
        <div style='background: rgba(239, 68, 68, 0.12); border: 2px solid #EF4444; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div style='display: flex; align-items: center; gap: 12px;'>
                    <span style='font-size: 24px;'>🚨</span>
                    <div>
                        <div style='font-size: 14px; font-weight: 700; color: #EF4444;'>
                            IMMEDIATE GEOTECHNICAL HAZARD TRIGGERED — PRIORITY ALERT
                        </div>
                        <div style='font-size: 12px; color: #F1F5F9; margin-top: 3px;'>
                            <b>Triggering Sensors:</b> <span style='color: #FCA5A5;'>{triggers_joined}</span>
                        </div>
                        <div style='font-size: 11px; color: #CBD5E1; margin-top: 3px; font-family: "JetBrains Mono", monospace;'>
                            Snapshot: Soil {soil_pct:.1f}% VWC | Temp {temp_c:.1f}°C | Slope {tilt_deg:.2f}° | Vibration {vib_g:.3f}g
                        </div>
                    </div>
                </div>
                <div style='text-align: right;'>
                    <span class='font-mono' style='background: #EF4444; color: #FFFFFF; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 700;'>
                        COOLDOWN ACTIVE (5m)
                    </span>
                    <div style='font-size: 10px; color: #94A3B8; margin-top: 4px;'>Duplicate warnings suppressed</div>
                </div>
            </div>
        </div>
        """)

    # -------------------------------------------------------------------------
    # 7. Five Live Sensor Dashboard Cards (with Real-Time Sparklines)
    # -------------------------------------------------------------------------
    st.markdown("<div class='hud-eyebrow'>PRIMARY GEOTECHNICAL TRANSDUCERS</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>Telemetry Channels & Trend Sparklines</h3>", unsafe_allow_html=True)

    if not hist_df.empty:
        spark_soil = [_safe_float(v, soil_pct) for v in hist_df["soil_moisture_pct"].tail(20).tolist()] if "soil_moisture_pct" in hist_df.columns else [soil_pct] * 10
        r_hist_col = "rainfall_intensity_mmh" if "rainfall_intensity_mmh" in hist_df.columns else ("rain_intensity" if "rain_intensity" in hist_df.columns else None)
        if r_hist_col and not hist_df[r_hist_col].dropna().empty:
            spark_rain = [_safe_float(v, 0.0) for v in hist_df[r_hist_col].tail(20).tolist()]
        elif rain_mmh is not None:
            spark_rain = [rain_mmh] * 10
        else:
            spark_rain = [0.0] * 5

        spark_tilt = [_safe_float(v, tilt_deg) for v in hist_df["tilt_degrees"].tail(20).tolist()] if "tilt_degrees" in hist_df.columns else [tilt_deg] * 10
        spark_vib = [_safe_float(v, vib_g) for v in hist_df["vibration_intensity_g"].tail(20).tolist()] if "vibration_intensity_g" in hist_df.columns else [vib_g] * 10
        spark_temp = [_safe_float(v, temp_c) for v in hist_df["temperature_c"].tail(20).tolist()] if "temperature_c" in hist_df.columns else [temp_c] * 10
    else:
        spark_soil = [soil_pct] * 10
        spark_rain = [rain_mmh] * 10 if rain_mmh is not None else [0.0] * 5
        spark_tilt = [tilt_deg] * 10
        spark_vib = [vib_g] * 10
        spark_temp = [temp_c] * 10

    card_c1, card_c2, card_c3, card_c4, card_c5 = st.columns(5)

    # CARD 1: Soil Moisture Sensor (Weight: 25%)
    with card_c1:
        soil_risk = sensor_scores.get("soil", 0.0)
        s_status = "CRITICAL" if soil_risk > 70 else ("ELEVATED" if soil_risk >= 40 else "NORMAL")
        s_color = "#EF4444" if s_status == "CRITICAL" else ("#F59E0B" if s_status == "ELEVATED" else "#10B981")
        with st.container(border=True):
            render_html(f"""
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span style='font-size: 11px; font-weight: 600; color: #94A3B8; text-transform: uppercase;'>1. Soil Moisture</span>
                <span style='font-family: "JetBrains Mono", monospace; font-size: 10px; font-weight: 600; color: {s_color}; background: rgba({_hex_to_rgb(s_color)}, 0.12); padding: 2px 6px; border-radius: 3px;'>
                    ● {s_status}
                </span>
            </div>
            <div style='font-size: 24px; font-weight: 700; color: {s_color}; margin-top: 4px; font-family: "Inter", sans-serif;'>
                {soil_pct:.1f} <span style='font-size: 13px; font-weight: 500; color: #94A3B8;'>% VWC</span>
            </div>
            <div style='font-size: 11px; color: #64748B; margin-bottom: 4px;'>
                Calibrated Pore Saturation
            </div>
            """)
            st.plotly_chart(render_sparkline_chart(spark_soil, color_hex=s_color, height=52), use_container_width=True, config={'displayModeBar': False}, key='spark_soil_chart')
            render_html(f"""
            <div style='display: flex; justify-content: space-between; font-size: 11px; font-family: "JetBrains Mono", monospace; color: #94A3B8; border-top: 1px solid #1F2937; padding-top: 4px;'>
                <span>Pore Pressure Risk:</span>
                <b style='color: {s_color};'>{soil_risk:.1f} / 100</b>
            </div>
            """)

    # CARD 2: Rain Intensity Sensor (Weight: 25% - 5th Sensor Channel)
    with card_c2:
        rain_risk = sensor_scores.get("rain", 0.0)
        is_rain_avail = (rain_mmh is not None)
        if not is_rain_avail:
            r_status = "UNAVAILABLE"
            r_color = "#94A3B8"
            rain_val_str = "N/A"
            rain_subtext = "Sensor Offline / Missing"
        else:
            r_status = "CRITICAL" if rain_risk > 70 else ("ELEVATED" if rain_risk >= 40 else "NORMAL")
            r_color = "#EF4444" if r_status == "CRITICAL" else ("#F59E0B" if r_status == "ELEVATED" else "#10B981")
            rain_val_str = f"{rain_mmh:.1f}"
            rain_subtext = "Active Precipitation Loading" if rain_mmh > 2.0 else "Dry Baseline (<2 mm/h)"

        with st.container(border=True):
            render_html(f"""
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span style='font-size: 11px; font-weight: 600; color: #94A3B8; text-transform: uppercase;'>2. Rain Intensity</span>
                <span style='font-family: "JetBrains Mono", monospace; font-size: 10px; font-weight: 600; color: {r_color}; background: rgba({_hex_to_rgb(r_color)}, 0.12); padding: 2px 6px; border-radius: 3px;'>
                    ● {r_status}
                </span>
            </div>
            <div style='font-size: 24px; font-weight: 700; color: {r_color}; margin-top: 4px; font-family: "Inter", sans-serif;'>
                {rain_val_str} <span style='font-size: 13px; font-weight: 500; color: #94A3B8;'>mm/hr</span>
            </div>
            <div style='font-size: 11px; color: #64748B; margin-bottom: 4px;'>
                {rain_subtext}
            </div>
            """)
            st.plotly_chart(render_sparkline_chart(spark_rain, color_hex=r_color, height=52), use_container_width=True, config={'displayModeBar': False}, key='spark_rain_chart')
            render_html(f"""
            <div style='display: flex; justify-content: space-between; font-size: 11px; font-family: "JetBrains Mono", monospace; color: #94A3B8; border-top: 1px solid #1F2937; padding-top: 4px;'>
                <span>Rain Risk Factor:</span>
                <b style='color: {r_color};'>{f"{rain_risk:.1f} / 100" if is_rain_avail else "UNAVAILABLE"}</b>
            </div>
            """)

    # CARD 3: Slope / Tilt Sensor (Weight: 25%)
    with card_c3:
        slope_risk = sensor_scores.get("slope", 0.0)
        # Calibrated trigger: tilt < 55° (dropped >5° from 60° baseline) is CRITICAL
        sl_status = "CRITICAL" if (slope_risk > 70 or tilt_deg < 55.0) else ("ELEVATED" if (slope_risk >= 40 or tilt_deg < 58.0) else "NORMAL")
        sl_color = "#EF4444" if sl_status == "CRITICAL" else ("#F59E0B" if sl_status == "ELEVATED" else "#10B981")
        
        # Calibration baseline: 60° resting slope
        delta_from_60 = 60.0 - tilt_deg
        if tilt_deg >= 55.0 and tilt_deg <= 65.0:
            tilt_cal_sub = f"Baseline: 60° (Δ {delta_from_60:+.1f}°: Stable)"
        elif tilt_deg < 55.0:
            tilt_cal_sub = f"<b style='color:#EF4444;'>⚠️ SLIP: Dropped {delta_from_60:.1f}° from 60°!</b>"
        else:
            tilt_cal_sub = f"Deviation: {delta_from_60:+.1f}° from 60°"

        with st.container(border=True):
            render_html(f"""
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span style='font-size: 11px; font-weight: 600; color: #94A3B8; text-transform: uppercase;'>3. Slope / Tilt</span>
                <span style='font-family: "JetBrains Mono", monospace; font-size: 10px; font-weight: 600; color: {sl_color}; background: rgba({_hex_to_rgb(sl_color)}, 0.12); padding: 2px 6px; border-radius: 3px;'>
                    ● {sl_status}
                </span>
            </div>
            <div style='font-size: 24px; font-weight: 700; color: {sl_color}; margin-top: 4px; font-family: "Inter", sans-serif;'>
                {tilt_deg:.2f} <span style='font-size: 13px; font-weight: 500; color: #94A3B8;'>Degrees (°)</span>
            </div>
            <div style='font-size: 11px; color: #64748B; margin-bottom: 4px;'>
                {tilt_cal_sub}
            </div>
            """)
            st.plotly_chart(render_sparkline_chart(spark_tilt, color_hex=sl_color, height=52), use_container_width=True, config={'displayModeBar': False}, key='spark_tilt_chart')
            render_html(f"""
            <div style='display: flex; justify-content: space-between; font-size: 11px; font-family: "JetBrains Mono", monospace; color: #94A3B8; border-top: 1px solid #1F2937; padding-top: 4px;'>
                <span>Shear Slip Risk:</span>
                <b style='color: {sl_color};'>{slope_risk:.1f} / 100</b>
            </div>
            """)

    # CARD 4: Vibration Sensor (Weight: 15%)
    with card_c4:
        vib_risk = sensor_scores.get("vibration", 0.0)
        v_status = "CRITICAL" if vib_risk > 70 else ("ELEVATED" if vib_risk >= 40 else "NORMAL")
        v_color = "#EF4444" if v_status == "CRITICAL" else ("#F59E0B" if v_status == "ELEVATED" else "#10B981")
        with st.container(border=True):
            render_html(f"""
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span style='font-size: 11px; font-weight: 600; color: #94A3B8; text-transform: uppercase;'>4. Vibration</span>
                <span style='font-family: "JetBrains Mono", monospace; font-size: 10px; font-weight: 600; color: {v_color}; background: rgba({_hex_to_rgb(v_color)}, 0.12); padding: 2px 6px; border-radius: 3px;'>
                    ● {v_status}
                </span>
            </div>
            <div style='font-size: 24px; font-weight: 700; color: {v_color}; margin-top: 4px; font-family: "Inter", sans-serif;'>
                {vib_g:.3f} <span style='font-size: 13px; font-weight: 500; color: #94A3B8;'>g (PGA)</span>
            </div>
            <div style='font-size: 11px; color: #64748B; margin-bottom: 4px;'>
                {"Seismic Tremor Active" if vib_detected else "Seismic Floor: Ambient"}
            </div>
            """)
            st.plotly_chart(render_sparkline_chart(spark_vib, color_hex=v_color, height=52), use_container_width=True, config={'displayModeBar': False}, key='spark_vib_chart')
            render_html(f"""
            <div style='display: flex; justify-content: space-between; font-size: 11px; font-family: "JetBrains Mono", monospace; color: #94A3B8; border-top: 1px solid #1F2937; padding-top: 4px;'>
                <span>Seismic Shock Risk:</span>
                <b style='color: {vib_risk:.1f} / 100</b>
            </div>
            """)

    # CARD 5: Temperature Sensor (Weight: 10%)
    with card_c5:
        temp_risk = sensor_scores.get("temperature", 0.0)
        t_status = "CRITICAL" if temp_risk > 70 else ("ELEVATED" if temp_risk >= 40 else "NORMAL")
        t_color = "#EF4444" if t_status == "CRITICAL" else ("#F59E0B" if t_status == "ELEVATED" else "#10B981")
        with st.container(border=True):
            render_html(f"""
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span style='font-size: 11px; font-weight: 600; color: #94A3B8; text-transform: uppercase;'>5. Temperature</span>
                <span style='font-family: "JetBrains Mono", monospace; font-size: 10px; font-weight: 600; color: {t_color}; background: rgba({_hex_to_rgb(t_color)}, 0.12); padding: 2px 6px; border-radius: 3px;'>
                    ● {t_status}
                </span>
            </div>
            <div style='font-size: 24px; font-weight: 700; color: {t_color}; margin-top: 4px; font-family: "Inter", sans-serif;'>
                {temp_c:.1f} <span style='font-size: 13px; font-weight: 500; color: #94A3B8;'>°C</span>
            </div>
            <div style='font-size: 11px; color: #64748B; margin-bottom: 4px;'>
                {"Freeze-Thaw Fissure Zone" if -4.0 <= temp_c <= 4.0 else "Thermal Gradient: Stable"}
            </div>
            """)
            st.plotly_chart(render_sparkline_chart(spark_temp, color_hex=t_color, height=52), use_container_width=True, config={'displayModeBar': False}, key='spark_temp_chart')
            render_html(f"""
            <div style='display: flex; justify-content: space-between; font-size: 11px; font-family: "JetBrains Mono", monospace; color: #94A3B8; border-top: 1px solid #1F2937; padding-top: 4px;'>
                <span>Thermal Wedge Risk:</span>
                <b style='color: {temp_risk:.1f} / 100</b>
            </div>
            """)

    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 8. Composite Risk Gauge & Synthesis Breakdown
    # -------------------------------------------------------------------------
    st.markdown("<div class='hud-eyebrow'>COMPOSITE LANDSLIDE RISK ENGINE</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>Landslide Risk Assessment & Multi-Factor Synthesis</h3>", unsafe_allow_html=True)

    gauge_col, desc_col = st.columns([1.3, 1.7])

    with gauge_col:
        gauge_fig = build_four_sensor_risk_gauge(overall_score, risk_level, status_color, height=275)
        st.plotly_chart(gauge_fig, use_container_width=True, config={'displayModeBar': False}, key='live_risk_gauge_chart')

    with desc_col:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span style='font-size: 11px; font-weight: 600; color: #94A3B8; text-transform: uppercase;'>Risk Classification</span>
                <span style='background: rgba({_hex_to_rgb(status_color)}, 0.15); border: 1px solid {status_color}; color: {status_color}; font-size: 12px; font-weight: 600; padding: 2px 10px; border-radius: 4px;'>
                    ● {risk_level} ({overall_score:.1f}%)
                </span>
            </div>
            <div style='font-size: 15px; font-weight: 600; color: #F8FAFC; margin-top: 8px; line-height: 1.4;'>
                {status_msg}
            </div>
            <div style='font-size: 11px; color: #64748B; margin-top: 4px;'>
                Piecewise evaluation across 5 geotechnical transducers (Soil 25%, Rain 25%, Slope 25%, Vib 15%, Temp 10%).
            </div>
        </div>
        """)

        weights_dict = current_stn.get("weights", {"soil": 0.25, "rain": 0.25, "slope": 0.25, "vibration": 0.15, "temperature": 0.10})
        w_soil = weights_dict.get("soil", 0.25)
        w_rain = weights_dict.get("rain", 0.25)
        w_slope = weights_dict.get("slope", 0.25)
        w_vib = weights_dict.get("vibration", 0.15)
        w_temp = weights_dict.get("temperature", 0.10)

        c_soil = soil_risk * w_soil
        c_rain = (rain_risk * w_rain) if is_rain_avail else 0.0
        c_slope = slope_risk * w_slope
        c_vib = vib_risk * w_vib
        c_temp = temp_risk * w_temp

        rain_label = f"{rain_mmh:.1f} mm/h" if is_rain_avail else "N/A - UNAVAILABLE"
        rain_score_display = f"{rain_risk:.1f}/100" if is_rain_avail else "UNAVAILABLE"
        rain_pts_display = f"+{c_rain:.1f} pts" if is_rain_avail else "+0.0 pts (missing)"
        rain_bar_width = rain_risk if is_rain_avail else 0.0

        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 8px; padding: 14px 18px;'>
            <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>
                <span style='font-size: 11px; font-weight: 600; color: #38BDF8; text-transform: uppercase;'>5-Factor Contributing Risk Breakdown (100% Weight)</span>
                <span style='font-size: 10px; color: #10B981; font-family: "JetBrains Mono", monospace;'>Sum: 100%</span>
            </div>
            <div style='display: flex; flex-direction: column; gap: 8px; font-family: "JetBrains Mono", monospace; font-size: 11px;'>
                <div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 2px;'>
                        <span>💧 Soil Moisture ({soil_pct:.1f}% VWC):</span>
                        <b>{soil_risk:.1f}/100 | W: {w_soil*100:.0f}% | +{c_soil:.1f} pts</b>
                    </div>
                    <div style='background: #1F2937; height: 5px; border-radius: 3px; overflow: hidden;'>
                        <div style='background: #38BDF8; width: {soil_risk}%; height: 100%;'></div>
                    </div>
                </div>
                <div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 2px;'>
                        <span>🌧️ Rain Intensity ({rain_label}):</span>
                        <b>{rain_score_display} | W: {w_rain*100:.0f}% | {rain_pts_display}</b>
                    </div>
                    <div style='background: #1F2937; height: 5px; border-radius: 3px; overflow: hidden;'>
                        <div style='background: #0284C7; width: {rain_bar_width}%; height: 100%;'></div>
                    </div>
                </div>
                <div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 2px;'>
                        <span>📐 Slope Inclinometer ({tilt_deg:.2f}°):</span>
                        <b style='color: {"#EF4444" if slope_risk > 70 else "#F8FAFC"};'>{slope_risk:.1f}/100 | W: {w_slope*100:.0f}% | +{c_slope:.1f} pts</b>
                    </div>
                    <div style='background: #1F2937; height: 5px; border-radius: 3px; overflow: hidden;'>
                        <div style='background: {"#EF4444" if slope_risk > 70 else "#F59E0B"}; width: {slope_risk}%; height: 100%;'></div>
                    </div>
                </div>
                <div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 2px;'>
                        <span>⚡ Seismic Vibration ({vib_g:.3f}g):</span>
                        <b>{vib_risk:.1f}/100 | W: {w_vib*100:.0f}% | +{c_vib:.1f} pts</b>
                    </div>
                    <div style='background: #1F2937; height: 5px; border-radius: 3px; overflow: hidden;'>
                        <div style='background: #EF4444; width: {vib_risk}%; height: 100%;'></div>
                    </div>
                </div>
                <div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 2px;'>
                        <span>🌡️ Temperature ({temp_c:.1f}°C):</span>
                        <b>{temp_risk:.1f}/100 | W: {w_temp*100:.0f}% | +{c_temp:.1f} pts</b>
                    </div>
                    <div style='background: #1F2937; height: 5px; border-radius: 3px; overflow: hidden;'>
                        <div style='background: #10B981; width: {temp_risk}%; height: 100%;'></div>
                    </div>
                </div>
            </div>
            <div style='font-size: 10px; color: #64748B; margin-top: 8px;'>
                Exact Formula: Composite Risk = (Soil × 0.25) + (Rain × 0.25) + (Slope × 0.25) + (Vib × 0.15) + (Temp × 0.10)
            </div>
        </div>
        """)

    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 9. Simulated Highway Interlock Actuator Console
    # -------------------------------------------------------------------------
    st.markdown("<div class='hud-eyebrow'>HIGHWAY INTERLOCK AUTOMATION • ACTUATOR SIMULATION</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>Simulated Physical Actuators & Signal Controls</h3>", unsafe_allow_html=True)

    b_state = interlock_summary["barrier_state"]
    sig_state = interlock_summary["traffic_signal"]
    emg_state = interlock_summary["emergency_response"]
    sys_health = interlock_summary["sensor_system"]
    disp_state = interlock_summary["dispatch_status"]

    # Actuator color mappings
    b_color = "#EF4444" if b_state == "CLOSED" else "#10B981"
    sig_color = "#EF4444" if sig_state == "RED" else ("#F59E0B" if sig_state == "YELLOW" else "#10B981")
    emg_color = "#EF4444" if emg_state == "ACTIVE" else "#10B981"
    sys_color = "#10B981" if sys_health == "ONLINE" else "#EF4444"
    disp_color = "#EF4444" if disp_state == "LOGGED" else ("#38BDF8" if disp_state == "ACKNOWLEDGED" else "#94A3B8")

    int_c1, int_c2, int_c3, int_c4, int_c5 = st.columns(5)

    with int_c1:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-top: 3px solid {b_color}; border-radius: 6px; padding: 14px; text-align: center;'>
            <div style='font-size: 10px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Boom Barrier</div>
            <div style='font-size: 20px; font-weight: 700; color: {b_color}; margin-top: 4px; font-family: "JetBrains Mono", monospace;'>
                {b_state}
            </div>
            <div style='font-size: 10px; color: #64748B; margin-top: 2px;'>Checkpoint km 42</div>
        </div>
        """)

    with int_c2:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-top: 3px solid {sig_color}; border-radius: 6px; padding: 14px; text-align: center;'>
            <div style='font-size: 10px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Traffic Signal</div>
            <div style='font-size: 20px; font-weight: 700; color: {sig_color}; margin-top: 4px; font-family: "JetBrains Mono", monospace;'>
                {sig_state}
            </div>
            <div style='font-size: 10px; color: #64748B; margin-top: 2px;'>Upstream Gantries</div>
        </div>
        """)

    with int_c3:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-top: 3px solid {emg_color}; border-radius: 6px; padding: 14px; text-align: center;'>
            <div style='font-size: 10px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Emergency State</div>
            <div style='font-size: 20px; font-weight: 700; color: {emg_color}; margin-top: 4px; font-family: "JetBrains Mono", monospace;'>
                {emg_state}
            </div>
            <div style='font-size: 10px; color: #64748B; margin-top: 2px;'>Auto Early Warning</div>
        </div>
        """)

    with int_c4:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-top: 3px solid {sys_color}; border-radius: 6px; padding: 14px; text-align: center;'>
            <div style='font-size: 10px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Sensor Link</div>
            <div style='font-size: 20px; font-weight: 700; color: {sys_color}; margin-top: 4px; font-family: "JetBrains Mono", monospace;'>
                {sys_health}
            </div>
            <div style='font-size: 10px; color: #64748B; margin-top: 2px;'>Node Telemetry</div>
        </div>
        """)

    with int_c5:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-top: 3px solid {disp_color}; border-radius: 6px; padding: 14px; text-align: center;'>
            <div style='font-size: 10px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Dispatch Status</div>
            <div style='font-size: 20px; font-weight: 700; color: {disp_color}; margin-top: 4px; font-family: "JetBrains Mono", monospace;'>
                {disp_state}
            </div>
            <div style='font-size: 10px; color: #64748B; margin-top: 2px;'>Incident Queue</div>
        </div>
        """)

    st.caption("⚠️ **HARDWARE SAFETY LIMITATION:** Barrier and signal controls are purely SIMULATED in software. Real-world actuation requires certified fail-safe PLCs, mechanical watchdogs, and authorized operator authorization.")

    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 10. Automated Incident Dispatch Center & CSV Export
    # -------------------------------------------------------------------------
    st.markdown("<div class='hud-eyebrow'>DISPATCH LOG CENTER • INTER-AGENCY NOTIFICATIONS</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>Automated Emergency Incident Log & Audit Trail</h3>", unsafe_allow_html=True)

    dispatch_df = interlock.get_dispatch_history_df()

    disp_col_a, disp_col_b = st.columns([3, 1])
    with disp_col_a:
        st.caption("Intended Recipient Agencies: **1. NH-58 Traffic Police** • **2. District Emergency Control Room** • **3. Highway Response Team (SDRF/BRO)**")
    with disp_col_b:
        csv_data = interlock.export_csv()
        st.download_button(
            label="📥 Download Dispatch Log (CSV)",
            data=csv_data,
            file_name=f"geoguard_dispatch_log_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    if not dispatch_df.empty:
        # Display incident table
        show_cols = [
            "incident_id", "timestamp", "station_id", "composite_risk_score",
            "risk_classification", "simulated_barrier_state", "simulated_traffic_signal",
            "dispatch_status", "acknowledgment_status"
        ]
        available_cols = [c for c in show_cols if c in dispatch_df.columns]
        st.dataframe(dispatch_df[available_cols], use_container_width=True, hide_index=True)

        # Operator Acknowledgment Console
        if interlock.active_incident_id and interlock.dispatch_status == "LOGGED":
            ack_c1, ack_c2 = st.columns([3, 1])
            with ack_c1:
                st.warning(f"Active Incident **{interlock.active_incident_id}** is awaiting authorized operator review and acknowledgment.")
            with ack_c2:
                if st.button("✅ ACKNOWLEDGE INCIDENT", type="primary", use_container_width=True):
                    interlock.acknowledge_active_incident(operator_name="Highway Operations Controller")
                    st.toast(f"Incident {interlock.active_incident_id} acknowledged!", icon="✅")
                    st.rerun()
    else:
        render_html("""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 14px; text-align: center; color: #94A3B8; font-size: 12px;'>
            🟢 No emergency dispatch incidents logged. All monitored highway corridors are operating within safe baseline limits.
        </div>
        """)

    st.markdown("<hr style='border:0; border-top:1px solid #1F2937; margin: 18px 0;'>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 10B. Mobile Phone Emergency Alert & Cellular SMS Terminal
    # -------------------------------------------------------------------------
    st.markdown("<div class='hud-eyebrow'>MOBILE EMERGENCY DISPATCH GATEWAY</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>📱 Mobile Phone Emergency Alert & Cellular SMS Terminal</h3>", unsafe_allow_html=True)

    sms_col1, sms_col2 = st.columns([1.5, 1.5])

    with sms_col1:
        st.markdown("#### 📶 1. 100% Offline Wi-Fi Portal (Active on ESP32)")
        render_html("""
        <div style='background: #111827; border: 1px solid #10B981; border-radius: 8px; padding: 14px 18px;'>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <b style='color:#10B981; font-size:14px;'>● LOCAL EMERGENCY WI-FI BROADCASTING</b>
                <span style='background:rgba(16,185,129,0.15); color:#10B981; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:700;'>OFFLINE</span>
            </div>
            <div style='font-size:12px; color:#E2E8F0; margin-top:8px; line-height:1.5;'>
                Connect your mobile phone right now to:<br>
                <b>Wi-Fi Name (SSID):</b> <span style='color:#38BDF8; font-weight:700;'>GEOGUARD-DISASTER-ALERT</span><br>
                <b>Password:</b> <i>None (Open Network)</i><br>
                <b>Browser URL:</b> <a href='http://192.168.4.1' target='_blank' style='color:#F59E0B; font-weight:700;'>http://192.168.4.1</a>
            </div>
            <div style='font-size:11px; color:#94A3B8; margin-top:6px;'>
                ⚡ Zero internet required. Features live tilt/rain streaming + loud oscillating siren sound on your phone speakers.
            </div>
        </div>
        """)

    with sms_col2:
        st.markdown("#### ✉️ 2. Real Cellular SMS to Indian Mobile (+91)")
        with st.container(border=True):
            sms_phone = st.text_input("Recipient Indian Mobile Number", value=st.session_state.get("emergency_mobile", ""), placeholder="e.g. 9876543210")
            st.session_state["emergency_mobile"] = sms_phone
            fast2sms_key = st.text_input("Fast2SMS API Key (Optional)", value=st.session_state.get("fast2sms_key", ""), type="password", help="Enter your free Fast2SMS API key to deliver SMS via GSM network.")
            st.session_state["fast2sms_key"] = fast2sms_key

            auto_sms = st.checkbox("🔔 Automatically send SMS on Critical Landslide / Heavy Rain Trigger", value=st.session_state.get("auto_sms_enabled", False))
            st.session_state["auto_sms_enabled"] = auto_sms

            if st.button("🚨 Send Test Emergency SMS to Phone", type="primary", use_container_width=True):
                if not sms_phone:
                    st.error("Please enter a valid 10-digit mobile number.")
                else:
                    sample_msg = format_landslide_sms_message(stn_id, tilt_deg, rain_mmh_val, soil_pct)
                    if fast2sms_key:
                        ok, res = send_fast2sms(fast2sms_key, sms_phone, sample_msg)
                        if ok:
                            st.success(f"SMS delivered: {res}")
                        else:
                            st.warning(f"Gateway Notice: {res}")
                    else:
                        st.info(f"📱 Demo SMS Simulated for +91 {sms_phone}!\n\nMessage Body:\n{sample_msg}\n\n(Tip: Enter your Fast2SMS key to send real cellular SMS over the carrier network!)")

    # If auto-SMS enabled and danger triggered:
    if st.session_state.get("auto_sms_enabled") and st.session_state.get("emergency_mobile"):
        cur_sensor_pkt = {
            "station_id": stn_id,
            "tilt_degrees": tilt_deg,
            "rain_intensity_mmh": rain_mmh_val,
            "soil_moisture_pct": soil_pct,
            "landslide": (risk_level == "CRITICAL" or tilt_deg < 55.0 or (rain_mmh_val is not None and rain_mmh_val > 25.0))
        }
        ok, res = check_and_dispatch_automatic_sms(
            sensor_dict=cur_sensor_pkt,
            mobile_number=st.session_state["emergency_mobile"],
            fast2sms_key=st.session_state.get("fast2sms_key", "")
        )
        if ok:
            st.toast(f"Emergency SMS dispatched to {st.session_state['emergency_mobile']}!", icon="🚨")

    st.markdown("<hr style='border:0; border-top:1px solid #1F2937; margin: 18px 0;'>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 11. 2D Mountain Slope Stratigraphy Cross-Section (SVG)
    # -------------------------------------------------------------------------
    render_slope_cross_section_svg(tilt_degrees=tilt_deg, soil_pct=soil_pct, risk_level=risk_level)

    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 12. Real-Time Telemetry History & 5 Plotly Charts
    # -------------------------------------------------------------------------
    st.markdown("<div class='hud-eyebrow'>REAL-TIME TIME-SERIES CHARTS</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>Synchronized Telemetry Histories & Risk Waveforms</h3>", unsafe_allow_html=True)

    if hist_df.empty:
        st.info(f"No historical telemetry logged yet for station {selected_id} in {time_window}. Stream is actively logging.")
    else:
        plotly_theme = dict(get_plotly_theme())
        plotly_theme.pop("margin", None)
        plotly_theme.pop("height", None)

        # 6 Separate Time-Series Charts (5 Transducers + 1 Composite Risk Index)
        # Row 1: Soil Moisture & Rain Intensity
        chart_r1_c1, chart_r1_c2 = st.columns(2)
        with chart_r1_c1:
            st.markdown("#### 1. Soil Moisture vs Time (% VWC)")
            fig_soil = go.Figure()
            fig_soil.add_trace(go.Scatter(
                x=hist_df["datetime"],
                y=hist_df["soil_moisture_pct"],
                name="Soil Moisture (% VWC)",
                line=dict(color="#38BDF8", width=2.0),
                fill="tozeroy",
                fillcolor="rgba(56, 189, 248, 0.08)",
                mode="lines"
            ))
            fig_soil.add_hline(y=70.0, line_dash="dash", line_color="#EF4444", annotation_text="Saturation Limit (70%)", annotation_font_color="#EF4444")
            fig_soil.update_layout(**plotly_theme, height=260, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_soil, use_container_width=True, key='history_soil_chart')

        with chart_r1_c2:
            st.markdown("#### 2. Rain Intensity vs Time (mm/hr)")
            fig_rain = go.Figure()
            r_col = "rainfall_intensity_mmh" if "rainfall_intensity_mmh" in hist_df.columns else ("rain_intensity" if "rain_intensity" in hist_df.columns else None)
            if r_col and not hist_df[r_col].dropna().empty:
                rain_plot_y = [_safe_float(v, None) for v in hist_df[r_col]]
            elif rain_mmh is not None:
                rain_plot_y = [rain_mmh] * len(hist_df)
            else:
                rain_plot_y = [None] * len(hist_df)

            fig_rain.add_trace(go.Scatter(
                x=hist_df["datetime"],
                y=rain_plot_y,
                name="Rain Intensity (mm/hr)",
                line=dict(color="#0284C7", width=2.0),
                fill="tozeroy",
                fillcolor="rgba(2, 132, 199, 0.08)",
                mode="lines",
                connectgaps=False
            ))
            fig_rain.add_hline(y=25.0, line_dash="dash", line_color="#F59E0B", annotation_text="Elevated Rain (25 mm/h)", annotation_font_color="#F59E0B")
            fig_rain.add_hline(y=50.0, line_dash="dash", line_color="#EF4444", annotation_text="Critical Cloudburst (50 mm/h)", annotation_font_color="#EF4444")
            fig_rain.update_layout(**plotly_theme, height=260, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_rain, use_container_width=True, key='history_rain_chart')

        # Row 2: Tilt Angle & Vibration PGA
        chart_r2_c1, chart_r2_c2 = st.columns(2)
        with chart_r2_c1:
            st.markdown("#### 3. Slope / Tilt Angle vs Time (Degrees)")
            fig_tilt = go.Figure()
            fig_tilt.add_trace(go.Scatter(
                x=hist_df["datetime"],
                y=hist_df["tilt_degrees"],
                name="Tilt Angle (°)",
                line=dict(color="#F59E0B", width=2.0),
                fill="tozeroy",
                fillcolor="rgba(245, 158, 11, 0.08)",
                mode="lines"
            ))
            fig_tilt.add_hline(y=60.0, line_dash="dot", line_color="#10B981", annotation_text="Baseline (60.0°)", annotation_font_color="#10B981")
            fig_tilt.add_hline(y=55.0, line_dash="dash", line_color="#EF4444", annotation_text="Critical Shear Limit (< 55.0°)", annotation_font_color="#EF4444")
            fig_tilt.update_layout(**plotly_theme, height=260, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_tilt, use_container_width=True, key='history_tilt_chart')

        with chart_r2_c2:
            st.markdown("#### 4. Vibration PGA vs Time (g)")
            fig_vib = go.Figure()
            fig_vib.add_trace(go.Scatter(
                x=hist_df["datetime"],
                y=hist_df["vibration_intensity_g"],
                name="Peak Acceleration (g)",
                line=dict(color="#EF4444", width=1.8),
                mode="lines"
            ))
            fig_vib.add_hline(y=0.35, line_dash="dash", line_color="#EF4444", annotation_text="Seismic Shock Limit (0.35g)", annotation_font_color="#EF4444")
            fig_vib.update_layout(**plotly_theme, height=260, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_vib, use_container_width=True, key='history_vib_chart')

        # Row 3: Temperature & Composite Risk Index
        chart_r3_c1, chart_r3_c2 = st.columns(2)
        with chart_r3_c1:
            st.markdown("#### 5. Temperature vs Time (°C)")
            fig_temp = go.Figure()
            t_col = "temperature_c" if "temperature_c" in hist_df.columns else "temp_c"
            fig_temp.add_trace(go.Scatter(
                x=hist_df["datetime"],
                y=hist_df[t_col] if t_col in hist_df.columns else [temp_c]*len(hist_df),
                name="Temperature (°C)",
                line=dict(color="#10B981", width=2.0),
                mode="lines"
            ))
            fig_temp.add_hrect(y0=-4.0, y1=4.0, line_width=0, fillcolor="rgba(239, 68, 68, 0.15)", annotation_text="Freeze-Thaw Fissure Zone (-4°C to +4°C)", annotation_font_color="#EF4444")
            fig_temp.update_layout(**plotly_theme, height=260, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_temp, use_container_width=True, key='history_temp_chart')

        with chart_r3_c2:
            st.markdown("#### 6. Composite Landslide Risk Index vs Time")
            fig_comp = go.Figure()

        # Compute composite risk trace across historical dataframe
        risk_hist = []
        for _, row in hist_df.iterrows():
            r_hist_val = _safe_float(row.get("rainfall_intensity_mmh", row.get("rain_intensity")), None)
            r = calculate_five_sensor_risk(
                soil_moisture_pct=_safe_float(row.get("soil_moisture_pct"), 30.0),
                rain_intensity_mmh=r_hist_val,
                temperature_c=_safe_float(row.get("temperature_c"), 14.5),
                tilt_degrees=_safe_float(row.get("tilt_degrees"), 0.3),
                vibration_pga=_safe_float(row.get("vibration_intensity_g"), 0.02)
            )
            risk_hist.append(r["overall_risk_score"])

        fig_comp.add_trace(go.Scatter(
            x=hist_df["datetime"],
            y=risk_hist,
            name="Composite Risk Index",
            line=dict(color="#F8FAFC", width=2.4),
            fill="tozeroy",
            fillcolor="rgba(248, 250, 252, 0.05)",
            mode="lines"
        ))
        fig_comp.add_hline(
            y=40.0,
            line_dash="dash",
            line_color="#F59E0B",
            annotation_text="Moderate Risk Warning Threshold (40.0)",
            annotation_font_color="#F59E0B"
        )
        fig_comp.add_hline(
            y=70.0,
            line_dash="dash",
            line_color="#EF4444",
            annotation_text="Critical Danger Emergency Interlock Threshold (70.0)",
            annotation_font_color="#EF4444"
        )
        fig_comp.update_layout(
            **plotly_theme,
            height=300,
            yaxis=dict(title="Risk Score (0–100)", range=[0, 105], showgrid=True, gridcolor="#1F2937"),
            margin=dict(l=10, r=10, t=30, b=10)
        )
        st.plotly_chart(fig_comp, use_container_width=True, key='history_comp_chart')

    # -------------------------------------------------------------------------
    # 13. Scientific Notice
    # -------------------------------------------------------------------------
    st.info("ℹ️ **Scientific Notice:** Thresholds and risk scores are unvalidated demonstration baselines for the SIH prototype. Real-world highway deployments require in-situ geotechnical drilling, borehole piezometers, and multi-sensor correlation before operational safety certification.")
