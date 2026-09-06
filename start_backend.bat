@echo off
echo ===================================================
echo Starting TransformAI Backend Server (FastAPI)
echo ===================================================
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
