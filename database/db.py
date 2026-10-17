"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Module: database/db.py
Purpose: SQLite Database Engine & Data Persistence Layer
=============================================================================
This module provides a robust, thread-safe SQLite persistence layer for:
- Monitoring Stations registry (GG-001 through GG-005)
- Telemetry History (time-series sensor readings)
- Landslide Risk Assessments logs
- Alert Center lifecycle & audit trail
- Highway Road Sections & Closure status
- Emergency Response Teams roster & dispatch records
- Persistent System Configuration settings
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
import pandas as pd

# Define database file path inside data/ directory
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "geoguard.db")

def get_connection():
    """Returns a SQLite connection with row factory configured."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes database schema and populates default reference data."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Stations Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stations (
            station_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            highway_corridor TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            elevation_m REAL DEFAULT 0.0,
            slope_aspect TEXT DEFAULT 'North-West',
            status TEXT DEFAULT 'ONLINE',
            last_seen TEXT
        )
    ''')

    # 2. Telemetry History Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telemetry_history (
            reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            station_id TEXT NOT NULL,
            soil_adc INTEGER,
            soil_moisture_pct REAL,
            temperature_c REAL DEFAULT 15.0,
            rain_adc INTEGER,
            rainfall_intensity_mmh REAL,
            rain_acc_24h_mm REAL,
            tilt_degrees REAL,
            tilt_rate_deg_h REAL,
            vibration_detected INTEGER DEFAULT 0,
            vibration_intensity_g REAL DEFAULT 0.0,
            battery_pct REAL DEFAULT 100.0,
            is_simulated INTEGER DEFAULT 1,
            FOREIGN KEY (station_id) REFERENCES stations (station_id)
        )
    ''')

    # Migration: Add temperature_c if legacy database table already exists
    try:
        cursor.execute("ALTER TABLE telemetry_history ADD COLUMN temperature_c REAL DEFAULT 15.0")
    except sqlite3.OperationalError:
        pass

    # Create index for fast time-series queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_telemetry_stn_time ON telemetry_history (station_id, timestamp)')

    # 3. Risk Assessments Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_assessments (
            assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            station_id TEXT NOT NULL,
            risk_score REAL NOT NULL,
            risk_level TEXT NOT NULL,
            soil_factor_score REAL DEFAULT 0.0,
            rain_factor_score REAL DEFAULT 0.0,
            tilt_factor_score REAL DEFAULT 0.0,
            vib_factor_score REAL DEFAULT 0.0,
            contributing_factors TEXT,
            recommended_action TEXT,
            assessment_mode TEXT DEFAULT 'RULE_BASED',
            FOREIGN KEY (station_id) REFERENCES stations (station_id)
        )
    ''')

    # 4. Alerts Lifecycle Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            station_id TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            risk_score REAL NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'NEW',
            acknowledged_by TEXT,
            ack_timestamp TEXT,
            resolved_by TEXT,
            res_timestamp TEXT,
            assigned_team TEXT,
            operator_notes TEXT,
            is_test INTEGER DEFAULT 0,
            FOREIGN KEY (station_id) REFERENCES stations (station_id)
        )
    ''')

    # 5. Highway Road Sections Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS road_sections (
            section_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            corridor TEXT NOT NULL,
            associated_station TEXT NOT NULL,
            status TEXT DEFAULT 'OPEN',
            risk_level TEXT DEFAULT 'LOW',
            start_lat REAL NOT NULL,
            start_lon REAL NOT NULL,
            end_lat REAL NOT NULL,
            end_lon REAL NOT NULL,
            condition_notes TEXT,
            last_updated TEXT,
            updated_by TEXT DEFAULT 'System'
        )
    ''')

    # 6. Emergency Response Teams Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS response_teams (
            team_id TEXT PRIMARY KEY,
            team_name TEXT NOT NULL,
            authority TEXT NOT NULL,
            base_location TEXT NOT NULL,
            contact_channel TEXT NOT NULL,
            status TEXT DEFAULT 'STANDBY',
            current_assignment TEXT,
            last_dispatch_time TEXT
        )
    ''')

    # 7. System Configuration Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            config_key TEXT PRIMARY KEY,
            config_value TEXT NOT NULL,
            description TEXT
        )
    ''')

    # Check and seed default reference stations (GG-001 to GG-005)
    cursor.execute("SELECT COUNT(*) FROM stations")
    if cursor.fetchone()[0] == 0:
        default_stations = [
            ("GG-001", "NH-58 Mountain Pass", "NH-58 km 42 (Byasi Gorge)", 30.1234, 78.4321, 620.0, "North-West Slope (42°)", "ONLINE", datetime.utcnow().isoformat()),
            ("GG-002", "Valley Gorge Sector A", "NH-58 km 58 (Kaudiyala)", 30.1567, 78.4890, 710.0, "South Escarpment (38°)", "ONLINE", datetime.utcnow().isoformat()),
            ("GG-003", "Ridge Tunnel Link", "NH-58 km 71 (Devprayag Confluence)", 30.2012, 78.5123, 830.0, "East Ridge Cleave (45°)", "ONLINE", datetime.utcnow().isoformat()),
            ("GG-004", "Highland Slope North", "NH-58 km 89 (Kirtinagar Bluffs)", 30.2456, 78.5678, 950.0, "North Bluff Wall (50°)", "ONLINE", datetime.utcnow().isoformat()),
            ("GG-005", "Alaknanda Escarpment", "NH-58 km 105 (Srinagar Approach)", 30.2810, 78.6140, 1040.0, "Valley Terrace Cut (35°)", "ONLINE", datetime.utcnow().isoformat()),
        ]
        cursor.executemany("INSERT INTO stations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", default_stations)

    # Check and seed default road sections
    cursor.execute("SELECT COUNT(*) FROM road_sections")
    if cursor.fetchone()[0] == 0:
        default_sections = [
            ("SEC-01", "Shivpuri - Byasi Mountain Corridor", "NH-58 km 35-48", "GG-001", "OPEN", "LOW", 30.1050, 78.3950, 30.1380, 78.4550, "Clear highway conditions, optimal dry friction.", datetime.utcnow().isoformat(), "Highway Inspector"),
            ("SEC-02", "Byasi - Kaudiyala Gorge Run", "NH-58 km 48-62", "GG-002", "OPEN", "LOW", 30.1380, 78.4550, 30.1750, 78.4980, "Active drainage channels clear; debris traps nominal.", datetime.utcnow().isoformat(), "Highway Inspector"),
            ("SEC-03", "Kaudiyala - Devprayag Bridge Cut", "NH-58 km 62-78", "GG-003", "OPEN", "LOW", 30.1750, 78.4980, 30.2200, 78.5350, "Bridge foundation telemetry secure; slope nets intact.", datetime.utcnow().isoformat(), "Highway Inspector"),
            ("SEC-04", "Devprayag - Kirtinagar Ridge", "NH-58 km 78-95", "GG-004", "OPEN", "LOW", 30.2200, 78.5350, 30.2650, 78.5900, "Minor loose gravel clearing completed.", datetime.utcnow().isoformat(), "Highway Inspector"),
            ("SEC-05", "Kirtinagar - Srinagar Riverway", "NH-58 km 95-110", "GG-005", "OPEN", "LOW", 30.2650, 78.5900, 30.2950, 78.6300, "Two-lane traffic moving smoothly.", datetime.utcnow().isoformat(), "Highway Inspector")
        ]
        cursor.executemany("INSERT INTO road_sections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", default_sections)

    # Check and seed default response teams
    cursor.execute("SELECT COUNT(*) FROM response_teams")
    if cursor.fetchone()[0] == 0:
        default_teams = [
            ("TEAM-NDRF-08", "NDRF 8th Battalion QRT", "National Disaster Response Force", "Rishikesh Operational Base", "VHF Ch 14 / Secure Satcom", "STANDBY", "None", datetime.utcnow().isoformat()),
            ("TEAM-SDRF-UK", "SDRF High-Altitude Rescue Team", "State Disaster Response Force", "Srinagar Garhwal Depot", "VHF Ch 09 / Hotline 1070", "STANDBY", "None", datetime.utcnow().isoformat()),
            ("TEAM-BRO-753", "BRO 753 Border Roads Task Force", "Border Roads Organisation", "Devprayag Heavy Equipment Base", "Radio Net B / Direct Line", "STANDBY", "None", datetime.utcnow().isoformat()),
            ("TEAM-HP-SECT4", "NH-58 Highway Patrol Unit 4", "Uttarakhand Highway Police", "Byasi Checkpost", "Police Wireless Ch 3", "STANDBY", "None", datetime.utcnow().isoformat()),
            ("TEAM-EMS-DIST", "Garhwal Emergency Medical Unit", "District Health Authority", "Srinagar Base Hospital", "Emergency Dial 108", "STANDBY", "None", datetime.utcnow().isoformat()),
        ]
        cursor.executemany("INSERT INTO response_teams VALUES (?, ?, ?, ?, ?, ?, ?, ?)", default_teams)

    # Check and seed default configuration settings
    cursor.execute("SELECT COUNT(*) FROM system_config")
    if cursor.fetchone()[0] == 0:
        default_config = [
            ("risk_threshold_critical", "75", "Risk score threshold for CRITICAL emergency state"),
            ("risk_threshold_high", "50", "Risk score threshold for HIGH risk state"),
            ("risk_threshold_moderate", "25", "Risk score threshold for MODERATE warning state"),
            ("soil_warning_adc", "2800", "Soil moisture ADC warning threshold"),
            ("rain_warning_adc", "3200", "Rain sensor ADC intense precipitation threshold"),
            ("tilt_warning_degrees", "1.5", "Abnormal slope tilt change warning threshold (degrees)"),
            ("alert_cooldown_minutes", "10", "Minimum time between identical alerts per station"),
            ("telemetry_freshness_seconds", "30", "Timeout before station is marked DELAYED or OFFLINE"),
            ("weather_provider", "open-meteo", "Weather data provider (open-meteo or openweathermap)"),
            ("weather_api_key", "", "API key for commercial weather services if configured"),
            ("notification_webhook", "", "Webhook URL for incident dispatch notifications"),
            ("simulation_mode", "1", "Flag indicating whether simulated telemetry generation is active")
        ]
        cursor.executemany("INSERT INTO system_config VALUES (?, ?, ?)", default_config)

    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Data Access Functions
# ---------------------------------------------------------------------------

def get_stations():
    """Returns a pandas DataFrame of all monitoring stations."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM stations ORDER BY station_id ASC", conn)
    conn.close()
    return df

