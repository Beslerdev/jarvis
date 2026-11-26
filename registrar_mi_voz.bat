@echo off
cd /d "%~dp0"
title Registro de voz - JARVIS
set "PY="
if exist py_ruta.txt set /p PY=<py_ruta.txt
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY (
  echo No encontre Python 3.12. Primero ejecuta instalar.bat y espera a que diga "Listo!".
  pause
  exit /b
)
"%PY%" registrar_voz.py
echo.
pause
