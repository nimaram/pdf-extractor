from fastapi import Request
from fastapi.responses import JSONResponse
import time

rate_limits = {}
WINDOW = 60  # seconds
LIMIT = 20


# Custom Rate Limiter
async def rate_limiter(request: Request, call_next):
    # Skip docs and openapi routes
    if (
        request.url.path.startswith("/docs")
        or request.url.path.startswith("/openapi")
        or request.url.path.startswith("/redoc")
    ):
        return await call_next(request)

    ip = request.client.host
    now = time.time()
    window_start = now - WINDOW

    calls = [t for t in rate_limits.get(ip, []) if t > window_start]

    if len(calls) >= LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too Many Requests. Try again later."},
        )

    calls.append(now)
    rate_limits[ip] = calls

    response = await call_next(request)
    return response
