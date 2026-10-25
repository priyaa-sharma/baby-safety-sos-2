@echo off
cd /d %~dp0
:loop
python monitor.py
timeout /t 5
goto loop