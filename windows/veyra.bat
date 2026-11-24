@echo off
rem Veyra launcher for Windows.  veyra.bat [model ^| video ^| intro ^| control ^| promo ...]
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PATH=%ProgramFiles%\Git\cmd;%LOCALAPPDATA%\Microsoft\WinGet\Links;%LOCALAPPDATA%\Programs\Ollama;%PATH%"
set "PY=%LOCALAPPDATA%\veyra\venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Veyra is not installed yet. Run windows\install_veyra.bat first.
  pause & exit /b 1
)
cd /d "%~dp0.."
if /i "%~1"=="promo" goto promo
"%PY%" tarot.py %*
goto done
:promo
shift
"%PY%" veyra_promo.py %1 %2 %3 %4 %5 %6 %7 %8 %9
:done
if errorlevel 1 pause
