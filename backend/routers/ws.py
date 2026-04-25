"""
ws.py — WebSocket endpoint for real-time job status updates.

Uses Redis pub/sub to push status changes instantly to the frontend,
eliminating the need for 2-second polling intervals.

The frontend connects to /api/ws/{job_id} and receives JSON messages
with the same format as GET /api/jobs/{job_id}/status.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis
import json
import os
import asyncio

router = APIRouter()

_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


@router.websocket("/ws/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: str):
    await websocket.accept()

    try:
        r = redis.from_url(_redis_url)
        pubsub = r.pubsub()
        pubsub.subscribe(f"job_updates:{job_id}")
    except Exception:
        # If Redis isn't available, fall back to polling-style over WS
        try:
            await websocket.send_json({"error": "Redis not available"})
            await websocket.close()
        except Exception:
            pass
        return

    try:
        # Send current status immediately on connect
        current = r.get(f"job:{job_id}")
        if current:
            await websocket.send_text(current.decode())

        # Listen for pub/sub updates
        while True:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
            if message and message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                await websocket.send_text(data)

                # Close WebSocket when job is done or errored
                try:
                    parsed = json.loads(data)
                    if parsed.get("status") in ("ready", "error"):
                        await asyncio.sleep(0.5)  # Give client time to process
                        break
                except json.JSONDecodeError:
                    pass

            # Small sleep to prevent busy-looping
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[ws] WebSocket error for job {job_id}: {e}", flush=True)
    finally:
        try:
            pubsub.unsubscribe()
            pubsub.close()
        except Exception:
            pass
