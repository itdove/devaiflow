"""Tests for daf setup command."""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from devflow.cli.commands.setup_command import (
    strip_jsonc_comments,
    load_overlay,
    deep_merge,
    resolve_target_path,
    setup_agent_config,
)


class TestStripJsoncComments:
    def test_line_comments(self):
        text = '{\n  // this is a comment\n  "key": "value"\n}'
        result = strip_jsonc_comments(text)
        assert "//" not in result
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    def test_block_comments(self):
        text = '{\n  /* block\n  comment */\n  "key": "value"\n}'
        result = strip_jsonc_comments(text)
        assert "/*" not in result
        assert "*/" not in result
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    def test_inline_comment_after_value(self):
        text = '{\n  "key": "value" // inline comment\n}'
        result = strip_jsonc_comments(text)
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    def test_no_comments(self):
        text = '{"key": "value"}'
        result = strip_jsonc_comments(text)
        assert json.loads(result) == {"key": "value"}

    def test_url_in_string_not_stripped(self):
        text = '{"url": "https://example.com"}'
        result = strip_jsonc_comments(text)
        parsed = json.loads(result)
        assert parsed["url"] == "https://example.com"


class TestDeepMerge:
    def test_empty_base(self):
        base = {}
        overlay = {"a": {"b": "c"}}
        merged, added = deep_merge(base, overlay)
        assert merged == {"a": {"b": "c"}}
        assert "a" in added

    def test_no_overwrite(self):
        base = {"a": {"b": "existing"}}
        overlay = {"a": {"b": "new", "c": "added"}}
        merged, added = deep_merge(base, overlay)
        assert merged["a"]["b"] == "existing"
        assert merged["a"]["c"] == "added"
        assert "a.c" in added
        assert "a.b" not in added

    def test_idempotent(self):
        base = {"a": {"b": "c"}}
        overlay = {"a": {"b": "c"}}
        _, added = deep_merge(base, overlay)
        assert added == []

    def test_nested_merge(self):
        base = {"permission": {"bash": {"daf info *": "allow"}}}
        overlay = {
            "permission": {
                "bash": {"daf info *": "allow", "gh * view *": "allow"},
                "read": {"~/.config/devaiflow/**": "allow"},
            }
        }
        merged, added = deep_merge(base, overlay)
        assert merged["permission"]["bash"]["daf info *"] == "allow"
        assert merged["permission"]["bash"]["gh * view *"] == "allow"
        assert merged["permission"]["read"]["~/.config/devaiflow/**"] == "allow"
        assert "permission.bash.gh * view *" in added
        assert "permission.read" in added

    def test_preserves_extra_keys_in_base(self):
        base = {"custom": "user_setting", "permission": {"bash": {"my_cmd *": "allow"}}}
        overlay = {"permission": {"bash": {"daf info *": "allow"}}}
        merged, _ = deep_merge(base, overlay)
        assert merged["custom"] == "user_setting"
        assert merged["permission"]["bash"]["my_cmd *"] == "allow"
        assert merged["permission"]["bash"]["daf info *"] == "allow"


class TestResolveTargetPath:
    def test_opencode_project(self):
        path = resolve_target_path("opencode", "project")
        assert path.name == "opencode.json"
        assert path.parent == Path.cwd()

    def test_opencode_global_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_CONFIG_HOME", None)
            path = resolve_target_path("opencode", "global")
            assert path == Path.home() / ".config" / "opencode" / "opencode.json"

    def test_opencode_global_xdg(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}):
            path = resolve_target_path("opencode", "global")
            assert path == Path("/custom/config/opencode/opencode.json")

    def test_claude_project(self):
        path = resolve_target_path("claude", "project")
        assert path.name == "settings.json"
        assert ".claude" in str(path)


class TestLoadOverlay:
    def test_load_opencode_overlay(self):
        overlay = load_overlay("opencode")
        assert overlay is not None
        assert "permission" in overlay
        assert "bash" in overlay["permission"]
        assert "daf info *" in overlay["permission"]["bash"]

    def test_load_claude_overlay(self):
        overlay = load_overlay("claude")
        assert overlay is not None

    def test_load_nonexistent_overlay(self):
        overlay = load_overlay("nonexistent-backend")
        assert overlay is None


