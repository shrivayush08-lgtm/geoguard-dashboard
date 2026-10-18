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
from datetime import datetime, timezone
from io import BytesIO
import html
import re

import pandas as pd
import streamlit as st

from database.db import get_connection, get_road_sections, get_response_teams
from modules.report_generator import convert_df_to_csv, generate_incident_report_markdown


def utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def safe_filename(value):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value)).strip("_") or "report"


def load_data():
    conn = get_connection()
    try:
        telemetry = pd.read_sql_query(
            "SELECT * FROM telemetry_history ORDER BY reading_id DESC LIMIT 1000", conn
        )
        alerts = pd.read_sql_query("SELECT * FROM alerts ORDER BY alert_id DESC", conn)
    finally:
        conn.close()
    return telemetry, alerts, get_road_sections(), get_response_teams()


def build_html_report(markdown, incident_id):
    """Create a self-contained HTML report that opens cleanly in a browser."""
    blocks = []
    in_list = False
    for raw in str(markdown).splitlines():
        line = raw.strip()
        if not line:
            if in_list:
                blocks.append("</ul>")
                in_list = False
            continue
        if line.startswith(("- ", "* ")):
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{html.escape(line[2:])}</li>")
            continue
        if in_list:
            blocks.append("</ul>")
            in_list = False
        if line.startswith("---"):
            blocks.append("<hr>")
        elif line.startswith("#"):
            level = min(len(line) - len(line.lstrip("#")), 3)
            blocks.append(f"<h{level}>{html.escape(line.lstrip('# ').strip())}</h{level}>")
        else:
            escaped = html.escape(line)
            escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
            blocks.append(f"<p>{escaped}</p>")
    if in_list:
        blocks.append("</ul>")

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GeoGuard Incident Report {html.escape(str(incident_id))}</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#eef3ef;color:#202923;
font:16px/1.65 Arial,sans-serif}} main{{max-width:900px;margin:30px auto;padding:36px 42px;
background:#fff;border:1px solid #dce5df;border-radius:14px}}
.eyebrow{{color:#174c3c;font-weight:bold;letter-spacing:2px;font-size:12px}}
h1,h2,h3{{color:#174c3c;line-height:1.3}} .notice{{padding:12px 15px;background:#fff4d8;
color:#725317;border-radius:8px;font-size:13px}} footer{{border-top:1px solid #dce5df;
margin-top:30px;padding-top:12px;color:#637168;font-size:12px}}
@media print{{body{{background:#fff}}main{{margin:0;border:0;padding:0}}}}
</style></head><body><main>
<div class="eyebrow">GEOGUARD / INCIDENT ARCHIVE</div>
<h1>Incident Report #{html.escape(str(incident_id))}</h1>
<p style="color:#637168;font-size:13px">Generated {generated}</p>
<div class="notice">Prototype-generated report. Verify incident details and sensor
readings before operational use. This is not an official regulatory certification
or a validated landslide prediction.</div>
{''.join(blocks)}
<footer>GeoGuard · Prototype reporting output</footer>
</main></body></html>"""


def build_pdf_report(markdown, incident_id):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    except ImportError as exc:
        raise RuntimeError("PDF export needs reportlab. Add 'reportlab' to requirements.txt.") from exc

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=18*mm, bottomMargin=18*mm,
                            title=f"GeoGuard Incident Report {incident_id}")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="GGTitle", parent=styles["Title"], fontSize=20,
                              leading=25, textColor=colors.HexColor("#174c3c"),
                              spaceAfter=12))
    styles.add(ParagraphStyle(name="GGHeading", parent=styles["Heading2"], fontSize=12,
                              leading=16, textColor=colors.HexColor("#174c3c"),
                              spaceBefore=9, spaceAfter=5))
    styles.add(ParagraphStyle(name="GGBody", parent=styles["BodyText"], fontSize=9,
                              leading=13, spaceAfter=5))
    story = [
        Paragraph(f"GeoGuard Incident Report #{html.escape(str(incident_id))}", styles["GGTitle"]),
        Paragraph("Prototype-generated report. Verify details before operational use.",
                  styles["GGBody"]),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dce5df")),
        Spacer(1, 8),
    ]
    for raw in str(markdown).splitlines():
        line = raw.strip()
        if not line:
            story.append(Spacer(1, 3))
        elif line.startswith("#"):
            story.append(Paragraph(html.escape(line.lstrip("# ").strip()), styles["GGHeading"]))
        elif line.startswith(("- ", "* ")):
            story.append(Paragraph(f"&bull;&nbsp;{html.escape(line[2:])}", styles["GGBody"]))
        elif line.startswith("---"):
            story.append(HRFlowable(width="100%", thickness=.5,
                                    color=colors.HexColor("#dce5df")))
        else:
            line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            line = re.sub(r"\*(.*?)\*", r"\1", line)
            story.append(Paragraph(html.escape(line), styles["GGBody"]))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#637168"))
        canvas.drawString(18*mm, 10*mm, "GeoGuard | Prototype report")
        canvas.drawRightString(A4[0]-18*mm, 10*mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def export_card(icon, title, description, df, filename, key):
    with st.container(border=True):
        st.markdown(f"#### {icon} {title}")
        st.caption(description)
        st.metric("Available rows", f"{len(df):,}")
        st.download_button(
            "Download CSV", data=convert_df_to_csv(df), file_name=filename,
            mime="text/csv", use_container_width=True, disabled=df.empty, key=key,
        )


def render_reports_page(enriched_stations):
    st.markdown(
        "<div style='color:#78968A;font-size:12px;letter-spacing:2px;"
        "font-weight:700'>GEOGUARD / REPORTING CENTER</div>",
        unsafe_allow_html=True,
    )
    st.title("Reports & Data Center")
    st.caption("Review incidents, preview reports, and export GeoGuard data from one place.")

    try:
        telemetry, alerts, roads, teams = load_data()
    except Exception as exc:
        st.error("Could not load reporting data from the database.")
        st.caption(f"Details: {exc}")
        return

    stamp = utc_stamp()
    st.subheader("Archive overview")
    a, b, c, d = st.columns(4)
    a.metric("Telemetry records", f"{len(telemetry):,}")
    b.metric("Alert records", f"{len(alerts):,}")
    c.metric("Road sections", f"{len(roads):,}")
    d.metric("Response units", f"{len(teams):,}")
    st.divider()

    st.subheader("Download datasets")
    st.caption("Telemetry export contains the latest 1,000 readings; other exports contain rows returned by their data functions.")
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    with col1:
        export_card("📊", "Telemetry history", "Sensor readings for analysis.", telemetry,
                    f"geoguard_telemetry_{stamp}.csv", "export_telemetry")
    with col2:
        export_card("🚨", "Incident alerts", "Recorded alerts and risk fields.", alerts,
                    f"geoguard_alerts_{stamp}.csv", "export_alerts")
    with col3:
        export_card("🚧", "Road sections", "Road-section records and stored statuses.", roads,
                    f"geoguard_road_sections_{stamp}.csv", "export_roads")
    with col4:
        export_card("🧑‍🚒", "Response units", "Configured response teams and contact channels.", teams,
                    f"geoguard_response_units_{stamp}.csv", "export_teams")

    st.divider()
    st.subheader("Incident report")
    st.caption("Choose an alert; its report preview appears immediately below.")

    if alerts.empty:
        st.info("No alert records are available yet. Reports can be generated when alerts are recorded.")
        return

    required = {"alert_id", "station_id", "risk_level", "timestamp"}
    missing = required - set(alerts.columns)
    if missing:
        st.error("Alerts table is missing required fields: " + ", ".join(sorted(missing)))
        return

    options = {
        row["alert_id"]: (
            f"#{row['alert_id']} | Station {row['station_id']} | "
            f"{row['risk_level']} | {row['timestamp']}"
        )
        for _, row in alerts.iterrows()
    }
    selected_id = st.selectbox(
        "Select incident", list(options.keys()),
        format_func=lambda value: options[value], key="geoguard_selected_incident",
    )
    selected = alerts[alerts["alert_id"] == selected_id]
    if selected.empty:
        st.warning("The selected incident could not be found.")
        return

    alert_row = selected.iloc[0].to_dict()
    station = next(
        (s for s in (enriched_stations or [])
         if str(s.get("id")) == str(alert_row["station_id"])),
        None,
    )
    try:
        report_md = generate_incident_report_markdown(alert_row, station_info=station)
    except Exception as exc:
        st.error("Could not generate this incident report.")
        st.caption(f"Details: {exc}")
        return

    with st.container(border=True):
        st.markdown("### 📄 Report preview")
        m1, m2, m3 = st.columns(3)
        m1.markdown(f"**Incident**\n\n#{selected_id}")
        m2.markdown(f"**Station**\n\n{alert_row['station_id']}")
        m3.markdown(f"**Risk level**\n\n{alert_row['risk_level']}")
        st.warning(
            "Prototype-generated report. Verify incident details and sensor readings "
            "before operational use. This is not an official regulatory certification "
            "or a validated landslide prediction."
        )
        st.markdown(report_md)

    st.markdown("#### Export selected report")
    pdf_col, html_col, md_col = st.columns(3)
    report_id = safe_filename(selected_id)

    with pdf_col:
        try:
            pdf = build_pdf_report(report_md, selected_id)
            st.download_button(
                "📄 Download PDF", data=pdf,
                file_name=f"GEO_INCIDENT_REPORT_{report_id}.pdf",
                mime="application/pdf", use_container_width=True, type="primary",
                key=f"report_pdf_{report_id}",
            )
        except RuntimeError as exc:
            st.info(str(exc))

    with html_col:
        html_report = build_html_report(report_md, selected_id)
        st.download_button(
            "🌐 Download HTML", data=html_report.encode("utf-8"),
            file_name=f"GEO_INCIDENT_REPORT_{report_id}.html",
            mime="text/html", use_container_width=True, key=f"report_html_{report_id}",
            help="Download, then open the HTML file in a browser for a clean report view.",
        )

    with md_col:
        st.download_button(
            "📝 Download Markdown", data=report_md.encode("utf-8"),
            file_name=f"GEO_INCIDENT_REPORT_{report_id}.md",
            mime="text/markdown", use_container_width=True, key=f"report_md_{report_id}",
        )

    with st.expander("View raw Markdown source"):
        st.code(report_md, language="markdown")

    st.caption(
        "Data note: telemetry is limited to the latest 1,000 readings. "
        "Confirm export completeness before using these files as formal archives."
    )
