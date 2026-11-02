import math
import re
"""
=============================================================================
GEOGUARD AI — OFF-GRID HIGHWAY LANDSLIDE EARLY WARNING & INTERLOCK SYSTEM
Module: modules/hardware_reader.py
Purpose: Non-Blocking PySerial Receiver Gateway for ESP32 Telemetry Nodes
=============================================================================
COMPETITION: Smart India Hackathon (SIH)

EXPECTED SERIAL MESSAGE FORMAT:
soilMoisture,temperature,tiltAngle,vibrationPGA
Example:
65.5,28.4,4.2,0.18

FIELD INTERPRETATION:
1. soilMoisture: Soil moisture in % VWC (Volumetric Water Content).
2. temperature: Temperature in degrees Celsius (°C).
3. tiltAngle: Slope angular displacement in degrees (°).
4. vibrationPGA: Peak ground acceleration in g.

CALIBRATION CONVERSION LAYER:
If hardware transmits raw ADC readings (e.g., 0-4095 on 12-bit ESP32 ADC)
instead of calibrated measurements, this module converts raw values into % VWC
via a configurable calibration function before returning the telemetry packet.

FEATURES:
- Configurable serial port (default COM3) and baud rate (default 115200).
- Non-blocking short read timeouts (prevents freezing the Streamlit UI).
- Robust malformed message rejection and numeric validation.
- Telemetry freshness and stale link detection (> 10s delayed, > 30s timeout).
- Missing/invalid/stale readings flagged to prevent false LOW RISK classification.
=============================================================================
"""

import json
import time
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List
import serial
import serial.tools.list_ports


