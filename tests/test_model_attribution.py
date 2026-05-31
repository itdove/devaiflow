"""Tests for model attribution in commit messages (Issue #191)."""

import pytest
from unittest.mock import MagicMock, patch

from devflow.utils.model_provider import (
    parse_claude_model_display_name,
    get_model_attribution_name,
    get_co_authored_by_line,
    get_active_profile,
)


class TestParseClaudeModelDisplayName:
    """Tests for parsing Claude model IDs to display names."""

    def test_opus_4_6(self):
        assert parse_claude_model_display_name("claude-opus-4-6") == "Claude Opus 4.6"

    def test_sonnet_4_6(self):
        assert parse_claude_model_display_name("claude-sonnet-4-6") == "Claude Sonnet 4.6"

    def test_haiku_4_5(self):
        assert parse_claude_model_display_name("claude-haiku-4-5") == "Claude Haiku 4.5"

    def test_opus_4_8(self):
        assert parse_claude_model_display_name("claude-opus-4-8") == "Claude Opus 4.8"

    def test_with_date_suffix(self):
        assert parse_claude_model_display_name("claude-opus-4-6-20250514") == "Claude Opus 4.6"

    def test_with_context_marker(self):
        assert parse_claude_model_display_name("claude-opus-4-6[1m]") == "Claude Opus 4.6"

    def test_claude_3_5_sonnet(self):
        assert parse_claude_model_display_name("claude-3-5-sonnet-20241022") == "Claude 3.5 Sonnet"

    def test_claude_3_opus(self):
        assert parse_claude_model_display_name("claude-3-opus-20240229") == "Claude 3 Opus"

    def test_claude_3_haiku(self):
        assert parse_claude_model_display_name("claude-3-haiku-20240307") == "Claude 3 Haiku"

    def test_non_claude_model_returned_as_is(self):
        assert parse_claude_model_display_name("devstral-small-2") == "devstral-small-2"

    def test_empty_string_returns_claude(self):
        assert parse_claude_model_display_name("") == "Claude"

    def test_none_returns_claude(self):
        assert parse_claude_model_display_name(None) == "Claude"

    def test_unrecognized_claude_format_returned_as_is(self):
        assert parse_claude_model_display_name("claude-unknown-format") == "claude-unknown-format"


class TestGetModelAttributionName:
    """Tests for resolving model display name from config."""

    def _make_config(self, profiles=None, default_profile="anthropic"):
        config = MagicMock()
        if profiles:
            provider = MagicMock()
            provider.default_profile = default_profile
            provider.profiles = {}
            for name, model_name in profiles.items():
                profile = MagicMock()
                profile.name = name
                profile.model_name = model_name
                profile.model_dump.return_value = {
                    "name": name,
                    "model_name": model_name,
                    "use_vertex": False,
                    "base_url": None,
                }
                provider.profiles[name] = profile
            config.model_provider = provider
        else:
            config.model_provider = None
        return config

    def test_no_config_returns_claude(self):
        assert get_model_attribution_name(None) == "Claude"

    def test_no_model_provider_returns_claude(self):
        config = self._make_config()
        assert get_model_attribution_name(config) == "Claude"

    def test_profile_with_claude_model_name(self):
        config = self._make_config(
            profiles={"vertex": "claude-opus-4-6"},
            default_profile="vertex",
        )
        assert get_model_attribution_name(config) == "Claude Opus 4.6"

    def test_profile_with_non_claude_model(self):
        config = self._make_config(
            profiles={"local": "devstral-small-2"},
            default_profile="local",
        )
        assert get_model_attribution_name(config) == "devstral-small-2"

    def test_override_profile(self):
        config = self._make_config(
            profiles={
                "anthropic": None,
                "vertex": "claude-sonnet-4-6",
            },
            default_profile="anthropic",
        )
        assert get_model_attribution_name(config, model_profile_override="vertex") == "Claude Sonnet 4.6"

    def test_profile_without_model_name_returns_claude(self):
        config = self._make_config(
            profiles={"anthropic": None},
            default_profile="anthropic",
        )
        assert get_model_attribution_name(config) == "Claude"


class TestGetCoAuthoredByLine:
    """Tests for generating the Co-Authored-By attribution line."""

    def _make_config(self, profiles=None, default_profile="anthropic"):
        config = MagicMock()
        if profiles:
            provider = MagicMock()
            provider.default_profile = default_profile
            provider.profiles = {}
            for name, model_name in profiles.items():
                profile = MagicMock()
                profile.name = name
                profile.model_name = model_name
                profile.model_dump.return_value = {
                    "name": name,
                    "model_name": model_name,
                    "use_vertex": False,
                    "base_url": None,
                }
                provider.profiles[name] = profile
            config.model_provider = provider
        else:
            config.model_provider = None
        return config

    def test_no_config_returns_generic(self):
        result = get_co_authored_by_line()
        assert result == "Co-Authored-By: Claude <noreply@anthropic.com>"

    def test_with_opus_model(self):
        config = self._make_config(
            profiles={"vertex": "claude-opus-4-6"},
            default_profile="vertex",
        )
        result = get_co_authored_by_line(config)
        assert result == "Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

    def test_with_sonnet_model(self):
        config = self._make_config(
            profiles={"vertex": "claude-sonnet-4-6"},
            default_profile="vertex",
        )
        result = get_co_authored_by_line(config)
        assert result == "Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

    def test_with_haiku_model(self):
        config = self._make_config(
            profiles={"vertex": "claude-haiku-4-5"},
            default_profile="vertex",
        )
        result = get_co_authored_by_line(config)
        assert result == "Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

    def test_with_non_claude_model(self):
        config = self._make_config(
            profiles={"local": "devstral-small-2"},
            default_profile="local",
        )
        result = get_co_authored_by_line(config)
        assert result == "Co-Authored-By: devstral-small-2 <noreply@anthropic.com>"

    def test_with_profile_override(self):
        config = self._make_config(
            profiles={
                "anthropic": None,
                "vertex": "claude-opus-4-6",
            },
            default_profile="anthropic",
        )
        result = get_co_authored_by_line(config, model_profile_override="vertex")
        assert result == "Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

    def test_fallback_when_no_model_in_profile(self):
        config = self._make_config(
            profiles={"anthropic": None},
            default_profile="anthropic",
        )
        result = get_co_authored_by_line(config)
        assert result == "Co-Authored-By: Claude <noreply@anthropic.com>"


class TestCommitMessageIntegration:
    """Tests verifying model attribution appears in commit message format."""

    def test_commit_message_format_with_model(self):
        config = MagicMock()
        provider = MagicMock()
        provider.default_profile = "vertex"
        profile = MagicMock()
        profile.name = "vertex"
        profile.model_name = "claude-opus-4-6"
        profile.model_dump.return_value = {
            "name": "vertex",
            "model_name": "claude-opus-4-6",
            "use_vertex": True,
            "base_url": None,
        }
        provider.profiles = {"vertex": profile}
        config.model_provider = provider

        co_authored_by = get_co_authored_by_line(config, model_profile_override="vertex")
        full_message = f"""feat: add new feature

🤖 Generated with [Claude Code](https://claude.com/claude-code)

{co_authored_by}"""

        assert "Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>" in full_message
        assert "Co-Authored-By: Claude <noreply@anthropic.com>" not in full_message

    def test_commit_message_format_fallback(self):
        co_authored_by = get_co_authored_by_line()
        full_message = f"""feat: add new feature

🤖 Generated with [Claude Code](https://claude.com/claude-code)

{co_authored_by}"""

        assert "Co-Authored-By: Claude <noreply@anthropic.com>" in full_message
