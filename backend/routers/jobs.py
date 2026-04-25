from fastapi import APIRouter, HTTPException
import redis
import json
import os
import shutil

router = APIRouter()

HISTORY_FILE = "storage/history.json"

try:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.from_url(redis_url)
    redis_client.ping()
except:
    redis_client = None

@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    if not redis_client:
        return {"id": job_id, "status": "analyzing", "progress": 30, "message": "Redis not connected."}
        
    status_str = redis_client.get(f"job:{job_id}")
    if not status_str:
        return {"id": job_id, "status": "uploading", "progress": 20, "message": "Queued for processing..."}
        
    return json.loads(status_str)

@router.get("/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    result = {
        "musicxml": f"/storage/results/{job_id}/output.musicxml",
        "midi": f"/storage/results/{job_id}/output.mid",
        "log": f"/storage/results/{job_id}/process.log"
    }
    # Include PDF only if it was generated
    pdf_path = os.path.join("storage", "results", job_id, "output.pdf")
    if os.path.exists(pdf_path):
        result["pdf"] = f"/storage/results/{job_id}/output.pdf"
    return result

@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job's files, Redis data, and history entry."""
    deleted_items = []

    # 1. Remove result files
    result_dir = os.path.join("storage", "results", job_id)
    if os.path.exists(result_dir):
        shutil.rmtree(result_dir, ignore_errors=True)
        deleted_items.append("results")

    # 2. Remove upload files
    upload_dir = os.path.join("storage", "uploads", job_id)
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir, ignore_errors=True)
        deleted_items.append("uploads")

    # 3. Remove Redis status
    if redis_client:
        try:
            redis_client.delete(f"job:{job_id}")
            deleted_items.append("redis")
        except Exception:
            pass

    # 4. Remove from history.json
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
            history = [h for h in history if h.get("id") != job_id]
            with open(HISTORY_FILE, "w") as f:
                json.dump(history, f)
            deleted_items.append("history")
        except Exception:
            pass

    return {"deleted": job_id, "items": deleted_items}

@router.get("/history")
async def get_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

