"""Isolated, production-asset-only entrypoint for a temporary public preview."""
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .main import create_app, PROJECT_ROOT


SHARE_ROOT = PROJECT_ROOT / ".runtime" / "share"
SITE_ROOT = SHARE_ROOT / "site"
app = create_app(SHARE_ROOT / "data")
# The public preview does not publish the development API explorer.
app.router.routes = [route for route in app.router.routes if route.path not in {
    "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"
}]


@app.middleware("http")
async def public_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", include_in_schema=False)
def homepage():
    return FileResponse(SITE_ROOT / "index.html")


app.mount("/assets", StaticFiles(directory=SITE_ROOT / "assets"), name="public-assets")

ALLOWED_CAMPUS_IMAGES = {
    "01_杭州校区_实训基地_透视图.jpg",
    "02_杭州校区_实训基地_鸟瞰图.jpg",
    "03_杭州校区_东校区公寓_鸟瞰图.jpg",
    "04_杭州校区_公寓_透视图.jpg",
}


@app.get("/references/campus/{filename}", include_in_schema=False)
def campus_image(filename: str):
    if filename not in ALLOWED_CAMPUS_IMAGES:
        raise HTTPException(404, "图片不存在")
    return FileResponse(PROJECT_ROOT / "public" / "references" / "campus" / filename)
