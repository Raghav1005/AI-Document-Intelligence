"""Application entrypoint and process health endpoints.

Health routes are public; product routes opt into explicit authentication
dependencies so public diagnostics do not require an access token.
"""

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router

app = FastAPI(
    title="Local AI Platform API",
    version="0.1.0",
    description="Local API for document intelligence and retrieval-augmented chat.",
)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)


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
