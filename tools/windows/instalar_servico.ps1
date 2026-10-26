# Installs the MANDACOR API as a scheduled task that starts with Windows.
#   instalar_servico.ps1           install (or update) and start
#   instalar_servico.ps1 remover   stop and remove
param([string]$Acao = "instalar")

$ErrorActionPreference = "Stop"
$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runner = Join-Path $PSScriptRoot "mandacor_servico.bat"
$PythonExe = Join-Path $ProjectDir ".venv-windows\Scripts\python.exe"
$Port = if ($env:MANDACOR_BACKEND_PORT) { [int]$env:MANDACOR_BACKEND_PORT } else { 8000 }
$TaskName = "MANDACOR API"
$FirewallRule = "MANDACOR API"

function Stop-Backend {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    }
    # Ending the task does not always end its child processes.
    Get-CimInstance Win32_Process |
        Where-Object { $_.CommandLine -and ($_.CommandLine -like "*mandacor_servico.bat*" -or $_.CommandLine -like "*mandacor api serve*") } |
        ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }
}

function Test-Health {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 1 | Out-Null
        return $true
    } catch {
        return $false
    }
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Pedindo permissao de administrador..."
    Start-Process powershell -Verb RunAs -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"", $Acao)
    exit 0
}

try {
    if ($Acao -eq "remover") {
        Stop-Backend
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        netsh advfirewall firewall delete rule name="$FirewallRule" | Out-Null
        Write-Host "Servico MANDACOR removido."
        Read-Host "Pressione Enter para fechar"
        exit 0
    }

    Write-Host "[1/5] Preparando o Python..."
    if (-not (Test-Path $PythonExe)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3 -m venv (Join-Path $ProjectDir ".venv-windows")
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            & python -m venv (Join-Path $ProjectDir ".venv-windows")
        } else {
            throw "Python 3.11 ou superior nao encontrado. Instale em https://www.python.org/downloads/ marcando 'Add Python to PATH'."
        }
        if (-not (Test-Path $PythonExe)) { throw "Nao foi possivel criar o ambiente Python." }
    }

    Write-Host "[2/5] Verificando as dependencias do backend..."
    # Windows PowerShell 5.1 turns redirected stderr into a terminating error under "Stop".
    $ErrorActionPreference = "Continue"
    & $PythonExe -c "import mandacor, fastapi, uvicorn" 2>$null
    $dependenciesReady = $LASTEXITCODE -eq 0
    $ErrorActionPreference = "Stop"
    if (-not $dependenciesReady) {
        & $PythonExe -m pip install -e $ProjectDir
        if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependencias do backend." }
    }

    Write-Host "[3/5] Liberando o Python no firewall (somente redes privadas)..."
    # The venv python.exe hands off to the base interpreter, so allow the port and both executables.
    $basePython = (& $PythonExe -c "import sys; print(getattr(sys, '_base_executable', sys.executable))").Trim()
    netsh advfirewall firewall delete rule name="$FirewallRule" | Out-Null
    netsh advfirewall firewall add rule name="$FirewallRule" dir=in action=allow protocol=TCP localport=$Port profile=private,domain enable=yes | Out-Null
    foreach ($program in @($PythonExe, $basePython) | Select-Object -Unique) {
        netsh advfirewall firewall add rule name="$FirewallRule" dir=in action=allow program="$program" profile=private,domain enable=yes | Out-Null
    }

    Write-Host "[4/5] Registrando a tarefa que inicia com o Windows..."
    Stop-Backend
    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$Runner`"" -WorkingDirectory $ProjectDir
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName $TaskName

    Write-Host "[5/5] Aguardando a API responder..."
    $ready = $false
    foreach ($attempt in 1..30) {
        if (Test-Health) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        throw "A API nao respondeu. Veja o log em $ProjectDir\logs\backend-servico.log"
    }

    $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue | Sort-Object RouteMetric, InterfaceMetric | Select-Object -First 1
    $lanIp = if ($route) {
        Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike "169.254.*" } |
            Select-Object -First 1 -ExpandProperty IPAddress
    }
    $networkCategory = if ($route) { (Get-NetConnectionProfile -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue).NetworkCategory }

    Write-Host ""
    Write-Host "MANDACOR esta rodando e vai iniciar sozinho com o Windows." -ForegroundColor Green
    Write-Host "No aplicativo, em CONFIG, use o servidor: http://$(if ($lanIp) { $lanIp } else { 'IP_DO_PC' }):$Port"
    Write-Host "Log: $ProjectDir\logs\backend-servico.log"
    if ($networkCategory -eq "Public") {
        Write-Host ""
        Write-Host "ATENCAO: esta rede esta marcada como PUBLICA no Windows. O celular nao vai conseguir conectar." -ForegroundColor Yellow
        Write-Host "Em Configuracoes > Rede e Internet > propriedades da rede, marque-a como PRIVADA." -ForegroundColor Yellow
    }
} catch {
    Write-Host ""
    Write-Host "ERRO: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Pressione Enter para fechar"
    exit 1
}
Read-Host "Pressione Enter para fechar"
