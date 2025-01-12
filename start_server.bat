@echo off
call conda activate aprvai-py310
echo GOOGLE_CLIENT_ID: %GOOGLE_CLIENT_ID%
uvicorn app.main:app --reload --port 9000
