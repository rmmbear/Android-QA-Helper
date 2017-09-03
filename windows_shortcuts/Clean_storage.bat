@echo off

title Helper - Storage Cleaner

set _root=%~dp0
set root=%_root:~0,-1%
set helper="%root%\helper\helper.exe"

echo.
call %helper% clean
echo.

pause
