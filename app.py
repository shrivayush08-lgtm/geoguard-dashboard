"""
=============================================================================
PROJECT: GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
File: app.py
Purpose: Main Application Entry Point, Navigation Router & Real-Time Orchestrator
=============================================================================
WHERE THIS CODE IS USED AND WHAT IT DOES:
-----------------------------------------------------------------------------
1. System Initialization:
   - Calls `init_db()` to create SQLite tables (stations, alerts, telemetry, roads).
   - Calls `seed_historical_telemetry_if_needed()` to preload 24 hours of baseline
     telemetry so all charts and metrics are immediately populated.
2. Page Configuration & Theme:
   - Sets wide layout, browser tab title, and shield icon via `st.set_page_config()`.
   - Injects the custom command-center HUD styling via `inject_custom_css()`.
3. Session State Management:
   - Manages live telemetry states, operating mode (Simulation vs Hardware ESP32),
     emergency drill flags, and communication gateways.
4. Real-time Telemetry Ingestion:
   - In Simulation Mode: advances synthetic sensor measurements via `generate_telemetry_tick()`.
   - In Hardware Mode: reads live JSON packets from physical ESP32 via `SerialTelemetryGateway`.
5. Risk & Anomaly Assessment:
   - Enriches all stations using `enrich_station_telemetry()` to compute 0-100 risk indices.
   - Automatically logs critical alerts with a 10-minute cooldown to prevent spam.
6. Navigation Routing:
   - Provides a streamlined 7-page menu:
     1. Overview Dashboard (System overview, KPIs, and corridor status)
     2. Live Sensor Monitoring (ESP32 stream, threshold vs average, nearby alarms)
     3. Geographic Risk Map (GIS map with colored highway sectors)
     4. Alert Center (Active incident queue & operator management)
     5. Highway Safety & Road Closures (Roadway conditions & detour advisories)
     6. Reports & Downloads (CSV exports & printable incident dossiers)
     7. Settings (Threshold configurations & system parameters)
=============================================================================
"""

import streamlit as st
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# SECTION 1: Database & Backend Modules Initialization
# ---------------------------------------------------------------------------
# These imports handle SQLite persistence, styling, simulation, and data access.
from database.db import (
    init_db,           # Initializes SQLite database tables
    log_alert,         # Logs alerts with duplicate prevention
    log_telemetry,     # Persists sensor measurements
    get_config         # Reads persistent system settings
)
from modules.ui import (
    inject_custom_css, # Injects dark command center HUD styles
    render_hud_header, # Renders top military-style telemetry header
    render_disclaimer  # Displays the required safety disclaimer
)
from modules.sensor_simulator import (
    DEFAULT_STATIONS,                    # Default 5 NH-58 monitoring stations
    generate_telemetry_tick,             # Generates realistic physical sensor walks
    seed_historical_telemetry_if_needed  # Seeds 24h of history if database is fresh
)
from modules.data_store import (
    enrich_station_telemetry, # Calculates geotechnical risk for all stations
    get_system_kpis           # Computes active stations, alerts, and system health
)
from modules.hardware_reader import SerialTelemetryGateway # PySerial ESP32 gateway

# ---------------------------------------------------------------------------
# SECTION 2: Page View Renderers (Streamlined 7 Core Pages)
# ---------------------------------------------------------------------------
# We import only the 7 active operational views requested by the user.
from pages.overview import render_overview_page             # 1. Overview Dashboard
from pages.live_sensor import render_live_sensor_page       # 2. Live Sensor Monitoring & ESP32 Alarm
from pages.geographic_map import render_geographic_map_page # 3. Geographic Risk Map
from pages.alert_center import render_alert_center_page     # 4. Alert Center & Audit Trail
from pages.highway_safety import render_highway_safety_page # 5. Highway Safety & Road Closures
from pages.reports import render_reports_page               # 6. Reports & Data Downloads
from pages.settings import render_settings_page             # 7. System Settings & Configuration

# ---------------------------------------------------------------------------
# SECTION 3: Persistent Database Bootstrapping
# ---------------------------------------------------------------------------
# Creates all required tables if they do not exist and populates initial records.
init_db()
seed_historical_telemetry_if_needed()

# ---------------------------------------------------------------------------
# SECTION 4: Streamlit Page Configuration & Styling Injection
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="GeoGuard | Highway Control Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply the custom dark command-center stylesheet
inject_custom_css()

