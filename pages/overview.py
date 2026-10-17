"""
=============================================================================
GEOGUARD AI — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/overview.py
Purpose: Geotechnical Control Center Overview & Sector Telemetry Matrix
=============================================================================
Renders:
- Telemetry KPIs (Nodes, Uplink, Risk Index, Hazards)
- Dynamic hazard status banner
- NH-58 Corridor Linear Strip Schematic
- Deployed Telemetry Node Matrix with status indicators
- Plotly Sector Risk Distribution Donut & Advisory Feed
=============================================================================
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from modules.ui import (
    render_hud_kpi,
    render_hud_banner,
    render_highway_linear_schematic,
    get_plotly_theme,
    render_html,
    COLOR_BLUE,
    COLOR_CYAN,
    COLOR_SAFE,
    COLOR_MODERATE,
    COLOR_HIGH,
    COLOR_CRITICAL
)
from modules.data_store import get_system_kpis
from database.db import get_alerts, get_road_sections


def render_overview_page(enriched_stations):
    """Renders the comprehensive overview control center page."""
    # 1. Fetch system operational KPIs
    kpis = get_system_kpis(enriched_stations)

    # 2. Render prominent dynamic status banner
    render_hud_banner(kpis["system_status"], kpis["system_detail"])

    # 3. Top Row: 6 KPI Metric Cards
    st.markdown("<div class='hud-eyebrow'>CORRIDOR TELEMETRY OVERVIEW</div>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    
    with c1:
        render_hud_kpi("Grid Nodes", f"{kpis['total_stations']}", "Telemetry Stations", "📡", "#38BDF8")
    with c2:
        render_hud_kpi("Node Uplink", f"{kpis['online_stations']}/{kpis['total_stations']}", "All Nodes Active", "🟢", "#10B981")
    with c3:
        alert_color = "#EF4444" if kpis["active_alerts"] > 0 else "#10B981"
        render_hud_kpi("Active Alerts", str(kpis["active_alerts"]), "Unresolved Hazards", "🚨", alert_color)
    with c4:
        risk_color = (
            "#EF4444" if kpis["max_risk_score"] >= 75 
            else ("#F97316" if kpis["max_risk_score"] >= 50 
            else ("#F59E0B" if kpis["max_risk_score"] >= 25 else "#10B981"))
        )
        render_hud_kpi("Max Risk Index", f"{kpis['max_risk_score']}", "Out of 100", "⚡", risk_color)
    with c5:
        crit_color = "#EF4444" if kpis["critical_events_today"] > 0 else "#94A3B8"
        render_hud_kpi("Critical Zones", str(kpis["critical_events_today"]), "Sectors at Risk", "⚠️", crit_color)
    with c6:
        render_hud_kpi("Link Health", kpis["network_health"], "LoRa / 4G Uplink", "🛡️", "#38BDF8")

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. NH-58 Corridor Linear Strip Schematic
    sections_df = get_road_sections()
    if not sections_df.empty:
        render_highway_linear_schematic(sections_df)

    # 5. Main Telemetry Matrix & Risk Distribution Chart
    col_matrix, col_chart = st.columns([2.3, 1])

    with col_matrix:
        st.markdown("<div class='hud-eyebrow'>MONITORING STATIONS</div>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0;'>Live Telemetry Node Matrix</h3>", unsafe_allow_html=True)
        
        table_rows = ""
        for s in enriched_stations:
            lvl = s["risk_level"]
            score = s["risk_score"]
            badge_class = (
                "hud-badge-critical" if lvl == "CRITICAL"
                else ("hud-badge-high" if lvl == "HIGH"
                else ("hud-badge-moderate" if lvl == "MODERATE" else "hud-badge-safe"))
            )
            vib_text = "<span style='color:#EF4444;'>TREMOR 🔴</span>" if s.get("vib") else "<span style='color:#10B981;'>STABLE 🟢</span>"
            temp_val = s.get("temp_c", s.get("temperature_c", 15.0))
            
            table_rows += f"""
            <tr style='border-bottom: 1px solid #1F2937;'>
                <td style='padding: 10px 14px; font-family: "JetBrains Mono", monospace; color: #38BDF8; font-weight:600;'>
                    {s['id']}
                </td>
                <td style='padding: 10px 14px; font-weight: 600; color: #F8FAFC;'>
                    {s['name']}
                    <div style='font-size: 11px; color: #64748B;'>{s.get('corridor', 'NH-58')}</div>
                </td>
                <td style='padding: 10px 14px; font-family: "JetBrains Mono", monospace;'>
                    <span style='color:#38BDF8;'>{s.get('soil_moisture_pct', 0.0)}%</span>
                </td>
                <td style='padding: 10px 14px; font-family: "JetBrains Mono", monospace;'>
                    <span style='color:#10B981;'>{temp_val:.1f}°C</span>
                </td>
                <td style='padding: 10px 14px; font-family: "JetBrains Mono", monospace;'>
                    <span style='color:{"#EF4444" if s.get("tilt", 0.0) > 2.0 else "#F8FAFC"}; font-weight:600;'>
                        {s.get('tilt', 0.0):.2f}°
                    </span>
                </td>
                <td style='padding: 10px 14px; font-size: 11px;'>
                    {vib_text}
                </td>
                <td style='padding: 10px 14px;'>
                    <div style='display:flex; align-items:center; gap:8px;'>
                        <div style='flex:1; background:#1F2937; border-radius:3px; height:6px; width:65px; overflow:hidden;'>
                            <div style='background:{"#EF4444" if score >= 75 else ("#F97316" if score >= 50 else ("#F59E0B" if score >= 25 else "#10B981"))}; height:100%; width:{min(100, int(score))}%;'></div>
                        </div>
                        <span class='font-mono' style='font-size:12px; font-weight:600; color:#F8FAFC;'>{score}</span>
                    </div>
                </td>
                <td style='padding: 10px 14px;'>
                    <span class='hud-badge {badge_class}'>{lvl}</span>
                </td>
            </tr>
            """

        table_html = f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 8px; overflow: hidden;'>
            <table style='width: 100%; border-collapse: collapse; text-align: left; font-size: 12px;'>
                <thead>
                    <tr style='background: #0E1422; border-bottom: 1px solid #1F2937; font-family: "Inter", sans-serif; font-size: 11px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>
                        <th style='padding: 10px 14px;'>Node ID</th>
                        <th style='padding: 10px 14px;'>Sector Location</th>
                        <th style='padding: 10px 14px;'>Soil (VWC)</th>
                        <th style='padding: 10px 14px;'>Temp (°C)</th>
                        <th style='padding: 10px 14px;'>Slope Tilt</th>
                        <th style='padding: 10px 14px;'>Tremor</th>
                        <th style='padding: 10px 14px;'>Risk Score</th>
                        <th style='padding: 10px 14px;'>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
        """
        render_html(table_html)

    with col_chart:
        st.markdown("<div class='hud-eyebrow'>RISK DISTRIBUTION</div>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0;'>Sector Breakdown</h3>", unsafe_allow_html=True)
        
        risk_counts = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "CRITICAL": 0}
        for s in enriched_stations:
            lvl = s.get("risk_level", "LOW")
            if lvl in risk_counts:
                risk_counts[lvl] += 1
            else:
                risk_counts["LOW"] += 1

        dist_df = pd.DataFrame([
            {"Risk Level": k, "Count": v} 
            for k, v in risk_counts.items()
        ])

        fig = px.pie(
            dist_df,
            values="Count",
            names="Risk Level",
            hole=0.68,
            color="Risk Level",
            color_discrete_map={
                "LOW": "#10B981",
                "MODERATE": "#F59E0B",
                "HIGH": "#F97316",
                "CRITICAL": "#EF4444"
            }
        )
        
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=10, r=10, t=10, b=10),
            height=210,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.28,
                xanchor="center",
                x=0.5,
                font=dict(color="#94A3B8", size=10, family="Inter")
            ),
            annotations=[
                dict(
                    text=f"<b>{len(enriched_stations)}</b><br><span style='font-size:10px; color:#94A3B8;'>NODES</span>",
                    x=0.5, y=0.5,
                    font_size=18,
                    font_family="Inter",
                    font_color="#F8FAFC",
                    showarrow=False
                )
            ]
        )
        fig.update_traces(
            textinfo='none',
            marker=dict(line=dict(color='#0B0F19', width=2))
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<hr style='border:0; border-top: 1px solid #1F2937; margin: 16px 0;'>", unsafe_allow_html=True)

    # 6. Bottom Row: Incident Stream & Corridor Action Directive
    b_col1, b_col2 = st.columns([1.6, 1.4])

    with b_col1:
        st.markdown("<div class='hud-eyebrow'>EVENT LOG</div>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0;'>Live Incident Dispatch Stream</h3>", unsafe_allow_html=True)
        
        alerts_df = get_alerts(limit=4)
        if alerts_df.empty:
            st.info("All highway sectors operating within nominal geotechnical tolerances. No active incident alerts.")
        else:
            for _, row in alerts_df.iterrows():
                badge_class = (
                    "hud-badge-critical" if "CRITICAL" in row["risk_level"] 
                    else ("hud-badge-high" if "HIGH" in row["risk_level"] 
                    else "hud-badge-moderate")
                )
                border_col = "#EF4444" if "CRITICAL" in row["risk_level"] else ("#F97316" if "HIGH" in row["risk_level"] else "#F59E0B")
                
                render_html(f"""
                <div style='background: #111827; border-left: 3px solid {border_col}; border-top: 1px solid #1F2937; border-right: 1px solid #1F2937; border-bottom: 1px solid #1F2937; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px;'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <div>
                            <span class='hud-badge {badge_class}'>{row['risk_level']}</span>
                            <span style='margin-left: 8px; font-weight: 600; color: #F8FAFC;'>Sector Node {row['station_id']}</span>
                        </div>
                        <span class='font-mono' style='font-size: 11px; color: #64748B;'>{row['timestamp']}</span>
                    </div>
                    <div style='font-size: 13px; color: #E2E8F0; margin-top: 5px;'>
                        {row['reason']}
                    </div>
                    <div class='font-mono' style='font-size: 10px; color: #94A3B8; margin-top: 4px;'>
                        Status: <b style='color:#38BDF8;'>{row['status']}</b> • Assigned: {row['assigned_team'] or 'Awaiting Dispatch'}
                    </div>
                </div>
                """)

    with b_col2:
        st.markdown("<div class='hud-eyebrow'>TRAFFIC ADVISORY DIRECTIVE</div>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0;'>Sector Safety Advisory</h3>", unsafe_allow_html=True)
        
        has_crit = any(s["risk_level"] == "CRITICAL" for s in enriched_stations)
        has_high = any(s["risk_level"] == "HIGH" for s in enriched_stations)
        
        if has_crit:
            adv_color = "#EF4444"
            adv_title = "RED ADVISORY: CORRIDOR TRAFFIC RESTRICTION"
            adv_desc = "NH-58 Byasi Gorge sector experiencing critical displacement. Divert all non-emergency traffic via Chamba-New Tehri expressway."
        elif has_high:
            adv_color = "#F97316"
            adv_title = "ORANGE ADVISORY: SPEED REDUCTION REQUIRED"
            adv_desc = "Heavy rain and active slope creep detected. Maximum speed limit reduced to 25 km/h. Heavy cargo vehicles held at Byasi checkpost."
        else:
            adv_color = "#10B981"
            adv_title = "NORMAL STATUS: CORRIDOR TRANSIT CLEAR"
            adv_desc = "All 5 highway sectors open to vehicular traffic. Drainage traps operational and road visibility normal."

        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-left: 4px solid {adv_color}; border-radius: 6px; padding: 16px;'>
            <div style='color: {adv_color}; font-size: 13px; font-weight: 700;'>
                {adv_title}
            </div>
            <div style='font-size: 13px; color: #F8FAFC; margin-top: 6px; line-height: 1.5;'>
                {adv_desc}
            </div>
            <hr style='border:0; border-top: 1px solid #1F2937; margin: 10px 0;'>
            <div class='font-mono' style='font-size: 10px; color: #64748B;'>
                Authority: Garhwal District Disaster Management • Helpline: 1070
            </div>
        </div>
        """)
