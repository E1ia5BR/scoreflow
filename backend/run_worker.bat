@echo off
echo Starting Celery worker...
echo Note: On Windows, --pool=solo is required to prevent tasks from hanging.

call .\venv\Scripts\activate
celery -A worker.tasks worker --loglevel=info --pool=solo
