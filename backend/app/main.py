"""Application entrypoint and process health endpoints.

This module intentionally exposes only infrastructure health at this stage.
Protected product APIs are added with their corresponding feature work.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Local AI Platform API",
    version="0.1.0",
    description="Local API for document intelligence and retrieval-augmented chat.",
)


@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    """Report that the API process can accept requests."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> JSONResponse:
    """Report startup readiness; dependency checks arrive with database features."""
    return JSONResponse(
        status_code=200,
        content={"status": "ready", "checks": {"api": "ok"}},
    )
