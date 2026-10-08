@echo off
cd /d "%~dp0"
py -3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8520