# ---------------------------------------------------------------------------
# SECTION 5: Global Session State Management
# ---------------------------------------------------------------------------
# Ensures application variables persist smoothly across Streamlit reruns.
if 'stations_telemetry' not in st.session_state:
    st.session_state.stations_telemetry = [dict(s) for s in DEFAULT_STATIONS]

if 'emergency' not in st.session_state:
    st.session_state.emergency = False

if 'emergency_target' not in st.session_state:
    st.session_state.emergency_target = "GG-001"

if 'operating_mode' not in st.session_state:
    st.session_state.operating_mode = "SIMULATION"

if 'dispatch_status' not in st.session_state:
    st.session_state.dispatch_status = "Standby — All Sector Rescue Units Nominal"

if 'serial_gateway' not in st.session_state:
    st.session_state.serial_gateway = SerialTelemetryGateway()

if 'auto_tick' not in st.session_state:
    st.session_state.auto_tick = False

# ---------------------------------------------------------------------------
# SECTION 6: Live Telemetry Ingestion (Simulation or Physical ESP32)
# ---------------------------------------------------------------------------
# In Simulation Mode: Updates sensor readings with smooth environmental random walks.
# In Hardware Mode: Reads incoming newline-delimited JSON packets from USB serial.
if st.session_state.operating_mode == "SIMULATION":
    st.session_state.stations_telemetry = generate_telemetry_tick(
        st.session_state.stations_telemetry,
        emergency=st.session_state.emergency,
        emergency_target=st.session_state.emergency_target
    )
elif st.session_state.operating_mode == "HARDWARE":
    packet = st.session_state.serial_gateway.read_latest_packet()
    if packet:
        stn_id = packet.get("station_id")
        for s in st.session_state.stations_telemetry:
            if s["id"] == stn_id:
                s["soil_adc"] = packet.get("soil_moisture_adc", s["soil_adc"])
                s["rain_adc"] = packet.get("rain_sensor_adc", s["rain_adc"])
                s["tilt"] = packet.get("tilt_degrees", s["tilt"])
                s["vib"] = packet.get("vibration_detected", s["vib"])
                s["temp_c"] = packet.get("temperature_c", s.get("temp_c", 15.0))
                s["is_simulated"] = False

# Evaluate real-time risk scores for all stations based on latest telemetry
enriched_stations = enrich_station_telemetry(st.session_state.stations_telemetry)

# Automated Safety Trigger: Log alert when any station breaches Critical limit
for stn in enriched_stations:
    if stn["risk_level"] == "CRITICAL":
        cooldown_val = int(get_config("alert_cooldown_minutes", "10"))
        log_alert(
            station_id=stn["id"],
            risk_level="CRITICAL",
            risk_score=stn["risk_score"],
            reason=f"Automated Alert: {'; '.join(stn['factors'])}",
            is_test=1 if st.session_state.emergency else 0,
            cooldown_minutes=cooldown_val
        )

