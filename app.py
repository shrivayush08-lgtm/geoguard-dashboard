"""
=============================================================================
PROJECT: GEOGUARD — OFF-GRID HIGHWAY LANDSLIDE EARLY WARNING
         AND AUTOMATED HIGHWAY INTERLOCK SYSTEM
File: app.py
Purpose: Main Application Entry Point, Navigation Router & Real-Time Orchestrator
=============================================================================
COMPETITION: Smart India Hackathon (SIH)
TARGET CORRIDOR: NH-58 Himalayan Highway (Rishikesh–Devprayag–Joshimath)

WHERE THIS CODE IS USED AND WHAT IT DOES:
-----------------------------------------------------------------------------
1. System Initialization:
   - Calls `init_db()` to bootstrap SQLite tables (stations, alerts, telemetry, roads).
   - Calls `seed_historical_telemetry_if_needed()` to preload 24 hours of baseline
     telemetry so all charts, sparklines, and maps are immediately functional.
2. Page Configuration & Professional Geotechnical Theme:
   - Sets wide layout, browser title, and shield icon via `st.set_page_config()`.
   - Injects custom dark command-center HUD stylesheet via `inject_custom_css()`.
3. Session State Management:
   - Manages live telemetry states, operating mode (Simulation vs Hardware ESP32),
     the Highway Interlock state machine, and communication gateways.
4. Serial & Telemetry Ingestion:
   - Simulation Mode: executes smooth random walk or deterministic SIH test scenarios
     (Low Risk, Moderate Risk, Critical Risk, ESP32 Surge, Reset).
   - Hardware Mode: reads live 4-value CSV or JSON frames from physical ESP32 via
     non-blocking `SerialTelemetryGateway`.
5. 4-Factor Composite Landslide Risk & Actuator Interlock:
   - Evaluates 0-100 risk index: Overall = (Soil*0.25 + Temp*0.25 + Slope*0.25 + Vib*0.25).
   - Tripping threshold > 70.0: closes simulated boom barrier, sets traffic signals to RED,
     and logs structured incident record to emergency agencies.
6. Navigation Routing:
   - Preserves the 7 core operational views:
     1. Overview Dashboard
     2. Live Sensor Monitoring & Interlock Center
     3. Geographic Risk Map & Live GPS Assets
     4. Alert Center
     5. Highway Safety & Road Closures
     6. Reports & Downloads
     7. Settings
=============================================================================
"""

import streamlit as st
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# SECTION 1: Database & Backend Modules Initialization
# ---------------------------------------------------------------------------
from database.db import (
    init_db,           # Initializes SQLite database schema
    log_alert,         # Logs alerts with cooldown & audit trail
    log_risk_assessment, # Persists risk assessment calculations
    log_telemetry,     # Persists sensor measurements
    get_config         # Reads persistent configuration parameters
)
from modules.ui import (
    inject_custom_css, # Injects dark command center HUD styles & geotechnical background
    render_hud_header, # Renders top telemetry status header
    render_disclaimer  # Displays the required operational safety disclaimer
)
from modules.sensor_simulator import (
    DEFAULT_STATIONS,                    # Default 5 NH-58 monitoring stations
    generate_telemetry_tick,             # Generates realistic environmental walks
    seed_historical_telemetry_if_needed  # Seeds 24h baseline if database is fresh
)
from modules.data_store import (
    enrich_station_telemetry, # Calculates multi-factor risk scores across all stations
    get_system_kpis           # Computes active stations, alerts, and system health
)
from modules.hardware_reader import SerialTelemetryGateway, get_hardware_gateway # Non-blocking PySerial ESP32 gateway
from modules.cloud_relay import fetch_telemetry_from_cloud # Cloud IoT Relay bridge
from modules.interlock import HighwayInterlockSystem       # Highway interlock & dispatch logger
from modules.gps_simulator import (
    DEFAULT_GPS_UNITS,  # Default 5 mobile emergency response & patrol units
    simulate_gps_tick   # Kinematic waypoint advancement along NH-58 corridor
)
from modules.gps_reader import GPSHardwareGateway # Modular real GPS telemetry gateway

