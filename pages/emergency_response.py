"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/emergency_response.py
Purpose: Crisis Dispatch Terminal, Disaster Agency Rosters & SOP Workflows
=============================================================================
Manages:
- Deployed agencies: NDRF 8th Bn, SDRF High-Altitude QRT, BRO 753 Task Force, Police, EMS
- Tactical dispatch commands & radio channel coordination
- Unit operational readiness states (STANDBY -> DISPATCHED -> ON SCENE)
- NDMA 5-Stage Geotechnical Incident Action Checklist
"""

import streamlit as st
from database.db import get_response_teams, update_response_team, get_alerts

def render_emergency_response_page(enriched_stations):
    """Renders the emergency response coordination management view."""
    st.markdown("<div class='hud-eyebrow'>INTER-AGENCY CRISIS OPERATIONS ROOM</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Emergency Response Coordination</h2>", unsafe_allow_html=True)

    # 1. Fetch Response Teams from Database
    teams_df = get_response_teams()

    if teams_df.empty:
        st.warning("No emergency response units configured.")
        return

    # 2. Deployed Response Teams Tactical Grid
    st.markdown("### Tactical Unit Deployment Roster")

    for _, team in teams_df.iterrows():
        team_id = team["team_id"]
        status = team["status"]
        
        status_color = (
            "#FF2A4D" if status == "DISPATCHED" 
            else ("#FF7A00" if status == "ON SCENE" 
            else ("#00E5A3" if status == "STANDBY" else "#00F0FF"))
        )

        with st.container():
            st.markdown(f"""
            <div style='background: rgba(13, 24, 41, 0.9); border: 1px solid #1B2F4C; border-left: 4px solid {status_color}; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px; backdrop-filter: blur(8px);'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <div>
                        <span style='font-size: 16px; font-weight: 700; color: #F0F6FC;'>{team['team_name']}</span>
                        <span class='font-mono' style='font-size: 11px; color: #00F0FF; margin-left: 10px;'>[{team['authority']}]</span>
                    </div>
                    <div style='background: {status_color}22; color: {status_color}; border: 1px solid {status_color}55; padding: 4px 12px; border-radius: 4px; font-family: "Orbitron"; font-size: 11px; font-weight: 700;'>
                        ● {status}
                    </div>
                </div>
                <div style='display: flex; gap: 24px; font-family: "JetBrains Mono", monospace; font-size: 11px; color: #8B9BB4; margin-top: 6px;'>
                    <div>BASE: <b style='color:#F0F6FC;'>{team['base_location']}</b></div>
                    <div>COMMS: <b style='color:#00E5A3;'>{team['contact_channel']}</b></div>
                    <div>LAST UPDATE: {team['last_dispatch_time']}</div>
                </div>
                <div style='background: rgba(255,255,255,0.03); border: 1px solid #1B2F4C; padding: 8px 12px; border-radius: 6px; font-size: 13px; color: #E2E8F0; margin-top: 8px;'>
                    <b>Active Sector Assignment:</b> {team['current_assignment'] or 'None — Unit in base readiness.'}
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<hr style='border:0; border-top:1px solid #1B2F4C; margin: 18px 0;'>", unsafe_allow_html=True)

    # 3. Tactical Dispatch Command Form
    st.markdown("### 🚀 Tactical Unit Dispatch Terminal")
    with st.form("dispatch_action_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_team = st.selectbox("Designated Response Unit", teams_df["team_id"].tolist())
        with col2:
            new_status = st.selectbox(
                "Deployment Order",
                ["STANDBY", "DISPATCHED", "ON SCENE", "OPERATION COMPLETED (STANDBY)"]
            )
        with col3:
            alerts_df = get_alerts()
            alert_opts = ["General Highway Sector Patrol"] + [f"Incident #{r['alert_id']} ({r['station_id']})" for _, r in alerts_df.iterrows()] if not alerts_df.empty else ["General Patrol"]
            assignment_target = st.selectbox("Target Sector Incident", alert_opts)

        notes = st.text_input("Operational Radio Orders & Tactical Directive", value="Proceed with heavy rock clearing excavators and drone thermal survey.")

        submit_dispatch = st.form_submit_button("📢 Transmit Encrypted Dispatch Order", type="primary", use_container_width=True)
        if submit_dispatch:
            target_status = "STANDBY" if "COMPLETED" in new_status else new_status
            update_response_team(selected_team, target_status, f"{assignment_target} — {notes}")
            st.success(f"Dispatch order transmitted to {selected_team}. Logged in emergency records.")
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. Standard 5-Stage NDMA Disaster Protocol Timeline
    with st.expander("📋 NDMA 5-Stage Landslide Incident Action Checklist", expanded=False):
        st.markdown("""
        1. **Stage 1 (T+0 min):** Early Warning Trigger — Verify sensor saturation, tilt delta, and automated alert.
        2. **Stage 2 (T+5 min):** Highway Patrol Checkpoint Notification — Restrict uphill heavy transit at Byasi and Kaudiyala.
        3. **Stage 3 (T+10 min):** BRO Debris Clearance Task Force Mobilization — Position backhoes and bulldozers at sector junctions.
        4. **Stage 4 (T+15 min):** District Medical & Ambulance Standby — Position trauma ambulances at Srinagar Base Hospital.
        5. **Stage 5 (T+30 min):** Drone Aerial Stability Verification — Confirm toe erosion and crown fissures before clearance sign-off.
        """)
