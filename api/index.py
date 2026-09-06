"""Vercel entry point.

Vercel's Python runtime serves a module-level ASGI app named `app`. FastAPI is
already ASGI, so the only work here is path handling: vercel.json rewrites
/api/py/* to this function, and the function still receives the full original
path. Mounting the real app under that prefix strips it, so the routes in
recast.api.main stay written as /applications rather than /api/py/applications.

This whole file only works because the renderer is pure Python. With a headless
browser in the dependency tree the bundle would be several hundred megabytes and
no serverless function would take it.
"""
import sys
import pathlib

sys.path.insert(
    0,
    str(pathlib.Path(__file__).resolve().parents[1] / "src")
)

from fastapi import FastAPI

from recast.api.main import api

app = FastAPI(docs_url=None, redoc_url=None)
app.mount("/api/py", api)

__all__ = ["app"]