# ---------------------------------------------------------------------------
# SECTION 2: Page View Renderers (Streamlined 7 Core Operational Pages)
# ---------------------------------------------------------------------------
import importlib
import pages.live_sensor
try:
    importlib.reload(pages.live_sensor)
except Exception:
    pass

from pages.overview import render_overview_page             # 1. Overview Dashboard
from pages.live_sensor import render_live_sensor_page       # 2. Live Sensor Monitoring & Interlock Center
from pages.geographic_map import render_geographic_map_page # 3. Geographic Risk Map & Live GPS Assets
from pages.alert_center import render_alert_center_page     # 4. Alert Center & Incident Queue
from pages.highway_safety import render_highway_safety_page # 5. Highway Safety & Road Closures
from pages.reports import render_reports_page               # 6. Reports & Data Downloads
from pages.settings import render_settings_page             # 7. System Settings & Calibration

# ---------------------------------------------------------------------------
# SECTION 3: Persistent Database Bootstrapping
# ---------------------------------------------------------------------------
init_db()
seed_historical_telemetry_if_needed()

# ---------------------------------------------------------------------------
# SECTION 4: Streamlit Page Configuration & Styling Injection
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="GeoGuard | Highway Control",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom dark command-center HUD styling and geotechnical background
inject_custom_css()

# ---------------------------------------------------------------------------
# SECTION 5: Global Session State Management
# ---------------------------------------------------------------------------
if 'stations_telemetry' not in st.session_state:
    st.session_state.stations_telemetry = [dict(s) for s in DEFAULT_STATIONS]

if 'gps_units' not in st.session_state:
    st.session_state.gps_units = [dict(u) for u in DEFAULT_GPS_UNITS]

if 'serial_gateway' not in st.session_state or not hasattr(st.session_state.serial_gateway, 'auto_detect_esp32'):
    st.session_state.serial_gateway = get_hardware_gateway(default_port="COM20", default_baud=115200)
    init_port, _ = SerialTelemetryGateway.auto_detect_esp32()
    if init_port:
        st.session_state.serial_gateway.port = init_port

if 'operating_mode' not in st.session_state:
    init_p, _ = SerialTelemetryGateway.auto_detect_esp32()
    st.session_state.operating_mode = "HARDWARE" if init_p else "SIMULATION"

if 'gps_gateway' not in st.session_state:
    st.session_state.gps_gateway = GPSHardwareGateway()

if 'interlock_system' not in st.session_state:
    st.session_state.interlock_system = HighwayInterlockSystem(hysteresis_ticks_required=3)

if 'emergency' not in st.session_state:
    st.session_state.emergency = True

if 'emergency_target' not in st.session_state:
    st.session_state.emergency_target = "GG-002"

if 'auto_tick' not in st.session_state:
    st.session_state.auto_tick = False

# ---------------------------------------------------------------------------
# SECTION 6: Live Telemetry Ingestion (Simulation Stream vs Physical Hardware)
# ---------------------------------------------------------------------------
if st.session_state.operating_mode == "SIMULATION":
    # 1. Advance fixed geotechnical monitoring stations
    st.session_state.stations_telemetry = generate_telemetry_tick(
        st.session_state.stations_telemetry,
        emergency=st.session_state.emergency,
        emergency_target=st.session_state.emergency_target
    )
    # 2. Advance mobile GPS asset tracking fleet along NH-58 corridor waypoints
    st.session_state.gps_units = simulate_gps_tick(
        st.session_state.gps_units,
        elapsed_sec=3.0,
        emergency=st.session_state.emergency,
        emergency_target=st.session_state.emergency_target
    )
