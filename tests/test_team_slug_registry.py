"""Tests for TeamSlugRegistry collision detection."""
import pytest
from src.utils import (
    TeamNameCollisionError,
    TeamSlugRegistry,
    resolve_team_slug,
    clear_team_registry,
    sanitize_team_name,
)


class TestSanitizeTeamNameUnchanged:
    """Verify sanitize_team_name behavior is preserved."""

    def test_spaces_to_underscores(self):
        assert sanitize_team_name("Cyber Falcons") == "cyber_falcons"

    def test_special_chars_stripped(self):
        assert sanitize_team_name("Team@#$%!") == "team"

    def test_hyphens_preserved(self):
        assert sanitize_team_name("Night-Owls") == "night-owls"

    def test_mixed_case_lowered(self):
        assert sanitize_team_name("CyberPunk Raccoons") == "cyberpunk_raccoons"


class TestTeamSlugRegistry:
    """Tests for collision detection."""

    def setup_method(self):
        self.registry = TeamSlugRegistry()

    def test_first_registration_returns_slug(self):
        slug = self.registry.resolve("Team Alpha")
        assert slug == "team_alpha"

    def test_same_name_returns_same_slug(self):
        self.registry.resolve("Team Alpha")
        slug = self.registry.resolve("Team Alpha")
        assert slug == "team_alpha"

    def test_collision_raises_error(self):
        self.registry.resolve("Team Alpha")
        with pytest.raises(TeamNameCollisionError, match="collides with existing team"):
            self.registry.resolve("Team_Alpha")

    def test_collision_with_punctuation_variant(self):
        self.registry.resolve("Team Alpha")
        with pytest.raises(TeamNameCollisionError):
            self.registry.resolve("Team Alpha!!")

    def test_collision_error_message_includes_both_names(self):
        self.registry.resolve("Team Alpha")
        with pytest.raises(TeamNameCollisionError, match="Team Alpha!!.*Team Alpha"):
            self.registry.resolve("Team Alpha!!")

    def test_different_slugs_no_collision(self):
        self.registry.resolve("Team Alpha")
        slug = self.registry.resolve("Team Beta")
        assert slug == "team_beta"

    def test_empty_name_raises_value_error(self):
        with pytest.raises(ValueError, match="empty slug"):
            self.registry.resolve("")

    def test_clear_allows_reregistration(self):
        self.registry.resolve("Team Alpha")
        self.registry.clear()
        # Now a different name can claim the same slug
        slug = self.registry.resolve("Team_Alpha")
        assert slug == "team_alpha"


class TestResolveTeamSlugModule:
    """Tests for the module-level resolve function."""

    def setup_method(self):
        clear_team_registry()

    def teardown_method(self):
        clear_team_registry()

    def test_resolve_registers_and_returns_slug(self):
        slug = resolve_team_slug("Cyber Wolves")
        assert slug == "cyber_wolves"

    def test_resolve_detects_collision(self):
        resolve_team_slug("Cyber Wolves")
        with pytest.raises(TeamNameCollisionError):
            resolve_team_slug("Cyber_Wolves")
