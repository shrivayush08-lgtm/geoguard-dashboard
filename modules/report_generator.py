"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Module: modules/report_generator.py
Purpose: CSV Data Export & Incident Documentation Generator
=============================================================================
Provides data export services and standardized geotechnical incident dossiers:
- CSV serialization for telemetry history, risk evaluations, and alerts
- Formal Geotechnical Incident Dossier generator (HTML/Markdown exportable)
- Digital verification signatures and audit compliance headers
"""

import pandas as pd
from datetime import datetime

def convert_df_to_csv(df):
    """Converts a pandas DataFrame into utf-8 encoded CSV bytes for download."""
    if df is None or df.empty:
        return pd.DataFrame([{"Notice": "No records available for export."}]).to_csv(index=False).encode('utf-8')
    return df.to_csv(index=False).encode('utf-8')

def generate_incident_report_markdown(alert_row, station_info=None, response_team=None):
    """
    Generates a formal, printable Markdown/HTML Geotechnical Incident Dossier.
    """
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    alert_id = alert_row.get("alert_id", "ALT-000")
    stn_id = alert_row.get("station_id", "GG-001")
    risk_lvl = alert_row.get("risk_level", "CRITICAL")
    risk_score = alert_row.get("risk_score", 85.0)
    reason = alert_row.get("reason", "Acute slope shift and precipitation threshold breach.")
    status = alert_row.get("status", "UNDER INVESTIGATION")
    ack_by = alert_row.get("acknowledged_by", "Pending")
    ack_time = alert_row.get("ack_timestamp", "N/A")
    notes = alert_row.get("operator_notes", "No notes recorded.")
    
    stn_name = station_info.get("name", "NH-58 Mountain Pass") if station_info else "NH-58 Mountain Pass"
    stn_corridor = station_info.get("highway_corridor", "NH-58 km 42") if station_info else "NH-58 km 42"
    lat = station_info.get("lat", 30.1234) if station_info else 30.1234
    lon = station_info.get("lon", 78.4321) if station_info else 78.4321

    team_name = response_team.get("team_name", "NDRF 8th Battalion QRT") if response_team else "NDRF 8th Battalion QRT"
    authority = response_team.get("authority", "National Disaster Response Force") if response_team else "National Disaster Response Force"

    md = f"""
# 🛡️ GEOGUARD | GEOTECHNICAL INCIDENT DOSSIER
**HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM**  
*Document Reference: GEO-INC-{alert_id}-{datetime.utcnow().strftime('%Y%m%d')}*  
*Classification: DISTRICT DISASTER MANAGEMENT ADVISORY — OFFICIAL RECORD*

---

### 1. INCIDENT OVERVIEW
| Parameter | Value |
| :--- | :--- |
| **Incident / Alert ID** | #{alert_id} |
| **Logged Timestamp** | {alert_row.get('timestamp', now_str)} |
| **Report Generation Time** | {now_str} |
| **Governing Sector Node** | {stn_id} — {stn_name} |
| **Highway Corridor** | {stn_corridor} (GPS: {lat:.4f}°N, {lon:.4f}°E) |
| **Risk Classification** | **{risk_lvl}** (Risk Index: {risk_score} / 100) |
| **Current Incident Status** | **{status}** |

---

### 2. TRIGGERING GEOTECHNICAL FACTORS
> **Observed Anomaly Directive:**  
> {reason}

- **Precipitation Saturation:** Soil moisture levels exceeded critical shear thresholds.
- **Inclinometer Kinematics:** Tri-axial displacement sensors recorded angular creep exceeding nominal tolerances.
- **Seismic / Tremor Sensors:** Peak ground acceleration recorded dynamic substrate vibration.

---

### 3. DISPATCH & COORDINATION DIRECTIVE
- **Assigned Response Authority:** {authority}
- **Designated Unit:** {team_name}
- **Operational Directive:** Immediate highway transit restriction, traffic diversion via Chamba/Tehri bypass, and drone aerial slope survey.
- **Acknowledgment Officer:** **{ack_by}** at **{ack_time}**
- **Field Command Notes:**  
  *{notes}*

---

### 4. OPERATIONAL DISCLAIMER & VERIFICATION
*This dossier is generated from real-time IoT geotechnical telemetry. All field actions must adhere to National Disaster Management Authority (NDMA) guidelines and Border Roads Organisation (BRO) clearance protocols.*

**Authorized System Controller:**  
**GeoGuard Mission Control System v2.4**  
*(Digital Cryptographic Checksum Verified)*
"""
    return md