from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Form
import uuid
import os
import shutil
import json
import redis

router = APIRouter()

UPLOAD_DIR = "storage/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Connect to Redis for writing initial job status
try:
    _redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    _redis_client = redis.from_url(_redis_url)
    _redis_client.ping()
except Exception:
    _redis_client = None

# --- Celery vs BackgroundTasks ---
# Try to dispatch via Celery first (scalable, separate worker process).
# Fall back to FastAPI BackgroundTasks if Celery broker is unreachable
# (e.g., local dev without Docker).
_USE_CELERY = False
try:
    if _redis_client:
        from worker.tasks import process_audio as _celery_task
        _USE_CELERY = True
        print("[upload] Celery broker available — using Celery for task dispatch", flush=True)
except Exception:
    print("[upload] Celery broker not available — falling back to BackgroundTasks", flush=True)


def _run_process_audio_sync(job_id: str, file_path: str, time_signature: str, audio_type: str):
    """Thin wrapper that imports and calls the task function directly (no Celery broker needed)."""
    from worker.tasks import process_audio as _task
    _task(job_id, file_path, time_signature, audio_type)


@router.post("/upload")
async def upload_audio(
    background_tasks: BackgroundTasks,
    time_signature: str = Form("auto"),
    audio_type: str = Form("piano"),
    file: UploadFile = File(...),
):
    if not file.filename.endswith((".mp3", ".wav")):
        raise HTTPException(status_code=400, detail="Unsupported format")

    job_id = str(uuid.uuid4())
    job_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    file_path = os.path.join(job_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Write an initial status to Redis immediately so the frontend shows progress
    if _redis_client:
        _redis_client.set(
            f"job:{job_id}",
            json.dumps({"id": job_id, "status": "analyzing", "progress": 10, "message": "Upload concluído, iniciando processamento..."}),
        )

    # Dispatch task via Celery or BackgroundTasks
    if _USE_CELERY:
        _celery_task.delay(job_id, file_path, time_signature, audio_type)
    else:
        background_tasks.add_task(_run_process_audio_sync, job_id, file_path, time_signature, audio_type)

    return {"job_id": job_id, "status": "uploading"}
