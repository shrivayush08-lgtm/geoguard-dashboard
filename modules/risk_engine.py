"""
=============================================================================
GEOGUARD AI — SATELLITE-POWERED TERRAIN RISK & EARLY WARNING PLATFORM
Module: modules/risk_engine.py
Purpose: 4-Sensor Geotechnical Landslide Risk Detection & Normalization Engine
=============================================================================
WHERE THIS CODE IS USED:
- pages/live_sensor.py: Real-time 4-sensor telemetry processing & gauge rendering
- modules/data_store.py: Station-fleet enrichment & corridor anomaly evaluation
- app.py: Mission-critical safety trigger evaluation

THE 4 SENSORS EVALUATED:
1. Soil Moisture Sensor: Identifies volumetric water content (% VWC) & saturation
2. Temperature Sensor: Measures ambient/soil temperature (°C) & freeze-thaw cycles
3. Slope/Tilt Sensor: Detects angular displacement (°) indicating ground shear slip
4. Vibration Sensor: Detects peak ground acceleration (g) and micro-seismic activity

NORMALIZATION & RISK FORMULA:
Raw sensor readings with different physical units are converted into normalized
risk scores (0–100) using configurable domain thresholds.
Initially, equal weighting (0.25 each) is applied:
Overall Risk Score = (Soil Moisture Risk + Temperature Risk + Slope Risk + Vibration Risk) / 4

RISK CLASSIFICATION CATEGORIES:
- 0–25%: Low Risk ("Conditions appear normal.")
- 26–50%: Moderate Risk ("Monitor sensor readings.")
- 51–75%: High Risk ("Elevated landslide risk; issue a warning.")
- 76–100%: Critical Risk ("Potentially dangerous conditions; issue an urgent alert.")
"""

import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# SECTION 1: Individual Sensor Normalization Functions (0 to 100 Scale)
# ---------------------------------------------------------------------------

def normalize_soil_moisture_risk(soil_pct, soil_adc=None):
    """
    Normalizes soil moisture into a 0–100 risk score.
    - < 35% VWC: Normal, dry to healthy moisture (0–25 pts)
    - 35% – 55% VWC: Moderate dampness, elevated pore pressure (26–50 pts)
    - 55% – 75% VWC: High saturation, approaching soil liquefaction (51–75 pts)
    - > 75% VWC: Critical saturation, acute shear strength loss (76–100 pts)
    """
    if soil_pct is None and soil_adc is not None:
        # Calibrate 12-bit ADC (1100 dry to 3700 saturated)
        soil_pct = max(0.0, min(100.0, ((soil_adc - 1100) / 2600.0) * 100.0))
    if soil_pct is None:
        return None

    val = float(soil_pct)
    if val <= 35.0:
        score = (val / 35.0) * 25.0
    elif val <= 55.0:
        score = 25.0 + ((val - 35.0) / 20.0) * 25.0
    elif val <= 75.0:
        score = 50.0 + ((val - 55.0) / 20.0) * 25.0
    else:
        score = 75.0 + ((min(100.0, val) - 75.0) / 25.0) * 25.0
    return round(max(0.0, min(100.0, score)), 1)


def normalize_temperature_risk(temp_c):
    """
    Normalizes temperature into a 0–100 risk score.
    In mountain geotechnical engineering, freeze-thaw cycles between -4°C and +4°C
    cause water in rock fissures to expand (+9% ice volume) and thaw, driving
    rapid joint destabilization and spring debris flows.
    - Stable comfortable temps (10°C to 22°C): Low Risk (0–25 pts)
    - Warm thawing temps (5°C to 9°C or 23°C to 28°C): Moderate Risk (26–50 pts)
    - Freeze-thaw fluctuation zone (-4°C to +4°C): High to Critical (51–85 pts)
    - Rapid glacial/permafrost melt (> 28°C): High Risk (51–75 pts)
    """
    if temp_c is None:
        return None

    val = float(temp_c)
    # Peak hazard: Freeze-thaw transition zone centered near 0°C
    if -4.0 <= val <= 4.0:
        # Distance from 0°C: closer to 0°C = highest ice/water phase change stress
        proximity_to_zero = 4.0 - abs(val)
        score = 55.0 + (proximity_to_zero / 4.0) * 25.0  # 55 to 80 pts
    elif val < -4.0:
        # Deep frost wedging
        score = min(75.0, 45.0 + abs(val + 4.0) * 2.5)
    elif val > 28.0:
        # Rapid thermal snow/permafrost melting
        score = min(80.0, 45.0 + (val - 28.0) * 4.0)
    elif 4.0 < val <= 9.0 or 23.0 < val <= 28.0:
        score = 30.0 + (abs(val - 16.0) / 12.0) * 20.0
    else:
        # Baseline mild temperature (9°C to 23°C)
        score = max(5.0, (abs(val - 16.0) / 7.0) * 20.0)
    return round(max(0.0, min(100.0, score)), 1)