# ---------------------------------------------------------------------------
# SECTION 7: Sidebar Navigation & Control Panel
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🛡️ GeoGuard")
    st.markdown("<div class='hud-eyebrow'>HIGHWAY INTELLIGENCE</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size: 11px; color: #94A3B8; margin-top: -2px;'>Himalayan Landslide Early Warning</div>", unsafe_allow_html=True)
    st.divider()

    # Streamlined 7 Navigation Sections
    menu_selection = st.radio(
        "Navigation",
        [
            "1. Overview Dashboard",
            "2. Live Sensor Monitoring",
            "3. Geographic Risk Map",
            "4. Alert Center",
            "5. Highway Safety & Road Closures",
            "6. Reports & Downloads",
            "7. Settings"
        ],
        index=0
    )

    st.divider()

    # Operating Mode Selector (Simulation Stream vs Physical ESP32)
    st.markdown("<div class='hud-eyebrow'>OPERATING MODE</div>", unsafe_allow_html=True)
    sim_toggle = st.toggle("Simulation Telemetry Stream", value=(st.session_state.operating_mode == "SIMULATION"))
    st.session_state.operating_mode = "SIMULATION" if sim_toggle else "HARDWARE"

    # Emergency Crisis Drill Testing Controls
    st.markdown("<div class='hud-eyebrow'>DRILL TESTING CONTROLS</div>", unsafe_allow_html=True)
    if st.button("🚨 Trigger Emergency Drill", type="primary", use_container_width=True):
        st.session_state.emergency = True
        st.session_state.emergency_target = "GG-001"
        st.toast("Emergency drill triggered on GG-001 Byasi Pass!", icon="🚨")
        st.rerun()

    if st.button("↺ Reset Status & Baselines", use_container_width=True):
        st.session_state.emergency = False
        st.session_state.dispatch_status = "Standby — All Sector Rescue Units Nominal"
        st.session_state.stations_telemetry = [dict(s) for s in DEFAULT_STATIONS]
        st.toast("System status reset to nominal baseline.", icon="✅")
        st.rerun()

    st.divider()

    # Monitored Sectors Status Summary
    st.markdown("<div class='hud-eyebrow'>SECTOR RISK SUMMARY</div>", unsafe_allow_html=True)
    for s in enriched_stations:
        badge_style = (
            "color: #EF4444;" if s["risk_level"] == "CRITICAL"
            else ("color: #F97316;" if s["risk_level"] == "HIGH"
            else ("color: #F59E0B;" if s["risk_level"] == "MODERATE" else "color: #10B981;"))
        )
        st.markdown(f"<div style='font-size: 11px; margin-bottom: 3px;'><span style='{badge_style}'>●</span> <b>{s['id']}</b>: {s['name'][:18]} <span style='float:right; {badge_style}'>{s['risk_score']}</span></div>", unsafe_allow_html=True)

    st.markdown("<hr style='border:0; border-top:1px solid #1F2937; margin: 12px 0;'>", unsafe_allow_html=True)
    
    # Telemetry Stepper Controls
    refresh_col1, refresh_col2 = st.columns([1, 1])
    with refresh_col1:
        if st.button("⚡ Step Tick", use_container_width=True, help="Advances simulation by one measurement tick"):
            st.rerun()
    with refresh_col2:
        auto_stream = st.checkbox("Auto Stream", value=st.session_state.auto_tick, help="Enables continuous telemetry refresh loop")
        st.session_state.auto_tick = auto_stream

    st.caption("GeoGuard v2.4.0 • NH-58 Corridor")

# ---------------------------------------------------------------------------
# SECTION 8: Global Command Center HUD Header
# ---------------------------------------------------------------------------
# Displays real-time UTC/IST clocks, active nodes count, and link health.
kpis = get_system_kpis(enriched_stations)
render_hud_header(
    operating_mode=st.session_state.operating_mode,
    total_stations=kpis["total_stations"],
    online_stations=kpis["online_stations"],
    network_health=kpis["network_health"]
)

# ---------------------------------------------------------------------------
# SECTION 9: Navigation Routing Dispatcher
# ---------------------------------------------------------------------------
# Routes user selection to the corresponding modular page renderer.
if menu_selection.startswith("1."):
    # Page 1: High-level overview, KPI cards, and live corridor telemetry matrix
    render_overview_page(enriched_stations)

elif menu_selection.startswith("2."):
    # Page 2: Live ESP32 monitoring, corridor baseline comparison & nearby alarm cascade
    render_live_sensor_page(enriched_stations)

elif menu_selection.startswith("3."):
    # Page 3: Full-width Folium GIS map with colored highway corridors and weather ribbon
    render_geographic_map_page(enriched_stations)

elif menu_selection.startswith("4."):
    # Page 4: Emergency alert management center, audit log, and status transitions
    render_alert_center_page(enriched_stations)

elif menu_selection.startswith("5."):
    # Page 5: Road closure controls, checkpoint runway schematic, and bypass detour advisories
    render_highway_safety_page(enriched_stations)

elif menu_selection.startswith("6."):
    # Page 6: CSV downloads (telemetry, alerts, roads) & formal incident dossiers
    render_reports_page(enriched_stations)

elif menu_selection.startswith("7."):
    # Page 7: Geotechnical thresholds configuration, alert cooldowns, and database tools
    render_settings_page()

# ---------------------------------------------------------------------------
# SECTION 10: Standard Operational Safety Disclaimer
# ---------------------------------------------------------------------------
render_disclaimer()

# ---------------------------------------------------------------------------
# SECTION 11: Controlled Telemetry Auto-Stream Loop
# ---------------------------------------------------------------------------
if st.session_state.auto_tick:
    time.sleep(3)
    st.rerun()