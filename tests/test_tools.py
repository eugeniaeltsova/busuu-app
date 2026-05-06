"""
tests/test_tools.py

Unit tests for exercises/tools.py parsers:
  - parse_short_story
  - parse_translation
  - parse_gap_fill
"""
import json
import pytest


# ── parse_short_story ─────────────────────────────────────────────────────────

class TestParseShortStory:
    def setup_method(self):
        from exercises.tools import parse_short_story
        self.parse = parse_short_story

    def make_args(self, **kwargs):
        defaults = {
            "title": "El misterio del lunes",
            "story": "Era un lunes tranquilo cuando María encontró algo extraño.",
            "story_translation": "It was a quiet Monday when María found something strange.",
            "questions": [
                {"question": "¿Qué día era?", "answer": "Era lunes."},
                {"question": "¿Quién encontró algo?", "answer": "María."},
            ],
            "vocab_used": ["el lunes", "tranquilo"],
            "grammar_used": ["Preterite tense"],
            "difficulty": "A2",
        }
        defaults.update(kwargs)
        return defaults

    def test_returns_three_tuple(self):
        result = self.parse(self.make_args())
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_content_contains_title_and_story(self):
        args = self.make_args()
        content, _, _ = self.parse(args)
        assert args["title"] in content
        assert args["story"] in content

    def test_content_does_not_contain_questions(self):
        """Questions should be in structured_data, not content."""
        args = self.make_args()
        content, _, _ = self.parse(args)
        assert "¿Qué día era?" not in content

    def test_answer_key_is_valid_json(self):
        _, answer_key, _ = self.parse(self.make_args())
        parsed = json.loads(answer_key)
        assert "story_translation" in parsed
        assert "answers" in parsed

    def test_answer_key_contains_translation(self):
        args = self.make_args()
        _, answer_key, _ = self.parse(args)
        parsed = json.loads(answer_key)
        assert parsed["story_translation"] == args["story_translation"]

    def test_answer_key_contains_all_answers(self):
        args = self.make_args()
        _, answer_key, _ = self.parse(args)
        parsed = json.loads(answer_key)
        assert len(parsed["answers"]) == 2
        assert "Era lunes." in parsed["answers"]

    def test_structured_data_has_all_fields(self):
        _, _, sd = self.parse(self.make_args())
        assert "title" in sd
        assert "story" in sd
        assert "story_translation" in sd
        assert "questions" in sd
        assert "vocab_used" in sd
        assert "grammar_used" in sd

    def test_structured_data_questions_intact(self):
        args = self.make_args()
        _, _, sd = self.parse(args)
        assert len(sd["questions"]) == 2
        assert sd["questions"][0]["question"] == "¿Qué día era?"

    def test_empty_questions(self):
        args = self.make_args(questions=[])
        content, answer_key, sd = self.parse(args)
        parsed = json.loads(answer_key)
        assert parsed["answers"] == []
        assert sd["questions"] == []

    def test_missing_optional_fields(self):
        """Should handle missing vocab_used and grammar_used gracefully."""
        args = {
            "title": "Test",
            "story": "Una historia.",
            "story_translation": "A story.",
            "questions": [],
            "difficulty": "A1",
        }
        content, answer_key, sd = self.parse(args)
        assert sd["vocab_used"] == []
        assert sd["grammar_used"] == []


# ── parse_translation ─────────────────────────────────────────────────────────