def update_station_status(station_id, status):
    """Updates station connection status and last_seen timestamp."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE stations SET status = ?, last_seen = ? WHERE station_id = ?",
                   (status, datetime.utcnow().isoformat(), station_id))
    conn.commit()
    conn.close()

def log_telemetry(reading_dict):
    """Logs a single telemetry reading record."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO telemetry_history (
            timestamp, station_id, soil_adc, soil_moisture_pct,
            temperature_c, rain_adc, rainfall_intensity_mmh, rain_acc_24h_mm,
            tilt_degrees, tilt_rate_deg_h, vibration_detected,
            vibration_intensity_g, battery_pct, is_simulated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        reading_dict.get("timestamp", datetime.utcnow().isoformat()),
        reading_dict["station_id"],
        reading_dict.get("soil_adc"),
        reading_dict.get("soil_moisture_pct"),
        reading_dict.get("temperature_c", 14.5),
        reading_dict.get("rain_adc"),
        reading_dict.get("rainfall_intensity_mmh"),
        reading_dict.get("rain_acc_24h_mm"),
        reading_dict.get("tilt_degrees"),
        reading_dict.get("tilt_rate_deg_h", 0.0),
        1 if reading_dict.get("vibration_detected") else 0,
        reading_dict.get("vibration_intensity_g", 0.0),
        reading_dict.get("battery_pct", 100.0),
        1 if reading_dict.get("is_simulated", True) else 0
    ))
    conn.commit()
    conn.close()

