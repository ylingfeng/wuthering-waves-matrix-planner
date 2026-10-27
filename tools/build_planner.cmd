@echo off
cd /d "%~dp0.."
python -m PyInstaller --noconfirm --onedir --windowed --name MatrixPlanner --icon "%CD%\assets\planner.ico" --paths . --distpath dist --workpath tmp/planner_build --specpath tmp --exclude-module torch --exclude-module tensorflow --exclude-module matplotlib --exclude-module pandas --exclude-module IPython --exclude-module cv2 tools/planner_launcher.py
if errorlevel 1 exit /b 1
python -m tools.package_planner
