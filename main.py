import os
import time
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

LOGGED_IN_EMAIL = "25f1001126@ds.study.iitm.ac.in"

ASSIGNED_ORIGIN = "https://app-wg66hi.example.com"
EXAM_ORIGIN = os.environ.get("EXAM_ORIGIN", "")  # set this in Render's Environment tab

ALLOWED_ORIGINS = [o for o in [ASSIGNED_ORIGIN, EXAM_ORIGIN] if o]

RATE_LIMIT_B = 12
RATE_LIMIT_WINDOW = 10
client_buckets = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Retry-After"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)  # never rate-limit preflight

    client_id = request.headers.get("X-Client-Id", "anonymous")
    now = time.time()
    timestamps = client_buckets.get(client_id, [])
    timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    if len(timestamps) >= RATE_LIMIT_B:
        retry = max(1, int(RATE_LIMIT_WINDOW - (now - timestamps[0])) + 1)
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(retry)},
        )
    timestamps.append(now)
    client_buckets[client_id] = timestamps
    return await call_next(request)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/ping")
async def ping(request: Request):
    return {"email": LOGGED_IN_EMAIL, "request_id": request.state.request_id}


@app.get("/")
def root():
    return {"status": "ok"}
