"""
exercises/prompts.py

All prompt templates used by the exercise agent.
Kept separate so they can be tuned independently of the logic.
"""

# Language code → full name mapping for prompts
LANGUAGE_NAMES = {
    "es": "Spanish", "fr": "French", "de": "German",
    "it": "Italian", "pt": "Portuguese", "zh": "Chinese",
    "ja": "Japanese", "ar": "Arabic", "tr": "Turkish",
    "pl": "Polish", "ko": "Korean", "ru": "Russian",
    "nl": "Dutch", "en": "English",
}


def lang_name(code: str) -> str:
    """Convert language code to full name, e.g. 'es' -> 'Spanish'."""
    return LANGUAGE_NAMES.get(code.lower(), code.upper())


# ── System prompts ────────────────────────────────────────────────────────────

def agent_system(target_language: str, native_language: str) -> str:
    return f"""You are a {lang_name(target_language)} language teacher generating exercises for an adult learner.
The learner's native language is {lang_name(native_language)}.
You have access to tools for generating different types of exercises.
Always call the appropriate tool — never respond with plain text."""


def feedback_system(target_language: str, native_language: str) -> str:
    return f"""You are a helpful {lang_name(target_language)} language teacher giving feedback on a learner's exercise.
Be encouraging but accurate. Point out errors clearly and explain the correct form.
Respond in {lang_name(native_language)}. Keep feedback concise.
Always respond with valid JSON only — no markdown, no backticks."""




# ── User prompt templates ─────────────────────────────────────────────────────

def short_story_user_prompt(
    vocab_str: str,
    grammar_str: str,
    user_level: str = "A2",
    target_language: str = "es",
    native_language: str = "en",
) -> str:
    tl = lang_name(target_language)
    nl = lang_name(native_language)
    return f"""You are a creative {tl} short-story writer crafting a story for a {nl}-speaking learner at {user_level} level.

Write a short story in {tl} with these qualities:
- Has a clear conflict and resolution (catharsis)
- Is either funny OR detective/mystery OR horror in style — choose one
- Is narratively coherent with a beginning, middle and end
- Uses natural, idiomatic {tl} appropriate for {user_level} level
- Is 150-200 words

Vocabulary to weave in naturally (use as many as possible):
{vocab_str}

Grammar topics to incorporate:
{grammar_str}

The story translation must be in {nl}. The comprehension questions must be in {tl}.
Call the generate_short_story tool with the result."""


def translation_user_prompt(
    vocab_str: str,
    grammar_str: str,
    user_level: str = "A2",
    target_language: str = "es",
    native_language: str = "en",
) -> str:
    tl = lang_name(target_language)
    nl = lang_name(native_language)
    return f"""Generate a translation exercise for a {tl} learner at {user_level} level.
Direction: {nl} to {tl} only.
The learner reads a {nl} sentence and must write the {tl} translation.

Vocabulary to use (include as many as naturally possible):
{vocab_str}

Grammar topics to practise:
{grammar_str}

Generate 6-8 sentences. Each sentence must have a clear, natural {tl} translation.
Call the generate_translation tool with the result."""


def gap_fill_step1_prompt(
    vocab_str: str,
    grammar_str: str,
    user_level: str = "A2",
    target_language: str = "es",
    native_language: str = "en",
) -> str:
    tl = lang_name(target_language)
    return f"""Write a short paragraph or story in {tl} (8-10 sentences) for a learner at {user_level} level, using some of the words from {vocab_str} and some topics from {grammar_str}.
The text must be a single coherent naturally sounding text in {tl} with a clear narrative flow — NOT a numbered list of separate sentences.

Use grammar topics from {grammar_str} and vocabulary from {vocab_str} ONLY where they fit naturally in context. Do not use vocabulary items as direct quotes or dialogue.
Integrate them naturally into the narrative as part of normal sentences.
Vocabulary (use where natural):
{vocab_str}

Grammar topics (use where natural):
{grammar_str}

Return only the {tl} text — no gaps, no explanations, no formatting."""


def gap_fill_step2_prompt(paragraph: str, target_language: str = "es", native_language: str = "en") -> str:
    tl = lang_name(target_language)
    nl = lang_name(native_language)
    return f"""Given this {tl} text, create a gap-fill exercise.

Text:
{paragraph}

Instructions:
- Replace 6-8 words or short phrases with [___]
- Choose words that are interesting to practise — vocabulary items, verb forms, connectors
- Keep the gaps challenging but fair
- Add 3-4 distractor words to the word bank that do not appear in the text
- The instructions for the learner must be in {nl}

Call the generate_gap_fill tool with the result."""


def feedback_user_prompt(
    exercise_type: str,
    content: str,
    answer_key: str,
    user_answer: str,
    target_language: str = "es",
    native_language: str = "en",
) -> str:
    tl = lang_name(target_language)
    nl = lang_name(native_language)
    return f"""A {tl} learner completed a {exercise_type} exercise.

Exercise:
{content}

Correct answer / answer key:
{answer_key}

Learner's answer:
{user_answer}

The {user_answer} must be in {tl}, if not, flag a mistake.

Return JSON (respond in {nl}):
{{
  "score": 0-100,
  "summary": "one sentence overall assessment",
  "correct": ["things the learner got right"],
  "errors": [
    {{"mistake": "what they wrote", "correction": "correct form", "explanation": "why"}}
  ],
  "encouragement": "a short motivating message"

}}"""
