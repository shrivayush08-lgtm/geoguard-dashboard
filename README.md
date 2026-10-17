# 🛡️ GeoGuard — Highway Intelligence & Landslide Early Warning System

> **A mission-critical disaster management control room and IoT telemetry analytics platform designed for mountainous highway corridors.**

---

## 📖 Executive Summary
GeoGuard transforms raw environmental and geotechnical sensor streams into actionable disaster early-warning intelligence. Developed specifically for high-risk mountain transit corridors like the **NH-58 Himalayan Highway (Rishikesh — Devprayag — Srinagar)**, GeoGuard bridges low-cost IoT sensor stations (ESP32/Arduino) with district disaster authorities, the Border Roads Organisation (BRO), and the National Disaster Response Force (NDRF).

---

## 🏛️ System Architecture

```
GeoGuard/
│
├── app.py                      # Main entry point & unified router
├── requirements.txt            # Python dependencies
├── README.md                   # System documentation & setup guide
│
├── .streamlit/
│   └── config.toml             # Custom theme (#0A101A) & navigation settings
│
├── database/
│   ├── __init__.py
│   └── db.py                   # SQLite engine, schema, indexing & CRUD
│
├── modules/
│   ├── __init__.py
│   ├── ui.py                   # Custom CSS, dark theme, banners & KPI cards
│   ├── data_store.py           # Central data coordinator & cache layer
│   ├── risk_engine.py          # Multi-factor geotechnical risk model & gauge
│   ├── sensor_simulator.py     # Physics-based telemetry & 24h historical seeder
│   ├── hardware_reader.py      # Non-blocking PySerial IoT gateway
│   ├── map_manager.py          # Folium GIS map with colored risk corridors
│   ├── weather_service.py      # Real-time mountain weather (Open-Meteo)
│   ├── ml_inference.py         # Scikit-learn Random Forest landslide classifier
│   └── report_generator.py     # CSV downloads & printable incident dossiers
│
├── pages/
│   ├── __init__.py
│   ├── overview.py             # 1. Overview Dashboard & matrix
│   ├── live_sensor.py          # 2. Live Sensor Telemetry & waveforms
│   ├── risk_intelligence.py    # 3. Geotechnical Risk Engine & gauge
│   ├── geographic_map.py       # 4. GIS Map & corridor overlays
│   ├── historical_analytics.py # 5. Cross-sensor correlation & trends
│   ├── alert_center.py         # 6. Incident lifecycle & audit trail
│   ├── highway_safety.py       # 7. Road closures & bypass routing
│   ├── emergency_response.py   # 8. Inter-agency crisis coordination
│   ├── hardware_management.py  # 9. PySerial COM port & sensor health
│   ├── reports.py              # 10. Data downloads & incident dossiers
│   └── settings.py             # 11. Thresholds, cooldowns & database tools
│
└── data/
    └── geoguard.db             # Local SQLite database
```

---

## ⚡ Key Features

1. **Mission Control Aesthetic:** Built with a dark navy (`#0A101A`) disaster-room theme, neon cyan (`#36D6E7`) accents, Space Grotesk / DM Sans typography, and color-coded risk alerts.
2. **Transparent Multi-Factor Risk Scoring:** Normalizes soil moisture (% VWC), precipitation intensity (mm/h), slope inclinometer shift (degrees), angular creep rate, and ground vibration into a 0–100 Landslide Risk Index.
3. **Interactive GIS Highway Corridors:** Folium-based map rendering highway polylines color-coded by risk (Green = Low, Yellow = Moderate, Orange = High, Red = Critical) with hazard buffer zones.
4. **Machine Learning Comparison:** Side-by-side Random Forest model estimating slope failure probability alongside the transparent rule-based standard.
5. **Real-Time Mountain Meteorology:** Automatic atmospheric telemetry synchronization via Open-Meteo API (requires zero API keys).
6. **Hardware Ingestion with PySerial:** Non-blocking serial port scanner reading newline-delimited JSON packets from physical ESP32 or Arduino nodes.
7. **End-to-End Alert Lifecycle:** Full incident transition workflow (`NEW` → `ACKNOWLEDGED` → `UNDER INVESTIGATION` → `RESOLVED`) with duplicate prevention cooldowns.
8. **Regulatory Reporting:** Export telemetry and alerts to CSV, or compile formal Markdown/HTML Geotechnical Incident Dossiers.

