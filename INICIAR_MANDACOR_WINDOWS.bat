@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title MANDACOR - Expo QR Code

cd /d "%~dp0"
set "PROJECT_DIR=%CD%"
if not defined MANDACOR_BACKEND_PORT set "MANDACOR_BACKEND_PORT=8000"
if not defined MANDACOR_EXPO_PORT set "MANDACOR_EXPO_PORT=8081"
set "BACKEND_PORT=%MANDACOR_BACKEND_PORT%"

echo.
echo ==========================================================
echo   MANDACOR - Inicializador Windows
echo ==========================================================
echo.

where node >nul 2>nul
if errorlevel 1 goto :missing_node
where npm >nul 2>nul
if errorlevel 1 goto :missing_node

set "PYTHON_EXE=%PROJECT_DIR%\.venv-windows\Scripts\python.exe"
if exist "%PYTHON_EXE%" goto :python_ready

echo [1/5] Preparando o Python...
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m venv "%PROJECT_DIR%\.venv-windows"
) else (
  where python >nul 2>nul
  if errorlevel 1 goto :missing_python
  python -m venv "%PROJECT_DIR%\.venv-windows"
)
if errorlevel 1 goto :setup_error

:python_ready
echo [2/5] Verificando o backend...
"%PYTHON_EXE%" -c "import mandacor, fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo Instalando dependencias do backend pela primeira vez...
  "%PYTHON_EXE%" -m pip install -e "%PROJECT_DIR%"
  if errorlevel 1 goto :setup_error
)

echo [3/5] Verificando o aplicativo Expo...
if not exist "%PROJECT_DIR%\mobile\node_modules\.bin\expo.cmd" (
  pushd "%PROJECT_DIR%\mobile"
  call npm ci
  if errorlevel 1 (
    popd
    goto :setup_error
  )
  popd
)

if not defined MANDACOR_LAN_IP (
  for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$route = Get-NetRoute -DestinationPrefix '0.0.0.0/0' ^| Sort-Object RouteMetric,InterfaceMetric ^| Select-Object -First 1; if ($route) { Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $route.InterfaceIndex ^| Where-Object { $_.IPAddress -notlike '169.254.*' } ^| Select-Object -First 1 -ExpandProperty IPAddress }"`) do set "MANDACOR_LAN_IP=%%I"
)
if not defined MANDACOR_LAN_IP set "MANDACOR_LAN_IP=127.0.0.1"
set "EXPO_PUBLIC_MANDACOR_API_URL=http://%MANDACOR_LAN_IP%:%BACKEND_PORT%"
set "EXPO_PUBLIC_MANDACOR_FORCE_API_URL=1"

echo [4/5] Iniciando API em %EXPO_PUBLIC_MANDACOR_API_URL% ...
powershell -NoProfile -Command "try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:%BACKEND_PORT%/health' -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>nul
if errorlevel 1 (
  start "MANDACOR - Backend" /D "%PROJECT_DIR%" "%PYTHON_EXE%" -m mandacor api serve --host 0.0.0.0 --port %BACKEND_PORT% --cors-origin http://localhost:%MANDACOR_EXPO_PORT% --cors-origin http://127.0.0.1:%MANDACOR_EXPO_PORT% --cors-origin http://%MANDACOR_LAN_IP%:%MANDACOR_EXPO_PORT%
)

set "API_READY="
for /L %%N in (1,1,30) do (
  powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:%BACKEND_PORT%/health' -TimeoutSec 1 ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
  if not errorlevel 1 (
    set "API_READY=1"
    goto :api_ready
  )
  >nul timeout /t 1 /nobreak
)

:api_ready
if not defined API_READY goto :backend_error

echo [5/5] Abrindo Expo...
echo.
echo API do celular: %EXPO_PUBLIC_MANDACOR_API_URL%
echo Leia o QR Code abaixo usando o Expo Go.
echo Para encerrar o Expo, pressione Ctrl+C.
echo.

pushd "%PROJECT_DIR%\mobile"
call npx expo start --lan --port %MANDACOR_EXPO_PORT%
set "EXPO_EXIT=%ERRORLEVEL%"
popd
if not "%EXPO_EXIT%"=="0" goto :expo_error
goto :end

:missing_node
echo ERRO: Node.js e npm nao foram encontrados.
echo Instale a versao LTS em https://nodejs.org/ e execute novamente.
goto :pause_error

:missing_python
echo ERRO: Python 3 nao foi encontrado.
echo Instale Python 3.11 ou superior em https://www.python.org/downloads/
echo Durante a instalacao, marque "Add Python to PATH".
goto :pause_error

:setup_error
echo ERRO: Nao foi possivel instalar ou validar as dependencias.
echo Verifique a conexao com a internet e as mensagens acima.
goto :pause_error

:backend_error
echo ERRO: O backend nao respondeu na porta %BACKEND_PORT%.
echo Consulte a janela "MANDACOR - Backend" para ver o motivo.
goto :pause_error

:expo_error
echo ERRO: O Expo foi encerrado com falha.
goto :pause_error

:pause_error
echo.
pause
exit /b 1

:end
endlocal
