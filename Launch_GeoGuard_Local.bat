@echo off
title GeoGuard AI - Local Hardware Interface
cls
echo ===============================================================================
echo     GEOGUARD AI - HIGHWAY INTELLIGENCE ^& LANDSLIDE EARLY WARNING PLATFORM
echo ===============================================================================
echo.
echo [*] Checking ESP32 USB Connection...
echo [*] IMPORTANT: Ensure Arduino IDE Serial Monitor is CLOSED!
echo.
echo [*] Starting Local Streamlit Dashboard on http://localhost:8501...
echo.
cd /d "C:\geoguard1\geoguard-dashboard"
"C:\Users\ayush srivastav\AppData\Local\Programs\Python\Python313\python.exe" -m streamlit run app.py --server.port 8501
pause
