"""System and auth routes for the FastAPI app."""

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from api.app import ApiUser, app, require_access


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": exc.status_code, "error": str(exc.detail)},
    )


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.get("/api/vi/docs", include_in_schema=False)
def docs_alias_vi():
    return RedirectResponse(url="/api/v1/docs", status_code=307)


@app.get("/api/v1/auth/whoami")
def whoami(user: ApiUser = Depends(require_access(min_level=1))):
    return {
        "username": user.username,
        "role": user.role,
        "access_level": user.access_level,
        "permissions": sorted(user.permissions),
        "denied_permissions": sorted(user.denied_permissions),
    }

