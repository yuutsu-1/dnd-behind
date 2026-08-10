from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import auth, campaigns, characters, compendium, ws

app = FastAPI(
    title="DnD Behind — Character Manager API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(characters.router, prefix="/api")
app.include_router(compendium.router, prefix="/api")
app.include_router(ws.router)  # WebSocket has no /api prefix — avoids proxy issues


@app.get("/health")
async def health():
    return {"status": "ok"}
