@echo off
title GeoGuard AI - ESP32 to Cloud Bridge
cls
echo ===============================================================================
echo     GEOGUARD AI - LIVE ESP32 HARDWARE TO CLOUD WEBSITE BRIDGE
echo ===============================================================================
echo Target Website: https://shrivayush08-lgtm-geoguard-system-app-nqdul8.streamlit.app
echo.
echo [*] IMPORTANT: Ensure Arduino IDE Serial Monitor is CLOSED!
echo [*] Launching Telemetry Bridge on COM20...
echo.
cd /d "C:\geoguard1\geoguard-dashboard"
"C:\Users\ayush srivastav\AppData\Local\Programs\Python\Python313\python.exe" run_cloud_bridge.py
pause
