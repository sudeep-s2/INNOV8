@echo off
echo ===================================================
echo Starting Info2Impact Backend Server (FastAPI)
echo ===================================================
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
