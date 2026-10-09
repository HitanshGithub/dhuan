"""The HTTP API behind the map. Runs under uvicorn locally and under Mangum on Lambda."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from . import forecast
from .config import settings
from .storage import get_json, storage

app = FastAPI(title="Dhuan", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin, "http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

if settings.storage == "local":  # deployed, CloudFront serves the run outputs straight from S3
    from fastapi.staticfiles import StaticFiles

    settings.out_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/data", StaticFiles(directory=settings.out_dir), name="data")


@app.get("/api/health")
def health():
    return {"ok": True, "storage": settings.storage, "llm": settings.llm}


@app.get("/api/latest")
def latest():
    """What the map needs to start: which run to show and where its files are."""
    store = storage()
    pointer = get_json(store, "latest.json")
    if not pointer:
        raise HTTPException(503, "No forecast run yet")
    meta = get_json(store, f"runs/{pointer['run_id']}/meta.json")
    meta["data_url"] = f"{settings.data_url}/runs/{pointer['run_id']}"
    return meta


@app.get("/api/forecast")
def point(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    result = forecast.point_forecast(lat, lon)
    if result is None:
        raise HTTPException(404, "Outside the forecast area (North India, 70-88E 22-34N) or no run yet")
    return result


@app.get("/api/advisory")
def advisory_text(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180), lang: str = Query("en", pattern="^(en|hi|pa)$"),
                  label: str = Query("", max_length=80)):
    """The plain-language advisory for a place, in English, Hindi or Punjabi."""
    from . import advisory

    fc = forecast.point_forecast(lat, lon)
    if fc is None:
        raise HTTPException(404, "Outside the forecast area or no run yet")
    return advisory.compose(fc, label, lang)


class Subscription(BaseModel):
    email: EmailStr
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    label: str = Field(default="", max_length=80)
    language: str = Field(default="en", pattern="^(en|hi|pa)$")


@app.post("/api/subscribe", status_code=201)
def subscribe(sub: Subscription):
    from . import alerts

    return alerts.subscribe(sub.email, sub.lat, sub.lon, sub.label, sub.language)


@app.post("/api/subscribe/{sub_id}/preview")
def preview(sub_id: str):
    """Send this subscriber the advisory for the current forecast right away (used in the demo)."""
    from . import alerts

    sent = alerts.send_now(sub_id)
    if sent is None:
        raise HTTPException(404, "Unknown subscription")
    return sent
