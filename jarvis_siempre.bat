@echo off
cd /d "%~dp0"
title J.A.R.V.I.S. (siempre activo)
set "PY="
if exist py_ruta.txt set /p PY=<py_ruta.txt
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY (
  echo No encontre Python 3.12. Primero ejecuta instalar.bat.
  pause
  exit /b
)
:inicio
"%PY%" actualizar.py
"%PY%" jarvis.py --siempre
if errorlevel 1 (
  echo.
  echo JARVIS se cerro o se esta actualizando. Reinicio en 10 segundos...
  timeout /t 10 /nobreak >nul
  goto inicio
)
