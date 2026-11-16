"""Request guards for web_ui.py, the local lab console on 127.0.0.1:8000.

CORS only stops other sites READING replies. These guards stop them making the machine do work:
- Host check: a DNS-rebound attacker domain is same-origin to the browser, but keeps its own Host header.
- Origin check on writes: a cross-site form POST needs no preflight, so it would run without this.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
ALLOWED_ORIGINS = {"http://127.0.0.1:8000", "http://localhost:8000"}


def install_guards(app: FastAPI) -> None:
    @app.middleware("http")
    async def same_origin_writes(request: Request, call_next):
        origin = request.headers.get("origin")
        # No Origin header: curl or scripts on this machine, which browsers cannot forge cross-site.
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin is not None and origin not in ALLOWED_ORIGINS:
            return JSONResponse({"detail": "Cross-site request refused"}, status_code=403)
        return await call_next(request)

    # Added last so it runs first: a rebound Host is refused before anything else.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
