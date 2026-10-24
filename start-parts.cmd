@echo off
rem Dobbeltklik for kun at starte komponentsøgningen (uden KiCad)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" parts
pause
