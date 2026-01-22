"""Tests for initial prompt generation with configured context files and session types."""

import pytest

from devflow.cli.commands.new_command import _generate_initial_prompt
from devflow.config.models import ContextFile


def test_generate_initial_prompt_defaults_only(temp_daf_home):
    """Test generating initial prompt with only default context files."""
    from devflow.config.loader import ConfigLoader

    # Create default config (no configured context files)
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config_loader.save_config(config)

    # Generate prompt
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="test goal",
    )

    # Verify defaults are included
    assert "AGENTS.md (agent-specific instructions)" in prompt
    assert "CLAUDE.md (project guidelines and standards)" in prompt
    assert "DAF_AGENTS.md (daf tool usage guide)" in prompt

    # Verify no additional files
    assert "ARCHITECTURE.md" not in prompt


def test_generate_initial_prompt_with_configured_local_file(temp_daf_home):
    """Test generating initial prompt with configured local context file."""
    from devflow.config.loader import ConfigLoader

    # Create config with additional local context file
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config.context_files.files = [
        ContextFile(path="ARCHITECTURE.md", description="system architecture")
    ]
    config_loader.save_config(config)

    # Generate prompt
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="test goal",
    )

    # Verify defaults are included
    assert "AGENTS.md (agent-specific instructions)" in prompt
    assert "CLAUDE.md (project guidelines and standards)" in prompt
    assert "DAF_AGENTS.md (daf tool usage guide)" in prompt

    # Verify configured file is included
    assert "ARCHITECTURE.md (system architecture)" in prompt


def test_generate_initial_prompt_with_configured_url(temp_daf_home):
    """Test generating initial prompt with configured URL context file."""
    from devflow.config.loader import ConfigLoader

    # Create config with URL context file
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    url = "https://github.com/example-org/.github/blob/main/STANDARDS.md"
    config.context_files.files = [
        ContextFile(path=url, description="coding standards")
    ]
    config_loader.save_config(config)

    # Generate prompt
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="test goal",
    )

    # Verify defaults are included
    assert "AGENTS.md (agent-specific instructions)" in prompt
    assert "CLAUDE.md (project guidelines and standards)" in prompt
    assert "DAF_AGENTS.md (daf tool usage guide)" in prompt

    # Verify URL is included
    assert url in prompt
    assert "(coding standards)" in prompt


def test_generate_initial_prompt_with_multiple_configured_files(temp_daf_home):
    """Test generating initial prompt with multiple configured context files."""
    from devflow.config.loader import ConfigLoader

    # Create config with multiple context files
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config.context_files.files = [
        ContextFile(path="ARCHITECTURE.md", description="system architecture"),
        ContextFile(path="DESIGN.md", description="design docs"),
        ContextFile(
            path="https://github.com/org/repo/blob/main/STANDARDS.md",
            description="coding standards",
        ),
    ]
    config_loader.save_config(config)

    # Generate prompt
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="test goal",
    )

    # Verify defaults are included
    assert "AGENTS.md (agent-specific instructions)" in prompt
    assert "CLAUDE.md (project guidelines and standards)" in prompt
    assert "DAF_AGENTS.md (daf tool usage guide)" in prompt

    # Verify all configured files are included in order
    assert "ARCHITECTURE.md (system architecture)" in prompt
    assert "DESIGN.md (design docs)" in prompt
    assert "https://github.com/org/repo/blob/main/STANDARDS.md (coding standards)" in prompt

    # Verify order (defaults first, then configured)
    agent_pos = prompt.find("AGENTS.md")
    claude_pos = prompt.find("CLAUDE.md")
    arch_pos = prompt.find("ARCHITECTURE.md")
    design_pos = prompt.find("DESIGN.md")

    assert agent_pos < claude_pos < arch_pos < design_pos


def test_generate_initial_prompt_with_jira_and_context_files(temp_daf_home):
    """Test generating initial prompt with JIRA and configured context files."""
    from devflow.config.loader import ConfigLoader

    # Create config with context files
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config.context_files.files = [
        ContextFile(path="ARCHITECTURE.md", description="system architecture")
    ]
    config_loader.save_config(config)

    # Generate prompt with JIRA
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="test goal",
        issue_key="PROJ-12345",
        issue_title="Implement feature X",
    )

    # Verify goal line
    assert "Work on: PROJ-12345: Implement feature X" in prompt

    # Verify context files
    assert "AGENTS.md (agent-specific instructions)" in prompt
    assert "CLAUDE.md (project guidelines and standards)" in prompt
    assert "DAF_AGENTS.md (daf tool usage guide)" in prompt
    assert "ARCHITECTURE.md (system architecture)" in prompt

    # Verify JIRA instruction
    assert "Also read the issue tracker ticket:" in prompt
    assert "daf jira view PROJ-12345" in prompt


def test_generate_initial_prompt_no_config(temp_daf_home):
    """Test generating initial prompt when config doesn't exist (graceful degradation)."""
    # Don't create config - should still work with defaults

    # Generate prompt
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="test goal",
    )

    # Should still include defaults
    assert "AGENTS.md (agent-specific instructions)" in prompt
    assert "CLAUDE.md (project guidelines and standards)" in prompt
    assert "DAF_AGENTS.md (daf tool usage guide)" in prompt


def test_generate_initial_prompt_empty_context_files(temp_daf_home):
    """Test generating initial prompt when context_files config exists but is empty."""
    from devflow.config.loader import ConfigLoader

    # Create config with empty context files list
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config.context_files.files = []  # Explicitly empty
    config_loader.save_config(config)

    # Generate prompt
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="test goal",
    )

    # Should still include defaults
    assert "AGENTS.md (agent-specific instructions)" in prompt
    assert "CLAUDE.md (project guidelines and standards)" in prompt
    assert "DAF_AGENTS.md (daf tool usage guide)" in prompt

    # Should not have any additional files
    lines = prompt.split("\n")
    context_section = [line for line in lines if line.strip().startswith("-")]
    assert len(context_section) == 3  # Only AGENTS.md, CLAUDE.md, and DAF_AGENTS.md