class TestSetupAgentConfig:
    def test_opencode_fresh_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"agent_backend": "opencode"}))

        with patch("devflow.config.loader.ConfigLoader") as mock_loader:
            mock_config = MagicMock()
            mock_config.agent_backend = "opencode"
            mock_loader.return_value.load_config.return_value = mock_config

            exit_code = setup_agent_config(dry_run=False, scope="project")

        assert exit_code == 0
        target = tmp_path / "opencode.json"
        assert target.exists()
        data = json.loads(target.read_text())
        assert "permission" in data
        assert data["permission"]["bash"]["daf info *"] == "allow"

    def test_opencode_merge_existing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        existing = {
            "permission": {
                "bash": {
                    "*": "ask",
                    "my_custom *": "allow",
                }
            }
        }
        (tmp_path / "opencode.json").write_text(json.dumps(existing, indent=2))

        with patch("devflow.config.loader.ConfigLoader") as mock_loader:
            mock_config = MagicMock()
            mock_config.agent_backend = "opencode"
            mock_loader.return_value.load_config.return_value = mock_config

            exit_code = setup_agent_config(dry_run=False, scope="project")

        assert exit_code == 0
        data = json.loads((tmp_path / "opencode.json").read_text())
        assert data["permission"]["bash"]["*"] == "ask"
        assert data["permission"]["bash"]["my_custom *"] == "allow"
        assert data["permission"]["bash"]["daf info *"] == "allow"

    def test_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch("devflow.config.loader.ConfigLoader") as mock_loader:
            mock_config = MagicMock()
            mock_config.agent_backend = "opencode"
            mock_loader.return_value.load_config.return_value = mock_config

            setup_agent_config(dry_run=False, scope="project")
            first_content = (tmp_path / "opencode.json").read_text()

            setup_agent_config(dry_run=False, scope="project")
            second_content = (tmp_path / "opencode.json").read_text()

        assert first_content == second_content

    def test_dry_run_no_write(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch("devflow.config.loader.ConfigLoader") as mock_loader:
            mock_config = MagicMock()
            mock_config.agent_backend = "opencode"
            mock_loader.return_value.load_config.return_value = mock_config

            exit_code = setup_agent_config(dry_run=True, scope="project")

        assert exit_code == 0
        assert not (tmp_path / "opencode.json").exists()

    def test_non_opencode_backend(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch("devflow.config.loader.ConfigLoader") as mock_loader:
            mock_config = MagicMock()
            mock_config.agent_backend = "cursor"
            mock_loader.return_value.load_config.return_value = mock_config

            exit_code = setup_agent_config(dry_run=False, scope="project")

        assert exit_code == 0
        assert not (tmp_path / "opencode.json").exists()

    def test_backend_alias(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch("devflow.config.loader.ConfigLoader") as mock_loader:
            mock_config = MagicMock()
            mock_config.agent_backend = "opencode-ai"
            mock_loader.return_value.load_config.return_value = mock_config

            exit_code = setup_agent_config(dry_run=False, scope="project")

        assert exit_code == 0
        assert (tmp_path / "opencode.json").exists()

    def test_json_output(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)

        with patch("devflow.config.loader.ConfigLoader") as mock_loader:
            mock_config = MagicMock()
            mock_config.agent_backend = "opencode"
            mock_loader.return_value.load_config.return_value = mock_config

            exit_code = setup_agent_config(
                dry_run=False, scope="project", output_json=True
            )

        assert exit_code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["success"] is True
        assert output["backend"] == "opencode"
        assert len(output["added"]) > 0

    def test_global_scope(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        global_dir = tmp_path / "xdg_config" / "opencode"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_config"))

        with patch("devflow.config.loader.ConfigLoader") as mock_loader:
            mock_config = MagicMock()
            mock_config.agent_backend = "opencode"
            mock_loader.return_value.load_config.return_value = mock_config

            exit_code = setup_agent_config(dry_run=False, scope="global")

        assert exit_code == 0
        target = global_dir / "opencode.json"
        assert target.exists()

    def test_edit_deny_for_daf_sessions(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch("devflow.config.loader.ConfigLoader") as mock_loader:
            mock_config = MagicMock()
            mock_config.agent_backend = "opencode"
            mock_loader.return_value.load_config.return_value = mock_config

            setup_agent_config(dry_run=False, scope="project")

        data = json.loads((tmp_path / "opencode.json").read_text())
        assert data["permission"]["edit"]["~/.config/devaiflow/**"] == "deny"

    def test_config_load_failure_defaults_to_claude(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch("devflow.config.loader.ConfigLoader") as mock_loader:
            mock_loader.return_value.load_config.side_effect = Exception("no config")

            exit_code = setup_agent_config(dry_run=False, scope="project")

        assert exit_code == 0
