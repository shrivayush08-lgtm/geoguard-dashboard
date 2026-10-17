"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/settings.py
Purpose: System Parameters, Geotechnical Limits & Database Administration
=============================================================================
Manages:
- Geotechnical Risk Level Boundaries (Moderate, High, Critical)
- Physical Sensor Warning Trip Limits (Soil ADC, Rain ADC, Tilt Degrees)
- Telemetry Freshness & Alert Cooldown Timers
- External Integrations (OpenWeatherMap, Webhook Notifications)
- Database Optimization & Synthetic Telemetry Re-seeding Tools
"""

import streamlit as st
from database.db import get_config, set_config, get_connection
from modules.sensor_simulator import seed_historical_telemetry_if_needed

def render_settings_page():
    """Renders the settings and system configuration view."""
    st.markdown("<div class='hud-eyebrow'>SYSTEM CONFIGURATION & CALIBRATION</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Settings & Configuration</h2>", unsafe_allow_html=True)

    # 1. Geotechnical Risk Threshold Boundaries
    st.markdown("### ⚡ Geotechnical Risk Classification Thresholds")
    st.caption("Configure the 0–100 Landslide Risk Index tier boundary trip points:")

    with st.form("thresholds_form"):
        t_col1, t_col2, t_col3 = st.columns(3)
        with t_col1:
            mod_t = st.slider("Moderate Warning Boundary", 10, 40, int(get_config("risk_threshold_moderate", "25")))
        with t_col2:
            high_t = st.slider("High Risk Advisory Boundary", 41, 70, int(get_config("risk_threshold_high", "50")))
        with t_col3:
            crit_t = st.slider("Critical Emergency Boundary", 71, 95, int(get_config("risk_threshold_critical", "75")))

        st.markdown("#### Sensor Physical Trip Limits")
        s_col1, s_col2, s_col3 = st.columns(3)
        with s_col1:
            soil_warn = st.number_input("Pore Saturation Warning (ADC)", value=int(get_config("soil_warning_adc", "2800")), step=50)
        with s_col2:
            rain_warn = st.number_input("Precipitation Intensity Trip (ADC)", value=int(get_config("rain_warning_adc", "3200")), step=50)
        with s_col3:
            tilt_warn = st.number_input("Inclinometer Shear Trip (Degrees)", value=float(get_config("tilt_warning_degrees", "1.5")), step=0.1)

        save_thresh = st.form_submit_button("💾 Commit Geotechnical Boundaries", type="primary")
        if save_thresh:
            set_config("risk_threshold_moderate", str(mod_t), "Moderate warning threshold")
            set_config("risk_threshold_high", str(high_t), "High risk threshold")
            set_config("risk_threshold_critical", str(crit_t), "Critical emergency threshold")
            set_config("soil_warning_adc", str(soil_warn), "Soil moisture ADC warning")
            set_config("rain_warning_adc", str(rain_warn), "Rain sensor ADC trip point")
            set_config("tilt_warning_degrees", str(tilt_warn), "Slope tilt warning degrees")
            st.success("Geotechnical boundaries committed to SQLite configuration.")

    st.markdown("<hr style='border:0; border-top:1px solid #1B2F4C; margin: 20px 0;'>", unsafe_allow_html=True)

    # 2. Timing, Telemetry Freshness & Webhooks
    st.markdown("### ⏱️ Telemetry Freshness & Alert Cooldowns")
    
    with st.form("comms_form"):
        c_col1, c_col2 = st.columns(2)
        with c_col1:
            cooldown = st.number_input(
                "Alert Cooldown Period (Minutes)",
                value=int(get_config("alert_cooldown_minutes", "10")),
                min_value=1,
                max_value=120,
                help="Minimum time before the same station triggers another alert for an identical condition."
            )
            freshness = st.number_input(
                "Data Freshness Timeout (Seconds)",
                value=int(get_config("telemetry_freshness_seconds", "30")),
                min_value=5,
                max_value=300,
                help="Timeout before station is flagged DELAYED or OFFLINE."
            )
        with c_col2:
            webhook = st.text_input(
                "Notification Webhook URL (Telegram / Slack / Crisis Gateway)",
                value=get_config("notification_webhook", ""),
                placeholder="https://api.telegram.org/bot<TOKEN>/sendMessage"
            )
            weather_key = st.text_input(
                "Optional OpenWeatherMap API Key",
                value=get_config("weather_api_key", ""),
                type="password",
                help="Leave blank to use free public Open-Meteo numerical model."
            )

        save_comms = st.form_submit_button("💾 Save Integration Parameters")
        if save_comms:
            set_config("alert_cooldown_minutes", str(cooldown))
            set_config("telemetry_freshness_seconds", str(freshness))
            set_config("notification_webhook", webhook)
            set_config("weather_api_key", weather_key)
            st.success("Integration parameters saved.")

    st.markdown("<hr style='border:0; border-top:1px solid #1B2F4C; margin: 20px 0;'>", unsafe_allow_html=True)

    # 3. Database Maintenance Utilities
    st.markdown("### 🗄️ Database Administration & Reset Tools")
    
    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        if st.button("↺ Re-Seed 24h Historical Telemetry", use_container_width=True):
            conn = get_connection()
            conn.execute("DELETE FROM telemetry_history")
            conn.commit()
            conn.close()
            seed_historical_telemetry_if_needed()
            st.success("Re-seeded 96 synthetic historical intervals.")
            st.rerun()

    with m_col2:
        if st.button("🗑️ Clear Alert Incident Queue", use_container_width=True):
            conn = get_connection()
            conn.execute("DELETE FROM alerts")
            conn.commit()
            conn.close()
            st.info("Alerts table cleared.")
            st.rerun()

    with m_col3:
        if st.button("🧹 Vacuum SQLite Database", use_container_width=True):
            conn = get_connection()
            conn.execute("VACUUM")
            conn.close()
            st.success("Database vacuumed and optimized.")
