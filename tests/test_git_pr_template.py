"""Tests for AI-powered PR/MR template parsing and filling."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import subprocess

from devflow.git.pr_template import (
    fill_pr_template_with_ai,
    _fill_template_with_api,
    _fill_template_fallback
)


@pytest.fixture
def mock_session():
    """Create a mock session."""
    session = Mock()
    session.issue_key = "PROJ-12345"
    session.goal = "Add user authentication feature"

    # Mock active conversation
    conversation = Mock()
    conversation.branch = "feature/user-auth"
    session.active_conversation = conversation

    return session


@pytest.fixture
def sample_template():
    """Sample PR template."""
    return """## Description
<!-- Describe what this PR does -->

## Jira Issue
<!-- Link to JIRA ticket -->
Jira Issue: <PROJ-NNNN>

## Testing
<!-- How to test -->

## Deployment Considerations
<!-- Any deployment notes -->

Assisted-by: <!-- Who helped -->
"""


@pytest.fixture
def git_context():
    """Sample git context."""
    return {
        'commit_log': "feat: Add login endpoint\nfeat: Add JWT token generation",
        'changed_files': ["src/auth/login.py", "src/auth/jwt.py", "tests/test_auth.py"],
        'base_branch': "main",
        'current_branch': "feature/user-auth"
    }


class TestFillPrTemplateWithAi:
    """Tests for fill_pr_template_with_ai function."""

    def test_successful_claude_cli_filling(self, mock_session, sample_template, git_context, tmp_path, monkeypatch):
        """Test successful template filling using Claude CLI."""
        # Set up environment
        monkeypatch.chdir(tmp_path)

        filled_content = """## Description
Add user authentication feature with JWT tokens

## Jira Issue
Jira Issue: <https://jira.example.com/browse/PROJ-12345>

## Testing
1. Test login endpoint with valid credentials
2. Verify JWT token generation

## Deployment Considerations
No special deployment considerations

