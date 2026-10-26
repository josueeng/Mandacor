@echo off
rem Runs the MANDACOR API for the "MANDACOR API" scheduled task and restarts it if it stops.
rem Installed by INSTALAR_SERVICO_WINDOWS.bat; not meant to be opened by hand.
setlocal EnableExtensions
cd /d "%~dp0..\.."
set "PROJECT_DIR=%CD%"
if not defined MANDACOR_BACKEND_PORT set "MANDACOR_BACKEND_PORT=8000"
set "PYTHON_EXE=%PROJECT_DIR%\.venv-windows\Scripts\python.exe"
if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"

echo [%DATE% %TIME%] Servico MANDACOR iniciado > "%PROJECT_DIR%\logs\backend-servico.log"

:loop
echo [%DATE% %TIME%] Iniciando MANDACOR API na porta %MANDACOR_BACKEND_PORT% >> "%PROJECT_DIR%\logs\backend-servico.log"
"%PYTHON_EXE%" -m mandacor api serve --host 0.0.0.0 --port %MANDACOR_BACKEND_PORT% >> "%PROJECT_DIR%\logs\backend-servico.log" 2>&1
echo [%DATE% %TIME%] API encerrada; reiniciando em 5 segundos >> "%PROJECT_DIR%\logs\backend-servico.log"
rem timeout needs a console, which a scheduled task does not have.
>nul ping -n 6 127.0.0.1
goto :loop