---

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.10, 3.11, 3.12, or 3.13
- Git

### 1. Clone or Open Project Directory
```powershell
cd "C:\Users\ayush srivastav\OneDrive\Desktop\geoguard-dashboard"
```

### 2. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### 3. Launch the Control Center
```powershell
python -m streamlit run app.py
```
The application will launch automatically in your browser at `http://localhost:8501`.

---

## 🕹️ Simulation & Testing Guide

### Operating in Simulation Mode (Default)
1. In the sidebar, ensure the **Simulation Telemetry Stream** toggle is enabled.
2. Click **⚡ Step Tick** to advance sensor readings by one measurement interval.
3. Check **Auto Stream** for a live 3-second continuous telemetry update loop.

### Testing Emergency Drill Mode
1. Click the red **🚨 TRIGGER EMERGENCY DRILL** button in the sidebar.
2. Station **GG-001 (NH-58 Mountain Pass)** will immediately experience a rapid landslide precursor surge:
   - Soil moisture escalates above 85% VWC
   - Precipitation surges past 40 mm/h
   - Slope inclinometer tilts beyond 3.0°
   - Seismic sensor flags active ground vibration
3. The system status banner turns red (**CRITICAL LANDSLIDE EVENT**), an automated alert is recorded in the **Alert Center**, and the **Geographic Risk Map** displays a red flashing corridor.
4. Click **↺ Reset Status & Baselines** to return all sectors to nominal conditions.

---

## 🔌 Hardware Connection Guide (ESP32 / Arduino)

### JSON Serial Protocol
Program your microcontroller to stream newline-delimited JSON messages at **115200 baud**:
```json
{
  "station_id": "GG-001",
  "soil_moisture_adc": 2340,
  "rain_sensor_adc": 1820,
  "tilt_degrees": 0.38,
  "vibration_detected": false,
  "timestamp": "2026-10-17T12:00:00Z"
}
```

### Pinout Reference (ESP32)
- **Capacitive Soil Moisture Probe v1.2:** Signal -> `GPIO 34 (ADC1)`
- **Optical Rain Sensor:** Signal -> `GPIO 35 (ADC1)`
- **MPU-6050 / ADXL345 Inclinometer:** SDA -> `GPIO 21`, SCL -> `GPIO 22`
- **SW-420 Vibration Sensor:** Digital Out -> `GPIO 4`

### Connecting in GeoGuard
1. Navigate to **9. Hardware & Sensor Management**.
2. Select your USB COM port from the detected list and choose `115200` baud.
3. Click **🔌 Connect Port**.
4. Disable "Simulation Mode" in the sidebar to view pure hardware readings.

---

## 🧪 Comprehensive Verification Checklist

- [x] Application launches cleanly on `python -m streamlit run app.py`.
- [x] All 11 sidebar navigation sections render without exceptions.
- [x] Top KPI cards dynamically compute from SQLite and active telemetry.
- [x] System Status Banner accurately changes color based on current risk state.
- [x] Plotly circular risk gauge and waveforms render responsively.
- [x] Folium GIS map displays 5 stations and colored NH-58 highway corridor segments.
- [x] Emergency Drill Mode triggers critical alerts without infinite duplicate spam.
- [x] Alert Center supports Acknowledge, Investigation, and Resolution transitions.
- [x] Highway Safety page allows road status updates that persist to SQLite.
- [x] Emergency Response page allows incident assignment to NDRF/SDRF units.
- [x] CSV downloads export valid telemetry and alert datasets.
- [x] Formal Incident Dossier compiles and downloads in Markdown/HTML.
- [x] Settings page persists custom thresholds and cooldown intervals.

---

## ⚠️ Safety & Operational Disclaimer
GeoGuard is an engineering prototype platform. Demonstration data, risk thresholds, and machine learning outputs are intended for technical demonstration and require field sensor calibration and domain geotechnical validation. GeoGuard does not automatically operate physical road barriers or replace official commands from district disaster management authorities or the Border Roads Organisation.
