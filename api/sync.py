"""
api/sync.py — Busuu data sync and vocab/grammar API routes.

Routes:
  POST /api/sync              → trigger Busuu fetch + DB upsert
  GET  /api/vocab/{email}     → vocab items as JSON
  GET  /api/grammar/{email}   → grammar topics as JSON
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import User, VocabItem, GrammarTopic
from scraper.sync_service import sync_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class SyncRequest(BaseModel):
    email:           EmailStr
    cookie_file:     str = "busuu_cookies.json"
    language:        str = "es"
    native_language: str = "en"


class SyncResponse(BaseModel):
    user_id:        int
    busuu_user_id:  str | None
    vocab_synced:   int
    grammar_synced: int
    last_sync:      str


class VocabOut(BaseModel):
    id:           int
    word:         str
    translation:  str | None
    strength:     float
    strength_raw: int
    saved:        bool

    class Config:
        from_attributes = True


class GrammarOut(BaseModel):
    id:         int
    unit_name:  str
    topic_name: str | None
    cefr_level: str | None
    strength:   int
    percentage: int
    completed:  bool

    class Config:
        from_attributes = True


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/api/sync", response_model=SyncResponse)
async def sync(req: SyncRequest, db: AsyncSession = Depends(get_db)):
    try:
        summary = await sync_user(
            db=db,
            email=req.email,
            cookie_file=req.cookie_file,
            language=req.language,
            native_language=req.native_language,
        )
    except PermissionError as exc:
        raise HTTPException(401, str(exc))
    except FileNotFoundError:
        raise HTTPException(400, f"Cookie file '{req.cookie_file}' not found.")
    except Exception as exc:
        logger.exception("Sync failed")
        raise HTTPException(500, f"Sync failed: {exc}")
    return summary


@router.get("/api/vocab/{email}", response_model=list[VocabOut])
async def get_vocab(email: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    return (await db.execute(
        select(VocabItem)
        .where(VocabItem.user_id == user.id)
        .order_by(VocabItem.strength)
    )).scalars().all()


@router.get("/api/grammar/{email}", response_model=list[GrammarOut])
async def get_grammar(email: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    return (await db.execute(
        select(GrammarTopic)
        .where(GrammarTopic.user_id == user.id)
        .order_by(GrammarTopic.strength)
    )).scalars().all()