Assisted-by: Claude
"""

        with patch('devflow.git.pr_template.ConfigLoader') as mock_config_loader_class:
            with patch('devflow.git.pr_template.subprocess.run') as mock_run:
                # Mock successful subprocess run
                mock_result = Mock()
                mock_result.returncode = 0
                mock_result.stdout = filled_content
                mock_run.return_value = mock_result

                # Mock config loader
                mock_config = Mock()
                mock_config.jira.url = "https://jira.example.com"
                mock_loader = Mock()
                mock_loader.config_file.exists.return_value = True
                mock_loader.load_config.return_value = mock_config
                mock_config_loader_class.return_value = mock_loader

                result = fill_pr_template_with_ai(
                    sample_template,
                    mock_session,
                    tmp_path,
                    git_context
                )

                assert "Add user authentication feature" in result
                assert "PROJ-12345" in result
                mock_run.assert_called_once()

    def test_claude_cli_with_code_fences(self, mock_session, sample_template, git_context, tmp_path, monkeypatch):
        """Test that code fences are properly cleaned from Claude CLI output."""
        monkeypatch.chdir(tmp_path)

        filled_with_fences = """```
## Description
Test description

Assisted-by: Claude
```"""

        with patch('devflow.git.pr_template.ConfigLoader') as mock_config_loader_class:
            with patch('devflow.git.pr_template.subprocess.run') as mock_run:
                mock_result = Mock()
                mock_result.returncode = 0
                mock_result.stdout = filled_with_fences
                mock_run.return_value = mock_result

                mock_config = Mock()
                mock_config.jira.url = "https://jira.example.com"
                mock_loader = Mock()
                mock_loader.config_file.exists.return_value = True
                mock_loader.load_config.return_value = mock_config
                mock_config_loader_class.return_value = mock_loader

                result = fill_pr_template_with_ai(
                    sample_template,
                    mock_session,
                    tmp_path,
                    git_context
                )

                # Code fences should be removed
                assert not result.startswith("```")
                assert not result.endswith("```")
                assert "## Description" in result

    def test_claude_cli_not_found_fallback_to_api(self, mock_session, sample_template, git_context, tmp_path, monkeypatch):
        """Test fallback to API when Claude CLI is not found."""
        monkeypatch.chdir(tmp_path)

        with patch('devflow.git.pr_template.ConfigLoader') as mock_config_loader_class:
            with patch('devflow.git.pr_template.subprocess.run') as mock_run:
                with patch('devflow.git.pr_template._fill_template_with_api') as mock_api:
                    # Simulate Claude CLI not found
                    mock_run.side_effect = FileNotFoundError("claude not found")
                    mock_api.return_value = "Filled via API"

                    mock_loader = Mock()
                    mock_loader.config_file.exists.return_value = False
                    mock_config_loader_class.return_value = mock_loader

                    result = fill_pr_template_with_ai(
                        sample_template,
                        mock_session,
                        tmp_path,
                        git_context
                    )

                    assert result == "Filled via API"
                    mock_api.assert_called_once()

    def test_claude_cli_timeout_fallback(self, mock_session, sample_template, git_context, tmp_path, monkeypatch):
        """Test fallback when Claude CLI times out."""
        monkeypatch.chdir(tmp_path)

        with patch('devflow.git.pr_template.ConfigLoader') as mock_config_loader_class:
            with patch('devflow.git.pr_template.subprocess.run') as mock_run:
                with patch('devflow.git.pr_template._fill_template_fallback') as mock_fallback:
                    # Simulate timeout
                    mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=45)
                    mock_fallback.return_value = "Filled via fallback"

                    mock_loader = Mock()
                    mock_loader.config_file.exists.return_value = False
                    mock_config_loader_class.return_value = mock_loader

                    result = fill_pr_template_with_ai(
                        sample_template,
                        mock_session,
                        tmp_path,
                        git_context
                    )

                    assert result == "Filled via fallback"
                    mock_fallback.assert_called_once_with(sample_template, mock_session, git_context)

    def test_claude_cli_error_fallback(self, mock_session, sample_template, git_context, tmp_path, monkeypatch):
        """Test fallback when Claude CLI has an error."""
        monkeypatch.chdir(tmp_path)

        with patch('devflow.git.pr_template.ConfigLoader') as mock_config_loader_class:
            with patch('devflow.git.pr_template.subprocess.run') as mock_run:
                with patch('devflow.git.pr_template._fill_template_fallback') as mock_fallback:
                    # Simulate generic error
                    mock_run.side_effect = RuntimeError("Unexpected error")
                    mock_fallback.return_value = "Filled via fallback"

                    mock_loader = Mock()
                    mock_loader.config_file.exists.return_value = False
                    mock_config_loader_class.return_value = mock_loader

                    result = fill_pr_template_with_ai(
                        sample_template,
                        mock_session,
                        tmp_path,
                        git_context
                    )

                    assert result == "Filled via fallback"
                    mock_fallback.assert_called_once()

    def test_claude_cli_non_zero_return_code_api_fallback(self, mock_session, sample_template, git_context, tmp_path, monkeypatch):
        """Test API fallback when Claude CLI returns non-zero exit code."""
        monkeypatch.chdir(tmp_path)

        with patch('devflow.git.pr_template.ConfigLoader') as mock_config_loader_class:
            with patch('devflow.git.pr_template.subprocess.run') as mock_run:
                with patch('devflow.git.pr_template._fill_template_with_api') as mock_api:
                    # Simulate non-zero exit code
                    mock_result = Mock()
                    mock_result.returncode = 1
                    mock_run.return_value = mock_result
                    mock_api.return_value = "Filled via API"

                    mock_loader = Mock()
                    mock_loader.config_file.exists.return_value = False
                    mock_config_loader_class.return_value = mock_loader

                    result = fill_pr_template_with_ai(
                        sample_template,
                        mock_session,
                        tmp_path,
                        git_context
                    )

                    assert result == "Filled via API"
                    mock_api.assert_called_once()

    def test_session_without_issue_key(self, sample_template, git_context, tmp_path, monkeypatch):
        """Test template filling when session has no issue key."""
        monkeypatch.chdir(tmp_path)

        session_no_issue = Mock()
        session_no_issue.issue_key = None
        session_no_issue.goal = "Refactoring work"
        session_no_issue.active_conversation = None

        with patch('devflow.git.pr_template.ConfigLoader') as mock_config_loader_class:
            with patch('devflow.git.pr_template.subprocess.run') as mock_run:
                mock_result = Mock()
                mock_result.returncode = 0
                mock_result.stdout = "Filled template"
                mock_run.return_value = mock_result

                mock_loader = Mock()
                mock_loader.config_file.exists.return_value = False
                mock_config_loader_class.return_value = mock_loader

                result = fill_pr_template_with_ai(
                    sample_template,
                    session_no_issue,
                    tmp_path,
                    git_context
                )

                assert result == "Filled template"
                # Verify subprocess was called (meaning no early exit)
                mock_run.assert_called_once()

    def test_session_without_active_conversation(self, mock_session, sample_template, git_context, tmp_path, monkeypatch):
        """Test template filling when session has no active conversation."""
        monkeypatch.chdir(tmp_path)

        mock_session.active_conversation = None

        with patch('devflow.git.pr_template.ConfigLoader') as mock_config_loader_class:
            with patch('devflow.git.pr_template.subprocess.run') as mock_run:
                mock_result = Mock()
                mock_result.returncode = 0
                mock_result.stdout = "Filled template"
                mock_run.return_value = mock_result

                mock_loader = Mock()
                mock_loader.config_file.exists.return_value = False
                mock_config_loader_class.return_value = mock_loader

                result = fill_pr_template_with_ai(
                    sample_template,
                    mock_session,
                    tmp_path,
                    git_context
                )

                assert result == "Filled template"

    def test_many_changed_files_truncation(self, mock_session, sample_template, tmp_path, monkeypatch):
        """Test that long file lists are truncated in context."""
        monkeypatch.chdir(tmp_path)

        # Create context with >30 files
        many_files = [f"file_{i}.py" for i in range(50)]
        git_context_many = {
            'commit_log': "Many changes",
            'changed_files': many_files,
            'base_branch': "main",
            'current_branch': "feature/big-change"
        }

        with patch('devflow.git.pr_template.ConfigLoader') as mock_config_loader_class:
            with patch('devflow.git.pr_template.subprocess.run') as mock_run:
                mock_result = Mock()
                mock_result.returncode = 0
                mock_result.stdout = "Filled template"
                mock_run.return_value = mock_result

                mock_loader = Mock()
                mock_loader.config_file.exists.return_value = False
                mock_config_loader_class.return_value = mock_loader

                result = fill_pr_template_with_ai(
                    sample_template,
                    mock_session,
                    tmp_path,
                    git_context_many
                )

                # Check that subprocess was called with truncation message
                call_args = mock_run.call_args
                prompt_input = call_args.kwargs['input']
                assert "and 20 more files" in prompt_input


class TestFillTemplateWithApi:
    """Tests for _fill_template_with_api function."""

    def test_successful_api_call(self, sample_template, monkeypatch):
        """Test successful API template filling."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-12345")

        # Patch anthropic module import
        mock_anthropic_module = Mock()
        with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
            with patch.object(mock_anthropic_module, 'Anthropic') as mock_anthropic_class:
                mock_client = Mock()
                mock_message = Mock()
                mock_content = Mock()
                mock_content.text = "Filled template via API"
                mock_message.content = [mock_content]
                mock_client.messages.create.return_value = mock_message
                mock_anthropic_class.return_value = mock_client

                result = _fill_template_with_api(sample_template, "Test context")

                assert result == "Filled template via API"
                mock_client.messages.create.assert_called_once()

    def test_api_no_api_key(self, sample_template, monkeypatch):
        """Test API filling fails when ANTHROPIC_API_KEY is not set."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY not set"):
            _fill_template_with_api(sample_template, "Test context")

    def test_api_call_with_code_fences(self, sample_template, monkeypatch):
        """Test that API output code fences are cleaned."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-12345")

        api_output_with_fences = """```markdown
## Description
Test content
```"""

        mock_anthropic_module = Mock()
        with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
            with patch.object(mock_anthropic_module, 'Anthropic') as mock_anthropic_class:
                mock_client = Mock()
                mock_message = Mock()
                mock_content = Mock()
                mock_content.text = api_output_with_fences
                mock_message.content = [mock_content]
                mock_client.messages.create.return_value = mock_message
                mock_anthropic_class.return_value = mock_client

                result = _fill_template_with_api(sample_template, "Test context")

                # Code fences should be removed
                assert not result.startswith("```")
                assert not result.endswith("```")
                assert "## Description" in result

    def test_api_call_no_content(self, sample_template, monkeypatch):
        """Test API filling fails when response has no content."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-12345")

        mock_anthropic_module = Mock()
        with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
            with patch.object(mock_anthropic_module, 'Anthropic') as mock_anthropic_class:
                mock_client = Mock()
                mock_message = Mock()
                mock_message.content = []
                mock_client.messages.create.return_value = mock_message
                mock_anthropic_class.return_value = mock_client

                with pytest.raises(RuntimeError, match="No content in API response"):
                    _fill_template_with_api(sample_template, "Test context")

    def test_api_call_exception(self, sample_template, monkeypatch):
        """Test API filling handles exceptions properly."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-12345")

        mock_anthropic_module = Mock()
        with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
            with patch.object(mock_anthropic_module, 'Anthropic') as mock_anthropic_class:
                mock_client = Mock()
                mock_client.messages.create.side_effect = Exception("Network error")
                mock_anthropic_class.return_value = mock_client

                with pytest.raises(RuntimeError, match="API template filling failed"):
                    _fill_template_with_api(sample_template, "Test context")


