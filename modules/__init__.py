"""GeoGuard modules package."""
from modules.ui import (
    inject_custom_css,
    render_hud_header,
    render_hud_banner,
    render_hud_kpi,
    render_header,
    render_status_banner,
    render_kpi_card,
    render_slope_cross_section_svg,
    render_highway_linear_schematic,
    render_disclaimer,
    get_plotly_theme
)
from modules.risk_engine import calculate_risk, build_risk_gauge
from modules.sensor_simulator import (
    DEFAULT_STATIONS,
    generate_telemetry_tick,
    seed_historical_telemetry_if_needed
)
from modules.data_store import (
    enrich_station_telemetry,
    get_telemetry_dataframe,
    get_system_kpis,
    get_filtered_history
)
from modules.map_manager import render_risk_map
from modules.weather_service import fetch_corridor_weather
from modules.ml_inference import predict_landslide_probability
from modules.hardware_reader import SerialTelemetryGateway
from modules.report_generator import convert_df_to_csv, generate_incident_report_markdown
