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


def get_value(row, key, default="Not recorded"):
    value = row.get(key, default)
    if value is None or pd.isna(value):
        return default
    value = str(value).strip()
    return value if value and value.lower() != "nan" else default


def build_dossier(alert, stations):
    station_id = get_value(alert, "station_id")
    station = next(
        (
            item for item in (stations or [])
            if str(item.get("id", item.get("station_id", "")))
            == str(station_id)
        ),
        {},
    )

    score = get_value(alert, "risk_score")
    coords = "Not recorded"
    try:
        if station.get("lat") is not None and station.get("lon") is not None:
            coords = f"{float(station['lat']):.5f}, {float(station['lon']):.5f}"
    except (TypeError, ValueError):
        pass

    return {
        "id": get_value(alert, "alert_id"),
        "station": station_id,
        "location": get_value(station, "name", station_id),
        "corridor": get_value(station, "highway_corridor"),
        "coordinates": coords,
        "timestamp": get_value(alert, "timestamp"),
        "risk": get_value(alert, "risk_level", "UNKNOWN").upper(),
        "score": f"{score}/100" if score != "Not recorded" else score,
        "status": get_value(alert, "status", "NEW"),
        "reason": get_value(alert, "reason", "No reason recorded."),
        "notes": get_value(alert, "operator_notes"),
        "acknowledged_by": get_value(alert, "acknowledged_by"),
        "ack_time": get_value(alert, "ack_timestamp"),
        "generated": datetime.now(timezone.utc).strftime(
            "%d %b %Y, %H:%M UTC"
        ),
    }


