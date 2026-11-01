"""
=============================================================================
GEOGUARD AI — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/reports.py
Purpose: Telemetry Archives, Risk Assessment Exports & Incident Dossiers
=============================================================================
"""

import html
import io
import sqlite3
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from database.db import get_connection, get_response_teams, get_road_sections


def read_table(query):
    try:
        conn = get_connection()
        frame = pd.read_sql_query(query, conn)
        conn.close()
        return frame
    except Exception:
        return pd.DataFrame()


def val(row, key, default="Not recorded"):
    if not isinstance(row, dict):
        return default
    value = row.get(key)
    if value is None:
        return default
    value = str(value).strip()
    return value if value and value.lower() != "nan" else default


def build_report(alert, stations, roads_df=None):
    station_id = val(alert, "station_id")

    station = next(
        (s for s in stations if str(s.get("id")) == str(station_id)),
        {},
    )

    lat = station.get("latitude")
    lon = station.get("longitude")
    coordinates = (
        f"{lat:.4f}°N, {lon:.4f}°E"
        if lat is not None and lon is not None
        else "Not recorded"
    )

    score = val(alert, "risk_score")
    try:
        score = f"{float(score):.1f}"
    except (TypeError, ValueError):
        pass

    # Correlate highway checkpoint & road status
    checkpoint = "Not recorded"
    road_status = "Not recorded"
    if roads_df is not None and not roads_df.empty:
        match_road = roads_df[roads_df["associated_station"].astype(str) == str(station_id)]
        if not match_road.empty:
            r = match_road.iloc[0]
            checkpoint = f"{r['section_id']}: {r['name']}"
            road_status = str(r['status']).strip().upper()

    # Sensor telemetry from station if available
    soil_moisture = f"{station.get('soil_moisture_pct')}% VWC" if station.get("soil_moisture_pct") is not None else "Not recorded"
    slope_tilt = f"{station.get('tilt')}°" if station.get("tilt") is not None else "Not recorded"
    rainfall_rate = f"{station.get('rainfall_intensity_mmh')} mm/h" if station.get("rainfall_intensity_mmh") is not None else "Not recorded"
    temp_val = station.get("temp_c", station.get("temperature_c"))
    temperature = f"{temp_val}°C" if temp_val is not None else "Not recorded"
    seismic = "DETECTED 🔴" if station.get("vib") else ("STABLE 🟢" if station else "Not recorded")

    officer = val(alert, "acknowledged_by")
    if officer == "Not recorded":
        officer = val(alert, "resolved_by", "Pending assignment")

    return {
        "id": val(alert, "alert_id"),
        "station": station_id,
        "checkpoint": checkpoint,
        "road_status": road_status,
        "location": val(station, "name", station_id),
        "corridor": val(station, "highway_corridor"),
        "coordinates": coordinates,
        "time": val(alert, "timestamp"),
        "risk": val(alert, "risk_level"),
        "score": f"{score}/100" if score != "Not recorded" else score,
        "status": val(alert, "status", "NEW"),
        "reason": val(alert, "reason", "No trigger reason recorded."),
        "assigned_team": val(alert, "assigned_team", "Unassigned"),
        "officer": officer,
        "ack_time": val(alert, "ack_timestamp", "N/A"),
        "res_time": val(alert, "res_timestamp", "N/A"),
        "soil_moisture": soil_moisture,
        "slope_tilt": slope_tilt,
        "rainfall_rate": rainfall_rate,
        "temperature": temperature,
        "seismic": seismic,
        "operator_notes": val(alert, "operator_notes", "None"),
        "generated": datetime.now(timezone.utc).strftime(
            "%d %b %Y, %H:%M UTC"
        ),
    }


def make_html(d):
    def esc(k):
        return html.escape(str(d.get(k, "")))

    color = "#FF4058" if "CRITICAL" in d.get("risk", "") else "#E8A238"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>GEOGUARD Incident Report #{esc('id')}</title>
