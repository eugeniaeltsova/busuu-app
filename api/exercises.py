"""
api/exercises.py — Exercise generation, feedback, and listing routes.

Routes:
  POST /api/exercise/generate          → generate a new exercise
  POST /api/exercise/{id}/feedback     → submit answer + get AI feedback
  GET  /api/exercises/{email}          → list exercises for a user
  GET  /exercises                      → exercises UI page
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import time
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import User, Exercise
from exercises.generator import generate_exercise, generate_feedback
from exercises.tools import EXERCISE_TYPES

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


# ── Schemas ───────────────────────────────────────────────────────────────────

_rate_limit: dict[str, float] = {}
_RATE_LIMIT_SECONDS = 15


def _check_rate_limit(email: str) -> None:
    now = time.monotonic()
    since = now - _rate_limit.get(email, 0)
    if since < _RATE_LIMIT_SECONDS:
        wait = int(_RATE_LIMIT_SECONDS - since) + 1
        raise HTTPException(429, f"Wait {wait}s before generating another exercise.")
    _rate_limit[email] = now


class GenerateRequest(BaseModel):
    email:         EmailStr
    exercise_type: str = "short_story"


class FeedbackRequest(BaseModel):
    user_answer: str


class ExerciseOut(BaseModel):
    id:              int
    exercise_type:   str
    content:         str
    answer_key:      str | None = None
    difficulty:      str | None
    prompt_summary:  str | None
    completed:       bool
    feedback:        str | None
    structured_data: dict | None = None
    created_at:      datetime | None = None

    class Config:
        from_attributes = True


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/api/exercise/generate", response_model=ExerciseOut)
async def generate(req: GenerateRequest, db: AsyncSession = Depends(get_db)):
    """Generate a new exercise for the user."""
    _check_rate_limit(req.email)

    if req.exercise_type not in EXERCISE_TYPES:
        raise HTTPException(400, f"Invalid type. Choose from: {EXERCISE_TYPES}")

    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found — please sync first.")

    try:
        exercise = await generate_exercise(db, user, req.exercise_type)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("Exercise generation failed")
        raise HTTPException(500, f"Generation failed: {e}")

    return exercise


@router.post("/api/exercise/{exercise_id}/feedback", response_model=ExerciseOut)
async def feedback(exercise_id: int, req: FeedbackRequest, db: AsyncSession = Depends(get_db)):
    """Submit user answer and get AI feedback."""
    result = await db.execute(select(Exercise).where(Exercise.id == exercise_id))
    exercise = result.scalar_one_or_none()
    if not exercise:
        raise HTTPException(404, "Exercise not found.")

    try:
        user_result = await db.execute(select(User).where(User.id == exercise.user_id))
        exercise_user = user_result.scalar_one_or_none()
        exercise = await generate_feedback(db, exercise, req.user_answer, user=exercise_user)
    except Exception as e:
        logger.exception("Feedback generation failed")
        raise HTTPException(500, f"Feedback failed: {e}")

    return exercise


@router.get("/api/exercises/{email}", response_model=list[ExerciseOut])
async def list_exercises(email: str, db: AsyncSession = Depends(get_db)):
    """List last 10 exercises for a user, newest first."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    return (await db.execute(
        select(Exercise)
        .where(Exercise.user_id == user.id)
        .order_by(Exercise.created_at.desc())
        .limit(10)
    )).scalars().all()


@router.get("/exercises", response_class=HTMLResponse)
async def exercises_page(request: Request, email: str, db: AsyncSession = Depends(get_db)):
    """Exercise UI page."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found — please sync first.")

    exercises = (await db.execute(
        select(Exercise)
        .where(Exercise.user_id == user.id)
        .order_by(Exercise.created_at.desc())
        .limit(10)
    )).scalars().all()

    return templates.TemplateResponse(request=request, name="exercises.html", context={
        "user":           user,
        "exercises":      exercises,
        "exercise_types": EXERCISE_TYPES,
    })
