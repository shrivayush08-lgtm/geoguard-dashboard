"""
=============================================================================
GEOGUARD AI — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/highway_safety.py
Purpose: Highway Corridor Transit Management, Road Closures & Bypass Advisories
=============================================================================
Manages:
- Corridor runway schematic across 5 monitored sectors
- Roadway status (OPEN, UNDER OBSERVATION, RESTRICTED, CLOSED, REOPENED)
- Traffic speed advisory modifications & vehicle weight limits
- Alternative bypass route advisories (Chamba / New Tehri route)
=============================================================================
"""

import streamlit as st
from database.db import get_road_sections, update_road_section
from modules.ui import render_highway_linear_schematic, render_html


def render_highway_safety_page(enriched_stations):
    """Renders the highway safety and corridor closure management view."""
    st.markdown("<div class='hud-eyebrow'>HIGHWAY TRAFFIC SURVEILLANCE & CLOSURES</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Highway Safety & Road Closure Control</h2>", unsafe_allow_html=True)

    # 1. Fetch Highway Road Sections from Database
    sections_df = get_road_sections()

    if sections_df.empty:
        st.warning("No highway road sections registered in database.")
        return

    # 2. Highway Linear Corridor Strip Schematic
    render_highway_linear_schematic(sections_df)

    # 3. Highway Corridor Status Summary Cards
    st.markdown("### Corridor Checkpoint Status")
    
    for _, sec in sections_df.iterrows():
        sec_id = sec["section_id"]
        status = sec["status"]
        risk_lvl = sec["risk_level"]
        
        status_color_map = {
            "OPEN": "#10B981",
            "UNDER OBSERVATION": "#F59E0B",
            "RESTRICTED": "#F97316",
            "CLOSED": "#EF4444",
            "REOPENED": "#38BDF8"
        }
        color = status_color_map.get(status, "#94A3B8")

        with st.container():
            render_html(f"""
            <div style='background: #111827; border-left: 4px solid {color}; border-top: 1px solid #1F2937; border-right: 1px solid #1F2937; border-bottom: 1px solid #1F2937; border-radius: 6px; padding: 14px 18px; margin-bottom: 10px;'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <div>
                        <span style='font-size: 15px; font-weight: 600; color: #F8FAFC;'>{sec_id}: {sec['name']}</span>
                        <span class='font-mono' style='margin-left: 10px; font-size: 11px; color: #38BDF8;'>[Node: {sec['associated_station']}]</span>
                    </div>
                    <div style='background: rgba(16, 185, 129, 0.1); color: {color}; border: 1px solid {color}55; padding: 3px 10px; border-radius: 4px; font-family: "JetBrains Mono", monospace; font-size: 11px; font-weight: 600;'>
                        ● {status}
                    </div>
                </div>
                <div style='font-size: 12px; color: #94A3B8; margin-top: 5px;'>
                    Corridor Segment: {sec['corridor']} • Sector Risk Rating: <b style='color:{color};'>{risk_lvl}</b>
                </div>
                <div style='font-size: 13px; color: #E2E8F0; margin-top: 6px;'>
                    <b>Field Inspector Directive:</b> {sec['condition_notes']}
                </div>
                <div class='font-mono' style='font-size: 11px; color: #64748B; margin-top: 6px;'>
                    Modified: {sec['last_updated']} by {sec['updated_by']}
                </div>
            </div>
            """)

    st.markdown("<hr style='border:0; border-top:1px solid #1F2937; margin: 16px 0;'>", unsafe_allow_html=True)

    # 4. Authorized Operator Road Status Update Console
    st.markdown("### Sector Transit Modification Console")
    with st.form("road_status_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_sec_id = st.selectbox("Target Highway Section", sections_df["section_id"].tolist())
        with col2:
            new_status = st.selectbox(
                "Update Transit Status",
                ["OPEN", "UNDER OBSERVATION", "RESTRICTED", "CLOSED", "REOPENED"]
            )
        with col3:
            new_risk = st.selectbox(
                "Designated Risk Rating",
                ["LOW", "MODERATE", "HIGH", "CRITICAL"]
            )

        notes_input = st.text_input("Transit Restriction / Field Advisory Notes", value="Single-lane pilot clearance in effect. Heavy commercial vehicles diverted.")
        officer_input = st.text_input("Authorizing Officer Name & Badge ID", value="Inspector BRO Highway Command")

        submit = st.form_submit_button("Broadcast Corridor Advisory", type="primary", use_container_width=True)
        if submit:
            update_road_section(selected_sec_id, new_status, new_risk, notes_input, updated_by=officer_input)
            st.success(f"Sector {selected_sec_id} updated to {new_status}. Advisory broadcasted across corridor signs.")
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # 5. Alternative Route & Detour Guide
    st.markdown("### Emergency Highway Bypass & Traffic Diversion Advisory")
    render_html("""
    <div style='background: #111827; border: 1px solid #1F2937; border-radius: 8px; padding: 18px;'>
        <div class='hud-eyebrow'>PRIMARY BYPASS CORRIDOR • NH-707A CHIKHALIDHAR ARTERIAL</div>
        <div style='font-size: 13px; color: #E2E8F0; line-height: 1.6; margin-top: 6px;'>
            In the event of closure at <b>SEC-01 (Byasi Mountain Pass)</b> or <b>SEC-02 (Kaudiyala Gorge)</b>, 
            divert northbound passenger and emergency logistics traffic from Rishikesh via <b>NH-707A (Rishikesh - Chamba - New Tehri - Kirtinagar)</b>.<br>
            • Estimated transit delta: <b style='color:#38BDF8;'>+45 minutes</b><br>
            • Maximum Gross Vehicle Weight (GVW): <b style='color:#10B981;'>24 Metric Tonnes</b><br>
            • Highway Patrol Clearance: <b>Open with 24/7 Police Checkpoints</b>
        </div>
    </div>
    """)
