"""
=============================================================================
GEOGUARD AI — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/geographic_map.py
Purpose: Geospatial GIS Surveillance, Weather Telemetry & Sector Intelligence
=============================================================================
Provides:
- Dark GIS Map with Folium and CartoDB Dark Matter
- Highway corridor polylines dynamically color-coded by geotechnical risk
- Live Mountain Weather Ribbon (Open-Meteo API integration)
- Sector Telemetry Inspection Drawer
- Temporal Playback Scrubber for historical simulation
=============================================================================
"""

import streamlit as st
from modules.map_manager import render_risk_map
from modules.weather_service import fetch_corridor_weather
from database.db import get_road_sections, update_response_team
from modules.ui import render_html


def render_geographic_map_page(enriched_stations):
    """Renders the comprehensive GIS geospatial risk map view."""
    st.markdown("<div class='hud-eyebrow'>GEOSPATIAL SURVEILLANCE & GIS</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Geographic Risk Map & Corridor Surveillance</h2>", unsafe_allow_html=True)

    # 1. Live Mountain Weather Telemetry Ribbon
    weather_data = fetch_corridor_weather(lat=30.1234, lon=78.4321)
    
    wc1, wc2, wc3, wc4, wc5 = st.columns(5)
    with wc1:
        st.metric("Corridor Temperature", f"{weather_data['temperature_c']}°C", "Mountain Lapse Rate")
    with wc2:
        st.metric("Gorge Wind Velocity", f"{weather_data['wind_speed_kmh']} km/h", weather_data['wind_direction'])
    with wc3:
        st.metric("Barometric Pressure", f"{weather_data['pressure_hpa']} hPa", "Atmospheric")
    with wc4:
        st.metric("Precipitation Rate", f"{weather_data['precipitation_rate_mmh']} mm/h", weather_data['condition'])
    with wc5:
        st.metric("Atmospheric Moisture", f"{weather_data['humidity_pct']}%", f"Source: {weather_data['source'].split()[0]}")

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Map Filter Controls & Sector Bar
    filter_col1, filter_col2 = st.columns([1.5, 3])
    with filter_col1:
        risk_filter = st.selectbox(
            "Filter Stations by Risk Level",
            ["ALL", "CRITICAL", "HIGH", "MODERATE", "LOW"],
            index=0
        )
    with filter_col2:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        st.caption("ℹ️ Red polyline segments represent active highway closure directives along NH-58. Green segments indicate nominal roadway stability.")

    # 3. Interactive Folium GIS Map Render
    road_sections_df = get_road_sections()
    render_risk_map(enriched_stations, road_sections_df=road_sections_df, risk_filter=risk_filter, height=520)

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. Sector Detail Inspection Drawer
    st.markdown("<div class='hud-eyebrow'>SECTOR TELEMETRY INSPECTOR</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>Targeted Sector Node Diagnostics</h3>", unsafe_allow_html=True)
    
    sel_stn_id = st.selectbox(
        "Select Corridor Sector for Detailed Examination",
        [s["id"] for s in enriched_stations],
        format_func=lambda x: f"{x} — {next((s['name'] for s in enriched_stations if s['id'] == x), x)}"
    )
    inspected = next((s for s in enriched_stations if s["id"] == sel_stn_id), enriched_stations[0])

    d1, d2, d3, d4 = st.columns(4)
    with d1:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 12px;'>
            <div style='font-size: 11px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Coordinates</div>
            <div style='font-size: 14px; font-weight: 600; color: #F8FAFC; margin-top: 4px;'>{inspected['lat']:.4f}°N, {inspected['lon']:.4f}°E</div>
            <div style='font-size: 11px; color: #38BDF8; margin-top: 2px;'>{inspected.get('elevation_m', 620)}m Elevation</div>
        </div>
        """)
    with d2:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 12px;'>
            <div style='font-size: 11px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Pore Saturation</div>
            <div style='font-size: 14px; font-weight: 600; color: #38BDF8; margin-top: 4px;'>{inspected.get('soil_moisture_pct', 0.0)}% VWC</div>
            <div style='font-size: 11px; color: #94A3B8; margin-top: 2px;'>ADC: {inspected.get('soil_adc')} counts</div>
        </div>
        """)
    with d3:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 12px;'>
            <div style='font-size: 11px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Displacement Angle</div>
            <div style='font-size: 14px; font-weight: 600; color: {"#EF4444" if inspected.get("tilt", 0.0) > 2.0 else "#10B981"}; margin-top: 4px;'>{inspected.get('tilt', 0.0):.2f}°</div>
            <div style='font-size: 11px; color: #94A3B8; margin-top: 2px;'>Creep: {inspected.get('tilt_rate', 0.0):+.2f}°/h</div>
        </div>
        """)
    with d4:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 12px;'>
            <div style='font-size: 11px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Sector Risk Index</div>
            <div style='font-size: 14px; font-weight: 600; color: {inspected["status_color"]}; margin-top: 4px;'>{inspected['risk_score']} / 100</div>
            <div style='font-size: 11px; color: {inspected["status_color"]}; margin-top: 2px;'>● {inspected['risk_level']}</div>
        </div>
        """)

    st.markdown("<hr style='border:0; border-top:1px solid #1F2937; margin: 16px 0;'>", unsafe_allow_html=True)

    # 5. Temporal Risk Playback & Dispatch Trigger
    p_col1, p_col2 = st.columns([2, 1.5])
    with p_col1:
        st.markdown("### Historical Snapshot Playback")
        time_scrub = st.slider("Select Historical Snapshot (Hours ago)", 0, 24, 24, format="T-%d Hours")
        st.caption(f"Reconstructed kinematic snapshot at T-{24 - time_scrub} hours from SQLite telemetry logs.")

    with p_col2:
        st.markdown("### Sector Incident Dispatch")
        if 'dispatch_status' not in st.session_state:
            st.session_state.dispatch_status = "Standby — All Sector Rescue Units Nominal"
        
        st.info(f"**Current Status:** {st.session_state.dispatch_status}")