def normalize_slope_tilt_risk(tilt_deg, tilt_rate_deg_h=0.0):
    """
    Normalizes slope inclinometer angle into a 0–100 risk score.
    - < 0.5°: Normal slope angle (0–25 pts)
    - 0.5° – 1.2°: Moderate creep movement (26–50 pts)
    - 1.2° – 2.0°: Elevated shear deformation (51–75 pts)
    - > 2.0°: Critical structural failure / slip plane rupture (76–100 pts)
    """
    if tilt_deg is None:
        return None

    val = abs(float(tilt_deg))
    if val <= 0.5:
        base = (val / 0.5) * 25.0
    elif val <= 1.2:
        base = 25.0 + ((val - 0.5) / 0.7) * 25.0
    elif val <= 2.0:
        base = 50.0 + ((val - 1.2) / 0.8) * 25.0
    else:
        base = 75.0 + ((min(4.0, val) - 2.0) / 2.0) * 25.0

    # Dynamic angular acceleration factor
    rate = abs(float(tilt_rate_deg_h)) if tilt_rate_deg_h else 0.0
    rate_boost = min(20.0, rate * 35.0)
    return round(min(100.0, base + rate_boost), 1)


def normalize_vibration_risk(vib_g, vib_detected=False):
    """
    Normalizes ground vibration into a 0–100 risk score.
    - < 0.08g: Normal background microseismic noise (0–25 pts)
    - 0.08g – 0.25g: Moderate tremor / heavy logistics rumble (26–50 pts)
    - 0.25g – 0.50g: High seismic shock / rockfall impact (51–75 pts)
    - > 0.50g or persistent tremor: Critical ground disruption (76–100 pts)
    """
    g_val = abs(float(vib_g)) if vib_g is not None else 0.0
    if g_val <= 0.08 and not vib_detected:
        base = (g_val / 0.08) * 25.0
    elif g_val <= 0.25:
        base = 25.0 + ((g_val - 0.08) / 0.17) * 25.0
    elif g_val <= 0.50:
        base = 50.0 + ((g_val - 0.25) / 0.25) * 25.0
    else:
        base = 75.0 + ((min(2.5, g_val) - 0.50) / 2.0) * 25.0

    if vib_detected and base < 35.0:
        base = 35.0
    return round(min(100.0, base), 1)

# ---------------------------------------------------------------------------
# SECTION 2: 4-Sensor Automatic Landslide Risk Engine
# ---------------------------------------------------------------------------

