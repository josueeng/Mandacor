@echo off
rem Installs the MANDACOR API so it starts with Windows.
rem   INSTALAR_SERVICO_WINDOWS.bat           install (or update) and start
rem   INSTALAR_SERVICO_WINDOWS.bat remover   stop and remove
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\windows\instalar_servico.ps1" %*
