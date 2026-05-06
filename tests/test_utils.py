"""
tests/test_utils.py

Unit tests for exercises/utils.py:
  - pick_vocab
  - pick_grammar
  - infer_user_level
  - format_vocab
  - format_grammar
  - prompt_summary
"""
import pytest
from unittest.mock import MagicMock


def make_vocab(strength_raw: int, word: str = "test") -> MagicMock:
    """Create a mock VocabItem."""
    v = MagicMock()
    v.strength_raw = strength_raw
    v.word = word
    v.translation = f"{word}_translation"
    v.cert_level = None
    return v


def make_grammar(strength: int, cert_level: str = "A2", completed: bool = True) -> MagicMock:
    """Create a mock GrammarTopic."""
    g = MagicMock()
    g.strength = strength
    g.cert_level = cert_level
    g.completed = completed
    g.unit_name = f"Topic {cert_level}"
    g.percentage = 70
    return g


# ── pick_vocab ────────────────────────────────────────────────────────────────

class TestPickVocab:
    def setup_method(self):
        from exercises.utils import pick_vocab
        self.pick_vocab = pick_vocab

    def test_returns_n_items(self):
        vocab = [make_vocab(i % 6) for i in range(30)]
        result = self.pick_vocab(vocab, n=10)
        assert len(result) == 10

    def test_returns_all_if_fewer_than_n(self):
        vocab = [make_vocab(0) for _ in range(5)]
        result = self.pick_vocab(vocab, n=10)
        assert len(result) == 5

    def test_empty_list(self):
        result = self.pick_vocab([], n=10)
        assert result == []

    def test_prefers_weak_words(self):
        """With many weak words available, at least half should be weak."""
        weak   = [make_vocab(0, f"weak_{i}") for i in range(20)]
        strong = [make_vocab(5, f"strong_{i}") for i in range(20)]
        result = self.pick_vocab(weak + strong, n=10)
        weak_count = sum(1 for v in result if v.strength_raw == 0)
        assert weak_count >= 4  # at least 40% weak

    def test_no_duplicates(self):
        vocab = [make_vocab(i % 6, f"word_{i}") for i in range(30)]
        result = self.pick_vocab(vocab, n=10)
        ids = [id(v) for v in result]
        assert len(ids) == len(set(ids))


# ── pick_grammar ──────────────────────────────────────────────────────────────

class TestPickGrammar:
    def setup_method(self):
        from exercises.utils import pick_grammar
        self.pick_grammar = pick_grammar

    def test_returns_up_to_n(self):
        grammar = [make_grammar(i % 4) for i in range(10)]
        result = self.pick_grammar(grammar, n=3)
        assert len(result) <= 3

    def test_empty_list(self):
        result = self.pick_grammar([], n=3)
        assert result == []

    def test_prefers_weak_topics(self):
        weak   = [make_grammar(0) for _ in range(10)]
        strong = [make_grammar(4) for _ in range(10)]
        result = self.pick_grammar(weak + strong, n=3)
        weak_count = sum(1 for g in result if g.strength == 0)
        assert weak_count >= 1

    def test_fallback_when_no_weak(self):
        """Should still return items even if no weak/medium topics."""
        strong = [make_grammar(4) for _ in range(5)]
        result = self.pick_grammar(strong, n=3)
        assert len(result) > 0


# ── infer_user_level ──────────────────────────────────────────────────────────

class TestInferUserLevel:
    def setup_method(self):
        from exercises.utils import infer_user_level
        self.infer = infer_user_level

    def test_empty_returns_a2(self):
        assert self.infer([]) == "A2"

    def test_no_completed_returns_a2(self):
        grammar = [make_grammar(1, "B1", completed=False)]
        assert self.infer(grammar) == "A2"

    def test_single_level(self):
        grammar = [make_grammar(3, "A2", completed=True) for _ in range(3)]
        assert self.infer(grammar) == "A2"

    def test_highest_level_with_enough_topics(self):
        grammar = (
            [make_grammar(3, "A1", completed=True) for _ in range(5)] +
            [make_grammar(3, "A2", completed=True) for _ in range(5)] +
            [make_grammar(3, "B1", completed=True) for _ in range(3)]
        )
        assert self.infer(grammar) == "B1"

    def test_requires_at_least_two_completed(self):
        """Only 1 B2 topic — should fall back to lower level with 2+."""
        grammar = (
            [make_grammar(3, "A2", completed=True) for _ in range(4)] +
            [make_grammar(3, "B2", completed=True) for _ in range(1)]
        )
        result = self.infer(grammar)
        assert result == "A2"

    def test_case_insensitive_level(self):
        """CEFR levels stored as lowercase should still work."""
        g = make_grammar(3, "b1", completed=True)
        g2 = make_grammar(3, "b1", completed=True)
        assert self.infer([g, g2]) == "B1"

    def test_unknown_level_ignored(self):
        grammar = [make_grammar(3, "UNKNOWN", completed=True) for _ in range(5)]
        assert self.infer(grammar) == "A2"


# ── format_vocab ──────────────────────────────────────────────────────────────

class TestFormatVocab:
    def setup_method(self):
        from exercises.utils import format_vocab
        self.format_vocab = format_vocab

    def test_basic_format(self):
        vocab = [make_vocab(2, "el gato")]
        vocab[0].translation = "the cat"
        result = self.format_vocab(vocab)
        assert "el gato" in result
        assert "the cat" in result
        assert "2/5" in result

    def test_multiple_items(self):
        vocab = [make_vocab(i, f"word_{i}") for i in range(3)]
        result = self.format_vocab(vocab)
        lines = result.strip().split("\n")
        assert len(lines) == 3

    def test_empty(self):
        assert self.format_vocab([]) == ""


# ── format_grammar ────────────────────────────────────────────────────────────

class TestFormatGrammar:
    def setup_method(self):
        from exercises.utils import format_grammar
        self.format_grammar = format_grammar

    def test_basic_format(self):
        grammar = [make_grammar(2, "B1")]
        result = self.format_grammar(grammar)
        assert "B1" in result
        assert "70%" in result

    def test_empty(self):
        assert self.format_grammar([]) == ""


# ── prompt_summary ────────────────────────────────────────────────────────────

class TestPromptSummary:
    def setup_method(self):
        from exercises.utils import prompt_summary
        self.prompt_summary = prompt_summary

    def test_contains_vocab_and_grammar(self):
        vocab = [make_vocab(0, "el gato")]
        grammar = [make_grammar(1, "A2")]
        result = self.prompt_summary(vocab, grammar)
        assert "el gato" in result
        assert "Vocab" in result
        assert "Grammar" in result

    def test_empty_grammar(self):
        vocab = [make_vocab(0, "word")]
        result = self.prompt_summary(vocab, [])
        assert "Vocab" in result
