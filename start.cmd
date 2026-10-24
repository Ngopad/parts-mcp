@echo off
rem Dobbeltklik for at starte parts-mcp og kicad-mcp.
rem Kun den ene: start.cmd parts  eller  start.cmd kicad
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
pause
