@echo off
title Respected Brain Gateway
cd /d "%~dp0.."
py.exe -3 scripts\dashboard.py --open
if %ERRORLEVEL% NEQ 0 (
    python scripts\dashboard.py --open
)
