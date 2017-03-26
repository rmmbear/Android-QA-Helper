@echo off

title Helper - Quick install

set _root=%~dp0
set root=%_root:~0,-1%
set helper="%root%\helper\helper.exe"

echo.
echo To install applications using this shortcut, drag and drop files you want to install onto the 'Install.bat' file itself -- not the command line! You can install as many apk files as you like -- helper will install them one by one. When pushing obb files, there may be as many obb files as you like, but only one apk file may be present.
echo.
call %helper% -i %*
echo.
pause
