"""Tests for the ReplayProvider (canned LLM responses for rehearsal)."""

from __future__ import annotations

import json

import pytest

from src.rehearsal.replay_provider import ReplayProvider


# ---------------------------------------------------------------------------
# Keyword dispatch
# ---------------------------------------------------------------------------


class TestReplayProviderDispatch:
    @pytest.mark.asyncio
    async def test_scoring_keyword(self):
        provider = ReplayProvider()
        result = await provider.generate("any prompt", "You are a scoring judge")
        data = json.loads(result)
        assert "criteria" in data
        assert len(data["criteria"]) == 3

    @pytest.mark.asyncio
    async def test_commentary_arbiter_keyword(self):
        provider = ReplayProvider()
        result = await provider.generate("evaluate demo", "You are the Arbiter persona")
        assert "well" in result.lower()

    @pytest.mark.asyncio
    async def test_commentary_persona_keyword(self):
        provider = ReplayProvider()
        result = await provider.generate("evaluate demo", "Use this persona for commentary")
        assert len(result) > 20

    @pytest.mark.asyncio
    async def test_deliberation_keyword(self):
        provider = ReplayProvider()
        result = await provider.generate("rank teams", "You handle deliberation")
        data = json.loads(result)
        assert "rankings" in data
        assert "overall_narrative" in data

    @pytest.mark.asyncio
    async def test_qa_keyword_in_prompt(self):
        provider = ReplayProvider()
        result = await provider.generate("Generate a question for the team", "system")
        assert "question" in result.lower()

    @pytest.mark.asyncio
    async def test_qa_ampersand_keyword(self):
        provider = ReplayProvider()
        result = await provider.generate("Run Q&A session", "system")
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_default_fallback(self):
        provider = ReplayProvider()
        result = await provider.generate("something unrelated", "nothing special")
        assert "ReplayProvider" in result


# ---------------------------------------------------------------------------
# Custom responses
# ---------------------------------------------------------------------------


class TestCustomResponses:
    @pytest.mark.asyncio
    async def test_custom_keyword_match_in_system(self):
        custom = {"magic": "custom magic response"}
        provider = ReplayProvider(responses=custom)
        result = await provider.generate("test", "contains magic keyword")
        assert result == "custom magic response"

    @pytest.mark.asyncio
    async def test_custom_keyword_match_in_prompt(self):
        custom = {"special": "special answer"}
        provider = ReplayProvider(responses=custom)
        result = await provider.generate("this is special", "system")
        assert result == "special answer"

    @pytest.mark.asyncio
    async def test_custom_takes_precedence(self):
        """Custom responses are checked before built-in keywords."""
        custom = {"scoring": "my custom scoring"}
        provider = ReplayProvider(responses=custom)
        result = await provider.generate("test", "scoring prompt")
        assert result == "my custom scoring"

    @pytest.mark.asyncio
    async def test_custom_case_insensitive(self):
        custom = {"Magic": "found it"}
        provider = ReplayProvider(responses=custom)
        result = await provider.generate("test", "contains MAGIC keyword")
        assert result == "found it"


# ---------------------------------------------------------------------------
# Call counting and provider interface
# ---------------------------------------------------------------------------


class TestProviderInterface:
    @pytest.mark.asyncio
    async def test_call_count_increments(self):
        provider = ReplayProvider()
        assert provider._call_count == 0
        await provider.generate("a", "b")
        await provider.generate("c", "d")
        assert provider._call_count == 2

    def test_name_property(self):
        provider = ReplayProvider()
        assert provider.name == "replay"

    @pytest.mark.asyncio
    async def test_ignores_temperature_and_max_tokens(self):
        """Temperature and max_tokens are accepted but ignored."""
        provider = ReplayProvider()
        result = await provider.generate(
            "test", "nothing", temperature=0.9, max_tokens=5000,
        )
        assert isinstance(result, str)
