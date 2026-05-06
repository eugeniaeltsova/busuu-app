"""
exercises/utils.py

Utilities for selecting and formatting vocabulary and grammar data
before passing to the LLM.
"""
from __future__ import annotations

import random
from db.models import VocabItem, GrammarTopic


def pick_vocab(vocab: list[VocabItem], n: int = 10) -> list[VocabItem]:
    """
    Pick n vocab items weighted toward weaker words but including some strong ones.

    Distribution:
      50% weak   (strength_raw 0–1)
      30% medium (strength_raw 2–3)
      20% strong (strength_raw 4–5)
    """
    weak   = [v for v in vocab if v.strength_raw <= 1]
    medium = [v for v in vocab if 2 <= v.strength_raw <= 3]
    strong = [v for v in vocab if v.strength_raw >= 4]

    picked: list[VocabItem] = []
    picked += random.sample(weak,   min(int(n * 0.5), len(weak)))
    picked += random.sample(medium, min(int(n * 0.3), len(medium)))
    picked += random.sample(strong, min(int(n * 0.2), len(strong)))

    # Top up to n if needed
    remaining = [v for v in vocab if v not in picked]
    while len(picked) < n and remaining:
        picked.append(remaining.pop(random.randrange(len(remaining))))

    random.shuffle(picked)
    return picked[:n]


def pick_grammar(grammar: list[GrammarTopic], n: int = 3) -> list[GrammarTopic]:
    """
    Pick n grammar topics weighted toward weaker ones.

    Distribution:
      ~2 weak   (strength 0–1)
      ~1 medium (strength 2–3)
    """
    weak   = [g for g in grammar if g.strength <= 1]
    medium = [g for g in grammar if 2 <= g.strength <= 3]

    picked: list[GrammarTopic] = []
    picked += random.sample(weak,   min(2, len(weak)))
    picked += random.sample(medium, min(1, len(medium)))

    # Fallback if no weak/medium topics
    if not picked:
        picked = random.sample(grammar, min(n, len(grammar)))

    return picked[:n]


def format_vocab(items: list[VocabItem]) -> str:
    """Format vocab items as a readable list for the prompt."""
    return "\n".join(
        f"  - {v.word} = {v.translation} (strength {v.strength_raw}/5)"
        for v in items
    )


def format_grammar(items: list[GrammarTopic]) -> str:
    """Format grammar topics as a readable list for the prompt."""
    return "\n".join(
        f"  - {g.unit_name} ({g.cert_level or '?'}, mastery {g.percentage}%)"
        for g in items
    )


def prompt_summary(vocab: list[VocabItem], grammar: list[GrammarTopic]) -> str:
    """One-line summary of what was used — stored on the Exercise record."""
    vocab_str   = ", ".join(v.word for v in vocab[:5])
    grammar_str = ", ".join(g.unit_name for g in grammar[:2])
    return f"Vocab: {vocab_str}… | Grammar: {grammar_str}"


CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]

def infer_user_level(grammar: list[GrammarTopic]) -> str:
    if not grammar:
        return "A2"
    level_counts: dict[str, int] = {}
    for g in grammar:
        level = (g.cert_level or "").upper().strip()
        if level in CEFR_ORDER and g.completed:
            level_counts[level] = level_counts.get(level, 0) + 1
    if not level_counts:
        return "A2"
    for level in reversed(CEFR_ORDER):
        if level_counts.get(level, 0) >= 2:
            return level
    for level in reversed(CEFR_ORDER):
        if level_counts.get(level, 0) >= 1:
            return level
    return "A2"