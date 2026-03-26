"""Tests for devflow.agent.skill_directories module."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from devflow.agent.skill_directories import (
    SUPPORTED_AGENTS,
    get_agent_global_skills_dir,
    get_agent_project_skills_dir,
    get_skill_install_paths,
    validate_agent_names,
)


class TestGetAgentGlobalSkillsDir:
    """Tests for get_agent_global_skills_dir function."""

    def test_claude_default_path(self):
        """Test Claude uses ~/.claude/skills/ by default."""
        with patch.dict(os.environ, {}, clear=True):
            path = get_agent_global_skills_dir('claude')
            assert path == Path.home() / '.claude' / 'skills'

    def test_claude_respects_env_var(self):
        """Test Claude respects CLAUDE_CONFIG_DIR environment variable."""
        with patch.dict(os.environ, {'CLAUDE_CONFIG_DIR': '/custom/claude'}, clear=True):
            path = get_agent_global_skills_dir('claude')
            assert path == Path('/custom/claude/skills')

    def test_copilot_default_path(self):
        """Test GitHub Copilot uses ~/.copilot/skills/ by default."""
        with patch.dict(os.environ, {}, clear=True):
            path = get_agent_global_skills_dir('copilot')
            assert path == Path.home() / '.copilot' / 'skills'

    def test_copilot_respects_env_var(self):
        """Test GitHub Copilot respects COPILOT_HOME environment variable."""
        with patch.dict(os.environ, {'COPILOT_HOME': '/custom/copilot'}, clear=True):
            path = get_agent_global_skills_dir('copilot')
            assert path == Path('/custom/copilot/skills')

    def test_copilot_alias(self):
        """Test github-copilot alias works."""
        path = get_agent_global_skills_dir('github-copilot')
        # Should work the same as 'copilot'
        assert path == Path.home() / '.copilot' / 'skills'

    def test_cursor_hardcoded_path(self):
        """Test Cursor uses hardcoded ~/.cursor/skills/ path."""
        path = get_agent_global_skills_dir('cursor')
        assert path == Path.home() / '.cursor' / 'skills'

    @patch('sys.platform', 'darwin')
    def test_windsurf_unix_path(self):
        """Test Windsurf uses ~/.codeium/windsurf/skills/ on Unix."""
        path = get_agent_global_skills_dir('windsurf')
        assert path == Path.home() / '.codeium' / 'windsurf' / 'skills'

    @patch('sys.platform', 'linux')
    def test_windsurf_linux_path(self):
        """Test Windsurf uses ~/.codeium/windsurf/skills/ on Linux."""
        path = get_agent_global_skills_dir('windsurf')
        assert path == Path.home() / '.codeium' / 'windsurf' / 'skills'

    @patch('sys.platform', 'win32')
    def test_windsurf_windows_path(self):
        """Test Windsurf uses %APPDATA%/Codeium/Windsurf/skills/ on Windows."""
        with patch.dict(os.environ, {'APPDATA': r'C:\Users\TestUser\AppData\Roaming'}, clear=True):
            path = get_agent_global_skills_dir('windsurf')
            # Compare path components rather than full path (to avoid Windows/Unix path separator issues)
            expected = Path(r'C:\Users\TestUser\AppData\Roaming') / 'Codeium' / 'Windsurf' / 'skills'
            assert str(path) == str(expected)

    @patch('sys.platform', 'win32')
    def test_windsurf_windows_fallback(self):
        """Test Windsurf falls back if APPDATA not set on Windows."""
        with patch.dict(os.environ, {}, clear=True):
            path = get_agent_global_skills_dir('windsurf')
            assert path == Path.home() / 'AppData' / 'Roaming' / 'Codeium' / 'Windsurf' / 'skills'

    def test_aider_hardcoded_path(self):
        """Test Aider uses hardcoded ~/.aider/skills/ path."""
        path = get_agent_global_skills_dir('aider')
        assert path == Path.home() / '.aider' / 'skills'

    def test_continue_hardcoded_path(self):
        """Test Continue uses hardcoded ~/.continue/skills/ path."""
        path = get_agent_global_skills_dir('continue')
        assert path == Path.home() / '.continue' / 'skills'

    def test_case_insensitive(self):
        """Test agent names are case-insensitive."""
        assert get_agent_global_skills_dir('CLAUDE') == get_agent_global_skills_dir('claude')
        assert get_agent_global_skills_dir('Cursor') == get_agent_global_skills_dir('cursor')

    def test_invalid_agent_raises_error(self):
        """Test invalid agent name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown agent: invalid"):
            get_agent_global_skills_dir('invalid')


