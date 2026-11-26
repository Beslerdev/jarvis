@echo off
cd /d "%~dp0"
echo ==================================================
echo    Instalando J.A.R.V.I.S.  (usa Python 3.12)
echo ==================================================
set "PY312=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PY312%" goto tengo_python
py -3.12 --version >nul 2>&1
if errorlevel 1 goto instalar_python
for /f "delims=" %%i in ('py -3.12 -c "import sys;print(sys.executable)"') do set "PY312=%%i"
goto tengo_python

:instalar_python
echo.
echo Instalando Python 3.12 (puede tardar unos minutos)...
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
if exist "%PY312%" goto tengo_python
echo.
echo No pude instalar Python 3.12 solo. Descargalo de:
echo https://www.python.org/downloads/release/python-31210/
echo (Windows installer 64-bit) y volve a ejecutar este archivo.
pause
exit /b

:tengo_python
echo Usando Python: %PY312%
>py_ruta.txt echo %PY312%
"%PY312%" -m pip install --upgrade pip
echo (Se descargan unos 300 MB, puede tardar varios minutos)
"%PY312%" -m pip install -r requirements.txt
if not errorlevel 1 "%PY312%" -m pip install --no-deps "resemblyzer>=0.1.4"
if errorlevel 1 (
  echo.
  echo Hubo un error instalando las librerias. Saca una foto de este mensaje y pasamela.
  pause
  exit /b
)
if exist clave_api.txt goto listo
echo.
echo ==================================================
echo  Pega tu clave de API de Anthropic (empieza con sk-ant-)
echo  Clic derecho en esta ventana para pegar, despues Enter.
echo ==================================================
set /p CLAVE=Clave: 
>clave_api.txt echo %CLAVE%
:listo
echo.
echo Listo! Ahora:
echo   1) Doble clic en registrar_mi_voz.bat  (para que Jarvis solo te responda a vos)
echo   2) Doble clic en iniciar_jarvis.bat
pause