def log_risk_assessment(assessment_dict):
    """Logs an assessment calculation from the risk engine."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO risk_assessments (
            timestamp, station_id, risk_score, risk_level,
            soil_factor_score, rain_factor_score, tilt_factor_score, vib_factor_score,
            contributing_factors, recommended_action, assessment_mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        assessment_dict.get("timestamp", datetime.utcnow().isoformat()),
        assessment_dict["station_id"],
        assessment_dict["risk_score"],
        assessment_dict["risk_level"],
        assessment_dict.get("soil_factor_score", 0.0),
        assessment_dict.get("rain_factor_score", 0.0),
        assessment_dict.get("tilt_factor_score", 0.0),
        assessment_dict.get("vib_factor_score", 0.0),
        json.dumps(assessment_dict.get("contributing_factors", [])),
        assessment_dict.get("recommended_action", ""),
        assessment_dict.get("assessment_mode", "RULE_BASED")
    ))
    conn.commit()
    conn.close()

def log_alert(station_id, risk_level, risk_score, reason, is_test=0, cooldown_minutes=10):
    """
    Logs an alert record if not within the cooldown period for the same station & level.
    Returns (alert_id, created_boolean).
    """
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.utcnow().isoformat()

    # Cooldown check: prevent rapid duplicate alerts unless test alert
    if not is_test:
        cutoff = (datetime.utcnow() - timedelta(minutes=cooldown_minutes)).isoformat()
        cursor.execute('''
            SELECT alert_id FROM alerts
            WHERE station_id = ? AND risk_level = ? AND timestamp >= ? AND status != 'RESOLVED'
            ORDER BY alert_id DESC LIMIT 1
        ''', (station_id, risk_level, cutoff))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return existing[0], False

    cursor.execute('''
        INSERT INTO alerts (
            timestamp, station_id, risk_level, risk_score, reason,
            status, is_test
        ) VALUES (?, ?, ?, ?, ?, 'NEW', ?)
    ''', (now_str, station_id, risk_level, risk_score, reason, is_test))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id, True

def get_alerts(status_filter=None, limit=100):
    """Retrieves alerts with optional status filtering."""
    conn = get_connection()
    query = "SELECT * FROM alerts"
    params = []
    if status_filter and status_filter != "ALL":
        query += " WHERE status = ?"
        params.append(status_filter)
    query += " ORDER BY alert_id DESC LIMIT ?"
    params.append(limit)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def update_alert_status(alert_id, new_status, operator_name="Authorized Operator", notes="", assigned_team=None):
    """Updates the status and audit trail of an alert."""
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.utcnow().isoformat()

    if new_status == "ACKNOWLEDGED":
        cursor.execute('''
            UPDATE alerts SET status = ?, acknowledged_by = ?, ack_timestamp = ?, operator_notes = ?
            WHERE alert_id = ?
        ''', (new_status, operator_name, now_str, notes, alert_id))
    elif new_status == "RESOLVED" or new_status == "FALSE ALARM":
        cursor.execute('''
            UPDATE alerts SET status = ?, resolved_by = ?, res_timestamp = ?, operator_notes = ?
            WHERE alert_id = ?
        ''', (new_status, operator_name, now_str, notes, alert_id))
    else:
        cursor.execute('''
            UPDATE alerts SET status = ?, operator_notes = ?, assigned_team = COALESCE(?, assigned_team)
            WHERE alert_id = ?
        ''', (new_status, notes, assigned_team, alert_id))

    conn.commit()
    conn.close()

def get_road_sections():
    """Returns all highway road sections."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM road_sections ORDER BY section_id ASC", conn)
    conn.close()
    return df

