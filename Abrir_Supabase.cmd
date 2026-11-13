@echo off
cd /d "%~dp0"
"venv\Scripts\python.exe" -m backend.consultar_evaluacion --consulta comparativo
pause