class TestFillTemplateFallback:
    """Tests for _fill_template_fallback function."""

    def test_fallback_with_issue_key(self, mock_session, sample_template):
        """Test fallback template filling with JIRA issue key."""
        git_context = {
            'commit_log': "feat: Add feature",
            'changed_files': ["file.py"],
            'base_branch': "main"
        }

        with patch('devflow.git.pr_template.ConfigLoader') as mock_config_loader_class:
            mock_config = Mock()
            mock_config.jira.url = "https://jira.example.com"
            mock_loader = Mock()
            mock_loader.config_file.exists.return_value = True
            mock_loader.load_config.return_value = mock_config
            mock_config_loader_class.return_value = mock_loader

            result = _fill_template_fallback(sample_template, mock_session, git_context)

            # Should replace PROJ-NNNN with actual issue key
            assert "PROJ-12345" in result
            assert "PROJ-NNNN" not in result
            assert "https://jira.example.com/browse/PROJ-12345" in result
            assert "Add user authentication feature" in result
            assert "Assisted-by: Claude" in result

    def test_fallback_without_issue_key(self, sample_template):
        """Test fallback template filling without JIRA issue key."""
        session_no_issue = Mock()
        session_no_issue.issue_key = None
        session_no_issue.goal = "General improvements"

        git_context = {
            'commit_log': "Refactor code",
            'changed_files': ["file.py"]
        }

        with patch('devflow.git.pr_template.ConfigLoader') as mock_config_loader_class:
            mock_loader = Mock()
            mock_loader.config_file.exists.return_value = False
            mock_config_loader_class.return_value = mock_loader

            result = _fill_template_fallback(sample_template, session_no_issue, git_context)

            # Should still fill description with goal
            assert "General improvements" in result
            assert "Assisted-by: Claude" in result

    def test_fallback_without_jira_config(self, mock_session, sample_template):
        """Test fallback when JIRA config is not available."""
        git_context = {
            'commit_log': "feat: Add feature",
            'changed_files': ["file.py"]
        }

        with patch('devflow.git.pr_template.ConfigLoader') as mock_config_loader_class:
            mock_loader = Mock()
            mock_loader.config_file.exists.return_value = False
            mock_config_loader_class.return_value = mock_loader

            result = _fill_template_fallback(sample_template, mock_session, git_context)

            # Should still replace issue key
            assert "PROJ-12345" in result
            assert "Add user authentication feature" in result

    def test_fallback_jira_key_pattern_variations(self, sample_template):
        """Test fallback handles various JIRA key patterns."""
        # Template with different JIRA patterns
        template_variations = """
        JIRA-1234
        jira-key
        PROJ-NNNN
        """

        session = Mock()
        session.issue_key = "PROJ-999"
        session.goal = "Fix bug"

        git_context = {}

        with patch('devflow.git.pr_template.ConfigLoader') as mock_config_loader_class:
            mock_loader = Mock()
            mock_loader.config_file.exists.return_value = False
            mock_config_loader_class.return_value = mock_loader

            result = _fill_template_fallback(template_variations, session, git_context)

            # Should replace various patterns
            assert "PROJ-999" in result
