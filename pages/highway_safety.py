"""
=============================================================================
GEOGUARD AI — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/highway_safety.py
Purpose: Highway Sector Management, Digital Interlock & Road Closure Advisories
=============================================================================
Manages:
- 5 Critical NH-58 Highway Mountain Segments (Byasi, Kaudiyala, Devprayag, Kirtinagar, Srinagar)
- Checkpoint status toggling (OPEN -> RESTRICTED -> CLOSED -> REOPENED)
- Digital variable message signs (VMS) advisory broadcaster
- Alternative route navigation guidance (NH-707A Chamba-Tehri detour)
=============================================================================
"""

import streamlit as st
import pandas as pd
from database.db import get_road_sections, update_road_section, get_alerts
from modules.ui import render_highway_linear_schematic, render_html


def render_highway_safety_page(enriched_stations):
    """Renders the highway safety and road closure operations panel."""
    st.markdown("<div class='hud-eyebrow'>CORRIDOR INTEGRITY & TRAFFIC CONTROLS</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Highway Safety & Road Closure Control</h2>", unsafe_allow_html=True)

    # 1. Fetch Highway Road Sections from Database
    sections_df = get_road_sections()

    # Automatically synchronize live sensor risk with highway sections
    station_risk_map = {
        str(stn["id"]): str(stn["risk_level"]).upper()
        for stn in enriched_stations
    }

    for _, section in sections_df.iterrows():
        section_id = section["section_id"]
        station_id = str(section["associated_station"])

        live_risk = station_risk_map.get(station_id)

        if live_risk not in ["LOW", "MODERATE", "HIGH", "CRITICAL"]:
            continue

        existing_status = str(section["status"]).upper()
        existing_risk = str(section["risk_level"]).upper()

        # Critical risk automatically closes the road.
        # Lower risk never automatically reopens a closed road without field authorization.
        updated_status = (
            "CLOSED" if live_risk == "CRITICAL"
            else existing_status
        )

        if updated_status != existing_status or live_risk != existing_risk:
            update_road_section(
                section_id,
                updated_status,
                live_risk,
                section["condition_notes"],
                updated_by="GeoGuard Automated Risk Monitor"
            )

    # Fetch updated database records
    sections_df = get_road_sections()

    if sections_df.empty:
        st.warning("No road section telemetry records found in database.")
        return

    # 2. Highway Linear Corridor Strip Schematic
    render_highway_linear_schematic(sections_df)

    # 3. Overall Highway Status Summary Cards
    st.markdown("### Highway Overview")

    status_counts = (
        sections_df["status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .value_counts()
    )

    total_sections = len(sections_df)
    open_sections = int(status_counts.get("OPEN", 0))
    observation_sections = int(status_counts.get("UNDER OBSERVATION", 0))
    restricted_sections = int(status_counts.get("RESTRICTED", 0))
    closed_sections = int(status_counts.get("CLOSED", 0))
    reopened_sections = int(status_counts.get("REOPENED", 0))

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric("Total Sections", total_sections)
    c2.metric("🟢 Open", open_sections)
    c3.metric("🟡 Observation", observation_sections)
    c4.metric("🟠 Restricted", restricted_sections)
    c5.metric("🔴 Closed", closed_sections)
    c6.metric("🔵 Reopened", reopened_sections)

    st.markdown("---")

    # Critical Closure and Risk Alerts
    st.markdown("### 🚨 Critical Highway Alerts")

    alert_sections = sections_df[
        sections_df["status"].fillna("").astype(str).str.strip().str.upper().eq("CLOSED")
        | sections_df["risk_level"].fillna("").astype(str).str.strip().str.upper().eq("CRITICAL")
    ]

    if alert_sections.empty:
        st.success("No active closure or CRITICAL-risk sections detected.")
    else:
        for _, alert_sec in alert_sections.iterrows():
            alert_status = str(alert_sec["status"]).strip().upper()
            alert_risk = str(alert_sec["risk_level"]).strip().upper()

            reasons = []
            if alert_status == "CLOSED":
                reasons.append("ROAD CLOSED")
            if alert_risk == "CRITICAL":
                reasons.append("CRITICAL RISK")

            st.error(
                f"🚨 {alert_sec['section_id']} — {alert_sec['name']} | "
                f"Status: {alert_status} | Risk: {alert_risk} | "
                f"Alert: {' + '.join(reasons)}"
            )

    st.markdown("---")

    # 4. Checkpoint Search and Filters
    st.markdown("### Corridor Checkpoint Status")

    search_text = st.text_input(
        "Search checkpoint",
        placeholder="Enter section ID or road name..."
    )

    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        selected_status = st.selectbox(
            "Filter by Status",
            ["ALL", "OPEN", "UNDER OBSERVATION", "RESTRICTED", "CLOSED", "REOPENED"]
        )

    with filter_col2:
        selected_risk = st.selectbox(
            "Filter by Risk Level",
            ["ALL", "LOW", "MODERATE", "HIGH", "CRITICAL"]
        )

    filtered_df = sections_df.copy()

    if search_text.strip():
        term = search_text.strip().lower()
        filtered_df = filtered_df[
            filtered_df["section_id"].str.lower().str.contains(term)
            | filtered_df["name"].str.lower().str.contains(term)
        ]

    if selected_status != "ALL":
        filtered_df = filtered_df[
            filtered_df["status"].str.upper() == selected_status
        ]

    if selected_risk != "ALL":
        filtered_df = filtered_df[
            filtered_df["risk_level"].str.upper() == selected_risk
        ]

    if filtered_df.empty:
        st.info("No checkpoints match your search and filter criteria.")
    else:
        recent_alerts = get_alerts(limit=20)
        
        for _, sec in filtered_df.iterrows():
            status = sec["status"]
            risk_lvl = sec["risk_level"]
            stn_id = sec["associated_station"]
            
            # Find associated live station telemetry
            station_info = next((s for s in enriched_stations if str(s["id"]) == str(stn_id)), None)
            sensor_info_html = ""
            if station_info:
                temp_val = station_info.get("temp_c", station_info.get("temperature_c", 15.0))
                sensor_info_html = f"""
                <div style='font-size: 11px; color: #94A3B8; margin-top: 4px; font-family: "JetBrains Mono", monospace;'>
                    Live Transducers: Soil <b style='color:#38BDF8;'>{station_info.get('soil_moisture_pct', 0.0)}%</b> | 
                    Tilt <b style='color:{"#EF4444" if station_info.get("tilt", 0.0) > 2.0 else "#10B981"};'>{station_info.get('tilt', 0.0):.2f}°</b> | 
                    Temp <b style='color:#F8FAFC;'>{temp_val:.1f}°C</b> | 
                    Tremor <b style='color:{"#EF4444" if station_info.get("vib") else "#10B981"};'>{"ACTIVE" if station_info.get("vib") else "NOMINAL"}</b>
                </div>
                """

            # Correlate active alerts
            active_alert_html = ""
            if not recent_alerts.empty:
                stn_alerts = recent_alerts[
                    (recent_alerts["station_id"].astype(str) == str(stn_id)) & 
                    (recent_alerts["status"].isin(["NEW", "ACKNOWLEDGED", "UNDER INVESTIGATION"]))
                ]
                if not stn_alerts.empty:
                    top_alert = stn_alerts.iloc[0]
                    active_alert_html = f"""
                    <div style='font-size: 11px; color: #EF4444; margin-top: 5px; background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.25); padding: 4px 8px; border-radius: 4px;'>
                        ⚠️ <b>Active Incident #{top_alert['alert_id']} ({top_alert['risk_level']}):</b> {top_alert['reason']}
                    </div>
                    """

            # Closure warning information
            closure_notice_html = ""
            if status == "CLOSED":
                closure_notice_html = """
                <div style='font-size: 11px; color: #EF4444; font-weight: 600; margin-top: 5px; background: rgba(239,68,68,0.15); padding: 4px 8px; border-radius: 4px;'>
                    ⛔ CORRIDOR TRAFFIC HALTED — Authorized clearance & inspection required prior to reopening.
                </div>
                """
            
            status_color_map = {
                "OPEN": "#10B981",
                "UNDER OBSERVATION": "#F59E0B",
                "RESTRICTED": "#F97316",
                "CLOSED": "#EF4444",
                "REOPENED": "#38BDF8"
            }
            color = status_color_map.get(status, "#94A3B8")
            
            last_insp = (
                sec["last_updated"] if "last_updated" in sec and pd.notna(sec["last_updated"])
                else (sec["last_status_change"] if "last_status_change" in sec and pd.notna(sec["last_status_change"]) else "Recent")
            )
            auth_by = sec["updated_by"] if "updated_by" in sec and pd.notna(sec["updated_by"]) else "Authorized Inspector"
            
            card_html = f"""
            <div style='background: #111827; border: 1px solid #1F2937; border-left: 4px solid {color}; border-radius: 6px; padding: 14px 18px; margin-bottom: 12px;'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <div>
                        <span class='font-mono' style='font-size: 12px; color: #38BDF8; font-weight:600;'>{sec['section_id']}</span>
                        <span style='font-size: 15px; font-weight: 700; color: #F8FAFC; margin-left: 10px;'>{sec['name']}</span>
                    </div>
                    <div>
                        <span class='font-mono' style='font-size: 11px; color: {color}; font-weight:700; border: 1px solid {color}40; background: {color}15; padding: 3px 8px; border-radius: 4px;'>
                            ● {status}
                        </span>
                    </div>
                </div>
                <div style='font-size: 12px; color: #94A3B8; margin-top: 5px;'>
                    Corridor Segment: {sec['corridor']} • Sector Risk Rating: <b style='color:{color};'>{risk_lvl}</b>
                </div>
                {sensor_info_html}
                {active_alert_html}
                {closure_notice_html}
                <div style='font-size: 13px; color: #E2E8F0; margin-top: 6px;'>
                    <b>Field Inspector Directive:</b> {sec['condition_notes']}
                </div>
                <div class='font-mono' style='font-size: 10px; color: #64748B; margin-top: 6px;'>
                    Last Inspection: {last_insp} • Authorized By: {auth_by} • Linked Node: {stn_id}
                </div>
            </div>
            """
            render_html(card_html)

    st.markdown("<br>", unsafe_allow_html=True)

    # 5. Field Interlock & Highway Authority Dispatch Form
    st.markdown("### Corridor Checkpoint Dispatch Controls")
    
    with st.form("road_control_form"):
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            selected_sec_id = st.selectbox("Select Highway Sector", sections_df["section_id"].tolist())
        with col_f2:
            new_status = st.selectbox("Assign Segment Status", ["OPEN", "UNDER OBSERVATION", "RESTRICTED", "CLOSED", "REOPENED"])
        with col_f3:
            new_risk = st.selectbox("Assign Sector Risk Level", ["LOW", "MODERATE", "HIGH", "CRITICAL"])
            
        notes_input = st.text_input("Transit Restriction / Field Advisory Notes", value="Single-lane pilot clearance in effect. Heavy commercial vehicles diverted.")
        officer_input = st.text_input("Authorizing Officer Name & Badge ID", value="Inspector BRO Highway Command")

        clearance_completed = st.checkbox(
            "I confirm that landslide debris clearance and repair work are completed."
        )

        inspection_completed = st.checkbox(
            "I confirm that the highway safety inspection has been completed."
        )

        reopening_approved = st.checkbox(
            "I authorize reopening this highway section."
        )

        submit = st.form_submit_button("Broadcast Corridor Advisory", type="primary", use_container_width=True)
        if submit:
            selected_section = sections_df[
                sections_df["section_id"] == selected_sec_id
            ].iloc[0]

            current_status = str(selected_section["status"]).upper()
            station_id = str(selected_section["associated_station"])
            live_risk = station_risk_map.get(station_id)

            # Validate road reopening
            if new_status in ["OPEN", "REOPENED"] and current_status != new_status:
                if not officer_input.strip():
                    st.error("Authorized Officer name is required.")
                elif live_risk is None:
                    st.error("Live sensor risk unavailable. Reopening cannot be approved.")
                elif live_risk == "CRITICAL":
                    st.error("Reopening blocked: CRITICAL risk is still detected on this sector.")
                elif not clearance_completed:
                    st.error("Confirm that landslide clearance and repair work are completed.")
                elif not inspection_completed:
                    st.error("Confirm that highway safety inspection is completed.")
                elif not reopening_approved:
                    st.error("Authorized officer approval is required.")
                else:
                    update_road_section(
                        selected_sec_id,
                        new_status,
                        new_risk,
                        notes_input,
                        updated_by=officer_input
                    )
                    st.success(f"Sector {selected_sec_id} approved for reopening. Advisory broadcasted across corridor signs.")
                    st.rerun()
            else:
                update_road_section(
                    selected_sec_id,
                    new_status,
                    new_risk,
                    notes_input,
                    updated_by=officer_input
                )
                st.success(f"Sector {selected_sec_id} updated to {new_status}. Advisory broadcasted across corridor signs.")
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # 6. Alternative Corridor Routing Information (NH-707A Detour)
    st.markdown("### Corridor Diversion & Evacuation Protocol")
    render_html("""
    <div style='background: #111827; border: 1px solid #1F2937; border-radius: 8px; padding: 18px;'>
        <div style='display: flex; align-items: center; gap: 10px; margin-bottom: 8px;'>
            <span style='font-size: 20px;'>🔄</span>
            <span style='font-size: 15px; font-weight: 700; color: #F8FAFC;'>NH-707A Alternative Himalayan Transit Bypass</span>
        </div>
        <div style='font-size: 13px; color: #94A3B8; line-height: 1.5;'>
            In the event of acute rockfall closure between <b>Shivpuri (km 35)</b> and <b>Kaudiyala (km 62)</b>, all civilian transit must divert via 
            <b style='color:#38BDF8;'>Rishikesh → Chamba → New Tehri → Kirtinagar</b>.
        </div>
        <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 14px;'>
            <div style='background: #0E1422; border: 1px solid #1F2937; border-radius: 6px; padding: 10px 12px;'>
                <div style='font-size: 11px; color: #64748B;'>TRANSIT TIME DELTA</div>
                <div style='font-size: 14px; font-weight: 700; color: #F59E0B; margin-top: 2px;'>+45 mins (Moderate)</div>
            </div>
            <div style='background: #0E1422; border: 1px solid #1F2937; border-radius: 6px; padding: 10px 12px;'>
                <div style='font-size: 11px; color: #64748B;'>HEAVY CARGO RESTRICTION</div>
                <div style='font-size: 14px; font-weight: 700; color: #EF4444; margin-top: 2px;'>Max GVW 24T Allowed</div>
            </div>
            <div style='background: #0E1422; border: 1px solid #1F2937; border-radius: 6px; padding: 10px 12px;'>
                <div style='font-size: 11px; color: #64748B;'>POLICE CHECKPOST STATUS</div>
                <div style='font-size: 14px; font-weight: 700; color: #10B981; margin-top: 2px;'>Chamba Escort Active</div>
            </div>
        </div>
    </div>
    """)
