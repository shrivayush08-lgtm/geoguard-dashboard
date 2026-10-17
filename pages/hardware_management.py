"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/hardware_management.py
Purpose: Hardware IoT Gateway, PySerial Diagnostics & CRT Telemetry Console
=============================================================================
Provides:
- Rack-Mount IoT Node Faceplate with live LED annunciators (PWR, TX, RX, ERR)
- PySerial USB COM port discovery & baud rate configuration
- Green/Cyan Phosphor CRT-style Serial Telemetry Terminal Console
- Packet integrity counters, CRC diagnostics, and data freshness tracking
- Microcontroller (ESP32/Arduino) wiring schematic reference
"""

import streamlit as st
import json
from modules.hardware_reader import SerialTelemetryGateway

def render_hardware_management_page():
    """Renders the physical IoT hardware configuration and serial diagnostic console."""
    st.markdown("<div class='hud-eyebrow'>IOT HARDWARE INTERFACE & TELEMETRY GATEWAY</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Hardware & Sensor Management</h2>", unsafe_allow_html=True)

    if "serial_gateway" not in st.session_state:
        st.session_state.serial_gateway = SerialTelemetryGateway()

    gateway = st.session_state.serial_gateway

    # 1. Rack-Mount Hardware Node Annunciator Faceplate
    diag = gateway.get_health_diagnostics()
    status_col = "#00E5A3" if "STREAMING" in diag["status"] else ("#FFB000" if "WAITING" in diag["status"] else "#8B9BB4")

    st.markdown(f"""
    <div style='background: #070D16; border: 2px solid #1B2F4C; border-radius: 8px; padding: 16px 22px; margin-bottom: 20px; box-shadow: inset 0 0 24px rgba(0,0,0,0.8), 0 4px 18px rgba(0,0,0,0.5);'>
        <div style='display: flex; justify-content: space-between; align-items: center;'>
            <div style='display: flex; align-items: center; gap: 14px;'>
                <div style='width: 14px; height: 14px; border-radius: 50%; background: {status_col}; box-shadow: 0 0 12px {status_col};'></div>
                <div>
                    <span style='font-size: 14px; font-weight: 600; color: #F8FAFC;'>GeoGuard Gateway Gateway • Unit 01</span>
                    <div style='font-size: 11px; color: #94A3B8; font-family: "JetBrains Mono";'>MODEM: SX1276 LORA / FTDI UART INTERFACE</div>
                </div>
            </div>
            <div style='display: flex; gap: 20px; font-family: "JetBrains Mono", monospace; font-size: 11px;'>
                <div><span style='color:{"#00E5A3" if diag["is_connected"] else "#334155"};'>●</span> PWR</div>
                <div><span style='color:{"#00F0FF" if diag["total_packets"] > 0 else "#334155"};'>●</span> LNK</div>
                <div><span style='color:{"#00E5A3" if diag["total_packets"] > 0 else "#334155"};'>●</span> RX</div>
                <div><span style='color:{"#FF2A4D" if diag["crc_errors"] > 0 else "#334155"};'>●</span> ERR</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Operating Mode & Serial Port Configuration
    cfg_col1, cfg_col2 = st.columns([1.5, 2])

    with cfg_col1:
        st.markdown("### Physical Serial Interface")
        
        available_ports = gateway.list_available_ports()
        port_options = available_ports if available_ports else ["No hardware ports found"]
        
        selected_port = st.selectbox("Target Serial Port (COM / ttyUSB)", port_options, index=0)
        selected_baud = st.selectbox("Baud Rate", [9600, 19200, 38400, 57600, 115200], index=4)

        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("🔌 Connect Port", type="primary", use_container_width=True, disabled=gateway.is_connected):
                if selected_port != "No hardware ports found":
                    success, msg = gateway.connect(selected_port, selected_baud)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.rerun()
                else:
                    st.warning("Please connect a physical ESP32/Arduino device to USB.")
        with btn_c2:
            if st.button("❌ Disconnect", use_container_width=True, disabled=not gateway.is_connected):
                gateway.disconnect()
                st.info("Serial interface safely disconnected.")
                st.rerun()

    with cfg_col2:
        st.markdown("### Hardware Diagnostics & Telemetry Freshness")
        st.markdown(f"""
        <div style='background: rgba(13, 24, 41, 0.9); border: 1px solid #1B2F4C; border-radius: 8px; padding: 18px; backdrop-filter: blur(8px);'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span class='font-hud' style='font-size: 11px; color: #8B9BB4;'>INTERFACE STATUS:</span>
                <span class='font-hud' style='font-size: 12px; font-weight: 700; color: {status_col};'>● {diag['status']}</span>
            </div>
            <hr style='border:0; border-top:1px solid #1B2F4C; margin: 12px 0;'>
            <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-family: "JetBrains Mono", monospace; font-size: 11px;'>
                <div>PORT: <b style='color:#F0F6FC;'>{diag['port'] or 'None'}</b></div>
                <div>BAUD: <b style='color:#00F0FF;'>{diag['baud']} bps</b></div>
                <div>PACKETS: <b style='color:#00E5A3;'>{diag['total_packets']}</b></div>
                <div>CRC ERRORS: <b style='color:{"#FF2A4D" if diag["crc_errors"] > 0 else "#8B9BB4"};'>{diag['crc_errors']}</b></div>
                <div>FRESHNESS: <b style='color:#00F0FF;'>{f"{diag['freshness_seconds']}s ago" if diag['freshness_seconds'] is not None else 'N/A'}</b></div>
                <div>LINK: <b style='color:{"#00E5A3" if diag["is_connected"] else "#8B9BB4"};'>{'ONLINE' if diag['is_connected'] else 'DISCONNECTED'}</b></div>
            </div>
            <div style='margin-top: 12px; font-size: 11px; color: #8B9BB4;'>
                <b>Driver Message:</b> {diag['status_message']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr style='border:0; border-top:1px solid #1B2F4C; margin: 20px 0;'>", unsafe_allow_html=True)

    # 3. Green Phosphor CRT-Style Serial Terminal Console
    st.markdown("### 🖥️ Real-Time Serial Telemetry Stream Console (CRT)")
    
    stream_content = ""
    if diag["last_reading"]:
        stream_content = json.dumps(diag["last_reading"], indent=2)
    else:
        # Show simulated incoming data stream format
        sample_packet = {
            "station_id": "GG-001",
            "soil_moisture_adc": 2340,
            "rain_sensor_adc": 1820,
            "tilt_degrees": 0.38,
            "vibration_detected": False,
            "timestamp": "2026-10-17T12:00:00Z"
        }
        stream_content = f"Awaiting incoming hardware packets on serial bus...\nSimulation telemetry stream specification:\n{json.dumps(sample_packet, indent=2)}"

    st.markdown(f"""
    <div style='background: #0E1422; border: 1px solid #1F2937; border-radius: 8px; padding: 18px; font-family: "JetBrains Mono", monospace; font-size: 12px; color: #38BDF8; overflow-x: auto;'>
        <div style='display: flex; justify-content: space-between; border-bottom: 1px solid #1F2937; padding-bottom: 6px; margin-bottom: 10px; color: #94A3B8; font-size: 10px;'>
            <span>TTY BUFFER • Baud: {diag['baud']} • UTF-8</span>
            <span>Packet Status: Valid</span>
        </div>
        <pre style='margin:0; color: #38BDF8; font-family: "JetBrains Mono", monospace; line-height: 1.4;'>{stream_content}</pre>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. Microcontroller Pinout & Wiring Reference
    with st.expander("🔌 ESP32 / Arduino Microcontroller Sensor Pinout Guide", expanded=False):
        st.markdown("""
        **Sensor Interface Reference for Prototype Station Node:**
        - **Microcontroller:** ESP32 NodeMCU-32S / ESP32-WROOM-32
        - **Capacitive Soil Moisture Probe (v1.2):**
          - VCC -> 3.3V, GND -> GND, Signal -> GPIO 34 (ADC1_CH6)
        - **Optical / Tipping Precipitation Sensor:**
          - VCC -> 5V / 3.3V, GND -> GND, Analog Pulse -> GPIO 35 (ADC1_CH7)
        - **Tri-Axial MEMS Inclinometer (MPU-6050 / ADXL345):**
          - VCC -> 3.3V, GND -> GND, SDA -> GPIO 21, SCL -> GPIO 22 (I2C Bus)
        - **Vibration Sensor (SW-420 Piezoelectric Sensor):**
          - VCC -> 3.3V, GND -> GND, Digital Out -> GPIO 4 (Interrupt)
        """)
