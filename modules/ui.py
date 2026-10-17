"""
=============================================================================
GEOGUARD AI — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Module: modules/ui.py
Purpose: Professional Geotechnical Engineering Design System & UI Components
=============================================================================
Provides clean, human-designed styling for environmental monitoring:
- Clean, modern slate palette (#0B0F19 base, #111827 cards, #1F2937 borders)
- Clear, readable typography (Inter, JetBrains Mono)
- Standardized engineering status indicators (Emerald, Amber, Orange, Red)
- Zero cheesy cyberpunk tropes, no neon matrix grids, no '//' syntax
- Interactive Geotechnical Slope Stratigraphy Cross-Section SVG
- Highway Linear Schematic visualizer
=============================================================================
"""

import base64
from functools import lru_cache
from pathlib import Path
import streamlit as st
from datetime import datetime
import plotly.graph_objects as go

# Clean Geotechnical Engineering Color Palette
COLOR_BASE = "#0B0F19"
COLOR_PANEL = "#111827"
COLOR_PANEL_ELEVATED = "#1A2234"
COLOR_BORDER = "#1F2937"
COLOR_BORDER_HOVER = "#374151"

COLOR_BLUE = "#3B82F6"
COLOR_CYAN = "#38BDF8"
COLOR_TEAL = "#14B8A6"
COLOR_SAFE = "#10B981"
COLOR_MODERATE = "#F59E0B"
COLOR_HIGH = "#F97316"
COLOR_CRITICAL = "#EF4444"
COLOR_TEXT_PRIMARY = "#F9FAFB"
COLOR_TEXT_MUTED = "#9CA3AF"