def make_html_report(d):
    e = lambda key: html.escape(str(d[key]))
    color = (
        "#ff4058" if d["risk"] == "CRITICAL"
        else "#ffad42" if d["risk"] == "HIGH"
        else "#36d6e7"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GeoGuard Dossier {e('id')}</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#08111f;color:#edf5ff;
font:15px/1.6 Arial,sans-serif}}
main{{max-width:900px;margin:30px auto;padding:22px}}
header{{border-bottom:2px solid #36d6e7;padding-bottom:18px}}
.eyebrow{{color:#36d6e7;letter-spacing:2px;font-size:12px}}
h1{{font-size:32px;margin:8px 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
gap:12px;margin:22px 0}}
.card,.section{{background:#101e31;border:1px solid #263b55;
border-radius:10px;padding:17px;margin-bottom:12px}}
.label{{font-size:11px;color:#9db0c8;letter-spacing:1px}}
.value{{font-size:20px;font-weight:bold;margin-top:6px;overflow-wrap:anywhere}}
.badge{{color:{color};border:1px solid {color};padding:4px 10px;
display:inline-block;border-radius:5px;font-weight:bold}}
.muted{{color:#9db0c8}}
.notice{{background:#102638;border-left:3px solid #36d6e7;padding:14px}}
@media print{{body{{background:white;color:#111}}
.card,.section,.notice{{background:white;color:#111;border-color:#bbb}}}}
</style>
</head>
<body><main>
<header>
<div class="eyebrow">GEOGUARD / INCIDENT ARCHIVE</div>
<h1>Geotechnical Incident Dossier</h1>
<div class="muted">Reference GEO-INC-{e('id')} · Generated {e('generated')}</div>
<p><span class="badge">{e('risk')}</span></p>
</header>
<div class="grid">
<div class="card"><div class="label">INCIDENT ID</div>
<div class="value">#{e('id')}</div></div>
<div class="card"><div class="label">RISK INDEX</div>
<div class="value">{e('score')}</div></div>
<div class="card"><div class="label">MONITORING STATION</div>
<div class="value">{e('station')}</div></div>
<div class="card"><div class="label">INCIDENT STATUS</div>
<div class="value">{e('status')}</div></div>
</div>
<div class="section"><h2>01 · Location & Detection</h2>
<p><b>Location:</b> {e('location')}</p>
<p><b>Highway corridor:</b> {e('corridor')}</p>
<p><b>Coordinates:</b> {e('coordinates')}</p>
<p><b>Recorded timestamp:</b> {e('timestamp')}</p></div>
<div class="section"><h2>02 · Recorded Trigger</h2>
<p>{e('reason')}</p></div>
<div class="section"><h2>03 · Response Audit Trail</h2>
<p><b>Status:</b> {e('status')}</p>
<p><b>Acknowledged by:</b> {e('acknowledged_by')}</p>
<p><b>Acknowledgment time:</b> {e('ack_time')}</p>
<p><b>Operator notes:</b> {e('notes')}</p></div>
<div class="notice"><b>Prototype safety notice</b><br>
This is a system-generated prototype report, not an official government
order or independently verified landslide prediction. Verify site conditions
and response actions with qualified professionals and responsible authorities.
Missing information is marked as not recorded.</div>
</main></body></html>"""


def render_reports_page(enriched_stations):
    st.markdown("""
    <div style="color:#36D6E7;letter-spacing:2px;font-size:12px">
    GEOGUARD / MISSION CONTROL</div>
    <h1>Reports & Downloads</h1>
    <p style="color:#9DB0C8">Incident intelligence · Data archive · Dossiers</p>
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
        st.error("Could not load report data.")
        st.caption(str(exc))
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Telemetry", len(telemetry))
    m2.metric("Incidents", len(alerts))
    m3.metric("Road sections", len(roads))
    m4.metric("Response teams", len(teams))

    st.markdown("---")
    st.subheader("Data Export Center")

    exports = [
        ("Telemetry History", telemetry, "telemetry"),
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
                border-top:2px solid #36D6E7;border-radius:9px;padding:14px">
                <b>{title}</b><p style="color:#36D6E7">{len(frame)} records</p>
                </div>""",
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
    st.caption("Select an incident and open its full dossier with one click.")

    if alerts.empty:
        st.info("No incidents recorded yet.")
        return

    if "alert_id" not in alerts.columns:
        st.error("The alerts table is missing alert_id.")
        return

    ids = alerts["alert_id"].tolist()
    labels = {
        row["alert_id"]: (
            f"#{row['alert_id']} · {get_value(row, 'station_id')} · "
            f"{get_value(row, 'risk_level', 'UNKNOWN')} · "
            f"{get_value(row, 'timestamp')}"
        )
        for _, row in alerts.iterrows()
    }

    selected = st.selectbox(
        "Choose incident",
        ids,
        format_func=lambda value: labels[value],
        key="selected_dossier",
    )

    alert = alerts[alerts["alert_id"] == selected].iloc[0].to_dict()
    dossier = build_dossier(alert, enriched_stations)
    report_html = make_html_report(dossier)

    # One click opens the selected dossier directly below.
    if st.button(
        "↗ Open Incident Dossier",
        type="primary",
        use_container_width=True,
        key="open_dossier",
    ):
        st.session_state["open_dossier_id"] = str(selected)

    if st.session_state.get("open_dossier_id") == str(selected):
        st.markdown(f"""
        <div style="background:#0A101A;border:1px solid #263B55;
        border-top:3px solid #36D6E7;padding:18px;border-radius:10px">
        <div style="color:#36D6E7;letter-spacing:2px;font-size:11px">
        DOSSIER OPEN · GEO-INC-{html.escape(str(selected))}</div>
        <h2>Geotechnical Incident Dossier</h2>
        <p style="color:#9DB0C8">Station {html.escape(dossier['station'])}
        · {html.escape(dossier['timestamp'])}</p></div>
        """, unsafe_allow_html=True)

        a, b, c = st.columns(3)
        a.metric("Risk level", dossier["risk"])
        b.metric("Risk index", dossier["score"])
        c.metric("Status", dossier["status"])

        st.markdown(f"**Incident ID:** `{dossier['id']}`")
        st.markdown(f"**Location:** {dossier['location']}")
        st.markdown(f"**Highway corridor:** {dossier['corridor']}")
        st.markdown(f"**Coordinates:** {dossier['coordinates']}")
        st.markdown(f"**Timestamp:** {dossier['timestamp']}")
        st.markdown("#### Recorded trigger")
        st.write(dossier["reason"])
        st.markdown("#### Response audit trail")
        st.write(f"**Acknowledged by:** {dossier['acknowledged_by']}")
        st.write(f"**Acknowledgment time:** {dossier['ack_time']}")
        st.write(f"**Operator notes:** {dossier['notes']}")

        st.warning(
            "Prototype report only. It is not an official government warning."
        )

        st.download_button(
            "⬇ Download HTML Dossier",
            data=report_html.encode("utf-8"),
            file_name=f"GEO_INCIDENT_DOSSIER_{selected}.html",
            mime="text/html",
            key=f"download_html_{selected}",
            use_container_width=True,
        )
        st.caption(
            "Open the downloaded HTML file in a browser. "
            "Use Print → Save as PDF for a PDF copy."
        )

    st.markdown("---")
    st.caption(
        "GeoGuard is an engineering prototype. Thresholds and risk outputs "
        "require field calibration and geotechnical validation."
    )
