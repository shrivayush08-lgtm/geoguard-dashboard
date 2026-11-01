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

STATUS_COLORS = {
    "OPEN": "#10B981",
    "UNDER OBSERVATION": "#F59E0B",
    "RESTRICTED": "#F97316",
    "CLOSED": "#EF4444",
    "REOPENED": "#38BDF8"
}
DEFAULT_STATUS_COLOR = "#94A3B8"


def _safe_str(val, default=""):
    """Safely coerces any value to string, handling None, NaN, and empty strings."""
    if val is None or pd.isna(val):
        return default
    s = str(val).strip()
    return s if s and s.lower() != "nan" else default


def render_highway_safety_page(enriched_stations=None):
    """Renders the highway safety and road closure operations panel."""
    st.markdown("<div class='hud-eyebrow'>CORRIDOR INTEGRITY & TRAFFIC CONTROLS</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Highway Safety & Road Closure Control</h2>", unsafe_allow_html=True)

    # Defensively normalize enriched_stations parameter
    stations_list = enriched_stations if isinstance(enriched_stations, list) else []

    # Build lookup maps of live station telemetry and calculated geotechnical risk
    station_risk_map = {}
    station_telemetry_map = {}
    for stn in stations_list:
        if isinstance(stn, dict):
            s_id = _safe_str(stn.get("id"))
            if s_id:
                station_risk_map[s_id] = _safe_str(stn.get("risk_level"), "LOW").upper()
                station_telemetry_map[s_id] = stn

    # 1. Fetch Highway Road Sections from Database
    sections_df = get_road_sections()
    if sections_df is None or sections_df.empty:
        st.warning("No road section telemetry records found in database.")
        return

    # Automatically synchronize live sensor risk with highway sections
    section_records = sections_df.to_dict(orient="records")
    for sec_data in section_records:
        sec_id = _safe_str(sec_data.get("section_id"))
        stn_id = _safe_str(sec_data.get("associated_station"))
        if not sec_id or not stn_id:
            continue

        live_risk = station_risk_map.get(stn_id)
        if live_risk not in ["LOW", "MODERATE", "HIGH", "CRITICAL"]:
            continue

        existing_status = _safe_str(sec_data.get("status"), "OPEN").upper()
        existing_risk = _safe_str(sec_data.get("risk_level"), "LOW").upper()

        # Critical risk automatically closes the road.
        # Lower risk never automatically reopens a closed road without field authorization.
        updated_status = "CLOSED" if live_risk == "CRITICAL" else existing_status

        if updated_status != existing_status or live_risk != existing_risk:
            condition_notes = _safe_str(sec_data.get("condition_notes"), "Automatic safety trigger active.")
            update_road_section(
                sec_id,
                updated_status,
                live_risk,
                condition_notes,
                updated_by="GeoGuard Automated Risk Monitor"
            )

    # Fetch updated database records after risk synchronization
    sections_df = get_road_sections()
    if sections_df is None or sections_df.empty:
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
        for alert_sec in alert_sections.to_dict(orient="records"):
            alert_status = _safe_str(alert_sec.get("status"), "CLOSED").upper()
            alert_risk = _safe_str(alert_sec.get("risk_level"), "LOW").upper()
            sec_id = _safe_str(alert_sec.get("section_id"), "SEC")
            sec_name = _safe_str(alert_sec.get("name"), "Corridor Sector")

            reasons = []
            if alert_status == "CLOSED":
                reasons.append("ROAD CLOSED")
            if alert_risk == "CRITICAL":
                reasons.append("CRITICAL RISK")

            st.error(
                f"🚨 {sec_id} — {sec_name} | "
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
            filtered_df["section_id"].astype(str).str.lower().str.contains(term, na=False)
            | filtered_df["name"].astype(str).str.lower().str.contains(term, na=False)
        ]

    if selected_status != "ALL":
        filtered_df = filtered_df[
            filtered_df["status"].astype(str).str.strip().str.upper() == selected_status
        ]

    if selected_risk != "ALL":
        filtered_df = filtered_df[
            filtered_df["risk_level"].astype(str).str.strip().str.upper() == selected_risk
        ]

    if filtered_df.empty:
        st.info("No checkpoints match your search and filter criteria.")
    else:
        recent_alerts = get_alerts(limit=20)
        checkpoints_data = filtered_df.to_dict(orient="records")

        for sec in checkpoints_data:
            sec_id = _safe_str(sec.get("section_id"), "SEC-??")
            sec_name = _safe_str(sec.get("name"), "Corridor Section")
            corridor = _safe_str(sec.get("corridor"), "NH-58 Corridor")
            status = _safe_str(sec.get("status"), "OPEN").upper()
            risk_lvl = _safe_str(sec.get("risk_level"), "LOW").upper()
            stn_id = _safe_str(sec.get("associated_station"), "")
            notes = _safe_str(sec.get("condition_notes"), "Nominal highway conditions.")
            
            # Retrieve last inspection timestamp and author safely
            last_insp = _safe_str(sec.get("last_updated") or sec.get("last_status_change"), default="Recent")
            auth_by = _safe_str(sec.get("updated_by"), default="Authorized Inspector")

            # Correlate live station telemetry
            station_info = station_telemetry_map.get(stn_id)
            sensor_info_html = ""
            if station_info:
                soil_val = station_info.get("soil_moisture_pct", 0.0)
                tilt_val = station_info.get("tilt", 0.0)
                temp_val = station_info.get("temp_c", station_info.get("temperature_c", 15.0))
                vib_val = station_info.get("vib", False)

                try:
                    soil_disp = f"{float(soil_val):.1f}%"
                except (ValueError, TypeError):
                    soil_disp = "0.0%"

                try:
                    tilt_float = float(tilt_val)
                    tilt_color = "#EF4444" if tilt_float > 2.0 else "#10B981"
                    tilt_disp = f"{tilt_float:.2f}°"
                except (ValueError, TypeError):
                    tilt_color = "#10B981"
                    tilt_disp = "0.00°"

                try:
                    temp_disp = f"{float(temp_val):.1f}°C"
                except (ValueError, TypeError):
                    temp_disp = "15.0°C"

                vib_status = "ACTIVE" if vib_val else "NOMINAL"
                vib_color = "#EF4444" if vib_val else "#10B981"

                sensor_info_html = f"""
                <div style='font-size: 11px; color: #94A3B8; margin-top: 4px; font-family: "JetBrains Mono", monospace;'>
                    Live Transducers: Soil <b style='color:#38BDF8;'>{soil_disp}</b> | 
                    Tilt <b style='color:{tilt_color};'>{tilt_disp}</b> | 
                    Temp <b style='color:#F8FAFC;'>{temp_disp}</b> | 
                    Tremor <b style='color:{vib_color};'>{vib_status}</b>
                </div>
                """

            # Correlate active alerts
            active_alert_html = ""
            if recent_alerts is not None and not recent_alerts.empty:
                if "station_id" in recent_alerts.columns and "status" in recent_alerts.columns:
                    stn_alerts = recent_alerts[
                        (recent_alerts["station_id"].astype(str) == str(stn_id)) & 
                        (recent_alerts["status"].isin(["NEW", "ACKNOWLEDGED", "UNDER INVESTIGATION"]))
                    ]
                    if not stn_alerts.empty:
                        top_alert = stn_alerts.iloc[0]
                        alert_id_val = top_alert.get("alert_id", "N/A") if hasattr(top_alert, "get") else top_alert["alert_id"]
                        alert_risk_val = top_alert.get("risk_level", "ALERT") if hasattr(top_alert, "get") else top_alert["risk_level"]
                        alert_reason_val = top_alert.get("reason", "Hazard detected") if hasattr(top_alert, "get") else top_alert["reason"]
                        active_alert_html = f"""
                        <div style='font-size: 11px; color: #EF4444; margin-top: 5px; background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.25); padding: 4px 8px; border-radius: 4px;'>
                            ⚠️ <b>Active Incident #{alert_id_val} ({alert_risk_val}):</b> {alert_reason_val}
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

            color = STATUS_COLORS.get(status, DEFAULT_STATUS_COLOR)

            card_html = f"""
            <div style='background: #111827; border: 1px solid #1F2937; border-left: 4px solid {color}; border-radius: 6px; padding: 14px 18px; margin-bottom: 12px;'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <div>
                        <span class='font-mono' style='font-size: 12px; color: #38BDF8; font-weight:600;'>{sec_id}</span>
                        <span style='font-size: 15px; font-weight: 700; color: #F8FAFC; margin-left: 10px;'>{sec_name}</span>
                    </div>
                    <div>
                        <span class='font-mono' style='font-size: 11px; color: {color}; font-weight:700; border: 1px solid {color}40; background: {color}15; padding: 3px 8px; border-radius: 4px;'>
                            ● {status}
                        </span>
                    </div>
                </div>
                <div style='font-size: 12px; color: #94A3B8; margin-top: 5px;'>
                    Corridor Segment: {corridor} • Sector Risk Rating: <b style='color:{color};'>{risk_lvl}</b>
                </div>
                {sensor_info_html}
                {active_alert_html}
                {closure_notice_html}
                <div style='font-size: 13px; color: #E2E8F0; margin-top: 6px;'>
                    <b>Field Inspector Directive:</b> {notes}
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
        
        sec_ids = sections_df["section_id"].tolist() if "section_id" in sections_df.columns else []
        with col_f1:
            selected_sec_id = st.selectbox("Select Highway Sector", sec_ids)
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
            match = sections_df[sections_df["section_id"] == selected_sec_id]
            if match.empty:
                st.error("Selected sector ID not found.")
            else:
                selected_section = match.iloc[0]
                current_status = _safe_str(selected_section.get("status"), "OPEN").upper()
                station_id = _safe_str(selected_section.get("associated_station"))
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
