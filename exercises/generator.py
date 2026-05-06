"""
exercises/generator.py

Thin orchestrator:
  1. Fetch user's vocab + grammar from DB
  2. Pick and format items via utils
  3. Call the agent to generate the exercise
  4. Store result in Exercise table
  5. Return the Exercise object

Also handles feedback generation.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models import VocabItem, GrammarTopic, Exercise, User
from exercises.agent import run_agent
from exercises.client import get_client
from exercises.prompts import feedback_system, feedback_user_prompt
from exercises.utils import pick_vocab, pick_grammar, format_vocab, format_grammar, prompt_summary, infer_user_level

logger = logging.getLogger(__name__)


def _parse_feedback_json(raw: str) -> dict:
    candidates = [raw, raw.replace("```json", "").replace("```", "").strip()]
    for text in candidates:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    logger.error("Could not parse feedback JSON: %.200s", raw)
    raise ValueError("Feedback response was not valid JSON. Please try again.")


async def generate_exercise(
    db: AsyncSession,
    user: User,
    exercise_type: str,
) -> Exercise:
    """Generate an exercise, store in DB, return it."""

    # 1. Fetch from DB
    vocab = (await db.execute(
        select(VocabItem).where(VocabItem.user_id == user.id)
    )).scalars().all()

    grammar = (await db.execute(
        select(GrammarTopic).where(GrammarTopic.user_id == user.id)
    )).scalars().all()

    if not vocab:
        raise ValueError("No vocabulary found. Please sync your Busuu data first.")

    # 2. Pick and format
    selected_vocab   = pick_vocab(list(vocab), n=10)
    selected_grammar = pick_grammar(list(grammar), n=3) if grammar else []

    vocab_str   = format_vocab(selected_vocab)
    grammar_str = format_grammar(selected_grammar)
    user_level  = infer_user_level(list(grammar))
    logger.info("Inferred user level: %s", user_level)

    # 3. Run agent
    result = await run_agent(
        exercise_type, vocab_str, grammar_str, user_level,
        target_language=user.language,
        native_language=user.native_language,
    )
    # 4. Store in DB
    exercise = Exercise(
        user_id         = user.id,
        exercise_type   = exercise_type,
        content         = result["content"],
        answer_key      = result["answer_key"],
        difficulty      = result["difficulty"],
        prompt_summary  = prompt_summary(selected_vocab, selected_grammar),
        raw_response    = result["raw_args"],
        structured_data = result["structured_data"],
    )
    db.add(exercise)
    await db.commit()
    await db.refresh(exercise)

    logger.info("Exercise created: id=%s type=%s difficulty=%s",
                exercise.id, exercise_type, exercise.difficulty)
    return exercise


async def generate_feedback(
    db: AsyncSession,
    exercise: Exercise,
    user_answer: str,
    user: User | None = None,
) -> Exercise:
    """Generate AI feedback on user's answer, update and return Exercise."""
    client = get_client()

    response = await client.chat.completions.create(
        model=settings.AZURE_OPENAI_DEPLOYMENT,
        messages=[
                    {"role": "system", "content": feedback_system(
            target_language=user.language if user else "es",
            native_language=user.native_language if user else "en",
        )},
        {"role": "user", "content": feedback_user_prompt(
            exercise.exercise_type,
            exercise.content,
            exercise.answer_key,
            user_answer,
            target_language=user.language if user else "es",
            native_language=user.native_language if user else "en",
        )},
        ],
        temperature=0.3,
        max_tokens=800,
    )

    raw = response.choices[0].message.content.strip()
    parsed = _parse_feedback_json(raw)

    errors_text = "\n".join(
        f"  ✗ '{e['mistake']}' → '{e['correction']}': {e['explanation']}"
        for e in parsed.get("errors", [])
    ) or "  No errors found!"

    correct_text = "\n".join(
        f"  ✓ {c}" for c in parsed.get("correct", [])
    )

    feedback = (
        f"Score: {parsed.get('score', '?')}/100\n\n"
        f"{parsed.get('summary', '')}\n\n"
        f"What you got right:\n{correct_text}\n\n"
        f"Errors:\n{errors_text}\n\n"
        f"{parsed.get('encouragement', '')}"
    )

    exercise.user_answer = user_answer
    exercise.feedback    = feedback
    exercise.completed   = True
    await db.commit()
    await db.refresh(exercise)

    return exercise
