"""
tests/test_short_story.py

Tests for short story exercise generation (agent + tool parsing).
Azure OpenAI is mocked — no credentials or network calls required.

To test against a real Azure deployment instead:
    python -m pytest tests/test_short_story.py -m integration
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from exercises.tools import parse_short_story
from exercises.agent import run_agent


SAMPLE_VOCAB = """
  - el lavabo = the sink (strength 0/5)
  - el despertador = the alarm clock (strength 1/5)
  - hacer la cama = to make the bed (strength 1/5)
  - el vecino = the neighbour (strength 2/5)
  - la farmacia = the pharmacy (strength 2/5)
"""

SAMPLE_GRAMMAR = """
  - Discovering "hay" and "está" (A2, mastery 67%)
  - "Muy" and "mucho" (A2, mastery 54%)
"""

SAMPLE_STORY_ARGS = {
    "title": "Una mañana ocupada",
    "story": "María se despierta con el despertador. Va al lavabo y hace la cama.",
    "story_translation": "Maria wakes up with the alarm clock. She goes to the sink and makes the bed.",
    "questions": [
        {
            "question": "¿Con qué se despierta María?",
            "answer": "Con el despertador.",
        },
        {
            "question": "¿Qué hace después de ir al lavabo?",
            "answer": "Hace la cama.",
        },
    ],
    "difficulty": "A2",
    "vocab_used": ["el despertador", "el lavabo", "hacer la cama"],
    "grammar_used": ["Discovering \"hay\" and \"está\""],
}


def _make_mock_response(tool_name: str, args: dict) -> MagicMock:
    tool_call = MagicMock()
    tool_call.function.name = tool_name
    tool_call.function.arguments = json.dumps(args)

    message = MagicMock()
    message.tool_calls = [tool_call]

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


class TestParseShortStoryIntegration:
    def test_parse_returns_content_and_answer_key(self):
        content, answer_key, structured = parse_short_story(SAMPLE_STORY_ARGS)

        assert SAMPLE_STORY_ARGS["story"] in content
        assert SAMPLE_STORY_ARGS["title"] in content

        parsed_key = json.loads(answer_key)
        assert parsed_key["story_translation"] == SAMPLE_STORY_ARGS["story_translation"]
        assert len(parsed_key["answers"]) == 2

    def test_structured_data_contains_questions(self):
        _, _, structured = parse_short_story(SAMPLE_STORY_ARGS)
        assert len(structured["questions"]) == 2
        assert structured["questions"][0]["question"] == SAMPLE_STORY_ARGS["questions"][0]["question"]

    def test_structured_data_contains_vocab_and_grammar(self):
        _, _, structured = parse_short_story(SAMPLE_STORY_ARGS)
        assert "el despertador" in structured.get("vocab_used", [])


class TestRunAgentMocked:
    @pytest.mark.asyncio
    async def test_run_agent_short_story_success(self):
        mock_response = _make_mock_response("generate_short_story", SAMPLE_STORY_ARGS)
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("exercises.agent.get_client", return_value=mock_client):
            result = await run_agent(
                exercise_type="short_story",
                vocab_str=SAMPLE_VOCAB,
                grammar_str=SAMPLE_GRAMMAR,
                user_level="A2",
                target_language="Spanish",
                native_language="English",
            )

        assert result["difficulty"] == "A2"
        assert SAMPLE_STORY_ARGS["story"] in result["content"]
        assert len(result["structured_data"]["questions"]) == 2

    @pytest.mark.asyncio
    async def test_run_agent_raises_on_missing_tool_call(self):
        message = MagicMock()
        message.tool_calls = None
        choice = MagicMock()
        choice.message = message
        mock_response = MagicMock()
        mock_response.choices = [choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("exercises.agent.get_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="no tool call"):
                await run_agent(
                    exercise_type="short_story",
                    vocab_str=SAMPLE_VOCAB,
                    grammar_str=SAMPLE_GRAMMAR,
                )

    @pytest.mark.asyncio
    async def test_run_agent_raises_on_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown exercise type"):
            await run_agent(exercise_type="unknown", vocab_str="", grammar_str="")
