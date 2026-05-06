"""
api/main.py — FastAPI application entry point.

Mounts routers:
  - sync.py     → /api/sync, /api/vocab, /api/grammar
  - exercises.py → /api/exercise/*, /exercises
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from config import settings
from logging_config import configure_logging

configure_logging(debug=settings.DEBUG)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import init_db, get_db
from db.models import User, VocabItem, GrammarTopic
from api.sync import router as sync_router
from api.exercises import router as exercises_router

from fastapi.staticfiles import StaticFiles


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Busuu Exercise App", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="frontend/templates")

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


app.include_router(sync_router)
app.include_router(exercises_router)


# ── Web UI routes ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, email: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found — please sync first.")

    vocab = (await db.execute(
        select(VocabItem)
        .where(VocabItem.user_id == user.id)
        .order_by(VocabItem.strength)
    )).scalars().all()

    grammar = (await db.execute(
        select(GrammarTopic)
        .where(GrammarTopic.user_id == user.id)
        .order_by(GrammarTopic.strength)
    )).scalars().all()

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "user":          user,
        "vocab":         vocab,
        "grammar":       grammar,
        "vocab_count":   len(vocab),
        "grammar_count": len(grammar),
        "weak_vocab":    sum(1 for v in vocab if v.strength_raw == 0),
    })
