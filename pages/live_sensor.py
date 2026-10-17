"""
=============================================================================
GEOGUARD AI — SATELLITE-POWERED TERRAIN RISK & EARLY WARNING PLATFORM
Page: pages/live_sensor.py
Purpose: Live 4-Sensor Telemetry Monitoring, Risk Normalization & Alarm Cascade
=============================================================================
WHERE THIS CODE IS USED:
- Invoked by app.py when the user selects "2. Live Sensor Monitoring" from sidebar.
- Provides real-time ingestion, visualization, and early warning detection for:
  1. Soil Moisture Sensor (% VWC & saturation detection)
  2. Temperature Sensor (°C & freeze-thaw hazard detection)
  3. Slope/Tilt Sensor (° angular displacement & shear movement)
  4. Vibration Sensor (g Peak Ground Acceleration & micro-seismic motion)
- Normalizes raw sensor readings into 0-100 risk scores with configurable weights.
- Calculates Overall Landslide Risk Score = (Soil + Temp + Slope + Vib) / 4.
- Evaluates corridor baseline averages and broadcasts proximity alarms to nearby stations.
- Renders high-resolution sparklines, circular gauge, and slope stratigraphy SVG.
=============================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import textwrap

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
from modules.risk_engine import (
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
from database.db import log_alert, get_alerts, get_config


def _hex_to_rgb(hex_code):
    """Converts a hex color code to an R,G,B string for CSS rgba() usage."""
    hex_code = hex_code.lstrip('#')
    if len(hex_code) == 6:
        return f"{int(hex_code[0:2], 16)}, {int(hex_code[2:4], 16)}, {int(hex_code[4:6], 16)}"
    return "56, 189, 248"


def render_sparkline_chart(values, color_hex="#38BDF8", height=56):
    """Generates a compact, minimalist Plotly sparkline without axis clutter."""
    if not values or len(values) == 0:
        values = [0.0] * 12
    elif len(values) < 5:
        values = list(values) + [values[-1]] * (5 - len(values))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=values,
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
    Renders the live sensor monitoring dashboard with 4 distinct IoT sensor cards,
    real-time sparklines, automatic normalized landslide risk calculation,
    circular gauge, immediate warning triggers, and corridor proximity alarm cascade.
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

    if "risk_thresholds" not in st.session_state:
        st.session_state.risk_thresholds = {
            "low_max": 25.0,
            "moderate_max": 50.0,
            "high_max": 75.0,
            "critical_min": 76.0
        }

    # -------------------------------------------------------------------------
    # 2. Header and Top Command Bar
    # -------------------------------------------------------------------------
    st.markdown("<div class='hud-eyebrow'>FIELD TELEMETRY & EARLY WARNING</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Live Geotechnical Sensor Monitoring</h2>", unsafe_allow_html=True)

    # Top Filter & Status Ribbon
    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([2.0, 1.2, 1.3, 1.5])

    with ctrl_col1:
        station_options = [s["id"] for s in enriched_stations]
        station_names = {s["id"]: f"{s['id']} — {s['name']} ({s.get('corridor', 'NH-58')})" for s in enriched_stations}
        selected_id = st.selectbox(
            "Target Sensor Node (ESP32 Stream)",
            station_options,
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
            if st.button("⏸ PAUSE MONITORING", use_container_width=True, help="Temporarily pause live telemetry polling"):
                st.session_state.is_monitoring = False
                st.rerun()
        else:
            if st.button("▶ RESUME MONITORING", type="primary", use_container_width=True, help="Resume live telemetry polling"):
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
            if is_conn:
                conn_html = "<span style='background: rgba(16, 185, 129, 0.12); border: 1px solid #10B981; color: #10B981; padding: 6px 12px; border-radius: 4px; font-family: monospace; font-size: 11px; font-weight: 600; display: inline-block;'>● HARDWARE CONNECTED</span>"
            else:
                conn_html = "<span style='background: rgba(239, 68, 68, 0.12); border: 1px solid #EF4444; color: #EF4444; padding: 6px 12px; border-radius: 4px; font-family: monospace; font-size: 11px; font-weight: 600; display: inline-block;'>○ HARDWARE DISCONNECTED</span>"
        else:
            conn_html = "<span style='background: rgba(56, 189, 248, 0.12); border: 1px solid #38BDF8; color: #38BDF8; padding: 6px 12px; border-radius: 4px; font-family: monospace; font-size: 11px; font-weight: 600; display: inline-block;'>● SIMULATION MODE</span>"
        
        st.markdown(f"<div style='text-align: right;'>{conn_html}</div>", unsafe_allow_html=True)

    # Locate active station telemetry record
    current_stn = next((s for s in enriched_stations if s["id"] == selected_id), enriched_stations[0])
    last_update_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Fetch historical data for sparklines & waveform charts
    hist_df = get_filtered_history(station_id=selected_id, time_range=time_window)

    # -------------------------------------------------------------------------
    # 3. Sensor Node Enclosure Status
    # -------------------------------------------------------------------------
    batt = current_stn.get("battery", 98.2)
    soil_pct = float(current_stn.get("soil_moisture_pct", 42.0))
    soil_adc = int(current_stn.get("soil_adc", 2150))
    temp_c = float(current_stn.get("temp_c", current_stn.get("temperature_c", 14.5)))
    tilt_deg = float(current_stn.get("tilt", 0.35))
    tilt_rate = float(current_stn.get("tilt_rate", 0.0))
    vib_detected = bool(current_stn.get("vib", False))
    vib_g = float(current_stn.get("vib_g", 0.04))

    render_html(f"""
    <div style='background: #111827; border: 1px solid #1F2937; border-radius: 8px; padding: 12px 18px; margin: 10px 0 16px 0; display: flex; justify-content: space-between; align-items: center;'>
        <div style='display: flex; gap: 20px; align-items: center;'>
            <div>
                <span style='font-size: 13px; color: #38BDF8; font-weight: 700;'>STATION {current_stn['id']}</span>
                <span style='font-size: 12px; color: #94A3B8; margin-left: 8px;'>Telemetry Station</span>
            </div>
            <div style='display: flex; gap: 14px; font-family: "JetBrains Mono", monospace; font-size: 11px; color: #94A3B8;'>
                <span>Coordinates: <b style='color:#F8FAFC;'>{current_stn['lat']:.4f}°N, {current_stn['lon']:.4f}°E</b></span>
                <span>Elevation: <b style='color:#38BDF8;'>{current_stn.get('elevation_m', 620)}m ASL</b></span>
                <span>Last Updated: <b style='color:#10B981;'>{last_update_ts}</b></span>
            </div>
        </div>
        <div style='display: flex; gap: 12px; align-items: center; font-family: "JetBrains Mono", monospace; font-size: 11px;'>
            <span style='color: #10B981;'>● Power 3.3V</span>
            <span style='color: #38BDF8;'>● Serial Link</span>
            <span style='color: {"#EF4444" if vib_detected else "#10B981"};'>● Seismic Sensor</span>
            <span style='color: #F8FAFC;'>Battery: <b style='color:#10B981;'>{batt:.1f}%</b></span>
        </div>
    </div>
    """)

    # -------------------------------------------------------------------------
    # 4. Automatic Landslide Risk Calculation
    # -------------------------------------------------------------------------
    risk_res = calculate_four_sensor_risk(
        soil_moisture_pct=soil_pct,
        temperature_c=temp_c,
        tilt_degrees=tilt_deg,
        vibration_g=vib_g,
        vibration_detected=vib_detected,
        tilt_rate_deg_h=tilt_rate,
        weights=st.session_state.sensor_weights,
        thresholds=st.session_state.risk_thresholds
    )

    overall_score = risk_res["overall_risk_score"]
    risk_level = risk_res["risk_level"]
    status_color = risk_res["status_color"]
    status_msg = risk_res["status_message"]
    sensor_scores = risk_res["sensor_scores"]

    # -------------------------------------------------------------------------
    # 5. Immediate Warnings Banner (Triggered by Sudden Slope or Tremor Event)
    # -------------------------------------------------------------------------
    if risk_res["immediate_warning"]:
        triggers_joined = " • ".join(risk_res["immediate_triggers"])
        log_alert(
            station_id=selected_id,
            risk_level="CRITICAL",
            risk_score=overall_score,
            reason=f"Immediate Geotechnical Trigger: {triggers_joined}",
            cooldown_minutes=5
        )

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
                            Snapshot: Soil {soil_pct:.1f}% VWC | Temp {temp_c:.1f}°C | Slope {tilt_deg:.2f}° | Vibration {vib_g:.3f}g | Time: {last_update_ts}
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
    # 6. Four Live Sensor Dashboard Cards (with Sparklines)
    # -------------------------------------------------------------------------
    st.markdown("<div class='hud-eyebrow'>PRIMARY GEOTECHNICAL SENSORS</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>Telemetry Channels & Trend Sparklines</h3>", unsafe_allow_html=True)

    # Prepare sparkline series from historical dataframe
    if not hist_df.empty:
        spark_soil = hist_df["soil_moisture_pct"].tail(20).tolist()
        spark_temp = hist_df["temperature_c"].tail(20).tolist() if "temperature_c" in hist_df.columns else [temp_c] * 15
        spark_tilt = hist_df["tilt_degrees"].tail(20).tolist()
        spark_vib = hist_df["vibration_intensity_g"].tail(20).tolist()
    else:
        spark_soil = [soil_pct] * 10
        spark_temp = [temp_c] * 10
        spark_tilt = [tilt_deg] * 10
        spark_vib = [vib_g] * 10

    card_c1, card_c2, card_c3, card_c4 = st.columns(4)

    # CARD 1: Soil Moisture Sensor
    with card_c1:
        soil_risk_score = sensor_scores["soil"]
        if soil_pct > 75.0:
            s_status, s_color = "CRITICAL", "#EF4444"
        elif soil_pct > 50.0:
            s_status, s_color = "ELEVATED", "#F59E0B"
        else:
            s_status, s_color = "NORMAL", "#10B981"

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
                Capacitive ADC: <b>{soil_adc}</b> counts
            </div>
            """)
            st.plotly_chart(
                render_sparkline_chart(spark_soil, color_hex=s_color, height=52),
                use_container_width=True,
                config={'displayModeBar': False}
            )
            render_html(f"""
            <div style='display: flex; justify-content: space-between; font-size: 11px; font-family: "JetBrains Mono", monospace; color: #94A3B8; border-top: 1px solid #1F2937; padding-top: 4px;'>
                <span>Pore Saturation Risk:</span>
                <b style='color: {s_color};'>{soil_risk_score:.1f} / 100</b>
            </div>
            """)

    # CARD 2: Temperature Sensor
    with card_c2:
        temp_risk_score = sensor_scores["temperature"]
        if -4.0 <= temp_c <= 4.0 or temp_c > 28.0:
            t_status, t_color = "CRITICAL", "#EF4444"
        elif (4.0 < temp_c <= 9.0) or (23.0 < temp_c <= 28.0):
            t_status, t_color = "ELEVATED", "#F59E0B"
        else:
            t_status, t_color = "NORMAL", "#10B981"

        with st.container(border=True):
            render_html(f"""
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span style='font-size: 11px; font-weight: 600; color: #94A3B8; text-transform: uppercase;'>2. Temperature</span>
                <span style='font-family: "JetBrains Mono", monospace; font-size: 10px; font-weight: 600; color: {t_color}; background: rgba({_hex_to_rgb(t_color)}, 0.12); padding: 2px 6px; border-radius: 3px;'>
                    ● {t_status}
                </span>
            </div>
            <div style='font-size: 24px; font-weight: 700; color: {t_color}; margin-top: 4px; font-family: "Inter", sans-serif;'>
                {temp_c:.1f} <span style='font-size: 13px; font-weight: 500; color: #94A3B8;'>°C</span>
            </div>
            <div style='font-size: 11px; color: #64748B; margin-bottom: 4px;'>
                {"Freeze-Thaw Zone" if -4.0 <= temp_c <= 4.0 else "Thermal Gradient: Stable"}
            </div>
            """)
            st.plotly_chart(
                render_sparkline_chart(spark_temp, color_hex=t_color, height=52),
                use_container_width=True,
                config={'displayModeBar': False}
            )
            render_html(f"""
            <div style='display: flex; justify-content: space-between; font-size: 11px; font-family: "JetBrains Mono", monospace; color: #94A3B8; border-top: 1px solid #1F2937; padding-top: 4px;'>
                <span>Thermal Wedge Risk:</span>
                <b style='color: {t_color};'>{temp_risk_score:.1f} / 100</b>
            </div>
            """)

    # CARD 3: Slope / Tilt Sensor
    with card_c3:
        slope_risk_score = sensor_scores["slope"]
        if tilt_deg > 2.0 or abs(tilt_rate) >= 0.35:
            sl_status, sl_color = "CRITICAL", "#EF4444"
        elif tilt_deg > 0.8:
            sl_status, sl_color = "ELEVATED", "#F59E0B"
        else:
            sl_status, sl_color = "NORMAL", "#10B981"

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
                Creep Rate: <b>{tilt_rate:+.2f}°/hour</b>
            </div>
            """)
            st.plotly_chart(
                render_sparkline_chart(spark_tilt, color_hex=sl_color, height=52),
                use_container_width=True,
                config={'displayModeBar': False}
            )
            render_html(f"""
            <div style='display: flex; justify-content: space-between; font-size: 11px; font-family: "JetBrains Mono", monospace; color: #94A3B8; border-top: 1px solid #1F2937; padding-top: 4px;'>
                <span>Shear Slip Risk:</span>
                <b style='color: {sl_color};'>{slope_risk_score:.1f} / 100</b>
            </div>
            """)

    # CARD 4: Vibration Sensor
    with card_c4:
        vib_risk_score = sensor_scores["vibration"]
        if vib_detected or vib_g > 0.35:
            v_status, v_color = "CRITICAL", "#EF4444"
        elif vib_g > 0.12:
            v_status, v_color = "ELEVATED", "#F59E0B"
        else:
            v_status, v_color = "NORMAL", "#10B981"

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
            st.plotly_chart(
                render_sparkline_chart(spark_vib, color_hex=v_color, height=52),
                use_container_width=True,
                config={'displayModeBar': False}
            )
            render_html(f"""
            <div style='display: flex; justify-content: space-between; font-size: 11px; font-family: "JetBrains Mono", monospace; color: #94A3B8; border-top: 1px solid #1F2937; padding-top: 4px;'>
                <span>Seismic Shock Risk:</span>
                <b style='color: {v_color};'>{vib_risk_score:.1f} / 100</b>
            </div>
            """)

    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 7. Overall Landslide Risk Gauge & Normalization Breakdown
    # -------------------------------------------------------------------------
    st.markdown("<div class='hud-eyebrow'>COMPOSITE LANDSLIDE RISK ENGINE</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>Landslide Risk Assessment & Multi-Factor Synthesis</h3>", unsafe_allow_html=True)

    gauge_col, desc_col = st.columns([1.3, 1.7])

    with gauge_col:
        gauge_fig = build_four_sensor_risk_gauge(overall_score, risk_level, status_color, height=280)
        st.plotly_chart(gauge_fig, use_container_width=True, config={'displayModeBar': False})

    with desc_col:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span style='font-size: 11px; font-weight: 600; color: #94A3B8; text-transform: uppercase;'>Risk Classification</span>
                <span style='background: rgba({_hex_to_rgb(status_color)}, 0.15); border: 1px solid {status_color}; color: {status_color}; font-size: 12px; font-weight: 600; padding: 2px 10px; border-radius: 4px;'>
                    ● {risk_level} RISK ({overall_score:.1f}%)
                </span>
            </div>
            <div style='font-size: 14px; font-weight: 600; color: #F8FAFC; margin-top: 8px; line-height: 1.4;'>
                {status_msg}
            </div>
            <div style='font-size: 11px; color: #64748B; margin-top: 4px;'>
                Computed from 4 IoT transducers with provisional terrain thresholds.
            </div>
        </div>
        """)

        w_soil = st.session_state.sensor_weights["soil"]
        w_temp = st.session_state.sensor_weights["temperature"]
        w_slope = st.session_state.sensor_weights["slope"]
        w_vib = st.session_state.sensor_weights["vibration"]

        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 8px; padding: 14px 18px;'>
            <div style='font-size: 11px; font-weight: 600; color: #38BDF8; text-transform: uppercase; margin-bottom: 8px;'>
                Contributing Risk Scores (Normalized 0–100 Scale)
            </div>
            <div style='display: flex; flex-direction: column; gap: 8px; font-family: "JetBrains Mono", monospace; font-size: 11px;'>
                <div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 2px;'>
                        <span>💧 Soil Moisture Risk:</span>
                        <b>{soil_risk_score:.1f} / 100 <span style='color:#64748B;'>(Weight: {w_soil:.2f})</span></b>
                    </div>
                    <div style='background: #1F2937; height: 5px; border-radius: 3px; overflow: hidden;'>
                        <div style='background: #38BDF8; width: {soil_risk_score}%; height: 100%;'></div>
                    </div>
                </div>
                <div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 2px;'>
                        <span>🌡️ Temperature Risk:</span>
                        <b>{temp_risk_score:.1f} / 100 <span style='color:#64748B;'>(Weight: {w_temp:.2f})</span></b>
                    </div>
                    <div style='background: #1F2937; height: 5px; border-radius: 3px; overflow: hidden;'>
                        <div style='background: #10B981; width: {temp_risk_score}%; height: 100%;'></div>
                    </div>
                </div>
                <div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 2px;'>
                        <span>📐 Slope Inclinometer Risk:</span>
                        <b>{slope_risk_score:.1f} / 100 <span style='color:#64748B;'>(Weight: {w_slope:.2f})</span></b>
                    </div>
                    <div style='background: #1F2937; height: 5px; border-radius: 3px; overflow: hidden;'>
                        <div style='background: #F59E0B; width: {slope_risk_score}%; height: 100%;'></div>
                    </div>
                </div>
                <div>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 2px;'>
                        <span>⚡ Seismic Vibration Risk:</span>
                        <b>{vib_risk_score:.1f} / 100 <span style='color:#64748B;'>(Weight: {w_vib:.2f})</span></b>
                    </div>
                    <div style='background: #1F2937; height: 5px; border-radius: 3px; overflow: hidden;'>
                        <div style='background: #EF4444; width: {vib_risk_score}%; height: 100%;'></div>
                    </div>
                </div>
            </div>
            <div style='font-size: 10px; color: #64748B; margin-top: 8px;'>
                Formula: Overall Score = (Soil Risk × {w_soil:.2f} + Temp Risk × {w_temp:.2f} + Slope Risk × {w_slope:.2f} + Vib Risk × {w_vib:.2f})
            </div>
        </div>
        """)

    with st.expander("⚙️ Advanced Risk Engine Calibration & Configurable Sensor Weights", expanded=False):
        st.markdown("Adjust individual sensor weight coefficients and risk category partition bounds:")
        w_c1, w_c2, w_c3, w_c4 = st.columns(4)
        with w_c1:
            st.session_state.sensor_weights["soil"] = st.slider(
                "Soil Weight", min_value=0.0, max_value=1.0, value=st.session_state.sensor_weights["soil"], step=0.05
            )
        with w_c2:
            st.session_state.sensor_weights["temperature"] = st.slider(
                "Temp Weight", min_value=0.0, max_value=1.0, value=st.session_state.sensor_weights["temperature"], step=0.05
            )
        with w_c3:
            st.session_state.sensor_weights["slope"] = st.slider(
                "Slope Weight", min_value=0.0, max_value=1.0, value=st.session_state.sensor_weights["slope"], step=0.05
            )
        with w_c4:
            st.session_state.sensor_weights["vibration"] = st.slider(
                "Vibration Weight", min_value=0.0, max_value=1.0, value=st.session_state.sensor_weights["vibration"], step=0.05
            )

        st.caption("Notice: Coefficients are dynamically normalized if their sum does not equal 1.0.")

    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 8. ESP32 Telemetry vs Corridor Average & Proximity Alarm Cascade
    # -------------------------------------------------------------------------
    st.markdown("<div class='hud-eyebrow'>CORRIDOR BASELINE COMPARISON & PROXIMITY ADVISORIES</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>Corridor Baseline Comparison & Proximity Early Warning</h3>", unsafe_allow_html=True)

    anom_c1, anom_c2 = st.columns([2.0, 1.5])
    with anom_c1:
        sensitivity_pct = st.slider(
            "Corridor Anomaly Trigger Sensitivity (Trigger when node exceeds corridor average by)",
            min_value=10,
            max_value=60,
            value=25,
            step=5,
            format="+%d%% Above Average",
            key="anomaly_sensitivity_slider"
        )
    with anom_c2:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        btn_s1, btn_s2 = st.columns(2)
        with btn_s1:
            if st.button("⚡ Test ESP32 Surge", use_container_width=True, help="Simulate an acute ESP32 sensor spike on this node to trigger proximity alarms"):
                for s in st.session_state.stations_telemetry:
                    if s["id"] == selected_id:
                        s["soil_adc"] = 3500
                        s["tilt"] = 2.75
                        s["vib"] = True
                        s["vib_g"] = 0.48
                        s["temp_c"] = 0.5
                st.toast(f"ESP32 acute telemetry surge injected into node {selected_id}!", icon="⚡")
                st.rerun()
        with btn_s2:
            if st.button("↺ Reset Node", use_container_width=True):
                for s in st.session_state.stations_telemetry:
                    if s["id"] == selected_id:
                        s["soil_adc"] = 2100
                        s["tilt"] = 0.35
                        s["vib"] = False
                        s["vib_g"] = 0.04
                        s["temp_c"] = 15.0
                st.toast(f"Node {selected_id} restored to corridor baseline.", icon="✅")
                st.rerun()

    ratio = 1.0 + (sensitivity_pct / 100.0)
    anomaly_result = evaluate_neighborhood_anomaly(current_stn, enriched_stations, anomaly_ratio=ratio)
    averages = anomaly_result["averages"]

    comp_c1, comp_c2, comp_c3, comp_c4 = st.columns(4)
    with comp_c1:
        s_curr = soil_pct
        s_avg = averages.get("avg_soil", 35.0)
        s_diff_pct = ((s_curr - s_avg) / max(1.0, s_avg)) * 100.0
        s_color = "#EF4444" if s_diff_pct >= sensitivity_pct and s_curr > 50 else "#38BDF8"
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 12px;'>
            <div style='font-size: 11px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Soil Saturation</div>
            <div style='font-size: 18px; font-weight: 700; color: {s_color}; margin-top: 2px;'>{s_curr:.1f}% VWC</div>
            <div style='font-size: 11px; color: #64748B;'>Corridor Mean: <b>{s_avg:.1f}%</b></div>
            <div style='font-size: 11px; color: {s_color}; font-weight: 600; margin-top: 2px;'>
                {s_diff_pct:+.1f}% vs Corridor
            </div>
        </div>
        """)

    with comp_c2:
        t_curr = temp_c
        t_avg = averages.get("avg_temp", 14.5)
        t_diff = t_curr - t_avg
        t_color = "#EF4444" if -4.0 <= t_curr <= 4.0 else "#10B981"
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 12px;'>
            <div style='font-size: 11px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Temperature</div>
            <div style='font-size: 18px; font-weight: 700; color: {t_color}; margin-top: 2px;'>{t_curr:.1f}°C</div>
            <div style='font-size: 11px; color: #64748B;'>Corridor Mean: <b>{t_avg:.1f}°C</b></div>
            <div style='font-size: 11px; color: {t_color}; font-weight: 600; margin-top: 2px;'>
                {t_diff:+.1f}°C Delta
            </div>
        </div>
        """)

    with comp_c3:
        tilt_curr = tilt_deg
        tilt_avg = averages.get("avg_tilt", 0.25)
        tilt_diff_pct = ((tilt_curr - tilt_avg) / max(0.05, tilt_avg)) * 100.0
        tilt_color = "#EF4444" if tilt_diff_pct >= sensitivity_pct and tilt_curr > 0.8 else "#F59E0B"
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 12px;'>
            <div style='font-size: 11px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Slope Displacement</div>
            <div style='font-size: 18px; font-weight: 700; color: {tilt_color}; margin-top: 2px;'>{tilt_curr:.2f}°</div>
            <div style='font-size: 11px; color: #64748B;'>Corridor Mean: <b>{tilt_avg:.2f}°</b></div>
            <div style='font-size: 11px; color: {tilt_color}; font-weight: 600; margin-top: 2px;'>
                {tilt_diff_pct:+.1f}% vs Corridor
            </div>
        </div>
        """)

    with comp_c4:
        rk_curr = overall_score
        rk_avg = averages.get("avg_risk", 15.0)
        rk_diff_pct = ((rk_curr - rk_avg) / max(1.0, rk_avg)) * 100.0
        rk_color = "#EF4444" if rk_curr >= 50 else "#10B981"
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 12px;'>
            <div style='font-size: 11px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Composite Risk Index</div>
            <div style='font-size: 18px; font-weight: 700; color: {rk_color}; margin-top: 2px;'>{rk_curr:.1f} / 100</div>
            <div style='font-size: 11px; color: #64748B;'>Corridor Mean: <b>{rk_avg:.1f} pts</b></div>
            <div style='font-size: 11px; color: {rk_color}; font-weight: 600; margin-top: 2px;'>
                {rk_diff_pct:+.1f}% vs Corridor
            </div>
        </div>
        """)

    st.markdown("<br>", unsafe_allow_html=True)

    # Proximity Cascade Warning Display
    if anomaly_result["is_anomaly"]:
        for alarm in anomaly_result["alarm_messages"]:
            log_alert(
                station_id=alarm["target_station_id"],
                risk_level="HIGH",
                risk_score=overall_score,
                reason=alarm["message"],
                cooldown_minutes=5
            )

        render_html(f"""
        <div style='background: rgba(239, 68, 68, 0.12); border: 2px solid #EF4444; border-radius: 8px; padding: 14px 18px; margin-bottom: 14px;'>
            <div style='display: flex; align-items: center; justify-content: space-between;'>
                <div style='display: flex; align-items: center; gap: 12px;'>
                    <span style='font-size: 22px;'>🚨</span>
                    <div>
                        <div style='font-size: 13px; color: #EF4444; font-weight: 700;'>
                            CORRIDOR BASELINE ANOMALY — PROXIMITY ALERT ACTIVE
                        </div>
                        <div style='font-size: 12px; color: #F1F5F9; margin-top: 2px;'>
                            ESP32 Telemetry for <b>{selected_id} ({current_stn['name']})</b> exceeded corridor baseline average threshold by >{sensitivity_pct}%.
                        </div>
                    </div>
                </div>
                <div class='font-mono' style='background: #EF4444; color: #FFFFFF; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;'>
                    ALARM TRANSMITTED
                </div>
            </div>
        </div>
        """)

        st.markdown("#### Automated Advisory Messages Broadcasted to Nearby Mountain Sectors:")
        for alarm in anomaly_result["alarm_messages"]:
            render_html(f"""
            <div style='background: #111827; border-left: 4px solid #F59E0B; border-top: 1px solid #1F2937; border-right: 1px solid #1F2937; border-bottom: 1px solid #1F2937; border-radius: 6px; padding: 12px 16px; margin-bottom: 8px;'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <span style='font-size: 12px; font-weight: 600; color: #F59E0B;'>
                        Recipient: Adjacent Station {alarm['target_station_id']} — {alarm['target_station_name']}
                    </span>
                    <span class='font-mono' style='font-size: 11px; color: #38BDF8;'>
                        Distance: {alarm['distance_km']} km • Sector {alarm['sector_id']}
                    </span>
                </div>
                <div style='font-size: 12px; color: #E2E8F0; margin-top: 6px; line-height: 1.5;'>
                    {alarm['message']}
                </div>
                <div class='font-mono' style='font-size: 10px; color: #64748B; margin-top: 5px;'>
                    Dispatch Channel: VHF Ch-14 & Variable Message Signs (VMS)
                </div>
            </div>
            """)
    else:
        render_html(f"""
        <div style='background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 12px 16px; margin-bottom: 14px; display: flex; align-items: center; justify-content: space-between;'>
            <div style='display: flex; align-items: center; gap: 10px;'>
                <span style='font-size: 16px;'>🟢</span>
                <div>
                    <span style='font-size: 12px; color: #10B981; font-weight: 600;'>
                        CORRIDOR TELEMETRY BALANCED — ADJACENT NODES ON STANDBY
                    </span>
                    <div style='font-size: 12px; color: #CBD5E1; margin-top: 2px;'>
                        Node <b>{selected_id}</b> is within nominal deviation tolerance (Threshold: +{sensitivity_pct}% above corridor average). Adjacent stations remain on standby.
                    </div>
                </div>
            </div>
            <div class='font-mono' style='font-size: 11px; color: #10B981;'>
                ADJACENT NODES: STANDBY
            </div>
        </div>
        """)

    st.markdown("<hr style='border:0; border-top:1px solid #1F2937; margin: 16px 0;'>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 9. 2D Mountain Slope Stratigraphy Cross-Section (SVG)
    # -------------------------------------------------------------------------
    render_slope_cross_section_svg(tilt_degrees=tilt_deg, soil_pct=soil_pct, risk_level=risk_level)

    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 10. Synchronized Telemetry Waveforms
    # -------------------------------------------------------------------------
    st.markdown("<div class='hud-eyebrow'>TIME-SERIES TELEMETRY CHARTS</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>Temporal Telemetry Trends & Synchronized Waveforms</h3>", unsafe_allow_html=True)

    if hist_df.empty:
        st.info(f"No historical telemetry logged yet for station {selected_id} in {time_window}. Stream is actively logging.")
    else:
        chart_c1, chart_c2 = st.columns(2)
        plotly_theme = get_plotly_theme()

        with chart_c1:
            st.markdown("#### Hydrologic Saturation & Thermal Gradient")
            fig1 = go.Figure()

            fig1.add_trace(go.Scatter(
                x=hist_df["datetime"],
                y=hist_df["soil_moisture_pct"],
                name="Soil Saturation (% VWC)",
                line=dict(color="#38BDF8", width=2.2),
                mode='lines'
            ))

            if "temperature_c" in hist_df.columns:
                fig1.add_trace(go.Scatter(
                    x=hist_df["datetime"],
                    y=hist_df["temperature_c"],
                    name="Temperature (°C)",
                    line=dict(color="#10B981", width=1.8, dash="dot"),
                    yaxis="y2",
                    mode='lines'
                ))

            fig1.update_layout(
                **plotly_theme,
                height=310,
                xaxis=dict(gridcolor='#1F2937', zerolinecolor='#374151', showline=True, linecolor='#1F2937'),
                yaxis=dict(title="Soil Saturation (% VWC)", color="#38BDF8", showgrid=True, gridcolor="#1F2937"),
                yaxis2=dict(title="Temperature (°C)", color="#10B981", overlaying="y", side="right", showgrid=False),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig1, use_container_width=True)

        with chart_c2:
            st.markdown("#### Inclinometer Creep & Seismic Ground Acceleration")
            fig2 = go.Figure()

            fig2.add_trace(go.Scatter(
                x=hist_df["datetime"],
                y=hist_df["tilt_degrees"],
                name="Inclinometer Tilt (°)",
                line=dict(color="#F59E0B", width=2.2),
                fill='tozeroy',
                fillcolor='rgba(245, 158, 11, 0.08)',
                mode='lines'
            ))

            fig2.add_trace(go.Scatter(
                x=hist_df["datetime"],
                y=hist_df["vibration_intensity_g"],
                name="Peak Acceleration (g)",
                line=dict(color="#EF4444", width=1.6),
                yaxis="y2",
                mode='lines'
            ))

            fig2.add_hline(
                y=2.0,
                line_dash="dash",
                line_color="#EF4444",
                annotation_text="Critical Shear Limit (2.0°)",
                annotation_font_color="#EF4444"
            )

            fig2.update_layout(
                **plotly_theme,
                height=310,
                xaxis=dict(gridcolor='#1F2937', zerolinecolor='#374151', showline=True, linecolor='#1F2937'),
                yaxis=dict(title="Tilt Angle (°)", color="#F59E0B", showgrid=True, gridcolor="#1F2937"),
                yaxis2=dict(title="Seismic Acceleration (g)", color="#EF4444", overlaying="y", side="right", showgrid=False),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig2, use_container_width=True)

    # -------------------------------------------------------------------------
    # 11. Recent Alerts & Event Audit Log Table
    # -------------------------------------------------------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='hud-eyebrow'>INCIDENT AUDIT LOG</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>Recent Geotechnical Incident History</h3>", unsafe_allow_html=True)

    alerts_df = get_alerts()
    if not alerts_df.empty:
        station_alerts = alerts_df[alerts_df["station_id"] == selected_id].head(6)
        if not station_alerts.empty:
            display_alerts = station_alerts[["timestamp", "risk_level", "risk_score", "reason", "status"]].copy()
            display_alerts.columns = ["Timestamp (UTC)", "Risk Level", "Score", "Trigger Reason", "Operational Status"]
            st.dataframe(display_alerts, use_container_width=True, hide_index=True)
        else:
            st.caption(f"No recent security or risk alerts recorded for station {selected_id}.")
    else:
        st.caption("No alerts currently recorded in database.")

    # -------------------------------------------------------------------------
    # 12. Geotechnical Calibration & Sensor Specs Reference
    # -------------------------------------------------------------------------
    with st.expander("🔬 Transducer Calibration Matrix & Hardware Conversion Reference", expanded=False):
        st.markdown(r"""
        | Sensor Subsystem | Transducer Model | Transfer Function / Calibration Formula | Operational Range | Ingestion Rate |
        | :--- | :--- | :--- | :--- | :--- |
        | **1. Soil Moisture** | Capacitive VWC Probe v1.2 | $VWC(\%) = \frac{ADC - 1100}{2600} \times 100$ | 0 – 100% VWC | 1.0 Hz |
        | **2. Temperature** | Dallas DS18B20 1-Wire | Direct digital Celsius conversion (12-bit) | -40°C to +85°C | 0.5 Hz |
        | **3. Slope / Tilt** | MPU-6050 Tri-Axial MEMS | $\theta = \arccos\left(\frac{A_z}{\sqrt{A_x^2 + A_y^2 + A_z^2}}\right)$ | ±15.0° (0.01° res) | 10.0 Hz |
        | **4. Vibration / Tremor** | SW-420 Piezo Transducer | Peak Ground Acceleration ($g$) integration | 0.0 – 5.0 g | Interrupt driven |
        """)
        st.info("Scientific Notice: Landslide initiation is governed by complex shear-strain mechanics, geological discontinuity dip angles, and hydrologic pore-water dissipation. Do not claim that a landslide is certain based only on the average score.")
