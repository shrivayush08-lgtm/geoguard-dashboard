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

import streamlit as st
import pandas as pd
from datetime import datetime
from database.db import get_connection, get_road_sections, get_response_teams
from modules.report_generator import convert_df_to_csv, generate_incident_report_markdown
from modules.ui import render_html

def render_reports_page(enriched_stations):
    """Renders the reports and data export management view."""
    st.markdown("<div class='hud-eyebrow'>REGULATORY REPORTING & ARCHIVES</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Reports & Data Download Center</h2>", unsafe_allow_html=True)

    # 1. CSV Data Export Hub
    st.markdown("### 📥 Telemetry & Event Log CSV Exports")
    st.caption("Export historical time-series records for GIS analysis, spatial modeling, or regulatory auditing:")

    exp_col1, exp_col2, exp_col3, exp_col4 = st.columns(4)

    conn = get_connection()

    # Telemetry CSV
    with exp_col1:
        telemetry_df = pd.read_sql_query("SELECT * FROM telemetry_history ORDER BY reading_id DESC LIMIT 1000", conn)
        t_csv = convert_df_to_csv(telemetry_df)
        render_html(f"""
        <div style='background: rgba(13, 24, 41, 0.9); border: 1px solid #1B2F4C; border-radius: 6px; padding: 14px; text-align: center; margin-bottom: 8px;'>
            <div style='font-size: 20px;'>📊</div>
            <div style='font-weight: 700; color: #F0F6FC; margin: 4px 0 2px 0;'>Telemetry Log</div>
            <div class='font-mono' style='font-size: 11px; color: #00F0FF;'>{len(telemetry_df)} Records</div>
        </div>
        """)
        st.download_button(
            label="Download Telemetry CSV",
            data=t_csv,
            file_name=f"geoguard_telemetry_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # Alerts CSV
    with exp_col2:
        alerts_df = pd.read_sql_query("SELECT * FROM alerts ORDER BY alert_id DESC", conn)
        a_csv = convert_df_to_csv(alerts_df)
        render_html(f"""
        <div style='background: rgba(13, 24, 41, 0.9); border: 1px solid #1B2F4C; border-radius: 6px; padding: 14px; text-align: center; margin-bottom: 8px;'>
            <div style='font-size: 20px;'>🚨</div>
            <div style='font-weight: 700; color: #F0F6FC; margin: 4px 0 2px 0;'>Incident Alerts</div>
            <div class='font-mono' style='font-size: 11px; color: #FF2A4D;'>{len(alerts_df)} Incidents</div>
        </div>
        """)
        st.download_button(
            label="Download Alerts CSV",
            data=a_csv,
            file_name=f"geoguard_alerts_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # Road Sections CSV
    with exp_col3:
        road_df = get_road_sections()
        r_csv = convert_df_to_csv(road_df)
        render_html(f"""
        <div style='background: rgba(13, 24, 41, 0.9); border: 1px solid #1B2F4C; border-radius: 6px; padding: 14px; text-align: center; margin-bottom: 8px;'>
            <div style='font-size: 20px;'>🚧</div>
            <div style='font-weight: 700; color: #F0F6FC; margin: 4px 0 2px 0;'>Road Status</div>
            <div class='font-mono' style='font-size: 11px; color: #00E5A3;'>{len(road_df)} Sectors</div>
        </div>
        """)
        st.download_button(
            label="Download Roads CSV",
            data=r_csv,
            file_name=f"geoguard_road_sections_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # Response Teams CSV
    with exp_col4:
        teams_df = get_response_teams()
        tm_csv = convert_df_to_csv(teams_df)
        render_html(f"""
        <div style='background: rgba(13, 24, 41, 0.9); border: 1px solid #1B2F4C; border-radius: 6px; padding: 14px; text-align: center; margin-bottom: 8px;'>
            <div style='font-size: 20px;'>🚒</div>
            <div style='font-weight: 700; color: #F0F6FC; margin: 4px 0 2px 0;'>Response Units</div>
            <div class='font-mono' style='font-size: 11px; color: #FFB000;'>{len(teams_df)} Units</div>
        </div>
        """)
        st.download_button(
            label="Download Teams CSV",
            data=tm_csv,
            file_name=f"geoguard_response_units_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    conn.close()

    st.markdown("<hr style='border:0; border-top:1px solid #1B2F4C; margin: 20px 0;'>", unsafe_allow_html=True)

    # 2. Formal Geotechnical Incident Dossier Generator
    st.markdown("### 📋 Formal Geotechnical Incident Dossier Compiler")
    st.caption("Compile a standardized NDMA / BRO disaster event dossier for government archives:")

    if alerts_df.empty:
        st.info("No alert records available to compile incident dossiers.")
        return

    alert_options = {
        row["alert_id"]: f"Incident #{row['alert_id']} — Sector {row['station_id']} ({row['risk_level']}) [{row['timestamp']}]"
        for _, row in alerts_df.iterrows()
    }
    
    selected_alert_id = st.selectbox(
        "Select Target Incident Record",
        list(alert_options.keys()),
        format_func=lambda x: alert_options[x]
    )

    alert_row = alerts_df[alerts_df["alert_id"] == selected_alert_id].iloc[0].to_dict()
    station_match = next((s for s in enriched_stations if s["id"] == alert_row["station_id"]), None)

    # Generate Markdown Dossier
    report_md = generate_incident_report_markdown(alert_row, station_info=station_match)

    with st.expander("📄 Formal Incident Dossier Document Preview", expanded=True):
        st.markdown(report_md)

    st.download_button(
        label="📥 Download Geotechnical Incident Dossier (.md)",
        data=report_md.encode('utf-8'),
        file_name=f"GEO_INCIDENT_REPORT_{selected_alert_id}.md",
        mime="text/markdown",
        type="primary"
    )
