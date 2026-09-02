@echo off
python -m pip install -r requirements.txt
python -m PyInstaller --clean --noconfirm --onefile --windowed --name AndoToolCarnet main.py
pause
