@echo off

title Helper - Show device information

set _root=%~dp0
set root=%_root:~0,-1%
set helper="%root%\helper\helper.exe"

echo.
call %helper% detailed-scan
echo.

pause
