from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from routers import upload, jobs, ws
import time
from collections import defaultdict

app = FastAPI(title="ScoreFlow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Rate Limiting (in-memory, per-IP) ---
# Max 5 uploads per IP per hour
_RATE_LIMIT = 5
_RATE_WINDOW = 3600  # 1 hour in seconds
_rate_store: dict[str, list[float]] = defaultdict(list)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Only rate-limit uploads
    if request.url.path == "/api/upload" and request.method == "POST":
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Clean old entries
        _rate_store[client_ip] = [t for t in _rate_store[client_ip] if now - t < _RATE_WINDOW]

        if len(_rate_store[client_ip]) >= _RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Max 5 uploads per hour."},
            )

        _rate_store[client_ip].append(now)

    return await call_next(request)

app.mount("/storage", StaticFiles(directory="storage"), name="storage")

app.include_router(upload.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(ws.router, prefix="/api")

@app.get("/")
def read_root():
    return {"status": "ok", "service": "ScoreFlow MVP"}

@app.on_event("startup")
async def startup_cleanup():
    """Clean up old files on server start."""
    try:
        from cleanup import cleanup_old_jobs
        cleanup_old_jobs(max_age_days=7)
    except Exception as e:
        print(f"Startup cleanup failed: {e}", flush=True)
