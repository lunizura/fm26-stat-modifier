@echo off
title FM26 Tactical Scout ^& Live Stat Modifier
cd /d "%~dp0"
python app_gui.py
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to launch GUI. Installing required packages...
    pip install -r requirements.txt
    python app_gui.py
)
