@echo off
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --clean --noconfirm --onefile --windowed --name AndoToolCarnet main.py
echo EXE cree dans dist\AndoToolCarnet.exe
pause