@lru_cache(maxsize=1)
def get_background_base64() -> str:
    """Reads and caches background image as base64 string."""
    bg_path = Path(__file__).resolve().parent.parent / "assets" / "backgrounds" / "dashboard_bg.jpg"
    if not bg_path.exists():
        bg_path = Path(__file__).resolve().parent.parent / "assets" / "backgrounds" / "option_05_geotechnical_slope_netting.jpg"
    if bg_path.exists():
        try:
            with open(bg_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            return ""
    return ""


def inject_custom_css():
    """Injects clean, professional enterprise dashboard CSS with geotechnical landslide terrain background."""
    bg_b64 = get_background_base64()
    if bg_b64:
        bg_style = f"""
        background-color: {COLOR_BASE} !important;
        background-image: linear-gradient(rgba(11, 15, 25, 0.85), rgba(11, 15, 25, 0.92)), url("data:image/jpeg;base64,{bg_b64}") !important;
        background-size: cover !important;
        background-position: center center !important;
        background-attachment: fixed !important;
        background-repeat: no-repeat !important;
        """
    else:
        bg_style = f"""
        background-color: {COLOR_BASE} !important;
        background-image: none !important;
        """

    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    /* Global App Container */
    .stApp {{
        {bg_style}
        color: {COLOR_TEXT_PRIMARY} !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }}

    /* Hide Streamlit Default Header and Footer */
    header[data-testid="stHeader"] {{
        background: transparent !important;
    }}
    footer {{visibility: hidden;}}
    #MainMenu {{visibility: hidden;}}

    /* Sidebar Styling */
    [data-testid="stSidebar"] {{
        background-color: #0E131F !important;
        border-right: 1px solid {COLOR_BORDER} !important;
    }}

    /* Navigation Radio Buttons */
    div[data-testid="stRadio"] > div {{
        gap: 3px !important;
    }}
    div[data-testid="stRadio"] label {{
        background: transparent !important;
        border: 1px solid transparent !important;
        border-radius: 6px !important;
        padding: 7px 12px !important;
        color: #94A3B8 !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
        margin-bottom: 2px !important;
    }}
    div[data-testid="stRadio"] label:hover {{
        background: #162032 !important;
        color: #F8FAFC !important;
    }}
    div[data-testid="stRadio"] label[data-checked="true"] {{
        background: #1A263D !important;
        border-color: #2D3E5E !important;
        color: #38BDF8 !important;
        font-weight: 600 !important;
    }}
    div[data-testid="stRadio"] label > div:first-child {{
        display: none !important;
    }}

    /* Typography */
    h1, h2, h3, h4 {{
        font-family: 'Inter', -apple-system, sans-serif !important;
        color: #F9FAFB !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
    }}
    .font-mono {{
        font-family: 'JetBrains Mono', monospace !important;
    }}
    .font-hud {{
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em !important;
    }}

    /* Clean Section Eyebrows */
    .hud-eyebrow {{
        font-family: 'Inter', -apple-system, sans-serif;
        color: #38BDF8;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        display: inline-flex;
        align-items: center;
        margin-bottom: 4px;
    }}

    /* Cards */
    .hud-kpi {{
        background: {COLOR_PANEL};
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        padding: 16px 18px;
        transition: border-color 0.15s ease;
    }}
    .hud-kpi:hover {{
        border-color: {COLOR_BORDER_HOVER};
    }}
    .hud-kpi-title {{
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        color: #94A3B8;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 6px;
    }}
    .hud-kpi-value {{
        font-family: 'Inter', sans-serif;
        font-size: 26px;
        font-weight: 700;
        line-height: 1.1;
    }}
    .hud-kpi-sub {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        color: #64748B;
        margin-top: 6px;
        display: flex;
        align-items: center;
        gap: 5px;
    }}

    /* Status Badges */
    .hud-badge {{
        font-family: 'JetBrains Mono', monospace;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }}
    .hud-badge-safe {{ background: rgba(16, 185, 129, 0.12); color: {COLOR_SAFE}; border: 1px solid rgba(16, 185, 129, 0.3); }}
    .hud-badge-moderate {{ background: rgba(245, 158, 11, 0.12); color: {COLOR_MODERATE}; border: 1px solid rgba(245, 158, 11, 0.3); }}
    .hud-badge-high {{ background: rgba(249, 115, 22, 0.12); color: {COLOR_HIGH}; border: 1px solid rgba(249, 115, 22, 0.3); }}
    .hud-badge-critical {{ background: rgba(239, 68, 68, 0.15); color: {COLOR_CRITICAL}; border: 1px solid rgba(239, 68, 68, 0.4); }}

    /* Hazard Status Banner */
    .hud-banner {{
        border-radius: 6px;
        padding: 14px 18px;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border: 1px solid {COLOR_BORDER};
        background: {COLOR_PANEL};
        border-left-width: 4px;
    }}
    .hud-banner-safe {{ border-left-color: {COLOR_SAFE}; }}
    .hud-banner-elevated {{ border-left-color: {COLOR_MODERATE}; }}
    .hud-banner-high {{ border-left-color: {COLOR_HIGH}; }}
    .hud-banner-critical {{ border-left-color: {COLOR_CRITICAL}; }}

    /* Standard Interactive Buttons */
    div.stButton > button {{
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        border-radius: 6px !important;
        border: 1px solid {COLOR_BORDER} !important;
        background: #162032 !important;
        color: #F8FAFC !important;
        padding: 7px 16px !important;
        transition: all 0.15s ease !important;
    }}
    div.stButton > button:hover {{
        border-color: #3B82F6 !important;
        color: #38BDF8 !important;
        background: #1B2940 !important;
    }}
    div.stButton > button[kind="primary"] {{
        background: #2563EB !important;
        border-color: #1D4ED8 !important;
        color: #FFFFFF !important;
    }}
    div.stButton > button[kind="primary"]:hover {{
        background: #1D4ED8 !important;
    }}

    /* Form Inputs & Selects */
    div[data-baseweb="select"] > div {{
        background: #0E1422 !important;
        border-color: {COLOR_BORDER} !important;
        color: #F8FAFC !important;
        border-radius: 6px !important;
    }}
    div[data-baseweb="input"] > div {{
        background: #0E1422 !important;
        border-color: {COLOR_BORDER} !important;
        color: #F8FAFC !important;
        border-radius: 6px !important;
    }}

    /* Scrollbars */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: #0B0F19; }}
    ::-webkit-scrollbar-thumb {{ background: #1F2937; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #374151; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_html(html_str):
    """
    Renders clean raw HTML while stripping all indentation
    so Markdown never confuses HTML lines with 4-space indented code blocks.
    """
    cleaned = "\n".join(line.strip() for line in html_str.splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


def render_hud_header(operating_mode="SIMULATION", total_stations=5, online_stations=5, network_health="99.2%"):
    """Renders the top control center header bar."""
    utc_time = datetime.utcnow().strftime('%H:%M:%S')
    utc_date = datetime.utcnow().strftime('%d %b %Y')

    col_left, col_right = st.columns([3.2, 1.8])
    with col_left:
        render_html(f"""
        <div style='display: flex; align-items: center; gap: 12px;'>
            <div style='background: #162032; border: 1px solid #1F2937; border-radius: 8px; width: 42px; height: 42px; display: flex; align-items: center; justify-content: center; font-size: 20px;'>
                🛡️
            </div>
            <div>
                <div class='hud-eyebrow'>NATIONAL HIGHWAY CORRIDOR 58 • GEOTECHNICAL MONITORING</div>
                <h1 style='margin:0; font-size: 24px; font-weight: 700; letter-spacing: -0.02em;'>
                    Highway Control Center
                </h1>
            </div>
        </div>
        """)

    with col_right:
        mode_color = COLOR_SAFE if operating_mode == "SIMULATION" else COLOR_MODERATE
        mode_label = "SIMULATION MODE" if operating_mode == "SIMULATION" else "HARDWARE SERIAL LINK"
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 10px 14px;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span class='font-mono' style='font-size: 11px; color: {mode_color}; font-weight: 600;'>
                    ● {mode_label}
                </span>
                <span class='font-mono' style='font-size: 11px; color: #94A3B8;'>
                    UTC <b style='color:#F8FAFC;'>{utc_time}</b> | {utc_date}
                </span>
            </div>
            <div style='display: flex; justify-content: space-between; margin-top: 6px; font-size: 11px; color: #94A3B8;'>
                <span>Monitoring Nodes: <b style='color:#38BDF8;'>{online_stations}/{total_stations} Active</b></span>
                <span>Telemetry Health: <b style='color:{COLOR_SAFE};'>{network_health}</b></span>
            </div>
        </div>
        """)

    st.markdown("<hr style='border: 0; border-top: 1px solid #1F2937; margin: 10px 0 16px 0;'>", unsafe_allow_html=True)


def render_hud_banner(status_code="STABLE", detail="All monitored slope sensors reporting nominal geotechnical stability."):
    """Renders the standard hazard status bar."""
    configs = {
        "STABLE": ("hud-banner-safe", "SYSTEM STATUS: NORMAL MONITORING", "🟢", COLOR_SAFE),
        "ELEVATED": ("hud-banner-elevated", "SYSTEM STATUS: ELEVATED GEOTECHNICAL ALERT", "🟡", COLOR_MODERATE),
        "HIGH RISK": ("hud-banner-high", "SYSTEM STATUS: HIGH RISK HAZARD WARNING", "🟠", COLOR_HIGH),
        "CRITICAL": ("hud-banner-critical", "SYSTEM STATUS: CRITICAL LANDSLIDE EVENT", "🔴", COLOR_CRITICAL),
        "DATA UNAVAILABLE": ("hud-banner-elevated", "SYSTEM STATUS: TELEMETRY LINK DEGRADED", "⚪", "#94A3B8")
    }

    cls, label, icon, color = configs.get(status_code, ("hud-banner-safe", f"SYSTEM STATUS: {status_code}", "ℹ️", COLOR_BLUE))

    render_html(f"""
    <div class='hud-banner {cls}'>
        <div style='display: flex; align-items: center; gap: 12px;'>
            <span style='font-size: 20px;'>{icon}</span>
            <div>
                <div style='font-size: 13px; font-weight: 700; color: {color};'>
                    {label}
                </div>
                <div style='font-size: 13px; color: #E2E8F0; margin-top: 2px;'>
                    {detail}
                </div>
            </div>
        </div>
        <div class='font-mono' style='text-align: right; font-size: 10px; color: #64748B;'>
            NDMA Guidelines 4.2<br>Automated Early Warning
        </div>
    </div>
    """)


def render_hud_kpi(title, value, subtext="", icon="📊", color_hex=COLOR_BLUE):
    """Renders a clean, modern KPI card."""
    render_html(f"""
    <div class='hud-kpi'>
        <div style='display: flex; justify-content: space-between; align-items: center;'>
            <div class='hud-kpi-title'>{title}</div>
            <span style='font-size: 15px; opacity: 0.8;'>{icon}</span>
        </div>
        <div class='hud-kpi-value' style='color: {color_hex};'>
            {value}
        </div>
        <div class='hud-kpi-sub'>
            <span>{subtext}</span>
        </div>
    </div>
    """)


def render_slope_cross_section_svg(tilt_degrees=0.35, soil_pct=45.0, risk_level="LOW"):
    """
    Renders a clean 2D SVG geotechnical slope cross-section diagram showing
    the mountain slope angle, soil shear layer, and failure slip plane.
    """
    color_map = {
        "LOW": ("#10B981", "Stable Matrix"),
        "MODERATE": ("#F59E0B", "Elevated Pore Pressure"),
        "HIGH": ("#F97316", "Active Shear Deformation"),
        "CRITICAL": ("#EF4444", "Acute Shear Plane Slip")
    }
    stroke_color, status_text = color_map.get(risk_level, ("#10B981", "Stable Matrix"))
    display_angle = min(35.0, max(5.0, 18.0 + float(tilt_degrees) * 4.0))

    svg_code = f"""
    <div style='background: #111827; border: 1px solid #1F2937; border-radius: 8px; padding: 16px;'>
        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;'>
            <div class='hud-eyebrow'>GEOTECHNICAL CROSS-SECTION • SECTOR STRATIGRAPHY</div>
            <span class='font-mono' style='font-size: 11px; color: {stroke_color};'>Displacement: {tilt_degrees:.2f}° [{status_text}]</span>
        </div>
        <svg viewBox="0 0 450 180" style="width: 100%; height: auto; overflow: visible;">
            <defs>
                <linearGradient id="slopeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="{stroke_color}" stop-opacity="0.25"/>
                    <stop offset="100%" stop-color="#0E1422" stop-opacity="0.8"/>
                </linearGradient>
            </defs>
            
            <!-- Mountain Slope Wedge -->
            <polygon points="40,160 380,160 380,40 180,{40 + int(display_angle)}" fill="url(#slopeGrad)" stroke="{stroke_color}" stroke-width="1.8"/>
            
            <!-- Roadway Cut Corridor -->
            <rect x="230" y="115" width="60" height="10" fill="#1E293B" stroke="#38BDF8" stroke-width="1.2"/>
            <text x="235" y="110" fill="#38BDF8" font-size="9" font-family="'JetBrains Mono', monospace">NH-58 ROADWAY</text>
            
            <!-- Slip Failure Plane Arc -->
            <path d="M 170,55 Q 260,105 380,145" fill="none" stroke="{stroke_color}" stroke-dasharray="5,4" stroke-width="2.2"/>
            
            <!-- Sensor Borehole Node GG-001 -->
            <circle cx="210" cy="80" r="4.5" fill="#38BDF8" stroke="#FFFFFF" stroke-width="1.2"/>
            <line x1="210" y1="80" x2="210" y2="135" stroke="#38BDF8" stroke-width="1.2" stroke-dasharray="3,3"/>
            <text x="145" y="75" fill="#F8FAFC" font-size="10" font-family="'Inter', sans-serif" font-weight="600">INCLINOMETER NODE</text>
            
            <!-- Saturation Level Indicator Bar -->
            <rect x="50" y="25" width="12" height="110" fill="#0E1422" stroke="#1F2937" rx="3"/>
            <rect x="52" y="{133 - int(soil_pct * 1.05)}" width="8" height="{int(soil_pct * 1.05)}" fill="#38BDF8" rx="2"/>
            <text x="68" y="45" fill="#94A3B8" font-size="9" font-family="'JetBrains Mono', monospace">Pore Saturation: {soil_pct:.1f}%</text>
            <text x="68" y="60" fill="#94A3B8" font-size="9" font-family="'JetBrains Mono', monospace">Slope Angle: {display_angle:.1f}°</text>
            <text x="68" y="75" fill="{stroke_color}" font-size="9" font-family="'JetBrains Mono', monospace">Factor of Safety: {max(0.85, 2.4 - (tilt_degrees * 0.45)):.2f}</text>
        </svg>
    </div>
    """
    render_html(svg_code)


def render_highway_linear_schematic(sections_df):
    """
    Renders a clean corridor schematic showing checkpoints and roadway segments.
    """
    st.markdown("<div class='hud-eyebrow'>NH-58 CORRIDOR • CHECKPOINT SCHEMATIC</div>", unsafe_allow_html=True)
    if sections_df is None or sections_df.empty:
        return
    cols = st.columns(len(sections_df))
    status_colors = {
        "OPEN": "#10B981",
        "UNDER OBSERVATION": "#F59E0B",
        "RESTRICTED": "#F97316",
        "CLOSED": "#EF4444",
        "REOPENED": "#38BDF8"
    }
    for col, (_, row) in zip(cols, sections_df.iterrows()):
        color = status_colors.get(row["status"], "#10B981")
        with col:
            col_html = (
                f"<div style='background: #111827; border: 1px solid #1F2937; border-top: 3px solid {color}; border-radius: 6px; padding: 12px 14px; margin-bottom: 12px;'>"
                f"<div style='display: flex; justify-content: space-between; font-size: 10px; color: #94A3B8; font-family: \"JetBrains Mono\", monospace;'><span>{row['section_id']}</span><span style='color: {color}; font-weight:600;'>● {row['status']}</span></div>"
                f"<div style='font-size: 13px; font-weight: 600; color: #F8FAFC; margin: 4px 0 2px 0;'>{row['name'][:18]}</div>"
                f"<div style='font-size: 11px; color: #64748B;'>Node: <b style='color:#38BDF8;'>{row['associated_station']}</b> • Risk: <span style='color:{color}; font-weight:600;'>{row['risk_level']}</span></div>"
                f"</div>"
            )
            render_html(col_html)


def get_plotly_theme():
    """Returns Plotly dark theme layout configuration."""
    return dict(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(17, 24, 39, 0.4)',
        font=dict(family='Inter, sans-serif', color='#94A3B8', size=11),
        margin=dict(l=35, r=20, t=35, b=25)
    )


def render_disclaimer():
    """Renders the required safety & prototype verification disclaimer."""
    render_html("""
    <div style='background: #111827; border-left: 3px solid #3B82F6; padding: 10px 16px; margin-top: 32px; font-size: 11px; color: #94A3B8; border-radius: 0 6px 6px 0;'>
        <b style='color:#38BDF8;'>OPERATIONAL VERIFICATION NOTICE:</b> GeoGuard is a high-altitude prototype telemetry platform. 
        Sensor readings, risk thresholds, and machine-learning failure projections require field geotechnical calibration and physical domain validation. 
        This interface does NOT actuate mechanical barriers or supersede official directives from the National Disaster Management Authority (NDMA) or Border Roads Organisation (BRO).
    </div>
    """)


# Backward-compatibility aliases
render_header = render_hud_header
render_status_banner = render_hud_banner
render_kpi_card = render_hud_kpi
