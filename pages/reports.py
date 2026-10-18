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

import html
import streamlit as st
import pandas as pd
from datetime import datetime

from database.db import (
    get_connection,
    get_road_sections,
    get_response_teams,
)
from modules.report_generator import (
    convert_df_to_csv,
    generate_incident_report_markdown,
)
from modules.ui import render_html


def _read_table(query):
    """Read a database table safely and always close its connection."""
    conn = get_connection()
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


def _download_card(title, description, icon, dataframe, filename, key):
    """Render a consistent dashboard-style export card."""
    st.markdown(
        f"""
        <div style="
            background:rgba(13,24,41,.92);
            border:1px solid #1B2F4C;
            border-top:2px solid #36D6E7;
            border-radius:10px;
            padding:16px;
            min-height:130px;
            margin-bottom:10px;">
            <div style="font-size:25px">{icon}</div>
            <div style="font-size:16px;font-weight:700;color:#F0F6FC;
                        margin-top:8px">{title}</div>
            <div style="font-size:12px;color:#9DB0C8;margin-top:5px">
                {description}
            </div>
            <div style="font-size:12px;color:#36D6E7;margin-top:10px">
                {len(dataframe):,} records available
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.download_button(
        label=f"⬇️ Download {title}",
        data=convert_df_to_csv(dataframe),
        file_name=filename,
        mime="text/csv",
        key=key,
        width="stretch",
    )


def _make_html_report(alert, station, markdown_report):
    """Create a standalone HTML report that opens in any browser."""
    alert_id = html.escape(str(alert.get("alert_id", "N/A")))
    station_id = html.escape(str(alert.get("station_id", "N/A")))
    risk = html.escape(str(alert.get("risk_level", "N/A")))
    score = html.escape(str(alert.get("risk_score", "N/A")))
    timestamp = html.escape(str(alert.get("timestamp", "N/A")))
    reason = html.escape(str(alert.get("reason", "No reason recorded.")))
    status = html.escape(str(alert.get("status", "N/A")))
    station_name = html.escape(
        str(station.get("name", station_id) if station else station_id)
    )
    generated = datetime.now().strftime("%d %b %Y, %H:%M")

    # Escape the generated Markdown before placing it in the HTML document.
    safe_report = html.escape(markdown_report)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GeoGuard Incident Report #{alert_id}</title>
<style>
    body {{
        margin:0; background:#08111F; color:#EAF2FF;
        font-family:Arial,Helvetica,sans-serif; line-height:1.6;
    }}
    .container {{max-width:900px;margin:35px auto;padding:24px;}}
    .header {{
        border-bottom:2px solid #36D6E7;padding-bottom:20px;
        margin-bottom:24px;
    }}
    .eyebrow {{color:#36D6E7;letter-spacing:2px;font-size:12px;}}
    h1 {{margin:8px 0;font-size:30px;}}
    .muted {{color:#9DB0C8;font-size:13px;}}
    .grid {{
        display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
        gap:12px;margin:20px 0;
    }}
    .card {{
        background:#101E31;border:1px solid #243A55;
        border-radius:10px;padding:16px;
    }}
    .label {{color:#9DB0C8;font-size:12px;}}
    .value {{font-size:20px;font-weight:bold;margin-top:6px;}}
    .section {{
        background:#101E31;border:1px solid #243A55;
        border-radius:10px;padding:20px;margin:18px 0;
    }}
    pre {{
        white-space:pre-wrap;overflow-wrap:anywhere;
        font-family:Arial,Helvetica,sans-serif;
    }}
    .notice {{
        border-left:3px solid #36D6E7;padding:12px 16px;
        background:#102638;color:#C9D8E8;font-size:13px;
    }}
    @media print {{
        body {{background:white;color:#111;}}
        .card,.section,.notice {{background:white;color:#111;border-color:#ccc;}}
        .muted,.label {{color:#444;}}
    }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="eyebrow">GEOGUARD / INCIDENT ARCHIVE</div>
        <h1>Incident Report #{alert_id}</h1>
        <div class="muted">Generated {generated} · Prototype report</div>
    </div>

    <div class="grid">
        <div class="card"><div class="label">MONITORING NODE</div>
            <div class="value">{station_id}</div></div>
        <div class="card"><div class="label">RISK LEVEL</div>
            <div class="value">{risk}</div></div>
        <div class="card"><div class="label">RISK SCORE</div>
            <div class="value">{score}</div></div>
        <div class="card"><div class="label">INCIDENT STATUS</div>
            <div class="value">{status}</div></div>
    </div>

    <div class="section">
        <h2>Incident Overview</h2>
        <p><b>Station:</b> {station_name}</p>
        <p><b>Timestamp:</b> {timestamp}</p>
        <p><b>Reported reason:</b> {reason}</p>
    </div>

    <div class="section">
        <h2>Detailed Report</h2>
        <pre>{safe_report}</pre>
    </div>

    <div class="notice">
        <b>Important:</b> GeoGuard is an engineering prototype.
        Sensor readings, thresholds, and risk outputs require field
        calibration and geotechnical validation. This report is not an
        official warning or a substitute for guidance from relevant authorities.
    </div>
</div>
</body>
</html>"""


def render_reports_page(enriched_stations):
    """Render the GeoGuard Reports & Downloads page."""

    # ---------- Page heading ----------
    st.markdown(
        """
        <div style="margin-bottom:4px;color:#36D6E7;
                    font-size:12px;letter-spacing:2px;font-weight:700">
            GEOGUARD / DATA MANAGEMENT
        </div>
        <h1 style="margin-top:0;margin-bottom:4px">
            Reports & Downloads
        </h1>
        <p style="color:#9DB0C8;margin-top:0">
            Export monitoring records and generate incident reports.
        </p>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        div[data-testid="stDownloadButton"] button {
            border:1px solid #2A526A;
            border-radius:8px;
            font-weight:600;
        }
        div[data-testid="stDownloadButton"] button:hover {
            border-color:#36D6E7;
            color:#36D6E7;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ---------- Load data ----------
    try:
        telemetry_df = _read_table(
            "SELECT * FROM telemetry_history "
            "ORDER BY reading_id DESC LIMIT 1000"
        )
        alerts_df = _read_table(
            "SELECT * FROM alerts ORDER BY alert_id DESC"
        )
        risks_df = _read_table(
            "SELECT * FROM risk_assessments ORDER BY assessment_id DESC"
        )
        roads_df = get_road_sections()
        teams_df = get_response_teams()

    except Exception as exc:
        st.error("Unable to load report data from the database.")
        st.caption(f"Technical detail: {exc}")
        return

    # ---------- Overview metrics ----------
    st.markdown("### System archive overview")

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Telemetry records", f"{len(telemetry_df):,}")
    metric2.metric("Alert records", f"{len(alerts_df):,}")
    metric3.metric("Road sections", f"{len(roads_df):,}")
    metric4.metric("Response teams", f"{len(teams_df):,}")

    if not telemetry_df.empty and "is_simulated" in telemetry_df.columns:
        simulated = pd.to_numeric(
            telemetry_df["is_simulated"], errors="coerce"
        ).fillna(1)
        simulated_count = int((simulated == 1).sum())
        st.caption(
            f"Latest telemetry export: {len(telemetry_df):,} records. "
            f"{simulated_count:,} are marked as simulated."
        )

    st.markdown("---")

    # ---------- CSV export hub ----------
    st.markdown("### 📦 Data export center")
    st.caption(
        "Choose an export to download the available records as a CSV file."
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M")

    # Two rows of cards keep the layout readable on smaller screens.
    row1 = st.columns(3)
    with row1[0]:
        _download_card(
            "Telemetry log",
            "Sensor history · latest 1,000 readings",
            "📡",
            telemetry_df,
            f"geoguard_telemetry_{stamp}.csv",
            "download_telemetry",
        )
    with row1[1]:
        _download_card(
            "Incident alerts",
            "Alert history and status records",
            "🚨",
            alerts_df,
            f"geoguard_alerts_{stamp}.csv",
            "download_alerts",
        )
    with row1[2]:
        _download_card(
            "Risk assessments",
            "Recorded risk scores and contributing factors",
            "📈",
            risks_df,
            f"geoguard_risk_assessments_{stamp}.csv",
            "download_risks",
        )

    row2 = st.columns(2)
    with row2[0]:
        _download_card(
            "Road sections",
            "Corridor details and recorded status",
            "🛣️",
            roads_df,
            f"geoguard_road_sections_{stamp}.csv",
            "download_roads",
        )
    with row2[1]:
        _download_card(
            "Response teams",
            "Response-unit roster and assignments",
            "🧭",
            teams_df,
            f"geoguard_response_teams_{stamp}.csv",
            "download_teams",
        )

    st.markdown("---")

    # ---------- Incident report generator ----------
    st.markdown("### 📄 Incident report generator")
    st.caption(
        "Select an existing alert to preview and download its report."
    )

    if alerts_df.empty:
        st.info("No alert records are available to generate a report yet.")
        return

    if "alert_id" not in alerts_df.columns:
        st.error("The alerts table does not contain an alert_id column.")
        return

    alert_options = {}
    for _, row in alerts_df.iterrows():
        alert_id = row["alert_id"]
        station_id = row.get("station_id", "Unknown")
        risk_level = row.get("risk_level", "Unknown")
        timestamp = row.get("timestamp", "No timestamp")
        alert_options[alert_id] = (
            f"Alert #{alert_id} · {station_id} · "
            f"{risk_level} · {timestamp}"
        )

    selected_alert_id = st.selectbox(
        "Choose an incident",
        options=list(alert_options.keys()),
        format_func=lambda value: alert_options[value],
        key="geoguard_selected_report_alert",
    )

    selected_rows = alerts_df[
        alerts_df["alert_id"] == selected_alert_id
    ]
    alert_row = selected_rows.iloc[0].to_dict()

    station_match = next(
        (
            station for station in (enriched_stations or [])
            if station.get("id") == alert_row.get("station_id")
            or station.get("station_id") == alert_row.get("station_id")
        ),
        None,
    )

    report_md = generate_incident_report_markdown(
        alert_row,
        station_info=station_match,
    )

    # Show the report directly; no expander click required.
    st.markdown("#### Report preview")
    st.markdown(
        """
        <div style="border-left:3px solid #36D6E7;
                    padding-left:14px;margin-bottom:12px">
            <span style="color:#36D6E7;font-size:12px;
                         letter-spacing:1px">
                SELECTED INCIDENT
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(report_md)

    html_report = _make_html_report(
        alert_row,
        station_match,
        report_md,
    )

    st.markdown("#### Download this report")
    report_col1, report_col2 = st.columns(2)

    with report_col1:
        st.download_button(
            label="🌐 Download HTML report",
            data=html_report.encode("utf-8"),
            file_name=f"geoguard_incident_{selected_alert_id}.html",
            mime="text/html",
            key="download_incident_html",
            type="primary",
            width="stretch",
        )

    with report_col2:
        st.download_button(
            label="📝 Download Markdown report",
            data=report_md.encode("utf-8"),
            file_name=f"geoguard_incident_{selected_alert_id}.md",
            mime="text/markdown",
            key="download_incident_markdown",
            width="stretch",
        )

    st.caption(
        "Tip: Open the downloaded HTML file in a browser. "
        "Use the browser's Print option if you want to save it as a PDF."
    )

    st.markdown("---")
    st.caption(
        "GeoGuard is an engineering prototype. Simulated data and "
        "unvalidated thresholds must not be treated as confirmed "
        "landslide predictions or official safety instructions."
    )
