"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/reports.py
Purpose: Regulatory Telemetry Archives, CSV Downloads & Formal Incident Dossiers
=============================================================================
Provides:
- One-click CSV exports for Telemetry History, Risk Assessments, Alerts, and Road Sections
- Formal Geotechnical Incident Dossier generator (Markdown/HTML printable format)
- Regulatory NDMA compliance audit formatting
"""
"""
GEOGUARD | Reports & Downloads
Dark mission-control design with one-click exports.
"""
"""
GeoGuard Reports & Data Center — pages/reports.py
Dashboard-style reporting page with one-click CSV exports and incident report
preview plus PDF, HTML, and Markdown downloads.
"""

import html
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from database.db import (
    get_connection,
    get_road_sections,
    get_response_teams,
)
from modules.report_generator import convert_df_to_csv


def read_table(query):
    conn = get_connection()
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


def val(row, key, default="Not recorded"):
    value = row.get(key, default)
    if value is None or pd.isna(value):
        return default
    value = str(value).strip()
    return value if value and value.lower() != "nan" else default


def build_report(alert, stations):
    station_id = val(alert, "station_id")

    station = next(
        (
            s for s in (stations or [])
            if str(s.get("id", s.get("station_id", "")))
            == str(station_id)
        ),
        {},
    )

    score = val(alert, "risk_score")
    coordinates = "Not recorded"

    try:
        if station.get("lat") is not None and station.get("lon") is not None:
            coordinates = (
                f"{float(station['lat']):.5f}, "
                f"{float(station['lon']):.5f}"
            )
    except (TypeError, ValueError):
        pass

    return {
        "id": val(alert, "alert_id"),
        "station": station_id,
        "location": val(station, "name", station_id),
        "corridor": val(station, "highway_corridor"),
        "coordinates": coordinates,
        "time": val(alert, "timestamp"),
        "risk": val(alert, "risk_level", "UNKNOWN").upper(),
        "score": f"{score}/100" if score != "Not recorded" else score,
        "status": val(alert, "status", "NEW"),
        "reason": val(alert, "reason", "No trigger reason recorded."),
        "generated": datetime.now(timezone.utc).strftime(
            "%d %b %Y, %H:%M UTC"
        ),
    }


def make_html(d):
    esc = lambda key: html.escape(str(d[key]))

    risk_color = (
        "#ff4058" if d["risk"] == "CRITICAL"
        else "#ffad42" if d["risk"] == "HIGH"
        else "#36d6e7"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GeoGuard Incident {esc('id')}</title>
<style>
body{{margin:0;background:#08111f;color:#edf5ff;
font:15px/1.6 Arial,sans-serif}}
main{{max-width:850px;margin:30px auto;padding:22px}}
header{{border-bottom:2px solid #36d6e7;padding-bottom:18px}}
.brand{{color:#36d6e7;letter-spacing:2px;font-size:12px}}
.muted,.label{{color:#9db0c8}}
.badge{{display:inline-block;border:1px solid {risk_color};
color:{risk_color};padding:4px 10px;border-radius:5px;font-weight:bold}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
gap:12px;margin:22px 0}}
.card,.section{{background:#101e31;border:1px solid #263b55;
border-radius:10px;padding:16px;margin-bottom:12px}}
.label{{font-size:11px;letter-spacing:1px}}
.value{{font-size:20px;font-weight:bold;overflow-wrap:anywhere}}
.notice{{background:#102638;border-left:3px solid #36d6e7;padding:14px}}
@media print{{body{{background:white;color:#111}}
.card,.section,.notice{{background:white;color:#111;border-color:#bbb}}}}
</style>
</head>
<body><main>
<header>
<div class="brand">GEOGUARD / INCIDENT ARCHIVE</div>
<h1>Geotechnical Incident Dossier</h1>
<div class="muted">GEO-INC-{esc('id')} · Generated {esc('generated')}</div>
<p><span class="badge">{esc('risk')}</span></p>
</header>
<div class="grid">
<div class="card"><div class="label">INCIDENT ID</div>
<div class="value">#{esc('id')}</div></div>
<div class="card"><div class="label">RISK INDEX</div>
<div class="value">{esc('score')}</div></div>
<div class="card"><div class="label">STATION</div>
<div class="value">{esc('station')}</div></div>
<div class="card"><div class="label">STATUS</div>
<div class="value">{esc('status')}</div></div>
</div>
<div class="section"><h2>01 · Location & Detection</h2>
<p><b>Location:</b> {esc('location')}</p>
<p><b>Highway corridor:</b> {esc('corridor')}</p>
<p><b>Coordinates:</b> {esc('coordinates')}</p>
<p><b>Recorded timestamp:</b> {esc('time')}</p></div>
<div class="section"><h2>02 · Trigger Evidence</h2>
<p>{esc('reason')}</p></div>
<div class="notice"><b>Prototype notice</b><br>
This system-generated dossier is not an official government warning or
verified landslide prediction. Verify site conditions and response actions
with qualified professionals and responsible authorities.</div>
</main></body></html>"""


