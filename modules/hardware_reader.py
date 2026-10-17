"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Module: modules/hardware_reader.py
Purpose: Non-Blocking PySerial IoT Gateway for Arduino/ESP32 Telemetry Nodes
=============================================================================
Provides asynchronous, non-blocking serial communication with hardware nodes:
- Auto-detects available serial COM ports
- Configures baud rates (9600, 19200, 38400, 57600, 115200)
- Parses and validates newline-delimited JSON packets
- Robust error handling: JSON syntax errors, timeouts, disconnects
- Telemetry freshness tracking and packet integrity diagnostics
"""

import json
import time
from datetime import datetime
import serial
import serial.tools.list_ports

class SerialTelemetryGateway:
    """Non-blocking gateway managing USB/Serial interface to physical ESP32/Arduino stations."""
    
    def __init__(self):
        self.serial_conn = None
        self.is_connected = False
        self.port = None
        self.baud = 115200
        self.last_reading = None
        self.last_packet_time = None
        self.total_packets_received = 0
        self.crc_json_errors = 0
        self.status_message = "Hardware interface idle. Select port to connect."

    @staticmethod
    def list_available_ports():
        """Scans system for active serial COM ports."""
        try:
            ports = serial.tools.list_ports.comports()
            return [p.device for p in ports]
        except Exception:
            return []

    def connect(self, port_name, baud_rate=115200):
        """Attempts connection to specified serial port."""
        if self.is_connected:
            self.disconnect()

        try:
            self.serial_conn = serial.Serial(
                port=port_name,
                baudrate=int(baud_rate),
                timeout=0.2, # Non-blocking short timeout
                write_timeout=0.2
            )
            self.port = port_name
            self.baud = int(baud_rate)
            self.is_connected = True
            self.status_message = f"Connected to {port_name} at {baud_rate} baud. Awaiting JSON stream..."
            return True, self.status_message
        except Exception as e:
            self.is_connected = False
            self.serial_conn = None
            self.status_message = f"Failed to open {port_name}: {str(e)}"
            return False, self.status_message

    def disconnect(self):
        """Safely closes serial port connection."""
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        self.is_connected = False
        self.serial_conn = None
        self.status_message = "Disconnected from hardware interface."

    def read_latest_packet(self):
        """
        Polls serial buffer for available newline-delimited JSON packet.
        Returns validated telemetry dict or None if no packet is ready.
        """
        if not self.is_connected or not self.serial_conn:
            return None

        try:
            if self.serial_conn.in_waiting > 0:
                raw_line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                if not raw_line:
                    return None

                try:
                    payload = json.loads(raw_line)
                    # Validate required schema fields
                    if "station_id" in payload:
                        self.last_reading = payload
                        self.last_packet_time = datetime.utcnow()
                        self.total_packets_received += 1
                        self.status_message = f"Receiving live telemetry from {payload['station_id']}"
                        return payload
                    else:
                        self.crc_json_errors += 1
                except json.JSONDecodeError:
                    self.crc_json_errors += 1
        except Exception as e:
            self.status_message = f"Serial read error: {str(e)}"
            self.disconnect()
            
        return None

    def get_health_diagnostics(self):
        """Returns hardware link quality metrics."""
        freshness_sec = None
        if self.last_packet_time:
            freshness_sec = round((datetime.utcnow() - self.last_packet_time).total_seconds(), 1)

        health_status = "OFFLINE"
        if self.is_connected:
            if freshness_sec is not None and freshness_sec < 5.0:
                health_status = "ONLINE (STREAMING)"
            elif freshness_sec is not None and freshness_sec < 30.0:
                health_status = "DELAYED"
            else:
                health_status = "CONNECTED (WAITING DATA)"

        return {
            "is_connected": self.is_connected,
            "port": self.port,
            "baud": self.baud,
            "status": health_status,
            "freshness_seconds": freshness_sec,
            "total_packets": self.total_packets_received,
            "crc_errors": self.crc_json_errors,
            "status_message": self.status_message,
            "last_reading": self.last_reading
        }
