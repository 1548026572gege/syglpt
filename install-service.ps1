# 生物实验室管理平台 - Windows 部署脚本
# 用法（管理员 PowerShell）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\install-service.ps1
# 可选参数：
#   .\install-service.ps1 -Port 8080 -TaskName BioLab-Web

param(
    [int]$Port = 8000,
    [string]$TaskName = "BioLab-Web"
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host $msg -ForegroundColor Red; exit 1 }

# 0. 管理员权限检查
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Fail "请以管理员身份运行此脚本（右键 PowerShell -> 以管理员身份运行）。" }

# 1. 路径检查
$Root = $PSScriptRoot
$AppDir = Join-Path $Root "test"
if (-not (Test-Path (Join-Path $AppDir "app.py"))) {
    Fail "未找到 test\app.py。请把本脚本放在项目根目录（与 test 文件夹同级）。"
}

# 2. 检查 Python
Write-Step "检查 Python 环境"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Fail "未找到 python 命令。请安装 Python 3.10+，安装时勾选 Add python.exe to PATH。" }
& python --version

# 3. 虚拟环境与依赖
Write-Step "准备虚拟环境并安装依赖（首次较慢，请耐心等待）"
$Venv = Join-Path $AppDir "venv"
$VenvPy = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $VenvPy)) { & python -m venv $Venv }
& $VenvPy -m pip install --upgrade pip
& $VenvPy -m pip install -r (Join-Path $AppDir "requirements.txt") waitress

# 3.1 Python 是否仅当前用户安装（SYSTEM 任务可能读不到）
$basePrefix = (& $VenvPy -c "import sys; print(sys.base_prefix)")
if ($basePrefix -like "*AppData\Local*") {
    Write-Host "警告：Python 似乎只安装在当前用户目录。SYSTEM 账户可能无法运行，建议卸载后选择“为所有用户安装”。" -ForegroundColor Yellow
}

# 4. 端口占用检查
Write-Step "检查端口 $Port"
$used = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($used) {
    $pids = ($used | Select-Object -ExpandProperty OwningProcess -Unique) -join ","
    Fail "端口 $Port 已被占用（PID: $pids）。请先释放端口，或换端口运行：.\install-service.ps1 -Port 8080"
}

# 5. 环境变量（机器级，服务以 SYSTEM 运行也能读取）
Write-Step "配置系统环境变量"
[Environment]::SetEnvironmentVariable("BIOLAB_PORT", "$Port", "Machine")

if (-not [Environment]::GetEnvironmentVariable("SECRET_KEY", "Machine")) {
    $secret = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
    [Environment]::SetEnvironmentVariable("SECRET_KEY", $secret, "Machine")
    Write-Host "已生成随机 SECRET_KEY。"
}

$randomPwd = $false
if (-not [Environment]::GetEnvironmentVariable("ADMIN_INIT_PASSWORD", "Machine")) {
    $pwdIn = Read-Host "管理员初始密码（直接回车则随机生成，首次启动后可在日志中查看）"
    if ($pwdIn) { [Environment]::SetEnvironmentVariable("ADMIN_INIT_PASSWORD", $pwdIn, "Machine") }
    else { $randomPwd = $true }
}
if (-not [Environment]::GetEnvironmentVariable("TEACHER_INIT_PASSWORD", "Machine")) {
    $pwdIn = Read-Host "教师初始密码（直接回车则随机生成，首次启动后可在日志中查看）"
    if ($pwdIn) { [Environment]::SetEnvironmentVariable("TEACHER_INIT_PASSWORD", $pwdIn, "Machine") }
    else { $randomPwd = $true }
}

# 6. 防火墙放行
Write-Step "配置防火墙"
$ruleName = "BioLab Web $Port"
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow | Out-Null
    Write-Host "已放行入站端口 $Port。"
} else {
    Write-Host "防火墙规则已存在，跳过。"
}

# 7. 注册开机自启任务
Write-Step "注册开机自启任务 $TaskName"
$Bat = Join-Path $Root "start-web.bat"
if (-not (Test-Path $Bat)) { Fail "未找到 start-web.bat（应与本脚本在同一目录）。" }

& schtasks.exe /End /TN $TaskName 2>$null | Out-Null
& schtasks.exe /Delete /TN $TaskName /F 2>$null | Out-Null
$taskCmd = '"' + $Bat + '"'
& schtasks.exe /Create /SC ONSTART /TN $TaskName /RU SYSTEM /RL HIGHEST /TR $taskCmd /F | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "任务注册失败，请检查任务计划服务是否正常。" }
& schtasks.exe /Run /TN $TaskName | Out-Null

# 8. 启动验证
Write-Step "等待服务启动并验证"
Start-Sleep -Seconds 8
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 10
    Write-Host "服务已启动，HTTP 状态码 $($resp.StatusCode)。" -ForegroundColor Green
} catch {
    Write-Host "服务暂未响应，请稍后查看日志：$AppDir\logs\web.log" -ForegroundColor Yellow
}

# 9. 输出访问信息
$ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -like "192.168.*" } |
        Select-Object -First 1).IPAddress
if (-not $ip) {
    $ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
            Select-Object -First 1).IPAddress
}

Write-Host "`n部署完成。" -ForegroundColor Green
Write-Host "  本机访问：http://127.0.0.1:$Port"
if ($ip) { Write-Host "  局域网访问：http://${ip}:$Port" }
Write-Host "  日志文件：$AppDir\logs\web.log"
Write-Host "  停止服务：schtasks /End /TN $TaskName"
Write-Host "  启动服务：schtasks /Run /TN $TaskName"
if ($randomPwd) {
    Write-Host "  初始密码为随机生成，请在首次启动后的日志中搜索“初始账号”查看。" -ForegroundColor Yellow
}