class TestGetAgentProjectSkillsDir:
    """Tests for get_agent_project_skills_dir function."""

    def test_claude_project_path(self):
        """Test Claude uses <project>/.claude/skills/ for project-level."""
        project_path = Path('/my/project')
        path = get_agent_project_skills_dir('claude', project_path)
        assert path == Path('/my/project/.claude/skills')

    def test_copilot_project_path(self):
        """Test GitHub Copilot uses <project>/.github-copilot/skills/."""
        project_path = Path('/my/project')
        path = get_agent_project_skills_dir('copilot', project_path)
        assert path == Path('/my/project/.github-copilot/skills')

    def test_cursor_project_path(self):
        """Test Cursor uses <project>/.cursor/skills/."""
        project_path = Path('/my/project')
        path = get_agent_project_skills_dir('cursor', project_path)
        assert path == Path('/my/project/.cursor/skills')

    def test_windsurf_project_path(self):
        """Test Windsurf uses <project>/.windsurf/skills/."""
        project_path = Path('/my/project')
        path = get_agent_project_skills_dir('windsurf', project_path)
        assert path == Path('/my/project/.windsurf/skills')

    def test_aider_project_path(self):
        """Test Aider uses <project>/.aider/skills/."""
        project_path = Path('/my/project')
        path = get_agent_project_skills_dir('aider', project_path)
        assert path == Path('/my/project/.aider/skills')

    def test_continue_project_path(self):
        """Test Continue uses <project>/.continue/skills/."""
        project_path = Path('/my/project')
        path = get_agent_project_skills_dir('continue', project_path)
        assert path == Path('/my/project/.continue/skills')

    def test_path_resolution(self):
        """Test project path is resolved to absolute path."""
        project_path = Path('.')
        path = get_agent_project_skills_dir('claude', project_path)
        # Should be resolved to absolute path
        assert path.is_absolute()

    def test_invalid_agent_raises_error(self):
        """Test invalid agent name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown agent: invalid"):
            get_agent_project_skills_dir('invalid', Path('/my/project'))


class TestGetSkillInstallPaths:
    """Tests for get_skill_install_paths function."""

    def test_single_agent_global(self):
        """Test single agent with global level."""
        paths = get_skill_install_paths(['claude'], level='global')
        assert len(paths) == 1
        assert paths[0][0] == 'claude'
        assert paths[0][1] == Path.home() / '.claude' / 'skills'

    def test_multiple_agents_global(self):
        """Test multiple agents with global level."""
        paths = get_skill_install_paths(['claude', 'cursor'], level='global')
        assert len(paths) == 2
        assert paths[0][0] == 'claude'
        assert paths[1][0] == 'cursor'
        assert paths[0][1] == Path.home() / '.claude' / 'skills'
        assert paths[1][1] == Path.home() / '.cursor' / 'skills'

    def test_single_agent_project(self):
        """Test single agent with project level."""
        project_path = Path('/my/project')
        paths = get_skill_install_paths(['claude'], level='project', project_path=project_path)
        assert len(paths) == 1
        assert paths[0][0] == 'claude'
        assert paths[0][1] == Path('/my/project/.claude/skills')

    def test_single_agent_both(self):
        """Test single agent with both levels (global + project)."""
        project_path = Path('/my/project')
        paths = get_skill_install_paths(['claude'], level='both', project_path=project_path)
        assert len(paths) == 2
        assert paths[0][0] == 'claude'
        assert paths[0][1] == Path.home() / '.claude' / 'skills'
        assert paths[1][0] == 'claude'
        assert paths[1][1] == Path('/my/project/.claude/skills')

    def test_multiple_agents_both(self):
        """Test multiple agents with both levels."""
        project_path = Path('/my/project')
        paths = get_skill_install_paths(['claude', 'cursor'], level='both', project_path=project_path)
        # Should be 4 paths: 2 agents × 2 levels
        assert len(paths) == 4
        # Global paths first
        assert paths[0] == ('claude', Path.home() / '.claude' / 'skills')
        assert paths[1] == ('claude', Path('/my/project/.claude/skills'))
        assert paths[2] == ('cursor', Path.home() / '.cursor' / 'skills')
        assert paths[3] == ('cursor', Path('/my/project/.cursor/skills'))

    def test_invalid_level_raises_error(self):
        """Test invalid level raises ValueError."""
        with pytest.raises(ValueError, match="Invalid level: invalid"):
            get_skill_install_paths(['claude'], level='invalid')

    def test_project_level_without_path_raises_error(self):
        """Test project level without project_path raises ValueError."""
        with pytest.raises(ValueError, match="project_path is required"):
            get_skill_install_paths(['claude'], level='project')

    def test_both_level_without_path_raises_error(self):
        """Test both level without project_path raises ValueError."""
        with pytest.raises(ValueError, match="project_path is required"):
            get_skill_install_paths(['claude'], level='both')


class TestValidateAgentNames:
    """Tests for validate_agent_names function."""

    def test_valid_single_agent(self):
        """Test validation of single valid agent."""
        result = validate_agent_names(['claude'])
        assert result == ['claude']

    def test_valid_multiple_agents(self):
        """Test validation of multiple valid agents."""
        result = validate_agent_names(['claude', 'cursor', 'windsurf'])
        assert result == ['claude', 'cursor', 'windsurf']

    def test_github_copilot_alias_normalization(self):
        """Test github-copilot is normalized to copilot."""
        result = validate_agent_names(['github-copilot'])
        assert result == ['copilot']

    def test_case_insensitive(self):
        """Test agent names are normalized to lowercase."""
        result = validate_agent_names(['CLAUDE', 'Cursor'])
        assert result == ['claude', 'cursor']

    def test_invalid_agent_raises_error(self):
        """Test invalid agent name raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported agent: invalid"):
            validate_agent_names(['claude', 'invalid'])

    def test_all_supported_agents(self):
        """Test all supported agents validate successfully."""
        # Test all agents except github-copilot (which is an alias)
        agents = [a for a in SUPPORTED_AGENTS if a != 'github-copilot']
        result = validate_agent_names(agents)
        assert len(result) == len(agents)
        # All should be lowercase
        assert all(a.islower() for a in result)


class TestSupportedAgents:
    """Tests for SUPPORTED_AGENTS constant."""

    def test_supported_agents_list(self):
        """Test SUPPORTED_AGENTS contains expected agents."""
        expected_agents = ['claude', 'copilot', 'github-copilot', 'cursor', 'windsurf', 'aider', 'continue']
        assert set(SUPPORTED_AGENTS) == set(expected_agents)

    def test_supported_agents_count(self):
        """Test SUPPORTED_AGENTS has the expected count."""
        # 6 unique agents + 1 alias
        assert len(SUPPORTED_AGENTS) == 7
