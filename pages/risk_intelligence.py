"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/risk_intelligence.py
Purpose: Multi-Axial Geotechnical Risk Engine, Circular Gauge & Radar Telemetry
=============================================================================
Provides:
- Tactical Plotly Circular Gauge with color-coded safety arc zones
- Multi-Axial Geotechnical Risk Radar / Spider Chart (5 failure dimensions)
- Parameter Factor Breakdown with contribution point tracking
- Machine Learning Random Forest Failure Probability comparative inference
- Real-time Sensitivity & Limit State Simulation Sandbox
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from modules.risk_engine import build_risk_gauge, calculate_risk
from modules.ml_inference import predict_landslide_probability
from modules.ui import get_plotly_theme

def render_risk_intelligence_page(enriched_stations):
    """Renders the comprehensive risk intelligence analytics view."""
    st.markdown("<div class='hud-eyebrow'>GEOTECHNICAL KINEMATICS & THREAT MODELING</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Landslide Risk Scoring Engine & Diagnostics</h2>", unsafe_allow_html=True)

    # 1. Station Selector
    station_options = [s["id"] for s in enriched_stations]
    station_names = {s["id"]: f"{s['id']} — {s['name']} [{s.get('corridor', 'NH-58')}]" for s in enriched_stations}
    selected_id = st.selectbox(
        "Target Node for Geotechnical Diagnostics",
        station_options,
        format_func=lambda x: station_names.get(x, x)
    )

    current_stn = next((s for s in enriched_stations if s["id"] == selected_id), enriched_stations[0])

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Top Row: Circular Risk Gauge + Multi-Axial Radar Chart
    gauge_col, radar_col = st.columns([1.2, 1.8])

    with gauge_col:
        st.markdown("### Landslide Risk Index")
        gauge_fig = build_risk_gauge(
            current_stn["risk_score"],
            current_stn["risk_level"],
            current_stn["status_color"],
            height=300
        )
        st.plotly_chart(gauge_fig, use_container_width=True)

        st.markdown(f"""
        <div style='background: rgba(13, 24, 41, 0.9); border: 1px solid #1B2F4C; border-radius: 8px; padding: 12px; text-align: center;'>
            <div style='font-size: 10px; color: #8B9BB4; font-family: "Orbitron", sans-serif;'>TELEMETRY DATA INTEGRITY</div>
            <div style='font-size: 15px; font-weight: 700; color: #00F0FF; margin-top: 2px;'>
                {current_stn['data_quality']} INTEGRITY
            </div>
        </div>
        """, unsafe_allow_html=True)

    with radar_col:
        st.markdown("### Multi-Axial Geotechnical Risk Dimensions")
        
        # Build 5-axis geotechnical radar chart
        breakdown = current_stn.get("breakdown", {})
        soil_p = current_stn.get("soil_moisture_pct", 40.0)
        rain_i = min(100.0, current_stn.get("rainfall_intensity_mmh", 5.0) * 2.5)
        acc_r = min(100.0, current_stn.get("acc_rain", 10.0) * 0.8)
        tilt_p = min(100.0, current_stn.get("tilt", 0.35) * 35.0)
        vib_p = 90.0 if current_stn.get("vib") else 15.0

        categories = [
            "Pore Saturation",
            "Precipitation Rate",
            "24h Antecedent Rain",
            "Inclinometer Tilt",
            "Ground Tremor"
        ]
        values = [soil_p, rain_i, acc_r, tilt_p, vib_p]
        # Close the radar loop
        values_closed = values + [values[0]]
        categories_closed = categories + [categories[0]]

        fig_radar = go.Figure()

        # Danger threshold polygon
        fig_radar.add_trace(go.Scatterpolar(
            r=[75, 75, 75, 75, 75, 75],
            theta=categories_closed,
            fill='none',
            name='Critical Limit (75%)',
            line=dict(color='rgba(255, 42, 77, 0.6)', dash='dash', width=1.5)
        ))

        # Current station radar polygon
        fig_radar.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill='toself',
            name=f"{current_stn['id']} Risk Profile",
            line=dict(color='#00F0FF', width=2),
            fillcolor='rgba(0, 240, 255, 0.2)'
        ))

        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], gridcolor="#1B2F4C", tickfont=dict(color="#8B9BB4", size=9)),
                angularaxis=dict(gridcolor="#1B2F4C", tickfont=dict(color="#F0F6FC", size=10, family="Space Grotesk"))
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=300,
            margin=dict(l=30, r=30, t=20, b=20),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5, font=dict(color="#8B9BB4", size=10))
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    st.markdown("<hr style='border:0; border-top:1px solid #1B2F4C; margin: 18px 0;'>", unsafe_allow_html=True)

    # 3. Factor Points Breakdown & Diagnostics Log
    f_col1, f_col2 = st.columns([1.5, 1.5])

    with f_col1:
        st.markdown("### Factor Score Contributions")
        breakdown_df = pd.DataFrame([
            {"Parameter": "Pore Saturation", "Points": breakdown.get("soil", 0.0), "Max": 30.0, "Color": "#00F0FF"},
            {"Parameter": "Slope Displacement", "Points": breakdown.get("tilt", 0.0), "Max": 30.0, "Color": "#FF7A00"},
            {"Parameter": "Precipitation Rate", "Points": breakdown.get("rain", 0.0), "Max": 25.0, "Color": "#00E5A3"},
            {"Parameter": "Seismic Tremor", "Points": breakdown.get("vibration", 0.0), "Max": 15.0, "Color": "#FF2A4D"},
        ])

        fig_bar = px.bar(
            breakdown_df,
            x="Points",
            y="Parameter",
            orientation="h",
            color="Parameter",
            color_discrete_map={
                "Pore Saturation": "#00F0FF",
                "Slope Displacement": "#FF7A00",
                "Precipitation Rate": "#00E5A3",
                "Seismic Tremor": "#FF2A4D"
            },
            text="Points"
        )
        
        plotly_theme = get_plotly_theme()
        fig_bar.update_layout(
            **plotly_theme,
            height=200,
            showlegend=False,
            xaxis=dict(range=[0, 35], title="Score Contribution (Points)", gridcolor="#1B2F4C"),
            yaxis=dict(title="", showgrid=False)
        )
        fig_bar.update_traces(
            texttemplate='%{x:.1f} pts',
            textposition='outside',
            textfont=dict(color="#F0F6FC", family="Space Grotesk")
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with f_col2:
        st.markdown("### Factor Diagnostic Observations")
        st.markdown(f"""
        <div style='background: rgba(13, 24, 41, 0.9); border: 1px solid #1B2F4C; border-radius: 8px; padding: 16px;'>
            <div class='hud-eyebrow'>REAL-TIME GEOTECHNICAL TELEMETRY FACTORS:</div>
            <div style='margin-top: 8px;'>
                {''.join([f"<div style='font-size:13px; color:#E2E8F0; margin-bottom:6px; display:flex; align-items:center; gap:8px;'><span style='color:#00F0FF;'>▸</span> {f}</div>" for f in current_stn.get('factors', [])])}
            </div>
            <hr style='border:0; border-top:1px solid #1B2F4C; margin:12px 0;'>
            <div style='font-size:12px; color:#8B9BB4; line-height:1.5;'>
                <b>Recommended Mitigation Action:</b><br>
                <span style='color:{current_stn["status_color"]}; font-weight:600;'>{current_stn.get("recommended_action")}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr style='border:0; border-top:1px solid #1B2F4C; margin: 18px 0;'>", unsafe_allow_html=True)

    # 4. Machine Learning Inference Model Comparison
    st.markdown("### 🤖 Applied Machine Learning Failure Probability (Random Forest)")
    
    ml_res = predict_landslide_probability(
        soil_pct=current_stn.get("soil_moisture_pct"),
        rain_mmh=current_stn.get("rainfall_intensity_mmh"),
        acc_rain_mm=current_stn.get("acc_rain", 15.0),
        tilt_deg=current_stn.get("tilt"),
        tilt_rate_deg_h=current_stn.get("tilt_rate", 0.0),
        vibration_detected=current_stn.get("vib", False)
    )

    ml_c1, ml_c2, ml_c3 = st.columns([1, 1, 1.5])
    with ml_c1:
        st.metric("ML Failure Probability", f"{ml_res['failure_probability_pct']}%", ml_res['predicted_class'])
    with ml_c2:
        st.metric("Model Architecture", ml_res["model_version"], "Random Forest (50 Estimators)")
    with ml_c3:
        st.caption(f"ℹ️ {ml_res['note']}")

    # 5. Geotechnical Sandbox Expander
    with st.expander("🛠️ Geotechnical Stress Simulation Sandbox", expanded=False):
        st.markdown("Adjust hypothetical parameters to test immediate risk engine reaction:")
        sb1, sb2, sb3, sb4 = st.columns(4)
        with sb1:
            t_soil = st.slider("Simulated Soil VWC (%)", 10.0, 100.0, float(current_stn.get("soil_moisture_pct", 45.0)))
        with sb2:
            t_rain = st.slider("Simulated Rain Rate (mm/h)", 0.0, 60.0, float(current_stn.get("rainfall_intensity_mmh", 5.0)))
        with sb3:
            t_tilt = st.slider("Simulated Inclinometer Tilt (°)", 0.0, 5.0, float(current_stn.get("tilt", 0.35)))
        with sb4:
            t_vib = st.checkbox("Trigger Seismic Tremor", value=current_stn.get("vib", False))

        test_res = calculate_risk(
            soil_moisture_pct=t_soil,
            rainfall_intensity_mmh=t_rain,
            tilt_degrees=t_tilt,
            vibration_detected=t_vib
        )

        st.info(f"**Sandbox Calculated Result:** Risk Index = **{test_res['risk_score']} / 100** ({test_res['risk_level']}) | Mitigation: {test_res['recommended_action']}")
