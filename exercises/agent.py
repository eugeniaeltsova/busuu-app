"""
exercises/agent.py

The exercise agent. Receives exercise type + formatted vocab/grammar,
calls Azure OpenAI with the appropriate tool via function calling,
and returns parsed (content, answer_key, difficulty, structured_data, raw_args).
"""
from __future__ import annotations

import json
import logging

from exercises.client import get_client
from exercises.prompts import (
    agent_system,
    short_story_user_prompt,
    translation_user_prompt,
    gap_fill_user_prompt,
)
from exercises.tools import TOOL_MAP, PARSER_MAP

logger = logging.getLogger(__name__)

USER_PROMPT_MAP = {
    "short_story": short_story_user_prompt,
    "translation": translation_user_prompt,
    "gap_fill":    gap_fill_user_prompt,
}


    
async def run_agent(
    exercise_type: str,
    vocab_str: str,
    grammar_str: str,
    user_level: str = "A2",
    target_language: str = "Spanish",
    native_language: str = "English",
) -> dict:
    """
    Call the LLM agent with the appropriate tool for the given exercise type.

    Returns a dict with:
      - content         : plain text exercise (story text only for short_story)
      - answer_key      : JSON string with correct answers
      - difficulty      : CEFR level string (e.g. "B1")
      - structured_data : full structured dict for UI rendering
      - raw_args        : raw parsed tool call arguments
    """
    if exercise_type not in TOOL_MAP:
        raise ValueError(f"Unknown exercise type: '{exercise_type}'. Choose from: {list(TOOL_MAP.keys())}")

    tool        = TOOL_MAP[exercise_type]
    parser      = PARSER_MAP[exercise_type]
    user_prompt = USER_PROMPT_MAP[exercise_type](vocab_str, grammar_str, user_level, target_language, native_language)
    client = get_client()
    logger.info("Agent calling tool '%s' …", tool["function"]["name"])

    from config import settings
    response = await client.chat.completions.create(
        model=settings.AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": agent_system(target_language, native_language)},
            {"role": "user",   "content": user_prompt},
        ],
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": tool["function"]["name"]}},
        temperature=1.0,
        max_tokens=2000,
    )

    tool_calls = response.choices[0].message.tool_calls
    if not tool_calls:
        raise RuntimeError(
            f"Azure OpenAI returned no tool call for exercise type '{exercise_type}'. "
            "Check your deployment name and API version."
        )
    tool_call = tool_calls[0]
    raw_args  = json.loads(tool_call.function.arguments)

    logger.info("Tool call received: %s", tool_call.function.name)

    # Parser now returns (content, answer_key, structured_data)
    content, answer_key, structured_data = parser(raw_args)

    return {
        "content":         content,
        "answer_key":      answer_key,
        "difficulty":      raw_args.get("difficulty", ""),
        "structured_data": structured_data,
        "raw_args":        raw_args,
    }
