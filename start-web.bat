@echo off
setlocal
rem BioLab Web launcher - used by Windows Task Scheduler "BioLab-Web"

cd /d "%~dp0test"
if not exist logs mkdir logs

if not exist venv\Scripts\python.exe (
  echo [ERROR] venv not found. Run install-service.ps1 first.
  exit /b 1
)

if "%BIOLAB_PORT%"=="" set BIOLAB_PORT=8000

call venv\Scripts\activate.bat
echo [%date% %time%] starting waitress on port %BIOLAB_PORT% >> logs\web.log
waitress-serve --host=0.0.0.0 --port=%BIOLAB_PORT% app:app >> logs\web.log 2>&1
