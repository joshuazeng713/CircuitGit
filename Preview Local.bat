@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0" || exit /b 1
set "PYTHONUTF8=1"

echo ==========================================
echo   CircuitGit (本地前端预览启动器)
echo ==========================================

set "PY_CMD="
set "PY_ARG="

for /d %%D in (".local\python\spiceowl-*") do (
  if exist "%%~fD\Scripts\python.exe" (
    "%%~fD\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
      set "PY_CMD=%%~fD\Scripts\python.exe"
      goto :check_git
    )
  )
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "PY_CMD=.venv\Scripts\python.exe"
    goto :check_git
  )
)

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  for %%V in (3.15 3.14 3.13 3.12 3.11 3) do (
    py -%%V -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
      set "PY_CMD=py"
      set "PY_ARG=-%%V"
      goto :check_git
    )
  )
)

for %%C in (python3.exe python.exe) do (
  where %%C >nul 2>&1
  if not errorlevel 1 (
    %%C -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
      set "PY_CMD=%%C"
      goto :check_git
    )
  )
)

for %%V in (315 314 313 312 311) do (
  if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
    goto :check_git
  )
  if exist "%ProgramFiles%\Python%%V\python.exe" (
    set "PY_CMD=%ProgramFiles%\Python%%V\python.exe"
    goto :check_git
  )
)

echo [CircuitGit] 需要 Python 3.11+。
echo   推荐安装方式：winget install Python.Python.3.12
echo   或从官网下载：https://www.python.org/downloads/windows/ （安装时勾选 Add Python to PATH）
pause
exit /b 1

:check_git
where git >nul 2>&1
if errorlevel 1 (
  echo [CircuitGit] 需要 Git 才能管理电路版本与安装依赖。
  echo   推荐安装方式：winget install Git.Git
  echo   或从官网下载：https://git-scm.com/download/win
  pause
  exit /b 1
)

echo [CircuitGit] 环境检查通过，正在构建并启动本地预览（请保持此窗口运行）…
echo.

:launch
if defined PY_ARG (
  "%PY_CMD%" %PY_ARG% -E -s -B tools\workbench\preview_local_pages.py %*
) else (
  "%PY_CMD%" -E -s -B tools\workbench\preview_local_pages.py %*
)
set "LAUNCH_STATUS=%ERRORLEVEL%"
if not "%LAUNCH_STATUS%"=="0" (
  echo.
  echo 未能启动。请查看上方提示信息。
  pause
)
exit /b %LAUNCH_STATUS%
