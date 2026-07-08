import os
import time
import uuid
import threading
from collections import deque
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

YOUR_EMAIL = "25f1001126@ds.study.iitm.ac.in"

ASSIGNED_ORIGIN = "https://app-wg66hi.example.com"
EXAM_ORIGIN = os.environ.get("EXAM_ORIGIN", "")

ALLOWED_ORIGINS = {o for o in {ASSIGNED_ORIGIN, EXAM_ORIGIN} if o}

RATE_LIMIT = 12
RATE_WINDOW_SECS = 10

app = FastAPI(title="Ping Middleware Service")

rate_lock = threading.Lock()
CLIENTS: dict = {}


def check_rate_limit(client_id: str):
    now = time.time()
    with rate_lock:
        bucket = CLIENTS.setdefault(client_id, deque())
        while bucket and now - bucket[0] >= RATE_WINDOW_SECS:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT:
            retry = max(1, int(RATE_WINDOW_SECS - (now - bucket[0])) + 1)
            return False, retry
        bucket.append(now)
        return True, 0


def cors_headers_for(origin):
    if origin and origin in ALLOWED_ORIGINS:
        return {
            "Access-Control-Allow-Origin": origin,
            "Vary": "Origin",
            "Access-Control-Allow-Credentials": "false",
        }
    return {}


@app.middleware("http")
async def unified_middleware(request: Request, call_next):
    origin = request.headers.get("origin")

    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
            "Access-Control-Allow-Headers": request.headers.get(
                "access-control-request-headers", "*"
            ),
            "Access-Control-Max-Age": "600",
            **cors_headers_for(origin),
        }
        return JSONResponse(status_code=200, content={}, headers=headers)

    client_id = request.headers.get("X-Client-Id", "anonymous")
    ok, retry = check_rate_limit(client_id)
    if not ok:
        headers = {
            "Retry-After": str(retry),
            **cors_headers_for(origin),
        }
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers=headers,
        )

    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)

    response.headers["X-Request-ID"] = request_id
    for k, v in cors_headers_for(origin).items():
        response.headers[k] = v

    return response


@app.get("/ping")
async def ping(request: Request):
    return {"email": YOUR_EMAIL, "request_id": request.state.request_id}


@app.get("/")
def root():
    return {"status": "ok"}
