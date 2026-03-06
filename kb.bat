@echo off
setlocal EnableDelayedExpansion
color 0A

:: ── Locate files next to this bat ────────────────────────────────────────────
set "DIR=%~dp0"
set "PS=%DIR%search_kb.ps1"
set "TOPICS=%DIR%topics.json"

:MAIN_MENU
cls
color 0A
echo.
echo  ==============================================================
echo   KB  //  Knowledge Base Search
echo  ==============================================================
echo.
echo   [1]  Search
echo   [2]  Browse by topic
echo   [3]  Commands only  ^(quick lookup^)
echo   [4]  Help
echo   [0]  Exit
echo.
echo  ==============================================================
echo.
set /p CHOICE=   Choose: 
if "!CHOICE!"=="1" goto SEARCH
if "!CHOICE!"=="2" goto BROWSE
if "!CHOICE!"=="3" goto QUICKREF
if "!CHOICE!"=="4" goto HELP
if "!CHOICE!"=="0" goto EXIT
goto MAIN_MENU


:SEARCH
cls
color 0A
echo.
echo  ==============================================================
echo   SEARCH
echo  ==============================================================
echo.
echo   Examples:
echo     add linux user        active directory      vlan trunk
echo     create ou             join desktop domain   vlsm example
echo     password aging        lock user account     ssh setup
echo.
echo   Leave blank to go back.
echo.
set /p QUERY=   Search: 
if "!QUERY!"=="" goto MAIN_MENU
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "!PS!" "!QUERY!"
echo.
set /p AGAIN=   Search again? (Y/N): 
if /i "!AGAIN!"=="Y" goto SEARCH
goto MAIN_MENU


:BROWSE
cls
color 0A
echo.
echo  ==============================================================
echo   BROWSE BY TOPIC
echo  ==============================================================
echo.

:: Build menu dynamically from topics.json using PowerShell
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t = Get-Content '!TOPICS!' | ConvertFrom-Json; $n=1; foreach ($cat in $t.categories) { Write-Host ('  ' + $cat.name.ToUpper()) -ForegroundColor White; Write-Host ('  ' + '-' * $cat.name.Length) -ForegroundColor DarkGray; foreach ($topic in $cat.topics) { Write-Host ('  [' + $n + ']  ' + $topic.display) -ForegroundColor Green; $n++ }; Write-Host '' }"

echo   [0]  Back
echo.
set /p BSEL=   Topic: 
if "!BSEL!"=="0" goto MAIN_MENU
if "!BSEL!"=="" goto BROWSE

:: Look up the query for the chosen number and run search
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t = Get-Content '!TOPICS!' | ConvertFrom-Json; $n=1; foreach ($cat in $t.categories) { foreach ($topic in $cat.topics) { if ($n -eq [int]'!BSEL!') { & '!PS!' $topic.query -MaxResults 20 }; $n++ } }"

echo.
set /p B2=   Press ENTER to browse again...
goto BROWSE


:QUICKREF
cls
color 0A
echo.
echo  ==============================================================
echo   COMMANDS ONLY
echo  ==============================================================
echo.
set /p QQUERY=   Lookup: 
if "!QQUERY!"=="" goto MAIN_MENU
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "!PS!" "!QQUERY!" -CommandOnly
echo.
set /p Q2=   Press ENTER to continue...
goto MAIN_MENU


:HELP
cls
color 0A
echo.
echo  ==============================================================
echo   HELP
echo  ==============================================================
echo.
echo   SEARCH TIPS
echo   -----------
echo   More keywords = more specific results.
echo   Fewer keywords = broader results.
echo.
echo   Examples:
echo     linux user               all Linux user management entries
echo     add linux user           specifically adding users
echo     create user aduc         GUI steps in ADUC
echo     join desktop domain      join a PC to the domain
echo     vlan trunk               VLAN trunk commands
echo     vlsm example             VLSM worked examples
echo.
echo   Result types:
echo     [COMMAND]  CLI / terminal commands  (green)
echo     [STEPS]    Numbered GUI steps       (yellow numbers)
echo     [PROSE]    Explanatory text
echo.
echo   FILES
echo   -----
echo     kb.bat               This menu
echo     search_kb.ps1        Search engine
echo     knowledge_base.csv   The database
echo     topics.json          Browse menu topics (auto-generated)
echo.
set /p H2=   Press ENTER...
goto MAIN_MENU


:EXIT
color 07
echo.
echo   Goodbye!
echo.
exit /b 0