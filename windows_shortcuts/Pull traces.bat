@echo off

title Helper - Quick pull traces

set _root=%~dp0
set root=%_root:~0,-1%
set helper="%root%\helper\helper.exe"

echo.
call %helper% traces %userprofile%\Desktop
echo.

pause