elif st.session_state.operating_mode == "HARDWARE":
    # 1. Read fixed geotechnical station packet via USB serial (CSV or JSON)
    gw = get_hardware_gateway(default_port="COM20", default_baud=115200)
    st.session_state.serial_gateway = gw
    if not gw.is_connected and st.session_state.get("auto_detect_esp", True):
        # Auto-detect and connect to ESP32 on whatever USB port it is plugged into
        now_ts = time.time()
        if now_ts - getattr(gw, "last_auto_scan_time", 0.0) > 3.5:
            gw.last_auto_scan_time = now_ts
            detected_p, _ = gw.auto_detect_esp32()
            if detected_p:
                gw.connect(detected_p, getattr(gw, "baud", 115200))

    packet = None
    if gw.is_connected:
        st.session_state.hardware_source = "USB_SERIAL"
        packet = gw.read_latest_packet()
    else:
        # Check if Cloud IoT Relay has an active packet from run_cloud_bridge.py
        relay_packet = fetch_telemetry_from_cloud(max_age_seconds=60.0)
        if relay_packet:
            st.session_state.hardware_source = "CLOUD_RELAY"
            packet = relay_packet
        else:
            st.session_state.hardware_source = "DISCONNECTED"

    if packet:
            # Physical ESP32 receiver telemetry routes directly into Shivpuri (GG-002)
            # and also updates GG-001 and the currently viewed node so all screens reflect live hardware readings
            stn_id = packet.get("station_id", "GG-002")
            viewed_id = st.session_state.get("live_sensor_station_select", "GG-002")
            target_ids = {stn_id, "GG-002", "GG-001", viewed_id}
            for s in st.session_state.stations_telemetry:
                if s["id"] in target_ids:
                    s["soil_moisture_pct"] = packet.get("soil_moisture_pct", s.get("soil_moisture_pct", 35.0))
                    if "soil_adc" in packet and packet["soil_adc"] is not None:
                        s["soil_adc"] = packet["soil_adc"]
                    s["temp_c"] = packet.get("temperature_c", s.get("temp_c", 15.0))
                    s["temperature_c"] = s["temp_c"]
                    s["tilt"] = packet.get("tilt_degrees", s.get("tilt", 0.3))
                    s["tilt_degrees"] = s["tilt"]
                    s["vib"] = (packet.get("vibration_pga", 0.0) > 0.15)
                    s["vib_g"] = packet.get("vibration_pga", s.get("vib_g", 0.02))
                    s["rainfall_intensity_mmh"] = packet.get("rain_intensity_mmh", 0.0)
                    s["rain_intensity"] = s["rainfall_intensity_mmh"]
                    s["is_simulated"] = False
                    s["is_valid"] = packet.get("is_valid", True)
                    s["timestamp"] = packet.get("timestamp", datetime.now(timezone.utc).isoformat())

            # Persist incoming real hardware packet into SQLite history
            try:
                log_telemetry({
                    "timestamp": packet.get("timestamp", datetime.utcnow().isoformat()),
                    "station_id": stn_id,
                    "soil_adc": packet.get("soil_adc"),
                    "soil_moisture_pct": packet.get("soil_moisture_pct"),
                    "temperature_c": packet.get("temperature_c"),
                    "rain_adc": None,
                    "rainfall_intensity_mmh": packet.get("rain_intensity_mmh"),
                    "rain_acc_24h_mm": 0.0,
                    "tilt_degrees": packet.get("tilt_degrees"),
                    "tilt_rate_deg_h": 0.0,
                    "vibration_detected": 1 if (packet.get("vibration_pga", 0.0) > 0.15) else 0,
                    "vibration_intensity_g": packet.get("vibration_pga", 0.02),
                    "battery_pct": 99.0,
                    "is_simulated": 0
                })
            except Exception:
                pass

    # 2. Read live GPS hardware packets if GPS gateway is active
    if st.session_state.gps_gateway and st.session_state.gps_gateway.is_connected:
        gps_packet = st.session_state.gps_gateway.read_latest_packet()
        if gps_packet:
            target_u_id = gps_packet.get("unit_id")
            for u in st.session_state.gps_units:
                if u["unit_id"] == target_u_id:
                    u["lat"] = gps_packet.get("lat", u["lat"])
                    u["lon"] = gps_packet.get("lon", u["lon"])
                    u["speed_kmh"] = gps_packet.get("speed_kmh", u["speed_kmh"])
                    u["heading_deg"] = gps_packet.get("heading_deg", u["heading_deg"])
                    u["altitude_m"] = gps_packet.get("altitude_m", u.get("altitude_m", 620.0))
                    u["battery_pct"] = gps_packet.get("battery_pct", u.get("battery_pct", 95.0))
                    u["health_status"] = gps_packet.get("health_status", "NOMINAL")
                    u["satellites_in_view"] = gps_packet.get("satellites_in_view", u.get("satellites_in_view", 8))
                    u["last_valid_ping"] = gps_packet.get("last_valid_ping", u["last_valid_ping"])
                    u["data_source"] = "REAL_HARDWARE"
                    u["is_simulated"] = False

