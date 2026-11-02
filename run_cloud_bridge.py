"""
=============================================================================
GEOGUARD AI — LIVE ESP32 CLOUD TELEMETRY BRIDGE
File: run_cloud_bridge.py
Purpose: Reads ESP32 serial data from local USB (COM20) and relays it to
         the live deployed Streamlit website in real time.
=============================================================================
"""

import sys
import time
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.hardware_reader import SerialTelemetryGateway
from modules.cloud_relay import send_telemetry_to_cloud

def main():
    print("=" * 75)
    print("      GEOGUARD AI — ESP32 TO CLOUD WEBSITE TELEMETRY BRIDGE")
    print("=" * 75)
    print("Target Live Website: https://shrivayush08-lgtm-geoguard-system-app-nqdul8.streamlit.app")
    print("=" * 75)
    print("\n[*] IMPORTANT: Close Arduino IDE Serial Monitor before running this bridge!")
    print("[*] Scanning for connected ESP32 hardware...")

    port, desc = SerialTelemetryGateway.auto_detect_esp32()
    if not port:
        port = "COM20"
        desc = "Default ESP32 USB Port"
        print(f"[!] Auto-detect did not find active USB device. Falling back to {port}")
    else:
        print(f"[+] Found ESP32: {port} ({desc})")

    gw = SerialTelemetryGateway(default_port=port, default_baud=115200)
    
    print(f"[*] Connecting to {port} @ 115200 baud...")
    success, msg = gw.connect(port, 115200)
    if not success:
        print(f"\n[!] CONNECTION ERROR: {msg}")
        print("\nFix:")
        print("1. Close the Serial Monitor in Arduino IDE (it locks the COM port).")
        print("2. Check that the ESP32 USB cable is securely connected.")
        input("\nPress Enter to exit...")
        return

    print(f"[+] Successfully connected to {port}!")
    print("[+] Bridge active. Relaying live telemetry packets to the cloud website...\n")
    print("-" * 75)
    print(f"{'TIMESTAMP':<12} | {'SOIL %':<8} | {'TEMP °C':<8} | {'TILT °':<8} | {'VIB (g)':<8} | {'STATUS'}")
    print("-" * 75)

    last_fwd_time = 0.0
    packet_count = 0

    try:
        while True:
            packet = gw.read_latest_packet()
            now = time.time()
            if packet and (now - last_fwd_time) >= 1.0:
                last_fwd_time = now
                packet_count += 1
                uploaded = send_telemetry_to_cloud(packet)
                
                soil = f"{packet.get('soil_moisture_pct', 0.0):.1f}%"
                temp = f"{packet.get('temperature_c', 0.0):.1f}°C"
                tilt = f"{packet.get('tilt_degrees', 0.0):.2f}°"
                vib = f"{packet.get('vibration_pga', 0.0):.3f}g"
                t_str = datetime.now().strftime("%H:%M:%S")
                status = "RELAYED TO CLOUD ✅" if uploaded else "UPLOAD RETRY ⏳"
                
                print(f"{t_str:<12} | {soil:<8} | {temp:<8} | {tilt:<8} | {vib:<8} | {status}")
            
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n[*] Bridge stopped by user.")
    finally:
        gw.disconnect()
        print("[*] Serial port released.")

if __name__ == "__main__":
    main()