def calculate_four_sensor_risk(
    soil_moisture_pct=None,
    temperature_c=None,
    tilt_degrees=None,
    vibration_g=None,
    vibration_detected=False,
    tilt_rate_deg_h=0.0,
    weights=None,
    thresholds=None
):
    """
    Calculates overall landslide risk from the 4 primary IoT sensors:
    1. Soil Moisture (% VWC)
    2. Temperature (°C)
    3. Slope Tilt (Degrees)
    4. Vibration (g)

    Formula:
    Overall Risk Score = (Soil Moisture Risk + Temperature Risk + Slope Risk + Vibration Risk) / 4
    (Using configurable weights, default: 0.25 each)
    """
    # 1. Configurable Sensor Weights (Equal 25% distribution by default)
    if weights is None:
        weights = {
            "soil": 0.25,
            "temperature": 0.25,
            "slope": 0.25,
            "vibration": 0.25
        }

    # 2. Configurable Risk Classification Thresholds
    if thresholds is None:
        thresholds = {
            "low_max": 25.0,
            "moderate_max": 50.0,
            "high_max": 75.0,
            "critical_min": 76.0
        }

    # 3. Individual Normalized Scores
    soil_risk = normalize_soil_moisture_risk(soil_moisture_pct)
    temp_risk = normalize_temperature_risk(temperature_c)
    slope_risk = normalize_slope_tilt_risk(tilt_degrees, tilt_rate_deg_h)
    vib_risk = normalize_vibration_risk(vibration_g, vibration_detected)

    # 4. Sensor Availability & Data Quality Validation
    sensor_scores = {
        "Soil Moisture": soil_risk,
        "Temperature": temp_risk,
        "Slope/Tilt": slope_risk,
        "Vibration": vib_risk
    }
    missing = [name for name, score in sensor_scores.items() if score is None]

    if len(missing) == 0:
        data_quality = "OPTIMAL"
        is_complete = True
    elif len(missing) <= 2:
        data_quality = "DEGRADED"
        is_complete = False
    else:
        data_quality = "INSUFFICIENT"
        is_complete = False

    # 5. Calculate Overall Weighted Risk Score
    active_weights_sum = sum(
        weights[k] for k, v in [
            ("soil", soil_risk),
            ("temperature", temp_risk),
            ("slope", slope_risk),
            ("vibration", vib_risk)
        ] if v is not None
    )

    if active_weights_sum > 0:
        weighted_sum = (
            (soil_risk or 0.0) * weights["soil"] +
            (temp_risk or 0.0) * weights["temperature"] +
            (slope_risk or 0.0) * weights["slope"] +
            (vib_risk or 0.0) * weights["vibration"]
        )
        overall_score = round(min(100.0, max(0.0, weighted_sum / active_weights_sum)), 1)
    else:
        overall_score = 0.0

    # 6. Risk Level Classification & Clear Domain Status Messages
    if overall_score <= thresholds["low_max"]:
        risk_level = "LOW"
        status_color = "#10B981"  # Emerald green
        status_message = "Low Risk: Conditions appear normal."
    elif overall_score <= thresholds["moderate_max"]:
        risk_level = "MODERATE"
        status_color = "#F59E0B"  # Amber
        status_message = "Moderate Risk: Monitor sensor readings."
    elif overall_score <= thresholds["high_max"]:
        risk_level = "HIGH"
        status_color = "#F97316"  # Orange
        status_message = "High Risk: Elevated landslide risk; issue a warning."
    else:
        risk_level = "CRITICAL"
        status_color = "#EF4444"  # Crimson red
        status_message = "Critical Risk: Potentially dangerous conditions; issue an urgent alert."

    # If data is completely missing, do not falsely claim low risk
    if not is_complete and risk_level == "LOW" and len(missing) >= 3:
        risk_level = "UNKNOWN"
        status_color = "#94A3B8"
        status_message = f"Sensor Disconnection: Missing {', '.join(missing)}. Risk cannot be certified."

    # 7. Immediate Warnings for Sudden Slope Movement or Abnormal Tremor
    immediate_warning = False
    immediate_triggers = []
    
    if tilt_degrees is not None and abs(float(tilt_degrees)) >= 1.5:
        immediate_warning = True
        immediate_triggers.append(f"Slope Inclinometer acute shear slip ({float(tilt_degrees):.2f}°)")
    if tilt_rate_deg_h is not None and abs(float(tilt_rate_deg_h)) >= 0.35:
        immediate_warning = True
        immediate_triggers.append(f"Rapid slope displacement rate (+{float(tilt_rate_deg_h):.2f}°/h)")
    if vibration_detected or (vibration_g is not None and float(vibration_g) >= 0.35):
        immediate_warning = True
        immediate_triggers.append(f"Abnormal ground vibration event ({float(vibration_g or 0.0):.2f}g shock)")

    return {
        "overall_risk_score": overall_score,
        "risk_level": risk_level,
        "status_color": status_color,
        "status_message": status_message,
        "sensor_scores": {
            "soil": soil_risk or 0.0,
            "temperature": temp_risk or 0.0,
            "slope": slope_risk or 0.0,
            "vibration": vib_risk or 0.0
        },
        "weights": weights,
        "data_quality": data_quality,
        "is_complete": is_complete,
        "missing_sensors": missing,
        "immediate_warning": immediate_warning,
        "immediate_triggers": immediate_triggers
    }