<style>
body{{font-family:Arial,sans-serif;background:#050910;color:#E0EBF7;margin:0;padding:24px}}
.wrap{{max-width:820px;margin:0 auto;background:#0A101A;border:1px solid #1C2B3E;border-radius:12px;padding:32px}}
.head{{border-bottom:1px solid #1C2B3E;padding-bottom:16px;margin-bottom:20px}}
.meta{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0E1724;border:1px solid #1C2B3E;border-radius:8px;padding:12px}}
.label{{font-size:10px;color:#6C829D;text-transform:uppercase}}
.value{{font-size:16px;font-weight:bold;margin-top:4px}}
.section{{background:#0E1724;border:1px solid #1C2B3E;border-radius:10px;padding:16px;margin-bottom:12px}}
.notice{{background:#080D14;border:1px solid #1C2B3E;border-radius:8px;padding:12px;font-size:11px;color:#6C829D}}
h1{{margin:0;font-size:22px}}
h2{{margin:0 0 10px 0;font-size:14px;color:#36D6E7}}
p{{margin:4px 0;font-size:13px;line-height:1.5}}
</style>
</head>
<body>
<div class="wrap">
<div class="head">
<h1>GEOGUARD · Geotechnical Incident Dossier</h1>
<p style="color:#6C829D;font-size:12px;margin:4px 0 0 0">Generated: {esc('generated')} · Incident ID #{esc('id')}</p>
</div>
<div class="meta">
<div class="card"><div class="label">RISK LEVEL</div>
<div class="value" style="color:{color}">{esc('risk')}</div></div>
<div class="card"><div class="label">RISK SCORE</div>
<div class="value">{esc('score')}</div></div>
<div class="card"><div class="label">STATUS</div>
<div class="value">{esc('status')}</div></div>
</div>
<div class="section"><h2>01 · Location & Checkpoint Identification</h2>
<p><b>Highway checkpoint:</b> {esc('checkpoint')}</p>
<p><b>Road transit status:</b> {esc('road_status')}</p>
<p><b>Station location:</b> {esc('location')}</p>
<p><b>Highway corridor:</b> {esc('corridor')}</p>
<p><b>Coordinates:</b> {esc('coordinates')}</p>
<p><b>Recorded timestamp:</b> {esc('time')}</p></div>
<div class="section"><h2>02 · Trigger Evidence & Physical Anomaly</h2>
<p>{esc('reason')}</p></div>
<div class="section"><h2>03 · Response Operations & Assignment</h2>
<p><b>Assigned response unit:</b> {esc('assigned_team')}</p>
<p><b>Assigned watch officer:</b> {esc('officer')}</p>
<p><b>Acknowledgment timestamp:</b> {esc('ack_time')}</p>
<p><b>Resolution timestamp:</b> {esc('res_time')}</p>
<p><b>Field notes:</b> {esc('operator_notes')}</p></div>
<div class="section"><h2>04 · Environmental & Sensor Telemetry</h2>
<p><b>Soil moisture:</b> {esc('soil_moisture')}</p>
<p><b>Slope inclinometer tilt:</b> {esc('slope_tilt')}</p>
<p><b>Precipitation rate:</b> {esc('rainfall_rate')}</p>
<p><b>Ambient temperature:</b> {esc('temperature')}</p>
<p><b>Seismic ground shock:</b> {esc('seismic')}</p></div>
<div class="notice"><b>Prototype notice</b><br>
This system-generated dossier is not an official government warning or
verified landslide prediction. Verify site conditions and response actions
with authorized highway management officers before acting.</div>
</div>
</body>
</html>"""


def make_markdown(d):
    color = "🔴" if "CRITICAL" in d.get("risk", "") else "🟡"

    return f"""# GEOGUARD · Geotechnical Incident Dossier

**Generated:** {d['generated']}
**Incident ID:** #{d['id']}

---

## Incident Overview

| Metric | Recorded value |
|---|---|
| Risk level | {color} {d['risk']} |
| Risk score | {d['score']} |
| Status | {d['status']} |

## Location & Identification

| Field | Recorded value |
|---|---|
| Station | {d['station']} |
| Highway checkpoint | {d['checkpoint']} |
| Road transit status | {d['road_status']} |
| Station location | {d['location']} |
| Highway corridor | {d['corridor']} |
| Coordinates | {d['coordinates']} |
| Timestamp | {d['time']} |

## Trigger Evidence

{d['reason']}

## Response Operations & Assignment

| Field | Recorded value |
|---|---|
| Assigned response unit | {d['assigned_team']} |
| Assigned watch officer | {d['officer']} |
| Acknowledgment timestamp | {d['ack_time']} |
| Resolution timestamp | {d['res_time']} |
| Field notes | {d['operator_notes']} |

## Environmental & Sensor Telemetry

| Sensor Factor | Recorded Reading |
|---|---|
| Soil moisture | {d['soil_moisture']} |
| Slope inclinometer tilt | {d['slope_tilt']} |
| Precipitation rate | {d['rainfall_rate']} |
| Ambient temperature | {d['temperature']} |
| Seismic ground shock | {d['seismic']} |

---

**Prototype notice:** This system-generated dossier is not an official
government warning or verified landslide prediction. Verify site conditions
and response actions with authorized highway management officers before acting.
"""


def render_reports_page(enriched_stations):
    st.markdown("<div class='hud-eyebrow'>REGULATORY ARCHIVES & AUDIT DOSSIERS</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Historical Reports & Regulatory Exports</h2>", unsafe_allow_html=True)

    try:
        telemetry = read_table(
            "SELECT * FROM telemetry_history "
            "ORDER BY reading_id DESC LIMIT 1000"
        )
        risk_assessments = read_table(
            "SELECT * FROM risk_assessments "
            "ORDER BY assessment_id DESC"
        )
        alerts = read_table(
            "SELECT * FROM alerts ORDER BY alert_id DESC"
        )
        roads = get_road_sections()
        teams = get_response_teams()

    except Exception:
        st.error("Could not load the report archive.")
        return

    a, b, c, d, e = st.columns(5)
    a.metric("Telemetry", len(telemetry))
    b.metric("Risk assessments", len(risk_assessments))
    c.metric("Incident records", len(alerts))
    d.metric("Road sections", len(roads))
    e.metric("Response teams", len(teams))

    st.markdown("---")
    st.subheader("Data Export Center")

    exports = [
        ("Telemetry", telemetry, "telemetry"),
        ("Risk Assessments", risk_assessments, "risk_assessments"),
        ("Incident Alerts", alerts, "alerts"),
        ("Road Sections", roads, "roads"),
        ("Response Teams", teams, "teams"),
    ]

    columns = st.columns(5)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")

    for col, (title, frame, slug) in zip(columns, exports):
        with col:
            st.markdown(f"**{title}**")
            st.caption(f"{len(frame)} records available")

            if frame.empty:
                st.caption("No records available yet.")
            else:
                csv_bytes = frame.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"⬇ Download {title} (CSV)",
                    data=csv_bytes,
                    file_name=f"geoguard_{slug}_{stamp}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key=f"csv_export_{slug}",
                )

    st.markdown("---")
    st.subheader("🚨 Geotechnical Incident Dossier")

    if alerts.empty:
        st.info("No recorded incidents available in the database yet.")
        return

    if "alert_id" not in alerts.columns:
        st.error("The alerts table does not contain alert_id.")
        return

    # Select any recorded incident, newest first.
    st.markdown("### Select an Incident")

    selected_index = st.selectbox(
        "Incident archive",
        options=list(range(len(alerts))),
        format_func=lambda i: (
            f"Incident #{val(alerts.iloc[i].to_dict(), 'alert_id')} · "
            f"{val(alerts.iloc[i].to_dict(), 'timestamp')} · "
            f"{val(alerts.iloc[i].to_dict(), 'risk_level', 'UNKNOWN')}"
        ),
        key="selected_incident_index",
    )

    alert = alerts.iloc[selected_index].to_dict()
    report = build_report(alert, enriched_stations, roads_df=roads)
    report_html = make_html(report)
    report_markdown = make_markdown(report)

    st.markdown(
        f"""<div style="background:#0A101A;border:1px solid #263B55;
        border-left:4px solid #FF4058;border-radius:10px;padding:18px">
        <div style="color:#36D6E7;letter-spacing:2px;font-size:11px">
        SELECTED RECORDED INCIDENT</div>
        <h2 style="margin-bottom:4px">Incident #{html.escape(report['id'])}</h2>
        <p style="color:#9DB0C8;margin-top:0">
        {html.escape(report['location'])} ·
        {html.escape(report['corridor'])} ·
        {html.escape(report['coordinates'])}
        </p>
        <p style="color:#E0EBF7">{html.escape(report['reason'])}</p>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("Risk Level", report["risk"])
    m2.metric("Composite Risk Score", report["score"])
    m3.metric("Status", report["status"])

    if st.button(
        "↗ Open Selected Incident Dossier",
        type="primary",
        use_container_width=True,
    ):
        st.session_state["dossier_open"] = (
            None
            if st.session_state.get("dossier_open") == report["id"]
            else report["id"]
        )

    if st.session_state.get("dossier_open") == report["id"]:
        st.markdown("### Geotechnical Incident Dossier")
        st.markdown(f"**Incident ID:** `#{report['id']}`")
        st.markdown(f"**Station:** {report['station']} — {report['location']}")
        st.markdown(f"**Highway Checkpoint:** {report['checkpoint']} (Road Status: `{report['road_status']}`)")
        st.markdown(f"**Corridor & Coordinates:** {report['corridor']} ({report['coordinates']})")
        st.markdown(f"**Recorded Timestamp:** {report['time']}")
        st.markdown(f"**Risk Level:** `{report['risk']}` | **Risk Score:** `{report['score']}`")
        st.markdown(f"**Incident Status:** `{report['status']}`")
        st.markdown(f"**Assigned Response Unit:** `{report['assigned_team']}` | **Duty Officer:** `{report['officer']}`")
        st.markdown(f"**Environmental Telemetry:** Soil: `{report['soil_moisture']}` | Tilt: `{report['slope_tilt']}` | Rain: `{report['rainfall_rate']}` | Temp: `{report['temperature']}` | Seismic: `{report['seismic']}`")
        st.markdown("#### Recorded trigger")
        st.write(report["reason"])

        h, m = st.columns(2)

        with h:
            st.download_button(
                "⬇ Download HTML Dossier",
                data=report_html.encode("utf-8"),
                file_name=f"GEO_INCIDENT_DOSSIER_{report['id']}.html",
                mime="text/html",
                use_container_width=True,
                key=f"dossier_html_{report['id']}",
            )

        with m:
            st.download_button(
                "⬇ Download Markdown Dossier",
                data=report_markdown.encode("utf-8"),
                file_name=f"GEO_INCIDENT_DOSSIER_{report['id']}.md",
                mime="text/markdown",
                use_container_width=True,
                key=f"dossier_md_{report['id']}",
            )

        st.caption(
            "Open the downloaded HTML file in your browser. "
            "Use Print → Save as PDF to create a PDF copy."
        )