class TestParseTranslation:
    def setup_method(self):
        from exercises.tools import parse_translation
        self.parse = parse_translation

    def make_args(self, **kwargs):
        defaults = {
            "instructions": "Translate these sentences into Spanish.",
            "sentences": [
                {"id": 1, "source": "I go to the gym.", "target": "Voy al gimnasio.", "notes": ""},
                {"id": 2, "source": "She reads every day.", "target": "Ella lee cada día.", "notes": "Present tense"},
            ],
            "vocab_used": ["el gimnasio", "leer"],
            "grammar_used": ["Present tense"],
            "difficulty": "A2",
        }
        defaults.update(kwargs)
        return defaults

    def test_returns_three_tuple(self):
        result = self.parse(self.make_args())
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_content_contains_instructions(self):
        args = self.make_args()
        content, _, _ = self.parse(args)
        assert args["instructions"] in content

    def test_content_contains_source_sentences(self):
        args = self.make_args()
        content, _, _ = self.parse(args)
        assert "I go to the gym." in content
        assert "She reads every day." in content

    def test_content_does_not_contain_targets(self):
        """Target translations should be in answer_key only."""
        args = self.make_args()
        content, _, _ = self.parse(args)
        assert "Voy al gimnasio." not in content

    def test_answer_key_is_valid_json(self):
        _, answer_key, _ = self.parse(self.make_args())
        parsed = json.loads(answer_key)
        assert isinstance(parsed, dict)

    def test_answer_key_keyed_by_sentence_id(self):
        _, answer_key, _ = self.parse(self.make_args())
        parsed = json.loads(answer_key)
        assert "1" in parsed
        assert "2" in parsed
        assert parsed["1"]["target"] == "Voy al gimnasio."

    def test_answer_key_contains_notes(self):
        _, answer_key, _ = self.parse(self.make_args())
        parsed = json.loads(answer_key)
        assert parsed["2"]["notes"] == "Present tense"

    def test_structured_data_contains_sentences(self):
        _, _, sd = self.parse(self.make_args())
        assert "sentences" in sd
        assert len(sd["sentences"]) == 2

    def test_empty_sentences(self):
        args = self.make_args(sentences=[])
        content, answer_key, sd = self.parse(args)
        parsed = json.loads(answer_key)
        assert parsed == {}
        assert sd["sentences"] == []


# ── parse_gap_fill ────────────────────────────────────────────────────────────

class TestParseGapFill:
    def setup_method(self):
        from exercises.tools import parse_gap_fill
        self.parse = parse_gap_fill

    def make_args(self, **kwargs):
        defaults = {
            "instructions": "Fill in the blanks with the correct word.",
            "text_with_gaps": "Ayer [___] al gimnasio con mi [___].",
            "word_bank": ["fui", "amigo", "casa", "libro"],
            "answer_key": ["fui", "amigo"],
            "full_text": "Ayer fui al gimnasio con mi amigo.",
            "vocab_used": ["el gimnasio", "el amigo"],
            "grammar_used": ["Preterite tense"],
            "difficulty": "A2",
        }
        defaults.update(kwargs)
        return defaults

    def test_returns_three_tuple(self):
        result = self.parse(self.make_args())
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_content_contains_instructions(self):
        args = self.make_args()
        content, _, _ = self.parse(args)
        assert args["instructions"] in content

    def test_content_contains_text_with_gaps(self):
        args = self.make_args()
        content, _, _ = self.parse(args)
        assert "[___]" in content

    def test_content_contains_word_bank(self):
        args = self.make_args()
        content, _, _ = self.parse(args)
        assert "fui" in content
        assert "amigo" in content

    def test_answer_key_is_valid_json(self):
        _, answer_key, _ = self.parse(self.make_args())
        parsed = json.loads(answer_key)
        assert "answers" in parsed
        assert "full_text" in parsed

    def test_answer_key_contains_correct_answers(self):
        _, answer_key, _ = self.parse(self.make_args())
        parsed = json.loads(answer_key)
        assert parsed["answers"] == ["fui", "amigo"]

    def test_answer_key_contains_full_text(self):
        args = self.make_args()
        _, answer_key, _ = self.parse(args)
        parsed = json.loads(answer_key)
        assert parsed["full_text"] == args["full_text"]

    def test_structured_data_has_all_fields(self):
        _, _, sd = self.parse(self.make_args())
        assert "instructions" in sd
        assert "text_with_gaps" in sd
        assert "word_bank" in sd
        assert "answer_key" in sd
        assert "full_text" in sd

    def test_word_bank_in_structured_data(self):
        args = self.make_args()
        _, _, sd = self.parse(args)
        assert sd["word_bank"] == args["word_bank"]

    def test_empty_word_bank(self):
        args = self.make_args(word_bank=[], answer_key=[])
        content, answer_key, sd = self.parse(args)
        parsed = json.loads(answer_key)
        assert parsed["answers"] == []
        assert sd["word_bank"] == []
