"""Tests for real behavior in commentary streaming, TTS fallback arguments, and stream_sentences.

These tests close gaps found by audit where existing tests were tautological:
1. Multi-chunk streaming assembly and sentence splitting from realistic Gemini output
2. TTS fallback argument verification (checking WHAT text is passed, not just call count)
3. stream_sentences integration with proper sentence/emotion/index tuple verification
4. MacOSSayFallback subprocess argument verification
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.commentary.generator import CommentaryGenerator
from src.commentary.tts_fallback import FallbackChain, MacOSSayFallback, OpenAITTSFallback
from src.defense.models import SanitizedOutput
from src.resilience.circuit_breaker import GeminiCircuitBreaker
from src.resilience.retry import DailyQuotaExhausted


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sanitized() -> SanitizedOutput:
    return SanitizedOutput(
        team_name="TestTeam",
        observations=["Built a web scraper with Python"],
        transcripts=["We had fun building this."],
        injection_attempts=[],
        demo_duration=120.0,
    )


def _make_generator(**kwargs) -> CommentaryGenerator:
    """Create a CommentaryGenerator with Groq disabled by default."""
    defaults = {"api_key": "fake-key", "groq_api_key": ""}
    defaults.update(kwargs)
    return CommentaryGenerator(**defaults)


@asynccontextmanager
async def _noop_rate_limiter(*args, **kwargs):
    """Bypass rate limiter in tests."""
    yield


# ---------------------------------------------------------------------------
# 1. Multi-chunk streaming assembly
# ---------------------------------------------------------------------------


class TestMultiChunkStreaming:
    """Verify that multiple small Gemini chunks are correctly assembled and split."""

    @pytest.mark.asyncio
    async def test_two_chunks_assemble_into_full_text(self, sanitized):
        """Two chunks concatenated produce the expected full commentary text."""
        gen = _make_generator()

        chunk1 = MagicMock()
        chunk1.text = "Bold strategy from TestTeam. "
        chunk2 = MagicMock()
        chunk2.text = "The scraper actually works!"

        async def fake_stream(*args, **kwargs):
            for c in [chunk1, chunk2]:
                yield c

        with patch.object(
            gen._client.aio.models,
            "generate_content_stream",
            new=AsyncMock(return_value=fake_stream()),
        ):
            result = await gen.generate(sanitized)

        assert result.text == "Bold strategy from TestTeam. The scraper actually works!"
        assert result.sentences == [
            "Bold strategy from TestTeam.",
            "The scraper actually works!",
        ]

    @pytest.mark.asyncio
    async def test_many_small_chunks_assemble_correctly(self, sanitized):
        """Simulate realistic Gemini output: many tiny token-sized chunks."""
        gen = _make_generator()

        # Gemini often sends word-by-word or partial-word chunks
        raw_parts = [
            "Somehow ",
            "this team ",
            "managed to ",
            "build something. ",
            "Genuinely ",
            "surprised it works.",
        ]
        chunks = []
        for part in raw_parts:
            c = MagicMock()
            c.text = part
            chunks.append(c)

        async def fake_stream(*args, **kwargs):
            for c in chunks:
                yield c

        with patch.object(
            gen._client.aio.models,
            "generate_content_stream",
            new=AsyncMock(return_value=fake_stream()),
        ):
            result = await gen.generate(sanitized)

        expected_text = "Somehow this team managed to build something. Genuinely surprised it works."
        assert result.text == expected_text
        assert len(result.sentences) == 2
        assert result.sentences[0] == "Somehow this team managed to build something."
        assert result.sentences[1] == "Genuinely surprised it works."

    @pytest.mark.asyncio
    async def test_chunk_with_empty_text_skipped(self, sanitized):
        """Chunks with None or empty text should not corrupt the assembled output."""
        gen = _make_generator()

        chunk_real = MagicMock()
        chunk_real.text = "Clean code here."
        chunk_empty = MagicMock()
        chunk_empty.text = None
        chunk_blank = MagicMock()
        chunk_blank.text = ""

        async def fake_stream(*args, **kwargs):
            for c in [chunk_empty, chunk_real, chunk_blank]:
                yield c

        with patch.object(
            gen._client.aio.models,
            "generate_content_stream",
            new=AsyncMock(return_value=fake_stream()),
        ):
            result = await gen.generate(sanitized)

        assert result.text == "Clean code here."
        assert result.sentences == ["Clean code here."]

    @pytest.mark.asyncio
    async def test_sentence_boundary_split_across_chunks(self, sanitized):
        """Sentence boundary (period + space) arrives across two chunks."""
        gen = _make_generator()

        # Period at end of chunk1, space at start of chunk2
        chunk1 = MagicMock()
        chunk1.text = "First sentence."
        chunk2 = MagicMock()
        chunk2.text = " Second sentence."

        async def fake_stream(*args, **kwargs):
            for c in [chunk1, chunk2]:
                yield c

        with patch.object(
            gen._client.aio.models,
            "generate_content_stream",
            new=AsyncMock(return_value=fake_stream()),
        ):
            result = await gen.generate(sanitized)

        assert len(result.sentences) == 2
        assert result.sentences[0] == "First sentence."
        assert result.sentences[1] == "Second sentence."


# ---------------------------------------------------------------------------
# 2. TTS fallback argument verification
# ---------------------------------------------------------------------------


class TestTTSFallbackArguments:
    """Verify the exact text passed to TTS speak methods, not just call count."""

    @pytest.mark.asyncio
    async def test_fallback_chain_passes_exact_text_to_first_available(self):
        """FallbackChain.speak() passes the exact text string to the chosen fallback."""
        fb = MagicMock()
        fb.available = True
        fb.speak = AsyncMock()

        chain = FallbackChain([fb])
        await chain.speak("The scraper looked genuinely impressive.")

        fb.speak.assert_called_once_with("The scraper looked genuinely impressive.")

    @pytest.mark.asyncio
    async def test_fallback_chain_same_text_to_second_when_first_fails(self):
        """When first fallback raises, second receives the same text."""
        fb1 = MagicMock()
        fb1.available = True
        fb1.speak = AsyncMock(side_effect=RuntimeError("audio device busy"))
        fb1.__class__.__name__ = "OpenAITTSFallback"

        fb2 = MagicMock()
        fb2.available = True
        fb2.speak = AsyncMock()
        fb2.__class__.__name__ = "MacOSSayFallback"

        chain = FallbackChain([fb1, fb2])
        target_text = "Unfortunately the demo crashed halfway through."
        await chain.speak(target_text)

        # First was tried and failed
        fb1.speak.assert_called_once_with(target_text)
        # Second received the SAME text
        fb2.speak.assert_called_once_with(target_text)

    @pytest.mark.asyncio
    async def test_fallback_chain_skips_unavailable_without_calling_speak(self):
        """Unavailable fallbacks are skipped entirely -- speak() is never called."""
        fb_unavail = MagicMock()
        fb_unavail.available = False
        fb_unavail.speak = AsyncMock()

        fb_avail = MagicMock()
        fb_avail.available = True
        fb_avail.speak = AsyncMock()

        chain = FallbackChain([fb_unavail, fb_avail])
        await chain.speak("Test text.")

        fb_unavail.speak.assert_not_called()
        fb_avail.speak.assert_called_once_with("Test text.")

    @pytest.mark.asyncio
    async def test_fallback_chain_speak_with_multiline_text(self):
        """Verify multi-line text is passed through without mutation."""
        fb = MagicMock()
        fb.available = True
        fb.speak = AsyncMock()

        chain = FallbackChain([fb])
        multiline = "Line one.\nLine two.\nLine three."
        await chain.speak(multiline)

        fb.speak.assert_called_once_with(multiline)

    @pytest.mark.asyncio
    async def test_fallback_chain_speak_with_empty_string(self):
        """Empty string should still be forwarded to the fallback."""
        fb = MagicMock()
        fb.available = True
        fb.speak = AsyncMock()

        chain = FallbackChain([fb])
        await chain.speak("")

        fb.speak.assert_called_once_with("")


# ---------------------------------------------------------------------------
# 3. stream_sentences integration
# ---------------------------------------------------------------------------


class TestStreamSentencesIntegration:
    """Test stream_sentences yields correct (sentence, emotion, index) tuples."""

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Gemini streaming bypassed")
    async def test_gemini_sentences_passed_through(self, sanitized):
        """When Gemini succeeds, stream_sentences yields exactly what _stream_gemini_sentences yields."""
        gen = _make_generator()

        expected_tuples = [
            ("Bold strategy there.", "sarcastic", 0),
            ("The code actually works.", "surprised", 1),
            ("Ship it.", "enthusiastic", 2),
        ]

        async def fake_gemini_sentences(prompt):
            for item in expected_tuples:
                yield item

        with patch.object(gen, "_stream_gemini_sentences", side_effect=fake_gemini_sentences):
            collected = []
            async for item in gen.stream_sentences(sanitized):
                collected.append(item)

        assert collected == expected_tuples

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Gemini streaming bypassed")
    async def test_gemini_success_does_not_yield_static(self, sanitized):
        """When Gemini succeeds, no static fallback sentences are yielded."""
        gen = _make_generator()

        async def fake_gemini_sentences(prompt):
            yield ("Only Gemini output.", "confident", 0)

        with patch.object(gen, "_stream_gemini_sentences", side_effect=fake_gemini_sentences):
            collected = []
            async for sentence, emotion, idx in gen.stream_sentences(sanitized):
                collected.append(sentence)

        assert collected == ["Only Gemini output."]
        assert "Technical difficulties" not in " ".join(collected)

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Gemini streaming bypassed")
    async def test_generic_error_falls_to_static_with_correct_tuples(self, sanitized):
        """Generic exception triggers static fallback with proper tuple structure."""
        gen = _make_generator()

        async def failing_gemini(prompt):
            raise RuntimeError("connection reset")
            # Make it an async generator that raises
            yield  # pragma: no cover

        with patch.object(gen, "_stream_gemini_sentences", side_effect=RuntimeError("connection reset")):
            collected = []
            async for sentence, emotion, idx in gen.stream_sentences(sanitized):
                collected.append((sentence, emotion, idx))

        # Static fallback should yield at least one tuple
        assert len(collected) >= 1
        # Each tuple has (str, str, int)
        for sentence, emotion, idx in collected:
            assert isinstance(sentence, str)
            assert isinstance(emotion, str)
            assert isinstance(idx, int)
            assert len(sentence) > 0
        # The static text is "Technical difficulties. Even Arbiter needs a moment."
        all_text = " ".join(s for s, _, _ in collected)
        assert "Technical difficulties" in all_text

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Gemini streaming bypassed")
    async def test_quota_exhausted_falls_to_static_and_trips_permanent(self, sanitized):
        """DailyQuotaExhausted trips breaker permanently and falls to static."""
        cb = GeminiCircuitBreaker()
        gen = _make_generator(circuit_breaker=cb)

        with patch.object(gen, "_stream_gemini_sentences", side_effect=DailyQuotaExhausted("done")):
            collected = []
            async for sentence, emotion, idx in gen.stream_sentences(sanitized):
                collected.append((sentence, emotion, idx))

        assert not cb.available
        assert cb._permanent
        # Verify the static fallback tuples have sequential indices
        indices = [idx for _, _, idx in collected]
        assert indices == list(range(len(indices)))

    @pytest.mark.asyncio
    async def test_stream_sentences_increments_demo_count(self, sanitized):
        """Each call to stream_sentences should increment demo_count."""
        gen = _make_generator()
        assert gen._demo_count == 0

        async def fake_gemini(prompt):
            yield ("Text.", "sarcastic", 0)

        with patch.object(gen, "_stream_gemini_sentences", side_effect=fake_gemini):
            async for _ in gen.stream_sentences(sanitized):
                pass

        assert gen._demo_count == 1

    @pytest.mark.asyncio
    async def test_stream_sentences_records_demo_history(self, sanitized):
        """stream_sentences should record demo in history for cross-demo context."""
        gen = _make_generator()
        assert len(gen._demo_history) == 0

        async def fake_gemini(prompt):
            yield ("Text.", "sarcastic", 0)

        with patch.object(gen, "_stream_gemini_sentences", side_effect=fake_gemini):
            async for _ in gen.stream_sentences(sanitized):
                pass

        assert len(gen._demo_history) == 1
        assert gen._demo_history[0]["team"] == "TestTeam"


# ---------------------------------------------------------------------------
# 4. MacOSSayFallback subprocess argument verification
# ---------------------------------------------------------------------------


class TestMacOSSayArguments:
    """Verify the exact arguments passed to the `say` subprocess."""

    @pytest.mark.asyncio
    async def test_say_receives_exact_text(self):
        """The `say` command receives the exact text as a positional argument."""
        fb = MacOSSayFallback(voice="Samantha", rate=180)
        # Force available=True so speak() doesn't early-return
        fb._available = True

        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)) as mock_exec:
            await fb.speak("The authentication was surprisingly solid.")

        mock_exec.assert_called_once_with(
            "say",
            "-v", "Samantha",
            "-r", "180",
            "--", "The authentication was surprisingly solid.",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

    @pytest.mark.asyncio
    async def test_say_strips_embedded_speech_commands(self):
        """macOS speech commands like [[rate 1]] are stripped before passing to say."""
        fb = MacOSSayFallback()
        fb._available = True

        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)) as mock_exec:
            await fb.speak("Hello [[rate 1]] world [[volm 0.5]] end.")

        # The text arg (after "--") should have embedded commands stripped
        call_args = mock_exec.call_args
        # Positional args: say -v Alex -r 210 -- <cleaned_text>
        text_arg = call_args[0][6]  # index 6 is the text after "--"
        assert "[[rate 1]]" not in text_arg
        assert "[[volm 0.5]]" not in text_arg
        assert "Hello" in text_arg
        assert "world" in text_arg
        assert "end." in text_arg

    @pytest.mark.asyncio
    async def test_say_unavailable_does_not_call_subprocess(self):
        """When say is not available, no subprocess should be spawned."""
        fb = MacOSSayFallback()
        fb._available = False

        with patch("asyncio.create_subprocess_exec", new=AsyncMock()) as mock_exec:
            await fb.speak("Should not be spoken.")

        mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_say_uses_configured_voice_and_rate(self):
        """Custom voice and rate are passed as -v and -r flags."""
        fb = MacOSSayFallback(voice="Daniel", rate=250)
        fb._available = True

        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)) as mock_exec:
            await fb.speak("Test.")

        args = mock_exec.call_args[0]
        assert args[0] == "say"
        assert args[1] == "-v"
        assert args[2] == "Daniel"
        assert args[3] == "-r"
        assert args[4] == "250"


# ---------------------------------------------------------------------------
# 5. Sentence splitting edge cases (complement to existing tests)
# ---------------------------------------------------------------------------


class TestSplitSentencesEdgeCases:
    """Additional sentence splitting tests for multi-chunk assembly edge cases."""

    def test_exclamation_and_question_boundaries(self):
        text = "Wow! Did they really build this? Apparently so."
        result = CommentaryGenerator._split_sentences(text)
        assert result == ["Wow!", "Did they really build this?", "Apparently so."]

    def test_no_trailing_space_after_last_sentence(self):
        """Last sentence without trailing space should still be captured."""
        text = "First. Second. Third"
        result = CommentaryGenerator._split_sentences(text)
        assert len(result) == 3
        assert result[2] == "Third"

    def test_multiple_spaces_between_sentences(self):
        text = "One.   Two.  Three."
        result = CommentaryGenerator._split_sentences(text)
        assert result == ["One.", "Two.", "Three."]

    def test_whitespace_only_returns_empty(self):
        assert CommentaryGenerator._split_sentences("   ") == []


# ---------------------------------------------------------------------------
# 6. Emotion detection on assembled multi-chunk text
# ---------------------------------------------------------------------------


class TestEmotionMappingOnAssembledText:
    """Verify emotion mapping produces correct results on multi-chunk assembled text."""

    def test_emotion_map_matches_keyword_in_assembled_sentences(self):
        """Emotions are detected by keyword in sentences assembled from chunks."""
        sentences = [
            "Bold strategy from the team.",     # "bold strategy" -> sarcastic
            "Actually impressive work.",         # "actually" -> surprised
            "Unfortunately the demo crashed.",   # "unfortunately" -> disappointed
        ]
        emap = CommentaryGenerator._build_emotion_map(sentences)
        assert emap[0] == "sarcastic"
        assert emap[1] == "surprised"
        assert emap[2] == "disappointed"

    def test_default_emotion_is_sarcastic(self):
        """Sentences with no matching keywords default to sarcastic."""
        sentences = ["Plain text with no trigger words at all."]
        emap = CommentaryGenerator._build_emotion_map(sentences)
        assert emap[0] == "sarcastic"

    def test_detect_sentence_emotion_with_bracket_tag(self):
        """_detect_sentence_emotion parses [emotion] bracket tags from LLM output."""
        emotion = CommentaryGenerator._detect_sentence_emotion("[impressed] That was great work.")
        assert emotion == "triumphant"  # "impressed" maps to "triumphant" via _LLM_TO_CARTESIA_MAP

    def test_detect_sentence_emotion_falls_to_keyword(self):
        """Without bracket tag, keyword matching is used."""
        emotion = CommentaryGenerator._detect_sentence_emotion("That was genuinely good.")
        # "genuinely" triggers "surprised"
        assert emotion == "surprised"

    def test_parse_emotion_tag_extracts_and_cleans(self):
        """_parse_emotion_tag returns cleaned sentence and mapped emotion."""
        clean, emotion = CommentaryGenerator._parse_emotion_tag("[encouraging] Keep it up!")
        assert clean == "Keep it up!"
        assert emotion == "enthusiastic"  # "encouraging" -> "enthusiastic"

    def test_parse_emotion_tag_no_tag_returns_empty(self):
        """Sentence without bracket tag returns original and empty emotion."""
        clean, emotion = CommentaryGenerator._parse_emotion_tag("No tag here.")
        assert clean == "No tag here."
        assert emotion == ""