# ---------------------------------------------------------------------------
# SECTION 3: Plotly Circular Risk Gauge Generator
# ---------------------------------------------------------------------------

def build_four_sensor_risk_gauge(risk_score, risk_level, status_color, height=270):
    """
    Renders an animated, highly legible circular gauge for the Overall Landslide Risk Score.
    Clean, modern, human-designed climate-tech styling (no sci-fi clutter).
    """
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=risk_score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={
            'text': f"<b>LANDSLIDE RISK INDEX</b><br><span style='font-size:12px; font-weight:600; color:{status_color};'>● {risk_level} RISK LEVEL</span>",
            'font': {'size': 14, 'family': 'Inter, sans-serif', 'color': '#F1F5F9'}
        },
        number={'suffix': "%", 'font': {'size': 34, 'family': 'JetBrains Mono, monospace', 'color': status_color}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#334155", 'tickfont': {'color': '#94A3B8', 'size': 10}},
            'bar': {'color': status_color, 'thickness': 0.28},
            'bgcolor': "rgba(15, 23, 42, 0.9)",
            'borderwidth': 1,
            'bordercolor': "#334155",
            'steps': [
                {'range': [0, 25], 'color': 'rgba(16, 185, 129, 0.15)'},
                {'range': [25, 50], 'color': 'rgba(245, 158, 11, 0.15)'},
                {'range': [50, 75], 'color': 'rgba(249, 115, 22, 0.20)'},
                {'range': [75, 100], 'color': 'rgba(239, 68, 68, 0.25)'}
            ],
            'threshold': {
                'line': {'color': "#EF4444", 'width': 3},
                'thickness': 0.85,
                'value': 75.0
            }
        }
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=50, b=10),
        height=height
    )
    return fig

# ---------------------------------------------------------------------------
# SECTION 4: Backward Compatibility Wrappers
# ---------------------------------------------------------------------------

def calculate_risk(
    soil_adc=None,
    soil_moisture_pct=None,
    rain_adc=None,
    rainfall_intensity_mmh=None,
    rain_acc_24h_mm=0.0,
    tilt_degrees=None,
    tilt_rate_deg_h=0.0,
    vibration_detected=False,
    vibration_intensity_g=0.0,
    temperature_c=14.5,
    weights=None,
    thresholds=None
):
    """Backward compatible wrapper calling the unified risk assessment function."""
    res = calculate_four_sensor_risk(
        soil_moisture_pct=soil_moisture_pct,
        temperature_c=temperature_c,
        tilt_degrees=tilt_degrees,
        vibration_g=vibration_intensity_g,
        vibration_detected=vibration_detected,
        tilt_rate_deg_h=tilt_rate_deg_h
    )

    factors = []
    if res["sensor_scores"]["soil"] > 50:
        factors.append(f"Elevated soil saturation ({soil_moisture_pct or 0:.1f}% VWC)")
    if res["sensor_scores"]["temperature"] > 50:
        factors.append(f"Thermal freeze-thaw instability ({temperature_c:.1f}°C)")
    if res["sensor_scores"]["slope"] > 50:
        factors.append(f"Active slope displacement ({tilt_degrees or 0:.2f}°)")
    if res["sensor_scores"]["vibration"] > 50:
        factors.append("Substrate vibration / tremor active")

    return {
        "risk_score": res["overall_risk_score"],
        "risk_level": res["risk_level"],
        "status_color": res["status_color"],
        "factors": factors if factors else ["All 4 monitored sensors within baseline limits."],
        "breakdown": res["sensor_scores"],
        "recommended_action": res["status_message"],
        "data_quality": res["data_quality"],
        "is_complete": res["is_complete"]
    }

build_risk_gauge = build_four_sensor_risk_gauge