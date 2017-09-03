@echo off

title Helper - Quick recording

set _root=%~dp0
set root=%_root:~0,-1%
set helper="%root%\helper\helper.exe"

echo.
call %helper% record %userprofile%\Desktop
echo.

pause