def update_road_section(section_id, new_status, new_risk, notes, updated_by="Authorized Operator"):
    """Updates road section status, risk level, and notes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE road_sections
        SET status = ?, risk_level = ?, condition_notes = ?, last_updated = ?, updated_by = ?
        WHERE section_id = ?
    ''', (new_status, new_risk, notes, datetime.utcnow().isoformat(), updated_by, section_id))
    conn.commit()
    conn.close()

def get_response_teams():
    """Returns emergency response teams roster."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM response_teams ORDER BY team_id ASC", conn)
    conn.close()
    return df

def update_response_team(team_id, status, assignment=None):
    """Updates team status and current assignment."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE response_teams
        SET status = ?, current_assignment = ?, last_dispatch_time = ?
        WHERE team_id = ?
    ''', (status, assignment, datetime.utcnow().isoformat(), team_id))
    conn.commit()
    conn.close()

def get_config(key, default=""):
    """Reads a configuration parameter from system_config."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT config_value FROM system_config WHERE config_key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def set_config(key, value, description=""):
    """Saves or updates a configuration parameter."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO system_config (config_key, config_value, description)
        VALUES (?, ?, ?)
        ON CONFLICT(config_key) DO UPDATE SET config_value = excluded.config_value
    ''', (key, str(value), description))
    conn.commit()
    conn.close()

def get_recent_telemetry(station_id=None, limit=200):
    """Retrieves recent telemetry history with optional station filter."""
    conn = get_connection()
    if station_id:
        query = "SELECT * FROM telemetry_history WHERE station_id = ? ORDER BY timestamp DESC LIMIT ?"
        df = pd.read_sql_query(query, conn, params=[station_id, limit])
    else:
        query = "SELECT * FROM telemetry_history ORDER BY timestamp DESC LIMIT ?"
        df = pd.read_sql_query(query, conn, params=[limit])
    conn.close()
    return df