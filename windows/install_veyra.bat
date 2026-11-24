@echo off
setlocal EnableDelayedExpansion
title Veyra installer
chcp 65001 >nul
echo.
echo   ======  VEYRA  -  Windows 10 installer  ======
echo   Installs Git, Python 3.12, ffmpeg, Windows Terminal, clones your repo,
echo   builds her engine and downloads her model. Safe to run again.
echo.

where winget >nul 2>nul || (
  echo   winget is missing. Install "App Installer" from the Microsoft Store, then run this again.
  pause & exit /b 1
)

set "WG=winget install -e --silent --accept-package-agreements --accept-source-agreements"
echo == Git
where git >nul 2>nul || %WG% --id Git.Git
echo == Python 3.12
if not exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" %WG% --id Python.Python.3.12 --scope user
echo == ffmpeg (for reading videos and her voice)
where ffmpeg >nul 2>nul || %WG% --id Gyan.FFmpeg
echo == Microsoft C++ runtime (her AI engine needs it)
%WG% --id Microsoft.VCRedist.2015+.x64
echo == Windows Terminal (for the 8-bit colors)
where wt >nul 2>nul || %WG% --id Microsoft.WindowsTerminal

rem new installs are not on PATH yet in this window
set "PATH=%ProgramFiles%\Git\cmd;%LOCALAPPDATA%\Microsoft\WinGet\Links;%LOCALAPPDATA%\Microsoft\WindowsApps;%PATH%"
set "PYBASE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PYBASE%" (
  echo   Python 3.12 did not install. Install it from python.org, then run this again.
  pause & exit /b 1
)

echo.
echo == GitHub
set "TAROT=%USERPROFILE%\Tarot"
for /f "delims=" %%a in ('git config --global user.name 2^>nul') do set "GN=%%a"
if not defined GN (
  set /p "GN=  Your name for GitHub commits: "
  git config --global user.name "!GN!"
  set /p "GE=  Your GitHub email: "
  git config --global user.email "!GE!"
)
if exist "%TAROT%\tarot.py" (
  echo   Updating %TAROT%
  git -C "%TAROT%" pull --rebase --autostash
) else (
  echo   Cloning into %TAROT%
  git clone https://github.com/aiekair-null/Tarot.git "%TAROT%" || (
    echo   Clone failed. Check your internet connection and run this again.
    pause & exit /b 1
  )
)

echo.
echo == Her engine
set "VENV=%LOCALAPPDATA%\veyra\venv"
set "PY=%VENV%\Scripts\python.exe"
if not exist "%PY%" "%PYBASE%" -m venv "%VENV%"
"%PY%" -m pip install -q --upgrade pip
"%PY%" -m pip install -q -r "%TAROT%\requirements.txt" windows-curses
echo   Installing llama.cpp (the built-in AI)...
"%PY%" -m pip install -q llama-cpp-python --only-binary=:all: --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
if not errorlevel 1 "%PY%" -c "import llama_cpp" 2>nul
if errorlevel 1 (
  echo   The built-in engine has no ready-made build for this PC.
  echo   Installing Ollama instead - she finds it automatically.
  %WG% --id Ollama.Ollama
  set "PATH=%LOCALAPPDATA%\Programs\Ollama;!PATH!"
  ollama pull qwen3:8b
) else (
  echo == Her model ^(Qwen3 8B, about 5 GB^)
  pushd "%TAROT%"
  "%PY%" models.py download qwen3-8b && "%PY%" models.py use qwen3-8b
  popd
)

echo.
echo == Desktop shortcut
set "LAUNCH=%TAROT%\windows\veyra.bat"
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Veyra.lnk');" ^
  "$wt=(Get-Command wt -ErrorAction SilentlyContinue).Source;" ^
  "if($wt){$s.TargetPath=$wt;$s.Arguments=[char]34+'%LAUNCH%'+[char]34}else{$s.TargetPath='%LAUNCH%'};" ^
  "$s.WorkingDirectory='%TAROT%';$s.Save()"

echo.
echo   Done. Double-click "Veyra" on your desktop, or run:  %LAUNCH%
echo   Memory and sessions sync to GitHub after every reading.
echo   ^(The first push asks you to sign in to GitHub once in a browser.^)
pause
