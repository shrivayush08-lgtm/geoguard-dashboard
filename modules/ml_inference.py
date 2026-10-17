"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Module: modules/ml_inference.py
Purpose: Machine Learning Landslide Failure Probability Inference Engine
=============================================================================
Provides a reference scikit-learn Random Forest Classifier pipeline
trained on slope stability failure kinematics (Mohr-Coulomb limit equilibrium
features):
- Volumetric Soil Saturation (%)
- Instantaneous Rainfall Intensity (mm/h)
- Antecedent 24h Rainfall Accumulation (mm)
- Slope Displacement Inclinometer Angle (deg)
- Angular Creep Velocity dTheta/dt (deg/h)
- Dynamic Seismic Acceleration / Ground Tremor (0/1)

Returns estimated failure probability %, confidence score, and feature importance.
"""

import numpy as np
from sklearn.ensemble import RandomForestClassifier

# Global singleton prototype model
_PROTOTYPE_MODEL = None
_FEATURE_NAMES = [
    "Soil Saturation (%)",
    "Rainfall Intensity (mm/h)",
    "Antecedent 24h Rain (mm)",
    "Slope Inclinometer (deg)",
    "Creep Rate (deg/h)",
    "Seismic Tremor (0/1)"
]

def _train_prototype_model():
    """
    Initializes and trains a prototype Random Forest Classifier on synthetic
    geotechnical limit-equilibrium samples representing Himalayan slope mechanics.
    """
    np.random.seed(42)
    n_samples = 600

    # Synthetic geotechnical feature distributions
    soil = np.random.uniform(10.0, 95.0, n_samples)
    rain_rate = np.random.uniform(0.0, 50.0, n_samples)
    acc_rain = np.random.uniform(5.0, 180.0, n_samples)
    tilt = np.random.uniform(0.1, 4.5, n_samples)
    creep = np.random.uniform(0.0, 0.8, n_samples)
    tremor = np.random.binomial(1, 0.15, n_samples)

    # Simplified physical Factor of Safety (FS) proxy:
    # Failure condition: high water pressure reduces friction, tilt indicates shear slip
    risk_index = (
        0.30 * (soil / 100.0) +
        0.20 * (rain_rate / 50.0) +
        0.15 * (acc_rain / 180.0) +
        0.25 * (tilt / 4.5) +
        0.05 * (creep / 0.8) +
        0.05 * tremor
    )
    
    # Classify into 0 (Stable/Low), 1 (Moderate), 2 (High Risk), 3 (Critical Failure)
    labels = np.zeros(n_samples, dtype=int)
    labels[risk_index >= 0.25] = 1
    labels[risk_index >= 0.50] = 2
    labels[risk_index >= 0.75] = 3

    X = np.column_stack([soil, rain_rate, acc_rain, tilt, creep, tremor])
    y = labels

    rf = RandomForestClassifier(n_estimators=50, max_depth=6, random_state=42)
    rf.fit(X, y)
    return rf

def get_ml_model():
    global _PROTOTYPE_MODEL
    if _PROTOTYPE_MODEL is None:
        _PROTOTYPE_MODEL = _train_prototype_model()
    return _PROTOTYPE_MODEL

def predict_landslide_probability(
    soil_pct=45.0,
    rain_mmh=0.0,
    acc_rain_mm=12.0,
    tilt_deg=0.3,
    tilt_rate_deg_h=0.02,
    vibration_detected=False
):
    """
    Infers landslide failure probability using Random Forest model.
    Returns:
    {
        "failure_probability_pct": float,
        "predicted_class": str,
        "model_version": str,
        "feature_importances": dict,
        "is_experimental": True
    }
    """
    model = get_ml_model()

    features = np.array([[
        float(soil_pct if soil_pct is not None else 30.0),
        float(rain_mmh if rain_mmh is not None else 0.0),
        float(acc_rain_mm if acc_rain_mm is not None else 0.0),
        float(tilt_deg if tilt_deg is not None else 0.2),
        float(tilt_rate_deg_h if tilt_rate_deg_h is not None else 0.0),
        1.0 if vibration_detected else 0.0
    ]])

    # Probability of class 2 (High) and class 3 (Critical)
    probs = model.predict_proba(features)[0]
    classes = model.classes_
    
    # Calculate composite failure probability
    p_high = probs[list(classes).index(2)] if 2 in classes else 0.0
    p_crit = probs[list(classes).index(3)] if 3 in classes else 0.0
    failure_prob = (p_high * 0.6 + p_crit * 1.0) * 100.0
    failure_prob = round(min(100.0, max(0.0, failure_prob)), 1)

    # Class label
    pred_idx = model.predict(features)[0]
    class_map = {0: "LOW RISK", 1: "MODERATE RISK", 2: "HIGH RISK", 3: "CRITICAL HAZARD"}
    pred_label = class_map.get(pred_idx, "MODERATE RISK")

    # Feature importance extraction
    importances = model.feature_importances_
    feat_dict = {
        name: round(float(imp) * 100, 1) 
        for name, imp in zip(_FEATURE_NAMES, importances)
    }

    return {
        "failure_probability_pct": failure_prob,
        "predicted_class": pred_label,
        "model_version": "RandomForest-SlopeGuard-v1.4",
        "feature_importances": feat_dict,
        "is_experimental": True,
        "note": "Prototype ML model calibrated on synthetic geotechnical failure limit states. For operational decision-making, reference the validated Rule-Based Risk Engine."
    }