def test_generate_initial_prompt_ticket_creation_type(temp_daf_home):
    """Test generating initial prompt for ticket_creation session type."""
    from devflow.config.loader import ConfigLoader

    # Create default config
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config_loader.save_config(config)

    # Generate prompt with ticket_creation session type
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="Create JIRA story",
        session_type="ticket_creation",
    )

    # Verify analysis-only constraints are included
    assert "ANALYSIS-ONLY" in prompt
    assert "DO NOT modify any code" in prompt
    assert "DO NOT make any file changes" in prompt
    assert "READ-ONLY analysis" in prompt

    # Should still include defaults
    assert "AGENTS.md (agent-specific instructions)" in prompt
    assert "CLAUDE.md (project guidelines and standards)" in prompt
    assert "DAF_AGENTS.md (daf tool usage guide)" in prompt


def test_generate_initial_prompt_development_type(temp_daf_home):
    """Test generating initial prompt for development session type (default)."""
    from devflow.config.loader import ConfigLoader

    # Create default config
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config_loader.save_config(config)

    # Generate prompt with development session type (default)
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="Implement feature",
        session_type="development",
    )

    # Verify analysis-only constraints are NOT included for development sessions
    assert "ANALYSIS-ONLY" not in prompt
    assert "DO NOT modify any code" not in prompt
    assert "READ-ONLY analysis" not in prompt

    # Should still include defaults
    assert "AGENTS.md (agent-specific instructions)" in prompt
    assert "CLAUDE.md (project guidelines and standards)" in prompt
    assert "DAF_AGENTS.md (daf tool usage guide)" in prompt


def test_generate_initial_prompt_ticket_creation_with_jira(temp_daf_home):
    """Test generating initial prompt for ticket_creation with issue key."""
    from devflow.config.loader import ConfigLoader

    # Create default config
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config_loader.save_config(config)

    # Generate prompt with ticket_creation and JIRA
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="Create JIRA story for backup feature",
        issue_key="PROJ-59038",
        issue_title="Implement backup and restore",
        session_type="ticket_creation",
    )

    # Verify analysis-only constraints are included
    assert "ANALYSIS-ONLY" in prompt
    assert "DO NOT modify any code" in prompt

    # Verify JIRA reading instruction is included
    assert "daf jira view PROJ-59038" in prompt

    # Verify goal line includes JIRA
    assert "PROJ-59038: Implement backup and restore" in prompt


def test_generate_initial_prompt_development_with_unit_tests_enabled(temp_daf_home):
    """Test generating initial prompt for development session with testing prompt enabled (default)."""
    from devflow.config.loader import ConfigLoader

    # Create config with show_prompt_unit_tests = True (default)
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config.prompts.show_prompt_unit_tests = True
    config_loader.save_config(config)

    # Generate prompt with development session type
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="Implement feature",
        session_type="development",
    )

    # Verify testing instructions are included
    assert "Testing Requirements:" in prompt
    assert "Identify the project's testing framework from the codebase" in prompt
    assert "Run the project's test suite after making code changes" in prompt
    assert "Create tests for new methods" in prompt
    assert "Fix all failing tests before marking tasks complete" in prompt
    assert "Common test commands by language:" in prompt
    assert "Python: pytest" in prompt
    assert "JavaScript/TypeScript: npm test" in prompt
    assert "Go: go test" in prompt

    # Should still include defaults
    assert "AGENTS.md (agent-specific instructions)" in prompt
    assert "CLAUDE.md (project guidelines and standards)" in prompt
    assert "DAF_AGENTS.md (daf tool usage guide)" in prompt


def test_generate_initial_prompt_development_with_unit_tests_disabled(temp_daf_home):
    """Test generating initial prompt for development session with testing prompt disabled."""
    from devflow.config.loader import ConfigLoader

    # Create config with show_prompt_unit_tests = False
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config.prompts.show_prompt_unit_tests = False
    config_loader.save_config(config)

    # Generate prompt with development session type
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="Implement feature",
        session_type="development",
    )

    # Verify testing instructions are NOT included
    assert "Testing Requirements:" not in prompt
    assert "Identify the project's testing framework" not in prompt
    assert "Run the project's test suite" not in prompt
    assert "Create tests for new methods" not in prompt

    # Should still include defaults
    assert "AGENTS.md (agent-specific instructions)" in prompt
    assert "CLAUDE.md (project guidelines and standards)" in prompt
    assert "DAF_AGENTS.md (daf tool usage guide)" in prompt


def test_generate_initial_prompt_ticket_creation_no_unit_tests_even_if_enabled(temp_daf_home):
    """Test that testing prompt is NOT shown for ticket_creation sessions even if enabled."""
    from devflow.config.loader import ConfigLoader

    # Create config with show_prompt_unit_tests = True
    config_loader = ConfigLoader()
    config = config_loader.create_default_config()
    config.prompts.show_prompt_unit_tests = True
    config_loader.save_config(config)

    # Generate prompt with ticket_creation session type
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="Create JIRA story",
        session_type="ticket_creation",
    )

    # Verify testing instructions are NOT included for ticket_creation
    assert "Testing Requirements:" not in prompt
    assert "Identify the project's testing framework" not in prompt
    assert "Run the project's test suite" not in prompt

    # Verify analysis-only constraints ARE included
    assert "ANALYSIS-ONLY" in prompt

    # Should still include defaults
    assert "AGENTS.md (agent-specific instructions)" in prompt