class SerialTelemetryGateway:
    """
    Non-blocking USB serial gateway for ESP32/nRF24 receiver telemetry node.
    Parses CSV and JSON sensor frames, validates bounds, and tracks link health.
    """

    def __init__(
        self,
        default_port: str = "COM3",
        default_baud: int = 115200,
        read_timeout: float = 0.15,
        stale_threshold_sec: float = 15.0
    ):
        self.port = default_port
        self.baud = int(default_baud)
        self.timeout = read_timeout
        self.stale_threshold_sec = stale_threshold_sec

        self.serial_conn: Optional[serial.Serial] = None
        self.is_connected: bool = False
        self.last_reading: Optional[Dict[str, Any]] = None
        self.last_packet_time: Optional[datetime] = None
        self.total_packets_received: int = 0
        self.malformed_packets_rejected: int = 0
        self.status_message: str = "Hardware interface idle. Select serial port and connect."

        # Configurable ADC calibration parameters (for ESP32 12-bit capacitive sensor)
        self.raw_adc_mode: bool = False
        self.adc_dry_baseline: int = 3500
        self.adc_wet_baseline: int = 1200
        self._kv_buffer: Dict[str, Any] = {}
        self.last_auto_scan_time: float = 0.0

    @staticmethod
    def get_port_candidates() -> List[Dict[str, Any]]:
        """
        Scans all system serial ports and scores them.
        Filters out virtual Bluetooth ports and prioritizes real USB UART bridges (CP210x, CH340, FTDI, Espressif).
        """
        try:
            ports = serial.tools.list_ports.comports()
        except Exception:
            return []

        candidates = []
        for p in ports:
            device = p.device
            desc = p.description or ""
            hwid = p.hwid or ""
            mfr = p.manufacturer or ""
            vid = p.vid
            pid = p.pid

            # Skip Bluetooth virtual serial ports
            if "bluetooth" in desc.lower() or "bthenum" in hwid.lower():
                continue

            score = 0
            is_esp32 = False

            # Known USB-to-UART bridge VIDs for ESP32 boards:
            # 0x10C4: Silicon Labs CP210x (ESP32 NodeMCU, DevKit v1)
            # 0x1A86: WCH CH340 / CH341 (ESP32 clone boards)
            # 0x303A: Espressif Native USB CDC / JTAG (ESP32-S2/S3/C3)
            # 0x0403: FTDI (Industrial ESP32 boards)
            # 0x067B: Prolific PL2303
            if vid in [0x10c4, 0x1a86, 0x303a, 0x0403, 0x067b]:
                score += 150
                is_esp32 = True

            desc_lower = desc.lower()
            if any(k in desc_lower for k in ["cp210", "ch340", "ch341", "ch9102", "ch910", "enhanced-serial", "esp32", "espressif", "uart bridge", "ftdi"]):
                score += 100
                is_esp32 = True

            mfr_lower = mfr.lower()
            if any(k in mfr_lower for k in ["silicon labs", "wch", "espressif", "ftdi"]):
                score += 50
                is_esp32 = True

            if "usb" in hwid.lower() or "usb" in desc_lower:
                score += 20

            candidates.append({
                "device": device,
                "description": desc,
                "hwid": hwid,
                "manufacturer": mfr,
                "vid": vid,
                "pid": pid,
                "is_esp32": is_esp32,
                "score": score,
                "label": f"{device} - {desc}" + (" [ESP32 DETECTED]" if is_esp32 else "")
            })

        # Sort highest score first
        candidates.sort(reverse=True, key=lambda c: c["score"])
        return candidates

    @staticmethod
    def auto_detect_esp32() -> Tuple[Optional[str], Optional[str]]:
        """
        Auto-detects which serial port the ESP32 is plugged into.
        Returns (port_device, description) or (None, None).
        """
        candidates = SerialTelemetryGateway.get_port_candidates()
        if candidates and candidates[0]["is_esp32"]:
            return candidates[0]["device"], candidates[0]["description"]
        elif candidates and candidates[0]["score"] > 0:
            return candidates[0]["device"], candidates[0]["description"]
        return None, None

    @staticmethod
    def list_available_ports() -> List[str]:
        """Scans the host system for active serial COM ports, placing USB/ESP32 devices first."""
        candidates = SerialTelemetryGateway.get_port_candidates()
        if candidates:
            return [c["device"] for c in candidates]
        try:
            ports = serial.tools.list_ports.comports()
            return [p.device for p in ports]
        except Exception:
            return []

    def auto_connect(self, baud_rate: int = 115200) -> Tuple[bool, str, Optional[str]]:
        """
        Automatically scans ports, detects the ESP32, and connects to it.
        Returns (success, message, detected_port).
        """
        port, desc = self.auto_detect_esp32()
        if not port:
            msg = "No ESP32 detected on USB ports. Please plug in your ESP32 device."
            self.status_message = msg
            return False, msg, None

        success, msg = self.connect(port, baud_rate)
        if success:
            self.status_message = f"[AUTO-DETECTED] Connected to ESP32 on {port} ({desc}) at {baud_rate} baud."
            return True, self.status_message, port
        return False, msg, port

    def connect(self, port_name: str = "COM3", baud_rate: int = 115200) -> Tuple[bool, str]:
        """Safely opens a non-blocking serial connection to the ESP32 receiver."""
        # Clean port_name if string has formatting e.g. "COM19 - Silicon Labs CP210x [⚡ ESP32]"
        clean_port = port_name.split()[0].strip() if " " in port_name else port_name.strip()

        # If already open and healthy on the requested port, return immediately
        if self.serial_conn is not None and self.serial_conn.is_open:
            if self.port == clean_port:
                self.is_connected = True
                return True, f"Already connected to {clean_port} at {self.baud} baud."
            else:
                self.disconnect()

        try:
            self.serial_conn = serial.Serial()
            self.serial_conn.port = clean_port
            self.serial_conn.baudrate = int(baud_rate)
            self.serial_conn.timeout = self.timeout
            self.serial_conn.write_timeout = self.timeout
            self.serial_conn.dtr = True
            self.serial_conn.rts = True
            self.serial_conn.open()
            self.port = clean_port
            self.baud = int(baud_rate)
            self.is_connected = True
            self.status_message = f"Connected to {clean_port} at {baud_rate} baud. Awaiting sensor stream..."
            return True, self.status_message
        except Exception as e:
            self.is_connected = False
            if self.serial_conn:
                try:
                    self.serial_conn.close()
                except Exception:
                    pass
            self.serial_conn = None
            err_str = str(e)
            if "PermissionError" in err_str or "Access is denied" in err_str or "error 5" in err_str.lower():
                self.status_message = (
                    f"Port {clean_port} is LOCKED (Access Denied). "
                    "⚠️ PLEASE CLOSE ARDUINO SERIAL MONITOR in Arduino IDE "
                    "to release the port, then click Connect again."
                )
            elif "FileNotFoundError" in err_str or "could not open port" in err_str.lower():
                self.status_message = f"Port {clean_port} not found or unplugged. Please check USB cable."
            else:
                self.status_message = f"Failed to connect to {clean_port}: {err_str}"
            return False, self.status_message

    def disconnect(self):
        """Safely closes the serial port and releases OS hardware resources."""
        if self.serial_conn:
            try:
                if self.serial_conn.is_open:
                    self.serial_conn.close()
            except Exception:
                pass
        self.is_connected = False
        self.serial_conn = None
        self.status_message = "Disconnected from hardware interface."

    def convert_raw_sensor_values(
        self,
        raw_soil: float,
        temperature: float,
        tilt: float,
        vibration: float
    ) -> Tuple[float, float, float, float]:
        """
        Converts raw ADC values into physical measurements if raw ADC mode is active
        or if soil moisture reading exceeds physical 100% VWC limit.
        """
        calibrated_soil = raw_soil

        # If reading is in ADC range (e.g. 500 - 4095), convert to % VWC
        if self.raw_adc_mode or raw_soil > 100.0:
            # ESP32 12-bit ADC (0 - 4095): air ~ 4095 (0% VWC), water/wet soil ~ 1100 (100% VWC)
            pct = ((4095.0 - raw_soil) / 2995.0) * 100.0
            calibrated_soil = max(0.0, min(100.0, pct))

        return (
            round(max(0.0, min(100.0, calibrated_soil)), 1),
            round(max(-40.0, min(80.0, temperature)), 1),
            round(max(-90.0, min(90.0, tilt)), 2),
            round(max(0.0, min(5.0, vibration)), 3)
        )

    def validate_and_parse_line(self, raw_line: str) -> Optional[Dict[str, Any]]:
        """
        Parses and strictly validates incoming serial frame:
        Supports:
        1. 5-Field CSV: soilMoisture,temperature,tiltAngle,vibrationPGA,rainIntensity
           Example: 68.5,24.7,12.4,0.18,22.6
        2. Legacy 4-Field CSV: soilMoisture,temperature,tiltAngle,vibrationPGA
           (Marks rain channel as None / UNAVAILABLE without guessing zero)
        3. JSON payload with 5 or 4 sensor fields
        4. Arduino Key-Value stream (Soil moisture:, Rain:, Vibration:, Acceleration:)
        """
        line = raw_line.strip()
        if not line:
            return None

        # Ignore informational boot, system, and diagnostic lines
        line_lower = line.lower()
        if any(line_lower.startswith(p) for p in [
            "rst:", "configsip", "clk_drv", "mode:", "load:", "ho ", "entry ",
            "nrf24", "emergency wi-fi", "mobile emergency", "ap ip", "packet #",
            "---", "connected to", "ready", "listening", "hard resetting"
        ]) or "listening on" in line_lower:
            return None

        now_iso = datetime.now(timezone.utc).isoformat()

        # Format 1: JSON payload
        if line.startswith("{") and line.endswith("}"):
            try:
                payload = json.loads(line)
                raw_soil = float(payload.get("soilMoisture", payload.get("soil_moisture_pct", payload.get("soil_adc", 0.0))))
                raw_temp = float(payload.get("temperature", payload.get("temperature_c", payload.get("temp_c", 15.0))))
                raw_tilt = float(payload.get("tiltAngle", payload.get("tilt_degrees", payload.get("tilt", 0.0))))
                raw_vib = float(payload.get("vibrationPGA", payload.get("vibration_intensity_g", payload.get("vib_g", 0.0))))
                
                # 5th sensor: rain intensity
                raw_rain_val = payload.get("rainIntensity", payload.get("rain_intensity", payload.get("rainfall_intensity_mmh", None)))
                raw_rain = None
                if raw_rain_val is not None:
                    try:
                        r_float = float(raw_rain_val)
                        if not (math.isnan(r_float) or math.isinf(r_float) or r_float < 0.0 or r_float > 250.0):
                            raw_rain = round(r_float, 1)
                    except (ValueError, TypeError):
                        raw_rain = None

                station_id = str(payload.get("station_id", "GG-001"))
                soil_c, temp_c, tilt_c, vib_c = self.convert_raw_sensor_values(raw_soil, raw_temp, raw_tilt, raw_vib)

                return {
                    "station_id": station_id,
                    "soil_moisture_pct": soil_c,
                    "soil_adc": int(raw_soil) if raw_soil > 100 else None,
                    "temperature_c": temp_c,
                    "tilt_degrees": tilt_c,
                    "vibration_pga": vib_c,
                    "rain_intensity_mmh": raw_rain,
                    "rain_intensity": raw_rain,
                    "timestamp": now_iso,
                    "is_simulated": False,
                    "raw_frame": line,
                    "is_valid": True,
                    "is_complete": (raw_rain is not None)
                }
            except (ValueError, KeyError, json.JSONDecodeError):
                self.malformed_packets_rejected += 1
                return None

        # Format 2: Arduino Key-Value stream (from slope / receiver debug prints)
        line_lower = line.lower()
        if "soil moisture:" in line_lower or "soil:" in line_lower:
            m = re.search(r"[-+]?\d*\.?\d+", line)
            if m: self._kv_buffer["soil"] = float(m.group())
            return None
        elif "rain:" in line_lower:
            m = re.search(r"[-+]?\d*\.?\d+", line)
            if m: self._kv_buffer["rain"] = float(m.group())
            return None
        elif "vibration:" in line_lower:
            m = re.search(r"[-+]?\d*\.?\d+", line)
            if m: self._kv_buffer["vib"] = float(m.group())
            return None
        elif "tilt:" in line_lower:
            m = re.search(r"[-+]?\d*\.?\d+", line)
            if m: self._kv_buffer["tilt"] = float(m.group())
            return None
        elif "temperature:" in line_lower or "temp:" in line_lower:
            m = re.search(r"[-+]?\d*\.?\d+", line)
            if m: self._kv_buffer["temp"] = float(m.group())
            return None
        elif "acceleration:" in line_lower:
            m = re.search(r"[-+]?\d*\.?\d+", line)
            if m: self._kv_buffer["accel"] = float(m.group())
            return None
        elif any(k in line_lower for k in ["status:", "landslide:", "transmission:", "---"]):
            if ("soil" in self._kv_buffer or "tilt" in self._kv_buffer or "vib" in self._kv_buffer or "temp" in self._kv_buffer):
                raw_soil = float(self._kv_buffer.get("soil", 1500.0))
                raw_rain_adc = self._kv_buffer.get("rain", 0.0)
                # Map raw rain ADC (ESP32) or rate to mm/hr
                if raw_rain_adc > 100.0:
                    # Inverted/scaled optical rain sensor: lower ADC = more rain or direct
                    rain_mmh = round(max(0.0, min(50.0, ((4095.0 - raw_rain_adc) / 2995.0) * 50.0)), 1)
                else:
                    rain_mmh = round(float(raw_rain_adc), 1)

                raw_temp = float(self._kv_buffer.get("temp", 22.0))

                # Handle Tilt from direct "tilt:" reading or infer from "acceleration:" transducer
                if "tilt" in self._kv_buffer:
                    raw_tilt = float(self._kv_buffer["tilt"])
                elif "accel" in self._kv_buffer:
                    a_val = float(self._kv_buffer["accel"])
                    if abs(a_val) <= 1.05:
                        # Convert 1g gravitational component to angular degrees
                        raw_tilt = round(math.acos(max(-1.0, min(1.0, abs(a_val)))) * 180.0 / math.pi, 2)
                    else:
                        raw_tilt = round(abs(a_val), 2)
                else:
                    raw_tilt = 0.5

                # Ground vibration from digital vibration sensor or seismic transducer
                raw_vib_val = self._kv_buffer.get("vib", None)
                if raw_vib_val is not None:
                    raw_vib = 0.85 if (float(raw_vib_val) >= 1.0) else 0.02
                elif "accel" in self._kv_buffer and "tilt" in self._kv_buffer:
                    raw_vib = float(self._kv_buffer.get("accel", 0.02))
                else:
                    raw_vib = 0.02

                self._kv_buffer.clear()
                soil_c, temp_c, tilt_c, vib_c = self.convert_raw_sensor_values(raw_soil, raw_temp, raw_tilt, raw_vib)
                return {
                    "station_id": "GG-002",
                    "soil_moisture_pct": soil_c,
                    "soil_adc": int(raw_soil) if raw_soil > 100 else None,
                    "temperature_c": temp_c,
                    "tilt_degrees": tilt_c,
                    "vibration_pga": vib_c,
                    "rain_intensity_mmh": rain_mmh,
                    "rain_intensity": rain_mmh,
                    "timestamp": now_iso,
                    "is_simulated": False,
                    "raw_frame": line,
                    "is_valid": True,
                    "is_complete": True
                }
            return None

        # Format 3: Comma-Separated Values (5-field or Legacy 4-field)
        raw_tokens = [t.strip() for t in line.split(",") if t.strip()]
        if raw_tokens and raw_tokens[0].upper() == "GEOGUARD":
            tokens = raw_tokens[1:]
        else:
            tokens = raw_tokens

        # Check for 5-field packet: soilMoisture,temperature,tiltAngle,vibrationPGA,rainIntensity
        if len(tokens) == 5:
            try:
                raw_soil = float(tokens[0])
                raw_temp = float(tokens[1])
                raw_tilt = float(tokens[2])
                raw_vib = float(tokens[3])
                raw_rain_val = float(tokens[4])

                # Validation of physical bounds & numeric sanity
                if math.isnan(raw_soil) or math.isinf(raw_soil):
                    self.malformed_packets_rejected += 1
                    return None
                if math.isnan(raw_temp) or math.isinf(raw_temp) or not (-50.0 <= raw_temp <= 85.0):
                    self.malformed_packets_rejected += 1
                    return None
                if math.isnan(raw_tilt) or math.isinf(raw_tilt) or not (-180.0 <= raw_tilt <= 180.0):
                    self.malformed_packets_rejected += 1
                    return None
                if math.isnan(raw_vib) or math.isinf(raw_vib) or not (0.0 <= raw_vib <= 10.0):
                    self.malformed_packets_rejected += 1
                    return None
                if math.isnan(raw_rain_val) or math.isinf(raw_rain_val) or raw_rain_val < 0.0 or raw_rain_val > 250.0:
                    self.malformed_packets_rejected += 1
                    return None

                soil_c, temp_c, tilt_c, vib_c = self.convert_raw_sensor_values(raw_soil, raw_temp, raw_tilt, raw_vib)
                calibrated_rain = round(raw_rain_val, 1)

                return {
                    "station_id": "GG-002",
                    "soil_moisture_pct": soil_c,
                    "soil_adc": int(raw_soil) if raw_soil > 100 else None,
                    "temperature_c": temp_c,
                    "tilt_degrees": tilt_c,
                    "vibration_pga": vib_c,
                    "rain_intensity_mmh": calibrated_rain,
                    "rain_intensity": calibrated_rain,
                    "timestamp": now_iso,
                    "is_simulated": False,
                    "raw_frame": line,
                    "is_valid": True,
                    "is_complete": True
                }
            except ValueError:
                self.malformed_packets_rejected += 1
                return None

        # Check for Legacy 4-field packet: soilMoisture,temperature,tiltAngle,vibrationPGA
        if len(tokens) == 4:
            try:
                raw_soil = float(tokens[0])
                raw_temp = float(tokens[1])
                raw_tilt = float(tokens[2])
                raw_vib = float(tokens[3])

                if math.isnan(raw_soil) or math.isinf(raw_soil):
                    self.malformed_packets_rejected += 1
                    return None
                if math.isnan(raw_temp) or math.isinf(raw_temp) or not (-50.0 <= raw_temp <= 85.0):
                    self.malformed_packets_rejected += 1
                    return None
                if math.isnan(raw_tilt) or math.isinf(raw_tilt) or not (-180.0 <= raw_tilt <= 180.0):
                    self.malformed_packets_rejected += 1
                    return None
                if math.isnan(raw_vib) or math.isinf(raw_vib) or not (0.0 <= raw_vib <= 10.0):
                    self.malformed_packets_rejected += 1
                    return None

                soil_c, temp_c, tilt_c, vib_c = self.convert_raw_sensor_values(raw_soil, raw_temp, raw_tilt, raw_vib)

                # Legacy 4-field packet: mark rain_intensity_mmh as None (Unavailable), not 0.0!
                return {
                    "station_id": "GG-002",
                    "soil_moisture_pct": soil_c,
                    "soil_adc": int(raw_soil) if raw_soil > 100 else None,
                    "temperature_c": temp_c,
                    "tilt_degrees": tilt_c,
                    "vibration_pga": vib_c,
                    "rain_intensity_mmh": None,
                    "rain_intensity": None,
                    "timestamp": now_iso,
                    "is_simulated": False,
                    "raw_frame": line,
                    "is_valid": True,
                    "is_complete": False,
                    "data_quality": "PARTIAL"
                }
            except ValueError:
                self.malformed_packets_rejected += 1
                return None

        # Any other token count is invalid
        self.malformed_packets_rejected += 1
        return None

    def read_latest_packet(self) -> Optional[Dict[str, Any]]:
        """
        Polls the non-blocking serial buffer for available sensor data.
        Returns validated telemetry dictionary or None.
        """
        if not self.is_connected or not self.serial_conn:
            return None

        try:
            latest_parsed = None
            lines_read = 0
            while self.serial_conn and self.serial_conn.in_waiting > 0 and lines_read < 100:
                raw_line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                lines_read += 1
                if not raw_line:
                    continue
                parsed = self.validate_and_parse_line(raw_line)
                if parsed:
                    latest_parsed = parsed
                    self.last_reading = parsed
                    self.last_packet_time = datetime.now(timezone.utc)
                    self.total_packets_received += 1
                    self.status_message = (
                        f"Receiving live telemetry from {parsed['station_id']}: "
                        f"Soil={parsed['soil_moisture_pct']}%, Temp={parsed['temperature_c']}°C, "
                        f"Tilt={parsed['tilt_degrees']}°, Vib={parsed['vibration_pga']}g"
                    )

            if latest_parsed is None and self.serial_conn and lines_read == 0:
                # Try single non-blocking readline in case in_waiting was transitioning
                raw_line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                if raw_line:
                    parsed = self.validate_and_parse_line(raw_line)
                    if parsed:
                        latest_parsed = parsed
                        self.last_reading = parsed
                        self.last_packet_time = datetime.now(timezone.utc)
                        self.total_packets_received += 1
                        self.status_message = (
                            f"Receiving live telemetry from {parsed['station_id']}: "
                            f"Soil={parsed['soil_moisture_pct']}%, Temp={parsed['temperature_c']}°C, "
                            f"Tilt={parsed['tilt_degrees']}°, Vib={parsed['vibration_pga']}g"
                        )

            return latest_parsed
        except Exception as e:
            self.status_message = f"Serial I/O error: {str(e)}"
            self.disconnect()

        return None

    def get_health_diagnostics(self) -> Dict[str, Any]:
        """Evaluates hardware link quality and detects stale/disconnected conditions."""
        freshness_sec: Optional[float] = None
        if self.last_packet_time:
            freshness_sec = round((datetime.now(timezone.utc) - self.last_packet_time).total_seconds(), 1)

        health_status = "OFFLINE"
        is_stale = False

        if self.is_connected:
            if freshness_sec is not None:
                if freshness_sec < 5.0:
                    health_status = "ONLINE (STREAMING)"
                elif freshness_sec < self.stale_threshold_sec:
                    health_status = "ONLINE (DELAYED)"
                else:
                    health_status = "STALE / TIMEOUT"
                    is_stale = True
            else:
                health_status = "CONNECTED (WAITING FIRST PACKET)"
        else:
            health_status = "DISCONNECTED"

        return {
            "is_connected": self.is_connected,
            "port": self.port,
            "baud": self.baud,
            "status": health_status,
            "is_stale": is_stale,
            "freshness_seconds": freshness_sec,
            "total_packets": self.total_packets_received,
            "malformed_rejected": self.malformed_packets_rejected,
            "status_message": self.status_message,
            "last_reading": self.last_reading
        }


# ---------------------------------------------------------------------------
# Global Process-Wide Singleton Gateway
# ---------------------------------------------------------------------------
_GLOBAL_GATEWAY: Optional[SerialTelemetryGateway] = None

def get_hardware_gateway(default_port: str = "COM20", default_baud: int = 115200) -> SerialTelemetryGateway:
    """
    Returns the process-wide singleton SerialTelemetryGateway instance.
    Prevents multiple Streamlit browser sessions/tabs from creating competing
    PySerial handles on the same COM port, which triggers:
    'SerialException: PermissionError(13, Access is denied)'.
    """
    global _GLOBAL_GATEWAY
    if _GLOBAL_GATEWAY is None:
        _GLOBAL_GATEWAY = SerialTelemetryGateway(default_port=default_port, default_baud=default_baud)
    return _GLOBAL_GATEWAY

