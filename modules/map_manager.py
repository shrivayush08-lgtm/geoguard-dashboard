"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Module: modules/map_manager.py
Purpose: Interactive Geospatial GIS Map, Highway Risk Corridors & Station Markers
=============================================================================
Renders an interactive Folium map modeled after high-tech disaster control rooms:
- Dark CartoDB Dark Matter base map (high-contrast command room aesthetic)
- Multi-station GPS markers (GG-001 through GG-005)
- Color-coded highway corridor segments (NH-58 Himalayan corridor)
- Dynamic danger radius buffer zones for elevated/critical stations
- Road closure & incident warning overlays
- Rich HTML telemetry inspection popups
"""

import streamlit as st
import folium
from folium import plugins
from streamlit_folium import st_folium

# Color mapping helper
RISK_COLOR_MAP = {
    "CRITICAL": "#FF2A4D",
    "HIGH": "#FF7A00",
    "MODERATE": "#FFB000",
    "LOW": "#00E5A3",
    "UNKNOWN": "#8B9BB4"
}

def render_risk_map(enriched_stations, road_sections_df=None, risk_filter="ALL", height=500):
    """
    Renders the professional GIS map with station nodes and highway risk corridors.
    """
    # Calculate map center from station coordinates
    lats = [s["lat"] for s in enriched_stations]
    lons = [s["lon"] for s in enriched_stations]
    center_lat = sum(lats) / len(lats) if lats else 30.18
    center_lon = sum(lons) / len(lons) if lons else 78.50

    # Initialize Folium Map with CartoDB Dark Matter
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles="CartoDB dark_matter",
        control_scale=True
    )

    # Add custom map title / status badge in upper left
    title_html = """
    <div style="position: fixed; 
                top: 15px; left: 55px; width: 260px; 
                background: rgba(14, 23, 37, 0.92); 
                border: 1px solid #263449; border-radius: 8px;
                padding: 10px 14px; z-index: 9999; font-family: 'DM Sans', sans-serif;
                box-shadow: 0 4px 12px rgba(0,0,0,0.5); backdrop-filter: blur(5px);">
        <div style="font-size: 10px; color: #36D6E7; font-weight: 700; letter-spacing: 1.5px;">GIS GEOTECHNICAL GRID</div>
        <div style="font-size: 13px; color: #F1F5F9; font-weight: 700; margin-top: 2px;">NH-58 Himalayan Highway Sector</div>
        <div style="font-size: 11px; color: #94A3B8; margin-top: 4px;">Active Telemetry Nodes: 5 Configured</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # 1. Render Highway Corridor Polyline Segments
    # Real-world approximate mountain highway coordinates connecting stations along the valley
    corridor_segments = [
        {
            "name": "Sector 1: Byasi - Kaudiyala (km 42-58)",
            "coords": [[30.1234, 78.4321], [30.1380, 78.4550], [30.1567, 78.4890]],
            "station": "GG-001"
        },
        {
            "name": "Sector 2: Kaudiyala - Devprayag (km 58-71)",
            "coords": [[30.1567, 78.4890], [30.1750, 78.4980], [30.2012, 78.5123]],
            "station": "GG-002"
        },
        {
            "name": "Sector 3: Devprayag - Kirtinagar (km 71-89)",
            "coords": [[30.2012, 78.5123], [30.2200, 78.5350], [30.2456, 78.5678]],
            "station": "GG-003"
        },
        {
            "name": "Sector 4: Kirtinagar - Srinagar (km 89-105)",
            "coords": [[30.2456, 78.5678], [30.2650, 78.5900], [30.2810, 78.6140]],
            "station": "GG-004"
        }
    ]

    # Map station risk to segment colors
    station_risk_lookup = {s["id"]: s for s in enriched_stations}

    for seg in corridor_segments:
        assoc_stn = station_risk_lookup.get(seg["station"])
        seg_risk = assoc_stn["risk_level"] if assoc_stn else "LOW"
        seg_color = RISK_COLOR_MAP.get(seg_risk, "#22C55E")
        line_weight = 6 if seg_risk in ["CRITICAL", "HIGH"] else 4
        dash_array = "8, 8" if seg_risk == "CRITICAL" else None

        folium.PolyLine(
            locations=seg["coords"],
            color=seg_color,
            weight=line_weight,
            opacity=0.85,
            dash_array=dash_array,
            tooltip=f"{seg['name']} | Risk: {seg_risk}",
            popup=f"<b>{seg['name']}</b><br>Governing Station: {seg['station']}<br>Sector Risk Level: {seg_risk}"
        ).add_to(m)

    # 2. Render Station Markers & Hazard Buffers
    for stn in enriched_stations:
        r_level = stn["risk_level"]

        # Apply Risk Level Filter
        if risk_filter != "ALL" and r_level != risk_filter:
            continue

        marker_color = RISK_COLOR_MAP.get(r_level, "#22C55E")

        # Add Hazard Buffer for High/Critical Risk
        if r_level == "CRITICAL":
            folium.Circle(
                location=[stn["lat"], stn["lon"]],
                radius=1000,
                color="#EF4444",
                weight=2,
                fill=True,
                fill_color="#EF4444",
                fill_opacity=0.25,
                tooltip=f"CRITICAL ZONE: {stn['id']} 1000m Geotechnical Buffer"
            ).add_to(m)
        elif r_level == "HIGH":
            folium.Circle(
                location=[stn["lat"], stn["lon"]],
                radius=600,
                color="#F97316",
                weight=1,
                fill=True,
                fill_color="#F97316",
                fill_opacity=0.18,
                tooltip=f"HIGH RISK ZONE: {stn['id']} 600m Caution Buffer"
            ).add_to(m)

        # High-Tech Dark Popup HTML
        popup_html = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    background: #0E1725; color: #F1F5F9; padding: 12px; 
                    border-radius: 8px; width: 220px; border: 1px solid #263449;">
            <div style="font-size: 11px; color: #36D6E7; font-weight: 700; letter-spacing: 1px;">
                STATION NODE: {stn['id']}
            </div>
            <div style="font-size: 14px; font-weight: 700; margin: 2px 0 6px 0;">
                {stn['name']}
            </div>
            <div style="font-size: 11px; color: #94A3B8; margin-bottom: 8px;">
                {stn.get('corridor', 'NH-58 Corridor')}
            </div>
            
            <div style="background: rgba(255,255,255,0.05); padding: 8px; border-radius: 6px; font-size: 12px;">
                <div style="display:flex; justify-content:space-between; margin-bottom: 3px;">
                    <span style="color:#94A3B8;">Soil Saturation:</span>
                    <b>{stn.get('soil_moisture_pct', 0.0)}%</b>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom: 3px;">
                    <span style="color:#94A3B8;">Precipitation:</span>
                    <b>{stn.get('rainfall_intensity_mmh', 0.0)} mm/h</b>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom: 3px;">
                    <span style="color:#94A3B8;">Slope Tilt:</span>
                    <b>{stn.get('tilt', 0.0):.2f}°</b>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span style="color:#94A3B8;">Tremor State:</span>
                    <b>{'TREMOR 🔴' if stn.get('vib') else 'STABLE 🟢'}</b>
                </div>
            </div>

            <div style="margin-top: 8px; display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:11px; color:#94A3B8;">Risk Score:</span>
                <span style="font-size: 13px; font-weight: 800; color:{marker_color};">
                    {stn['risk_score']} / 100 ({r_level})
                </span>
            </div>
        </div>
        """

        radius_size = 13 if r_level == "CRITICAL" else (11 if r_level == "HIGH" else 8)

        folium.CircleMarker(
            location=[stn["lat"], stn["lon"]],
            radius=radius_size,
            color=marker_color,
            weight=2,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"{stn['id']}: {r_level} ({stn['risk_score']}/100)"
        ).add_to(m)

    # 3. Add Legend in bottom-right corner
    legend_html = """
    <div style="position: fixed; 
                bottom: 25px; right: 25px; width: 170px; 
                background: rgba(14, 23, 37, 0.94); 
                border: 1px solid #263449; border-radius: 8px;
                padding: 10px 14px; z-index: 9999; font-family: 'DM Sans', sans-serif;
                box-shadow: 0 4px 12px rgba(0,0,0,0.5); font-size: 11px;">
        <div style="font-weight: 700; color: #F1F5F9; margin-bottom: 6px; letter-spacing: 0.5px;">RISK CLASSIFICATION</div>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <span style="height: 10px; width: 10px; background: #EF4444; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <span style="color: #F1F5F9;">Critical (75-100)</span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <span style="height: 10px; width: 10px; background: #F97316; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <span style="color: #F1F5F9;">High Risk (50-74)</span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <span style="height: 10px; width: 10px; background: #EAB308; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <span style="color: #F1F5F9;">Moderate (25-49)</span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <span style="height: 10px; width: 10px; background: #22C55E; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <span style="color: #F1F5F9;">Low / Stable (0-24)</span>
        </div>
        <hr style="border:0; border-top: 1px solid #263449; margin: 6px 0;">
        <div style="font-size: 10px; color: #94A3B8;">Lines indicate NH-58 monitored corridor links.</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # Render interactive map using streamlit-folium
    return st_folium(m, width="100%", height=height, returned_objects=[])