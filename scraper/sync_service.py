"""
scraper/sync_service.py

Orchestrates a full Busuu sync for a given user:
  1. Fetch data from Busuu API using cookie file
  2. Upsert user record
  3. Upsert all vocab items
  4. Upsert all grammar topics
  5. Update last_sync timestamp
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, VocabItem, GrammarTopic
from scraper.busuu_api import fetch_all

logger = logging.getLogger(__name__)


async def sync_user(
    db: AsyncSession,
    email: str,
    cookie_file: str,
    language: str = "es",
    native_language: str = "en",
) -> dict:
    """
    Full sync pipeline. Returns a summary dict.
    """
    logger.info("Starting Busuu sync for %s …", email)
    data = await fetch_all(cookie_file, language, native_lang=native_language)
    # Upsert user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(email=email, language=language, native_language=native_language)
        db.add(user)
        await db.flush()

    if data.get("user_uuid"):
        user.busuu_user_id = data["user_uuid"]
        user.native_language = native_language
    user.last_sync = datetime.now(timezone.utc)
    await db.flush()

    # Upsert vocab items
    vocab_count = 0
    for item in data["vocab"]:
        if not item.get("word"):
            continue

        last_reviewed = None
        if item.get("last_reviewed"):
            try:
                from datetime import datetime as dt
                last_reviewed = dt.fromisoformat(item["last_reviewed"])
            except Exception:
                pass

        values = dict(
            user_id       = user.id,
            busuu_item_id = item["busuu_item_id"],
            entity_id     = item["entity_id"],
            word          = item["word"],
            translation   = item["translation"],
            image_url     = item.get("image_url", ""),
            strength      = item["strength"],
            strength_raw  = item["strength_raw"],
            saved         = item.get("saved", False),
            last_reviewed = last_reviewed,
            raw           = item["raw"],
        )

        stmt = (
            pg_insert(VocabItem)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_user_vocab",
                set_={
                    "word":          values["word"],
                    "translation":   values["translation"],
                    "strength":      values["strength"],
                    "strength_raw":  values["strength_raw"],
                    "saved":         values["saved"],
                    "last_reviewed": values["last_reviewed"],
                    "raw":           values["raw"],
                },
            )
        )
        await db.execute(stmt)
        vocab_count += 1

    # Upsert grammar topics
    grammar_count = 0
    for topic in data["grammar"]:
        if not topic.get("unit_name"):
            continue

        values = dict(
            user_id        = user.id,
            busuu_topic_id = topic["busuu_topic_id"],
            unit_name      = topic["unit_name"],
            topic_name     = topic.get("topic_name", ""),
            cefr_level     = topic.get("cefr_level", ""),
            strength       = topic["strength"],
            strength_norm  = topic["strength_norm"],
            percentage     = topic["percentage"],
            completed      = topic["completed"],
            raw            = topic["raw"],
        )

        stmt = (
            pg_insert(GrammarTopic)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_user_grammar",
                set_={
                    "unit_name":     values["unit_name"],
                    "topic_name":    values["topic_name"],
                    "cefr_level":    values["cefr_level"],
                    "strength":      values["strength"],
                    "strength_norm": values["strength_norm"],
                    "percentage":    values["percentage"],
                    "completed":     values["completed"],
                    "raw":           values["raw"],
                },
            )
        )
        await db.execute(stmt)
        grammar_count += 1

    await db.commit()

    summary = {
        "user_id":       user.id,
        "busuu_user_id": data.get("user_uuid"),
        "vocab_synced":  vocab_count,
        "grammar_synced": grammar_count,
        "last_sync":     user.last_sync.isoformat(),
    }
    logger.info("Sync complete: %s", summary)
    return summary
