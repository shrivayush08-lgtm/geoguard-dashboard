"""
=============================================================================
GEOGUARD AI — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/alert_center.py
Purpose: Incident Operations Center, Alert Lifecycle & Audit Trail
=============================================================================
Manages:
- Incident queue with status badges (NEW -> ACKNOWLEDGED -> INVESTIGATING -> RESOLVED)
- Emergency drill injection with instant cooldown protection
- Inter-agency unit assignment (NDRF, SDRF, BRO, Police, EMS)
- Digital audit log with operator timestamps
=============================================================================
"""

import streamlit as st
from database.db import get_alerts, update_alert_status, log_alert, get_response_teams
from modules.ui import render_html


def render_alert_center_page(enriched_stations):
    """Renders the alert management center."""
    st.markdown("<div class='hud-eyebrow'>INCIDENT LOG & RESPONSE QUEUE</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Incident Operations & Alert Center</h2>", unsafe_allow_html=True)

    # 1. Top Controls Bar: Filter & Emergency Simulation Drill
    top_col1, top_col2, top_col3 = st.columns([1.5, 1.5, 2])
    with top_col1:
        status_filter = st.selectbox(
            "Filter Queue by Status",
            ["ALL", "NEW", "ACKNOWLEDGED", "UNDER INVESTIGATION", "RESOLVED", "FALSE ALARM"],
            index=0
        )
    with top_col2:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("🚨 TRIGGER DRILL INCIDENT", type="primary", use_container_width=True):
            alert_id, created = log_alert(
                station_id="GG-001",
                risk_level="CRITICAL",
                risk_score=88.5,
                reason="SIMULATED EMERGENCY DRILL: Acute pore saturation (88.4%) & slope shear slip (+3.12°).",
                is_test=1
            )
            st.toast(f"Drill Incident #{alert_id} Logged!", icon="🚨")
            st.rerun()
    with top_col3:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        st.caption("ℹ️ Incident lifecycle updates are committed to database with operator audit logging.")

    # 2. Fetch and Display Active Alerts
    alerts_df = get_alerts(status_filter=status_filter, limit=50)

    if alerts_df.empty:
        render_html("""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 8px; padding: 24px; text-align: center;'>
            <div style='font-size: 24px; margin-bottom: 6px;'>🟢</div>
            <div style='font-size: 14px; font-weight: 600; color: #10B981;'>INCIDENT QUEUE CLEAR</div>
            <div style='font-size: 12px; color: #94A3B8; margin-top: 4px;'>All monitored mountain corridors reporting nominal geotechnical stability.</div>
        </div>
        """)
        return

    st.markdown("### Active Incidents & Log Stream")

    for _, row in alerts_df.iterrows():
        alert_id = row["alert_id"]
        status = row["status"]
        risk_lvl = row["risk_level"]
        
        border_color = (
            "#EF4444" if "CRITICAL" in risk_lvl 
            else ("#F97316" if "HIGH" in risk_lvl else "#F59E0B")
        )
        badge_class = (
            "hud-badge-critical" if "CRITICAL" in risk_lvl 
            else ("hud-badge-high" if "HIGH" in risk_lvl else "hud-badge-moderate")
        )

        with st.container():
            render_html(f"""
            <div style='background: #111827; border-left: 4px solid {border_color}; border-top: 1px solid #1F2937; border-right: 1px solid #1F2937; border-bottom: 1px solid #1F2937; border-radius: 6px; padding: 14px 18px; margin-bottom: 10px;'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <div>
                        <span class='hud-badge {badge_class}'>{risk_lvl}</span>
                        <span style='font-size: 14px; font-weight: 600; color: #F8FAFC; margin-left: 10px;'>
                            Incident #{alert_id} • Station {row['station_id']}
                        </span>
                        {'<span class="hud-badge" style="background:rgba(255,255,255,0.08); color:#94A3B8; margin-left:8px;">TEST_DRILL</span>' if row.get('is_test') else ''}
                    </div>
                    <div class='font-mono' style='font-size: 11px; color: #64748B;'>
                        Logged: <b style='color:#F8FAFC;'>{row['timestamp']}</b> | Status: <b style='color:#38BDF8;'>{status}</b>
                    </div>
                </div>
                <div style='font-size: 13px; color: #E2E8F0; margin-top: 8px; line-height: 1.4;'>
                    <b>Geotechnical Anomaly:</b> {row['reason']}
                </div>
                <div class='font-mono' style='font-size: 11px; color: #94A3B8; margin-top: 8px;'>
                    Officer: <b style='color:#F8FAFC;'>{row['acknowledged_by'] or 'Pending'}</b> ({row['ack_timestamp'] or 'N/A'}) • 
                    Assigned Unit: <b style='color:#38BDF8;'>{row['assigned_team'] or 'Unassigned'}</b>
                </div>
                {f"<div style='font-size:12px; color:#94A3B8; margin-top:4px;'><b>Field Note:</b> {row['operator_notes']}</div>" if row['operator_notes'] else ''}
            </div>
            """)

            # Interactive Action Expander
            with st.expander(f"Incident Management Console — Incident #{alert_id}", expanded=False):
                act_col1, act_col2, act_col3 = st.columns([1.5, 2, 1.5])
                
                with act_col1:
                    new_state = st.selectbox(
                        "Transition Status",
                        ["NEW", "ACKNOWLEDGED", "UNDER INVESTIGATION", "RESOLVED", "FALSE ALARM"],
                        index=["NEW", "ACKNOWLEDGED", "UNDER INVESTIGATION", "RESOLVED", "FALSE ALARM"].index(status) if status in ["NEW", "ACKNOWLEDGED", "UNDER INVESTIGATION", "RESOLVED", "FALSE ALARM"] else 0,
                        key=f"status_sel_{alert_id}"
                    )
                with act_col2:
                    operator_name = st.text_input("Watch Officer ID", value="Duty Officer Garhwal", key=f"op_{alert_id}")
                    notes = st.text_input("Incident Action Notes", value=row['operator_notes'] or "", key=f"notes_{alert_id}")
                with act_col3:
                    teams_df = get_response_teams()
                    team_list = ["None"] + teams_df["team_name"].tolist() if not teams_df.empty else ["None"]
                    assigned_t = st.selectbox("Assign Response Unit", team_list, key=f"team_{alert_id}")
                    
                    if st.button("Commit Incident Update", key=f"commit_{alert_id}", type="primary", use_container_width=True):
                        team_val = None if assigned_t == "None" else assigned_t
                        update_alert_status(alert_id, new_state, operator_name=operator_name, notes=notes, assigned_team=team_val)
                        st.success(f"Incident #{alert_id} transition saved.")
                        st.rerun()