# Calculate real-time risk scores and categories across all stations
enriched_stations = enrich_station_telemetry(st.session_state.stations_telemetry)

# Automated Safety Trigger: Track critical state & all-clear resolution transitions
has_critical = any(stn["risk_level"] == "CRITICAL" for stn in enriched_stations)
was_critical = st.session_state.get("_was_critical_active", False)

if was_critical and not has_critical:
    # Alarm just stopped! Trigger all-clear resolution popup & banner
    st.toast("🟢 [RESOLVED] GeoGuard Alert: Landslide hazard at Shivpuri (GG-002) has cleared. Telemetry nominal. Sector reopened.", icon="✅")
    st.session_state._alert_resolved_timestamp = time.time()

st.session_state._was_critical_active = has_critical

# Automated Safety Trigger: Log critical alert with cooldown protection
for stn in enriched_stations:
    if stn["risk_level"] == "CRITICAL":
        cooldown_val = int(get_config("alert_cooldown_minutes", "10"))
        alert_id, created = log_alert(
            station_id=stn["id"],
            risk_level="CRITICAL",
            risk_score=stn["risk_score"],
            reason=f"Automated Alert: {'; '.join(stn['factors'])}",
            is_test=1 if st.session_state.emergency else 0,
            cooldown_minutes=cooldown_val
        )
        if created:
            bd = stn.get("breakdown", {})
            log_risk_assessment({
                "station_id": stn["id"],
                "risk_score": stn["risk_score"],
                "risk_level": stn["risk_level"],
                "soil_factor_score": bd.get("soil", 0.0),
                "rain_factor_score": bd.get("rain", 0.0),
                "tilt_factor_score": bd.get("slope", 0.0),
                "vib_factor_score": bd.get("vibration", 0.0),
                "contributing_factors": stn.get("factors", []),
                "recommended_action": stn.get("recommended_action", ""),
                "assessment_mode": "DRILL" if st.session_state.emergency else "AUTOMATED"
            })

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
    sim_toggle = st.checkbox(
        "Simulation Mode (No Hardware Required)",
        value=(st.session_state.operating_mode == "SIMULATION"),
        help="Mutually exclusive: Check to generate realistic simulation data; uncheck to read from USB serial."
    )
    st.session_state.operating_mode = "SIMULATION" if sim_toggle else "HARDWARE"

    # Simulation Testing Controls (Deterministic SIH Scenarios)
    if st.session_state.operating_mode == "SIMULATION":
        st.markdown("<div class='hud-eyebrow'>SIMULATION TEST SCENARIOS</div>", unsafe_allow_html=True)
        
        # 1. Test ESP32 Surge Button
        if st.button("⚡ Test ESP32 Surge", use_container_width=True, help="Injects an acute sensor spike into node GG-001"):
            for s in st.session_state.stations_telemetry:
                if s["id"] == "GG-001":
                    s["soil_adc"] = 3500
                    s["soil_moisture_pct"] = 78.0
                    s["temp_c"] = 0.5
                    s["tilt"] = 2.80
                    s["tilt_rate"] = 0.50
                    s["vib"] = True
                    s["vib_g"] = 0.42
                    s["rainfall_intensity_mmh"] = 42.0
                    s["rain_intensity"] = 42.0
            st.toast("ESP32 acute telemetry surge injected into GG-001!", icon="⚡")
            st.rerun()

        # 2. Test Low Risk Button (< 40.0)
        if st.button("🟢 Test Low Risk (< 40)", use_container_width=True, help="Sets deterministic readings producing score < 40 (Low Risk)"):
            for s in st.session_state.stations_telemetry:
                if s["id"] == "GG-001":
                    s["soil_adc"] = 1500
                    s["soil_moisture_pct"] = 20.0
                    s["temp_c"] = 18.0
                    s["tilt"] = 0.25
                    s["tilt_rate"] = 0.01
                    s["vib"] = False
                    s["vib_g"] = 0.02
                    s["rainfall_intensity_mmh"] = 1.5
                    s["rain_intensity"] = 1.5
            st.session_state.emergency = False
            st.session_state.interlock_system.reset_interlock()
            st.toast("Low Risk Scenario set on GG-001 (Score < 40)", icon="🟢")
            st.rerun()

        # 3. Test Moderate Risk Button (40.0 - 70.0)
        if st.button("🟡 Test Moderate Risk (40-70)", use_container_width=True, help="Sets deterministic readings producing score 40-70 (Moderate Risk)"):
            for s in st.session_state.stations_telemetry:
                if s["id"] == "GG-001":
                    s["soil_adc"] = 2350
                    s["soil_moisture_pct"] = 48.0
                    s["temp_c"] = 2.0  # freeze-thaw transition
                    s["tilt"] = 1.60
                    s["tilt_rate"] = 0.05
                    s["vib"] = False
                    s["vib_g"] = 0.16
                    s["rainfall_intensity_mmh"] = 26.5
                    s["rain_intensity"] = 26.5
            st.session_state.emergency = False
            st.toast("Moderate Risk Scenario set on GG-001 (40 <= Score <= 70)", icon="🟡")
            st.rerun()

        # 3b. Test Heavy Rain Event (Isolated 25% Rain Factor Test)
        if st.button("🌧️ Test Heavy Rain (45 mm/h)", use_container_width=True, help="Injects an isolated extreme precipitation event into GG-001"):
            for s in st.session_state.stations_telemetry:
                if s["id"] == "GG-001":
                    s["rainfall_intensity_mmh"] = 45.0
                    s["rain_intensity"] = 45.0
                    s["soil_moisture_pct"] = 62.0
                    s["temp_c"] = 14.0
                    s["tilt"] = 0.60
                    s["vib_g"] = 0.05
            st.toast("Heavy Rain Event (45 mm/h) injected into GG-001!", icon="🌧️")
            st.rerun()

        # 4. Test Critical Risk Button (> 70.0)
        if st.button("🔴 Test Critical Risk (> 70)", type="primary", use_container_width=True, help="Sets deterministic readings producing score > 70 (Critical Danger & Interlock Trip)"):
            for s in st.session_state.stations_telemetry:
                if s["id"] == "GG-002":
                    s["soil_adc"] = 3600
                    s["soil_moisture_pct"] = 82.0
                    s["temp_c"] = -1.5  # acute freeze-thaw wedging
                    s["tilt"] = 3.80   # shear plane slip
                    s["tilt_rate"] = 0.45
                    s["vib"] = True
                    s["vib_g"] = 0.45
                    s["rainfall_intensity_mmh"] = 48.5
                    s["rain_intensity"] = 48.5
            st.session_state.emergency = True
            st.session_state.emergency_target = "GG-002"
            # Mobilize emergency QRT units
            for u in st.session_state.gps_units:
                if u["unit_id"] in ["UNIT-SAR-01", "UNIT-BRO-753"]:
                    u["health_status"] = "DISPATCHED"
                    u["incident_assignment"] = "CRISIS DISPATCH — Emergency Response to Shivpuri (GG-002)"
            st.toast("CRITICAL DANGER: Interlock tripped, Barrier CLOSED, Signals RED!", icon="🔴")
            st.rerun()

        # 5. Reset Test Scenario Button
        if st.button("↺ Reset Test Scenario", use_container_width=True, help="Restores all sensor nodes and interlocks to nominal baselines"):
            st.session_state.emergency = False
            st.session_state.stations_telemetry = [dict(s) for s in DEFAULT_STATIONS]
            st.session_state.gps_units = [dict(u) for u in DEFAULT_GPS_UNITS]
            st.session_state.interlock_system.reset_interlock()
            st.toast("All scenarios and actuators reset to nominal baseline.", icon="✅")
            st.rerun()

    else:
        # Hardware Serial Receiver Management Console
        st.markdown("<div class='hud-eyebrow'>ESP32 HARDWARE INTERFACE</div>", unsafe_allow_html=True)
        gw = st.session_state.serial_gateway

        # Auto-detect ESP32 on any USB port
        detected_port, detected_desc = gw.auto_detect_esp32()
        candidates = gw.get_port_candidates()

        # Visual Auto-Detection Callout
        if detected_port:
            st.markdown(
                f"<div style='background:rgba(16,185,129,0.12); border:1px solid #10B981; border-radius:6px; padding:6px 10px; margin-bottom:8px;'>"
                f"<div style='font-size:11px; font-weight:700; color:#10B981;'>⚡ ESP32 AUTO-DETECTED</div>"
                f"<div style='font-size:13px; font-weight:600; color:#F3F4F6;'>Port: <code>{detected_port}</code></div>"
                f"<div style='font-size:10px; color:#9CA3AF;'>{detected_desc}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                "<div style='background:rgba(59,130,246,0.12); border:1px solid #3B82F6; border-radius:6px; padding:10px 12px; margin-bottom:10px;'>"
                "<div style='font-size:12px; font-weight:700; color:#38BDF8;'>☁️ CLOUD DEPLOYMENT NOTICE</div>"
                "<div style='font-size:11px; color:#CBD5E1; margin-top:4px; line-height:1.45;'>"
                "This website is running on Streamlit Cloud. Cloud servers cannot reach physical USB cables on your laptop.<br><br>"
                "<b>To stream live ESP32 readings:</b><br>"
                "1. <b>Close Arduino Serial Monitor</b> (to unlock COM20).<br>"
                "2. Run locally on your laptop: <code>streamlit run app.py</code><br>"
                "3. Open <b style='color:#38BDF8;'>http://localhost:8501</b>."
                "</div>"
                "</div>",
                unsafe_allow_html=True
            )

        st.checkbox(
            "⚡ Auto-Detect & Connect to Any Port",
            value=st.session_state.get("auto_detect_esp", True),
            key="auto_detect_esp",
            help="Automatically detects which USB port your ESP32 is plugged into and establishes live telemetry."
        )

        # Build clean port choice labels
        if candidates:
            port_labels = [c["label"] for c in candidates]
            if detected_port:
                default_port_idx = next((i for i, c in enumerate(candidates) if c["device"] == detected_port), 0)
            elif gw.is_connected:
                default_port_idx = next((i for i, c in enumerate(candidates) if c["device"] == gw.port), 0)
            else:
                default_port_idx = 0
        else:
            avail_ports = gw.list_available_ports()
            port_labels = avail_ports if avail_ports else ["COM20", "COM3", "COM4", "/dev/ttyUSB0"]
            default_port_idx = 0

        selected_label = st.selectbox("Serial Port (Auto-Ranked)", port_labels, index=default_port_idx)
        selected_port = selected_label.split()[0].strip() if " " in selected_label else selected_label.strip()
        selected_baud = st.selectbox("Baud Rate", [9600, 19200, 38400, 57600, 115200], index=4)

        if not gw.is_connected:
            btn_label = f"⚡ Connect ESP32 ({detected_port})" if detected_port else "🔌 Connect Receiver"
            if st.button(btn_label, type="primary", use_container_width=True):
                target_port = detected_port if detected_port else selected_port
                success, msg = gw.connect(target_port, selected_baud)
                if success:
                    st.toast(f"Connected to {target_port}!", icon="🔌")
                    st.rerun()
                else:
                    st.error(msg)
            
            # Show lock warning or status message if present
            if gw.status_message and ("locked" in gw.status_message.lower() or "busy" in gw.status_message.lower() or "access denied" in gw.status_message.lower()):
                st.error(f"⚠️ {gw.status_message}")
            elif gw.status_message and "Failed" in gw.status_message:
                st.warning(f"⚠️ {gw.status_message}")
        else:
            st.markdown(
                f"<div style='font-size:12px; color:#10B981; margin-bottom:6px;'>● <b>Connected:</b> <code>{gw.port}</code> @ {gw.baud} baud</div>",
                unsafe_allow_html=True
            )
            if st.button("⏹ Disconnect Receiver", use_container_width=True):
                gw.disconnect()
                st.toast("Disconnected from serial port.", icon="⏹")
                st.rerun()

        diag = gw.get_health_diagnostics()
        st.caption(f"Status: **{diag['status']}**")
        st.caption(f"Packets: **{diag['total_packets']}** | Errors: **{diag['malformed_rejected']}**")

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

    # Mobile Asset Fleet Quick Status in Sidebar
    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
    st.markdown("<div class='hud-eyebrow'>MOBILE ASSET FLEET</div>", unsafe_allow_html=True)
    dispatched_units = [u for u in st.session_state.gps_units if u.get("health_status") == "DISPATCHED"]
    if dispatched_units:
        st.markdown(f"<div style='font-size: 11px; color: #EF4444;'>🚨 <b>{len(dispatched_units)} Unit(s) Dispatched</b></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='font-size: 11px; color: #10B981;'>● <b>{len(st.session_state.gps_units)} Mobile Units</b> Nominal</div>", unsafe_allow_html=True)

    st.markdown("<hr style='border:0; border-top:1px solid #1F2937; margin: 12px 0;'>", unsafe_allow_html=True)
    
    # Telemetry Stepper Controls
    refresh_col1, refresh_col2 = st.columns([1, 1])
    with refresh_col1:
        if st.button("⚡ Step Tick", use_container_width=True, help="Advances simulation by one measurement tick"):
            st.rerun()
    with refresh_col2:
        auto_stream = st.checkbox("Auto Stream", value=st.session_state.auto_tick, help="Enables continuous telemetry refresh loop")
        st.session_state.auto_tick = auto_stream

    st.caption("GeoGuard v2.5.0 • SIH 2024–2026 Edition")

