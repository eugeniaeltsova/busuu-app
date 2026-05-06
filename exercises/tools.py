"""
exercises/tools.py

OpenAI function calling tool definitions.

Each tool has:
  - SCHEMA   : JSON schema passed to the API (defines the function signature)
  - parser   : extracts content + answer_key + structured_data from tool call args

The agent calls one of these tools based on the user's exercise choice.
"""
from __future__ import annotations

import json

# ── Tool schemas ──────────────────────────────────────────────────────────────

SHORT_STORY_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_short_story",
        "description": (
            "Generate a short story in Spanish using the learner's vocabulary "
            "and grammar topics. Returns the story and comprehension questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title of the story",
                },
                "story": {
                    "type": "string",
                    "description": "The Spanish story, 150-200 words",
                },
                "story_translation": {
                    "type": "string",
                    "description": "Full English translation of the story",
                },
                "questions": {
                    "type": "array",
                    "description": "3-4 comprehension questions about the story",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "answer":   {"type": "string"},
                        },
                        "required": ["question", "answer"],
                    },
                },
                "vocab_used": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Spanish words from the vocab list used in the story",
                },
                "grammar_used": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Grammar topics incorporated into the story",
                },
                "difficulty": {
                    "type": "string",
                    "enum": ["A1", "A2", "B1", "B2", "C1"],
                    "description": "CEFR difficulty level of the story",
                },
            },
            "required": ["title", "story", "story_translation", "questions", "difficulty"],
        },
    },
}


TRANSLATION_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_translation",
        "description": (
            "Generate a translation exercise with sentences to translate "
            "between Spanish and English."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "instructions": {
                    "type": "string",
                    "description": "Brief instructions for the learner",
                },
                "sentences": {
                    "type": "array",
                    "description": "6-8 sentences to translate",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id":     {"type": "integer"},
                            "source": {"type": "string", "description": "Sentence to translate"},
                            "target": {"type": "string", "description": "Correct translation"},
                            "notes":  {"type": "string", "description": "Optional grammar note"},
                        },
                        "required": ["id", "source", "target"],
                    },
                },
                "vocab_used":   {"type": "array", "items": {"type": "string"}},
                "grammar_used": {"type": "array", "items": {"type": "string"}},
                "difficulty": {
                    "type": "string",
                    "enum": ["A1", "A2", "B1", "B2", "C1"],
                },
            },
            "required": ["instructions", "sentences", "difficulty"],
        },
    },
}


GAP_FILL_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_gap_fill",
        "description": (
            "Generate a gap-fill exercise where the learner fills in missing "
            "Spanish words from a word bank."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "instructions": {
                    "type": "string",
                    "description": "Brief instructions for the learner",
                },
                "text_with_gaps": {
                    "type": "string",
                    "description": "Spanish text with [___] replacing target words (8-12 gaps)",
                },
                "word_bank": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Correct answers plus 3-4 distractors, shuffled",
                },
                "answer_key": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Correct answers in order",
                },
                "full_text": {
                    "type": "string",
                    "description": "Complete text with all gaps filled correctly",
                },
                "vocab_used":   {"type": "array", "items": {"type": "string"}},
                "grammar_used": {"type": "array", "items": {"type": "string"}},
                "difficulty": {
                    "type": "string",
                    "enum": ["A1", "A2", "B1", "B2", "C1"],
                },
            },
            "required": ["instructions", "text_with_gaps", "word_bank", "answer_key", "full_text", "difficulty"],
        },
    },
}

# Map exercise type → tool schema
TOOL_MAP: dict[str, dict] = {
    "short_story": SHORT_STORY_TOOL,
    "translation": TRANSLATION_TOOL,
    "gap_fill":    GAP_FILL_TOOL,
}

EXERCISE_TYPES = list(TOOL_MAP.keys())


# ── Result parsers ────────────────────────────────────────────────────────────
# Each parser returns (content, answer_key, structured_data)
# content        — plain text for storage/fallback
# answer_key     — JSON string with correct answers
# structured_data — full dict for UI rendering

def parse_short_story(args: dict) -> tuple[str, str, dict]:
    """Parse short story tool call result."""
    questions = args.get("questions", [])

    # content is just the story text — questions rendered separately by UI
    content = f"{args.get('title', '')}\n\n{args.get('story', '')}"

    answer_key = json.dumps({
        "story_translation": args.get("story_translation", ""),
        "answers": [q.get("answer", "") for q in questions],
    }, ensure_ascii=False)

    structured_data = {
        "title":             args.get("title", ""),
        "story":             args.get("story", ""),
        "story_translation": args.get("story_translation", ""),
        "questions":         questions,
        "vocab_used":        args.get("vocab_used", []),
        "grammar_used":      args.get("grammar_used", []),
    }

    return content, answer_key, structured_data


def parse_translation(args: dict) -> tuple[str, str, dict]:
    """Parse translation tool call result."""
    sentences = args.get("sentences", [])

    content = (
        f"{args.get('instructions', '')}\n\n"
        + "\n".join(f"{s['id']}. {s['source']}" for s in sentences)
    )

    answer_key = json.dumps(
        {str(s["id"]): {"target": s["target"], "notes": s.get("notes", "")} for s in sentences},
        ensure_ascii=False,
    )

    structured_data = {
        "instructions": args.get("instructions", ""),
        "sentences":    sentences,
        "vocab_used":   args.get("vocab_used", []),
        "grammar_used": args.get("grammar_used", []),
    }

    return content, answer_key, structured_data


def parse_gap_fill(args: dict) -> tuple[str, str, dict]:
    """Parse gap-fill tool call result."""
    word_bank = ", ".join(args.get("word_bank", []))

    content = (
        f"{args.get('instructions', '')}\n\n"
        f"{args.get('text_with_gaps', '')}\n\n"
        f"Word bank: {word_bank}"
    )

    answer_key = json.dumps({
        "answers":   args.get("answer_key", []),
        "full_text": args.get("full_text", ""),
    }, ensure_ascii=False)

    structured_data = {
        "instructions":  args.get("instructions", ""),
        "text_with_gaps": args.get("text_with_gaps", ""),
        "word_bank":     args.get("word_bank", []),
        "answer_key":    args.get("answer_key", []),
        "full_text":     args.get("full_text", ""),
        "vocab_used":    args.get("vocab_used", []),
        "grammar_used":  args.get("grammar_used", []),
    }

    return content, answer_key, structured_data


PARSER_MAP = {
    "short_story": parse_short_story,
    "translation": parse_translation,
    "gap_fill":    parse_gap_fill,
}
