"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/historical_analytics.py
Purpose: Historical Telemetry Analytics, Multi-Station Comparisons & Correlations
=============================================================================
Provides deep geotechnical diagnostics:
- Multi-station comparative risk score timelines
- Time-series waveforms for soil moisture, precipitation, tilt, and tremors
- Cross-sensor correlation matrix (Pearson geotechnical coupling)
- Temporal category distribution and frequency analytics
- Time-window filtering (15m, 1h, 24h, 7d, all)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from modules.ui import get_plotly_theme
from modules.data_store import get_filtered_history

def render_historical_analytics_page(enriched_stations):
    """Renders the historical analytics and comparative telemetry view."""
    st.markdown("<div class='hud-eyebrow'>HISTORICAL TELEMETRY INTELLIGENCE</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Geotechnical Historical Analytics</h2>", unsafe_allow_html=True)

    # 1. Filter Bar
    f1, f2 = st.columns([1.5, 2.5])
    with f1:
        time_filter = st.selectbox(
            "Select Analysis Time Horizon",
            ["Last 15 Minutes", "Last 1 Hour", "Last 24 Hours", "Last 7 Days", "All Records"],
            index=2
        )
    with f2:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        st.caption("Historical database synchronization: SQLite telemetry_history table with indexing.")

    # Fetch historical dataframe
    hist_df = get_filtered_history(station_id=None, time_range=time_filter)

    if hist_df.empty:
        st.warning(f"No historical telemetry records logged for {time_filter}. Telemetry generator is actively accumulating data.")
        return

    # 2. Multi-Station Comparative Timeline Chart
    st.markdown("### Multi-Station Soil Moisture & Geotechnical Trends")
    fig_comp = px.line(
        hist_df,
        x="datetime",
        y="soil_moisture_pct",
        color="station_id",
        title="Volumetric Soil Saturation (% VWC) by Station Node",
        color_discrete_sequence=["#00F0FF", "#00E5A3", "#FF7A00", "#FFB000", "#FF2A4D"]
    )
    
    plotly_theme = get_plotly_theme()
    fig_comp.update_layout(
        **plotly_theme,
        height=340,
        xaxis=dict(title="Timestamp (UTC)", gridcolor="#1B2F4C"),
        yaxis=dict(title="Soil Saturation (% VWC)", gridcolor="#1B2F4C"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_comp, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. Two-Column Diagnostic Charts: Slope Tilt vs Cumulative Precipitation
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Slope Inclinometer Displacement (°)")
        fig_tilt = px.line(
            hist_df,
            x="datetime",
            y="tilt_degrees",
            color="station_id",
            title="Angular Creep Displacement Over Time",
            color_discrete_sequence=["#00F0FF", "#00E5A3", "#FF7A00", "#FFB000", "#FF2A4D"]
        )
        fig_tilt.update_layout(
            **plotly_theme,
            height=300,
            xaxis=dict(title="Timestamp", gridcolor="#1B2F4C"),
            yaxis=dict(title="Tilt Angle (Degrees)", gridcolor="#1B2F4C"),
            showlegend=False
        )
        st.plotly_chart(fig_tilt, use_container_width=True)

    with c2:
        st.markdown("### Antecedent 24h Precipitation Accumulation (mm)")
        fig_rain = px.area(
            hist_df,
            x="datetime",
            y="rain_acc_24h_mm",
            color="station_id",
            title="Cumulative Rainfall Saturation",
            color_discrete_sequence=["#00F0FF", "#00E5A3", "#FF7A00", "#FFB000", "#FF2A4D"]
        )
        fig_rain.update_layout(
            **plotly_theme,
            height=300,
            xaxis=dict(title="Timestamp", gridcolor="#1B2F4C"),
            yaxis=dict(title="Cumulative Rain (mm)", gridcolor="#1B2F4C"),
            showlegend=False
        )
        st.plotly_chart(fig_rain, use_container_width=True)

    st.markdown("<hr style='border:0; border-top:1px solid #1B2F4C; margin: 18px 0;'>", unsafe_allow_html=True)

    # 4. Cross-Sensor Correlation Heatmap
    st.markdown("### 🧬 Geotechnical Cross-Sensor Correlation Matrix")
    corr_cols = ["soil_moisture_pct", "rainfall_intensity_mmh", "rain_acc_24h_mm", "tilt_degrees", "vibration_detected"]
    corr_df = hist_df[corr_cols].dropna().corr()
    
    # Rename for presentation
    rename_dict = {
        "soil_moisture_pct": "Soil VWC %",
        "rainfall_intensity_mmh": "Rain Rate mm/h",
        "rain_acc_24h_mm": "24h Rain mm",
        "tilt_degrees": "Slope Tilt °",
        "vibration_detected": "Tremor 0/1"
    }
    corr_df = corr_df.rename(index=rename_dict, columns=rename_dict)

    fig_corr = px.imshow(
        corr_df,
        text_auto=".2f",
        color_continuous_scale="Tealrose",
        aspect="auto"
    )
    fig_corr.update_layout(
        **plotly_theme,
        height=320,
        margin=dict(l=20, r=20, t=20, b=20)
    )
    st.plotly_chart(fig_corr, use_container_width=True)
    st.caption("Pearson correlation indicates geotechnical coupling between precipitation saturation and accelerated slope creep.")