# ---------------------------------------------------------------------------
# SECTION 8: Global Command Center HUD Header
# ---------------------------------------------------------------------------
kpis = get_system_kpis(enriched_stations)
render_hud_header(
    operating_mode=st.session_state.operating_mode,
    total_stations=kpis["total_stations"],
    online_stations=kpis["online_stations"],
    network_health=kpis["network_health"]
)

# Prominent All-Clear Resolution Banner when alarm stops
if time.time() - st.session_state.get("_alert_resolved_timestamp", 0) < 25.0:
    st.success("🟢 **ALL CLEAR &bull; [RESOLVED]** GeoGuard Alert: Landslide hazard at Shivpuri (GG-002) has cleared. Telemetry nominal. Sector reopened.")

# ---------------------------------------------------------------------------
# SECTION 9: Navigation Routing Dispatcher
# ---------------------------------------------------------------------------
if menu_selection.startswith("1."):
    render_overview_page(enriched_stations)

elif menu_selection.startswith("2."):
    render_live_sensor_page(enriched_stations)

elif menu_selection.startswith("3."):
    render_geographic_map_page(enriched_stations)

elif menu_selection.startswith("4."):
    render_alert_center_page(enriched_stations)

elif menu_selection.startswith("5."):
    render_highway_safety_page(enriched_stations)

elif menu_selection.startswith("6."):
    render_reports_page(enriched_stations)

elif menu_selection.startswith("7."):
    render_settings_page()

# ---------------------------------------------------------------------------
# SECTION 10: Standard Operational Safety Disclaimer
# ---------------------------------------------------------------------------
render_disclaimer()

# ---------------------------------------------------------------------------
# SECTION 11: Controlled Telemetry Auto-Stream Loop
# ---------------------------------------------------------------------------
# In HARDWARE mode, auto-refresh every 1.2s to stream live sensor readings
if st.session_state.operating_mode == "HARDWARE":
    time.sleep(1.2)
    st.rerun()
elif st.session_state.auto_tick:
    time.sleep(3)
    st.rerun()