def render_reports_page(enriched_stations):
    st.markdown("""
    <div style="color:#36D6E7;letter-spacing:2px;font-size:12px">
    GEOGUARD / MISSION CONTROL</div>
    <h1>Incident Reports & Dossiers</h1>
    <p style="color:#9DB0C8">
    Automated incident records · Evidence · Printable reports
    </p>
    """, unsafe_allow_html=True)

    try:
        telemetry = read_table(
            "SELECT * FROM telemetry_history "
            "ORDER BY reading_id DESC LIMIT 1000"
        )
        alerts = read_table(
            "SELECT * FROM alerts ORDER BY alert_id DESC"
        )
        roads = get_road_sections()
        teams = get_response_teams()
    except Exception as exc:
        st.error("Could not load the report archive.")
        st.caption(str(exc))
        return

    a, b, c, d = st.columns(4)
    a.metric("Telemetry records", len(telemetry))
    b.metric("Incident records", len(alerts))
    c.metric("Road sections", len(roads))
    d.metric("Response teams", len(teams))

    st.markdown("---")
    st.subheader("Data Export Center")

    exports = [
        ("Telemetry", telemetry, "telemetry"),
        ("Incident Alerts", alerts, "alerts"),
        ("Road Sections", roads, "roads"),
        ("Response Teams", teams, "teams"),
    ]

    columns = st.columns(4)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")

    for col, (title, frame, slug) in zip(columns, exports):
        with col:
            st.markdown(
                f"""<div style="background:#0D1829;border:1px solid #263B55;
                border-top:2px solid #36D6E7;border-radius:9px;padding:13px">
                <b>{title}</b><p style="color:#36D6E7">
                {len(frame)} records</p></div>""",
                unsafe_allow_html=True,
            )
            st.download_button(
                "Download CSV",
                data=convert_df_to_csv(frame),
                file_name=f"geoguard_{slug}_{stamp}.csv",
                mime="text/csv",
                key=f"export_{slug}",
                use_container_width=True,
            )

    st.markdown("---")
    st.subheader("🚨 Geotechnical Incident Dossier")

    if alerts.empty:
        st.info(
            "No incident has been recorded yet. Use the Emergency Drill "
            "control in the sidebar to test the simulated alert workflow."
        )
        st.caption(
            "A dossier will appear here after the system records an alert. "
            "No incident has been fabricated for this report."
        )
        return

    if "alert_id" not in alerts.columns:
        st.error("The alerts table does not contain alert_id.")
        return

    # Most recent alert is selected automatically.
    alert = alerts.iloc[0].to_dict()
    report = build_report(alert, enriched_stations)
    report_html = make_html(report)

    st.markdown(
        f"""<div style="background:#0A101A;border:1px solid #263B55;
        border-left:4px solid #FF4058;border-radius:10px;padding:18px">
        <div style="color:#36D6E7;letter-spacing:2px;font-size:11px">
        LATEST RECORDED INCIDENT</div>
        <h2 style="margin-bottom:4px">Incident #{html.escape(report['id'])}</h2>
        <p style="color:#9DB0C8;margin-top:0">
        {html.escape(report['location'])} ·
        {html.escape(report['time'])}</p></div>""",
        unsafe_allow_html=True,
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Risk level", report["risk"])
    m2.metric("Risk index", report["score"])
    m3.metric("Status", report["status"])

    if st.button(
        "↗ Open Latest Incident Dossier",
        type="primary",
        use_container_width=True,
    ):
        st.session_state["dossier_open"] = report["id"]

    if st.session_state.get("dossier_open") == report["id"]:
        st.markdown("### Geotechnical Incident Dossier")
        st.markdown(f"**Incident ID:** `{report['id']}`")
        st.markdown(f"**Station:** {report['station']}")
        st.markdown(f"**Location:** {report['location']}")
        st.markdown(f"**Highway corridor:** {report['corridor']}")
        st.markdown(f"**Coordinates:** {report['coordinates']}")
        st.markdown(f"**Recorded timestamp:** {report['time']}")
        st.markdown(f"**Risk level:** {report['risk']}")
        st.markdown(f"**Risk index:** {report['score']}")
        st.markdown(f"**Incident status:** {report['status']}")
        st.markdown("#### Recorded trigger")
        st.write(report["reason"])

        st.download_button(
            "⬇ Download / Open HTML Dossier",
            data=report_html.encode("utf-8"),
            file_name=f"GEO_INCIDENT_DOSSIER_{report['id']}.html",
            mime="text/html",
            use_container_width=True,
            key=f"dossier_download_{report['id']}",
        )
        st.caption(
            "Open the downloaded HTML file in your browser. "
            "Use Print → Save as PDF to create a PDF copy."
        )

    st.markdown("---")
    st.caption(
        "GeoGuard is an engineering prototype. Risk thresholds and outputs "
        "require field calibration and geotechnical validation."
    )
