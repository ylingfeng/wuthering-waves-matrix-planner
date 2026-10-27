@echo off
cd /d "%~dp0"
python -X utf8 -m tools.planner_dev_server --port 8765
pause
