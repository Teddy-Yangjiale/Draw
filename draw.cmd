@echo off
setlocal
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -m pptdraw %*
) else (
  python -m pptdraw %*
)
