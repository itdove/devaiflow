"""Tests for devflow/utils/claude_commands.py - bundled slash command installation."""

import pytest
from pathlib import Path
import shutil

from devflow.utils.claude_commands import (
    get_bundled_commands_dir,
    get_bundled_skills_dir,
    get_workspace_commands_dir,
    get_workspace_skills_dir,
    list_bundled_commands,
    list_bundled_skills,
    install_or_upgrade_commands,
    install_or_upgrade_skills,
    get_command_status,
    get_all_command_statuses,
    get_skill_status,
    get_all_skill_statuses,
    _are_skill_dirs_identical,
)


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace directory."""
    workspace = tmp_path / "test_workspace"
    workspace.mkdir()
    return str(workspace)


def test_get_bundled_commands_dir():
    """Test getting the bundled commands directory path."""
    bundled_dir = get_bundled_commands_dir()
    assert bundled_dir.exists()
    assert bundled_dir.name == "claude_commands"
    assert (bundled_dir.parent.name == "devflow")  # Should be in devflow/ package


def test_get_workspace_commands_dir(temp_workspace):
    """Test getting the workspace .claude/commands directory path."""
    commands_dir = get_workspace_commands_dir(temp_workspace)
    assert commands_dir == Path(temp_workspace) / ".claude" / "commands"


def test_list_bundled_commands():
    """Test listing bundled slash command files."""
    commands = list_bundled_commands()
    assert len(commands) >= 10  # All bundled daf-*.md commands 
    assert all(cmd.suffix == ".md" for cmd in commands)
    # Only daf-* commands remain after deprecation cleanup
    assert all(cmd.name.startswith("daf-") for cmd in commands)

    # Check that our expected commands are present
    command_names = [cmd.name for cmd in commands]
    # daf-* commands
    assert "daf-list-conversations.md" in command_names
    assert "daf-read-conversation.md" in command_names
    assert "daf-list.md" in command_names
    assert "daf-jira.md" in command_names
    assert "daf-status.md" in command_names
    assert "daf-help.md" in command_names
    assert "daf-info.md" in command_names
    assert "daf-notes.md" in command_names
    assert "daf-active.md" in command_names
    assert "daf-config.md" in command_names


def test_install_or_upgrade_commands_fresh_install(temp_workspace):
    """Test installing commands to a workspace that has none yet."""
    changed, up_to_date, failed = install_or_upgrade_commands(temp_workspace, quiet=True)

    # All commands should be installed 
    assert len(changed) >= 10
    assert len(up_to_date) == 0
    assert len(failed) == 0

    # Verify files were created
    commands_dir = get_workspace_commands_dir(temp_workspace)
    assert commands_dir.exists()
    # daf-* commands
    assert (commands_dir / "daf-list-conversations.md").exists()
    assert (commands_dir / "daf-read-conversation.md").exists()
    assert (commands_dir / "daf-list.md").exists()
    assert (commands_dir / "daf-jira.md").exists()
    assert (commands_dir / "daf-status.md").exists()
    assert (commands_dir / "daf-help.md").exists()
    assert (commands_dir / "daf-info.md").exists()
    assert (commands_dir / "daf-notes.md").exists()
    assert (commands_dir / "daf-active.md").exists()
    assert (commands_dir / "daf-config.md").exists()
    # daf-* commands 
    assert (commands_dir / "daf-list-conversations.md").exists()
    assert (commands_dir / "daf-read-conversation.md").exists()
    assert (commands_dir / "daf-list.md").exists()
    assert (commands_dir / "daf-jira.md").exists()
    assert (commands_dir / "daf-status.md").exists()
    assert (commands_dir / "daf-help.md").exists()
    assert (commands_dir / "daf-info.md").exists()
    assert (commands_dir / "daf-notes.md").exists()
    assert (commands_dir / "daf-active.md").exists()
    assert (commands_dir / "daf-config.md").exists()


def test_install_or_upgrade_commands_already_up_to_date(temp_workspace):
    """Test upgrade when commands are already up-to-date."""
    # First install
    changed1, _, _ = install_or_upgrade_commands(temp_workspace, quiet=True)
    assert len(changed1) >= 10  # 10 daf-*.md commands, daf-*.md removed

    # Second install should show all up-to-date
    changed2, up_to_date2, failed2 = install_or_upgrade_commands(temp_workspace, quiet=True)
    assert len(changed2) == 0
    assert len(up_to_date2) >= 10  # 10 daf-*.md commands, daf-*.md removed
    assert len(failed2) == 0


def test_install_or_upgrade_commands_outdated(temp_workspace):
    """Test upgrade when commands are outdated."""
    # Install commands first
    install_or_upgrade_commands(temp_workspace, quiet=True)

    # Modify one command to simulate outdated version
    commands_dir = get_workspace_commands_dir(temp_workspace)
    cmd_file = commands_dir / "daf-list-conversations.md"
    cmd_file.write_text("OLD CONTENT")

    # Upgrade should detect the outdated command
    changed, up_to_date, failed = install_or_upgrade_commands(temp_workspace, quiet=True)

    assert "daf-list-conversations.md" in changed
    assert len(failed) == 0

    # Verify file was updated
    assert cmd_file.read_text() != "OLD CONTENT"


def test_install_or_upgrade_commands_dry_run(temp_workspace):
    """Test dry run mode doesn't actually install commands."""
    changed, up_to_date, failed = install_or_upgrade_commands(
        temp_workspace, dry_run=True, quiet=True
    )

    # Should report what would be changed 
    assert len(changed) >= 10
    assert len(failed) == 0

    # But commands directory should not exist
    commands_dir = get_workspace_commands_dir(temp_workspace)
    assert not commands_dir.exists()


def test_install_or_upgrade_commands_workspace_not_exists(tmp_path):
    """Test error handling when workspace doesn't exist."""
    nonexistent = tmp_path / "nonexistent"

    with pytest.raises(FileNotFoundError, match="Workspace directory does not exist"):
        install_or_upgrade_commands(str(nonexistent), quiet=True)


def test_get_command_status_not_installed(temp_workspace):
    """Test getting status of a command that isn't installed yet."""
    status = get_command_status(temp_workspace, "daf-list-conversations.md")
    assert status == "not_installed"


def test_get_command_status_up_to_date(temp_workspace):
    """Test getting status of an up-to-date command."""
    # Install commands
    install_or_upgrade_commands(temp_workspace, quiet=True)

    status = get_command_status(temp_workspace, "daf-list-conversations.md")
    assert status == "up_to_date"


def test_get_command_status_outdated(temp_workspace):
    """Test getting status of an outdated command."""
    # Install commands
    install_or_upgrade_commands(temp_workspace, quiet=True)

    # Modify the installed file to make it outdated
    commands_dir = get_workspace_commands_dir(temp_workspace)
    cmd_file = commands_dir / "daf-list-conversations.md"
    cmd_file.write_text("MODIFIED CONTENT")

    status = get_command_status(temp_workspace, "daf-list-conversations.md")
    assert status == "outdated"


def test_get_command_status_not_in_bundle(temp_workspace):
    """Test getting status of a command that doesn't exist in the bundle."""
    status = get_command_status(temp_workspace, "nonexistent-command.md")
    assert status is None


def test_get_all_command_statuses_fresh_workspace(temp_workspace):
    """Test getting statuses of all commands in fresh workspace."""
    statuses = get_all_command_statuses(temp_workspace)

    assert len(statuses) >= 10  # 10 daf-*.md commands, daf-*.md removed
    assert all(status == "not_installed" for status in statuses.values())


def test_get_all_command_statuses_after_install(temp_workspace):
    """Test getting statuses after installation."""
    # Install commands
    install_or_upgrade_commands(temp_workspace, quiet=True)

    statuses = get_all_command_statuses(temp_workspace)

    assert len(statuses) >= 10  # 10 daf-*.md commands, daf-*.md removed
    assert all(status == "up_to_date" for status in statuses.values())


def test_get_all_command_statuses_mixed(temp_workspace):
    """Test getting statuses with a mix of states."""
    # Install commands
    install_or_upgrade_commands(temp_workspace, quiet=True)

    # Modify one command to make it outdated
    commands_dir = get_workspace_commands_dir(temp_workspace)
    cmd_file = commands_dir / "daf-list-conversations.md"
    cmd_file.write_text("MODIFIED CONTENT")

    statuses = get_all_command_statuses(temp_workspace)

    assert statuses["daf-list-conversations.md"] == "outdated"
    assert statuses["daf-read-conversation.md"] == "up_to_date"


def test_install_creates_parent_directories(temp_workspace):
    """Test that install creates .claude/commands directory if it doesn't exist."""
    commands_dir = get_workspace_commands_dir(temp_workspace)
    assert not commands_dir.exists()

    install_or_upgrade_commands(temp_workspace, quiet=True)

    assert commands_dir.exists()
    assert commands_dir.parent.exists()  # .claude directory


def test_commands_content_preserved(temp_workspace):
    """Test that command content matches bundled content after install."""
    install_or_upgrade_commands(temp_workspace, quiet=True)

    bundled_cmd = get_bundled_commands_dir() / "daf-list-conversations.md"
    installed_cmd = get_workspace_commands_dir(temp_workspace) / "daf-list-conversations.md"

    assert bundled_cmd.read_text() == installed_cmd.read_text()


def test_yaml_frontmatter_preserved(temp_workspace):
    """Test that YAML frontmatter is preserved during installation."""
    install_or_upgrade_commands(temp_workspace, quiet=True)

    # Check daf-list-conversations.md has frontmatter with name and description
    list_conv_path = get_workspace_commands_dir(temp_workspace) / "daf-list-conversations.md"
    list_conv_content = list_conv_path.read_text()

    assert list_conv_content.startswith("---\n")
    assert "name: daf-list-conversations" in list_conv_content
    assert "description: List all conversations in the current multi-project session" in list_conv_content
    # Verify frontmatter has both name and description fields
    frontmatter = list_conv_content.split("---\n")[1].strip()
    assert "name: daf-list-conversations" in frontmatter
    assert "description: List all conversations in the current multi-project session" in frontmatter

    # Check daf-read-conversation.md has frontmatter with name and description
    read_conv_path = get_workspace_commands_dir(temp_workspace) / "daf-read-conversation.md"
    read_conv_content = read_conv_path.read_text()

    assert read_conv_content.startswith("---\n")
    assert "name: daf-read-conversation" in read_conv_content
    assert "description: Read the conversation history from another repository in this multi-project session" in read_conv_content
    # Verify frontmatter has both name and description fields
    frontmatter = read_conv_content.split("---\n")[1].strip()
    assert "name: daf-read-conversation" in frontmatter
    assert "description: Read the conversation history from another repository in this multi-project session" in frontmatter


def test_yaml_frontmatter_preserved_during_upgrade(temp_workspace):
    """Test that YAML frontmatter is preserved when upgrading outdated commands."""
    # Install commands first
    install_or_upgrade_commands(temp_workspace, quiet=True)

    # Modify one command to simulate outdated version (but keep frontmatter structure)
    commands_dir = get_workspace_commands_dir(temp_workspace)
    cmd_file = commands_dir / "daf-list-conversations.md"
    cmd_file.write_text("---\nname: daf-list-conversations\ndescription: Old description\n---\n\nOLD CONTENT")

    # Upgrade should restore the correct frontmatter
    changed, up_to_date, failed = install_or_upgrade_commands(temp_workspace, quiet=True)

    assert "daf-list-conversations.md" in changed
    assert len(failed) == 0

    # Verify frontmatter was restored correctly with both name and description
    content = cmd_file.read_text()
    assert content.startswith("---\n")
    assert "name: daf-list-conversations" in content
    assert "description: List all conversations in the current multi-project session" in content
    assert "OLD CONTENT" not in content


# ============================================================================
# Skills Tests
# ============================================================================


@pytest.fixture
def temp_skill(tmp_path):
    """Create a temporary skill directory structure."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()

    # Create SKILL.md
    (skill_dir / "SKILL.md").write_text("""---
description: Test skill for testing
---

# Test Skill

This is a test skill.
""")

    # Create some additional files
    (skill_dir / "README.md").write_text("# Test Skill README")
    (skill_dir / "helpers.py").write_text("# Helper functions")

    return skill_dir


def test_get_bundled_skills_dir():
    """Test getting the bundled skills directory path."""
    skills_dir = get_bundled_skills_dir()
    # Should return path even if directory doesn't exist
    assert skills_dir.name == "cli_skills"
    assert skills_dir.parent.name == "devflow"


def test_get_workspace_skills_dir(temp_workspace):
    """Test getting the workspace .claude/skills directory path."""
    skills_dir = get_workspace_skills_dir(temp_workspace)
    assert skills_dir == Path(temp_workspace) / ".claude" / "skills"


def test_list_bundled_skills():
    """Test listing bundled skill directories."""
    skills = list_bundled_skills()
    # Should return list even if empty (bundled skills might not exist)
    assert isinstance(skills, list)
    # If skills exist, they should all be directories with SKILL.md
    for skill in skills:
        assert skill.is_dir()
        assert (skill / "SKILL.md").exists()


def test_are_skill_dirs_identical_same(temp_skill, tmp_path):
    """Test that identical skill directories are detected as identical."""
    dest_skill = tmp_path / "dest-skill"
    shutil.copytree(temp_skill, dest_skill)

    assert _are_skill_dirs_identical(temp_skill, dest_skill) is True


def test_are_skill_dirs_identical_different_content(temp_skill, tmp_path):
    """Test that skills with different file content are detected as different."""
    dest_skill = tmp_path / "dest-skill"
    shutil.copytree(temp_skill, dest_skill)

    # Modify a file
    (dest_skill / "SKILL.md").write_text("Different content")

    assert _are_skill_dirs_identical(temp_skill, dest_skill) is False


def test_are_skill_dirs_identical_missing_file(temp_skill, tmp_path):
    """Test that skills with missing files are detected as different."""
    dest_skill = tmp_path / "dest-skill"
    shutil.copytree(temp_skill, dest_skill)

    # Remove a file
    (dest_skill / "README.md").unlink()

    assert _are_skill_dirs_identical(temp_skill, dest_skill) is False


def test_install_or_upgrade_skills_workspace_not_exists(tmp_path):
    """Test error handling when workspace doesn't exist for skills."""
    nonexistent = tmp_path / "nonexistent"

    with pytest.raises(FileNotFoundError, match="Workspace directory does not exist"):
        install_or_upgrade_skills(str(nonexistent), quiet=True)


def test_install_or_upgrade_skills_no_bundled_skills(temp_workspace, monkeypatch):
    """Test install/upgrade when there are no bundled skills."""
    # Mock list_bundled_skills to return empty list
    monkeypatch.setattr('devflow.utils.claude_commands.list_bundled_skills', lambda: [])

    changed, up_to_date, failed = install_or_upgrade_skills(temp_workspace, quiet=True)

    assert len(changed) == 0
    assert len(up_to_date) == 0
    assert len(failed) == 0


def test_install_or_upgrade_skills_fresh_install(temp_workspace, temp_skill, monkeypatch):
    """Test installing skills to a workspace that has none yet."""
    # Mock list_bundled_skills to return our test skill
    monkeypatch.setattr('devflow.utils.claude_commands.list_bundled_skills', lambda: [temp_skill])

    # Mock config loader to avoid actual config file operations
    from unittest.mock import Mock, patch
    with patch('devflow.config.loader.ConfigLoader'):
        changed, up_to_date, failed = install_or_upgrade_skills(temp_workspace, quiet=True)

    assert len(changed) == 1
    assert "test-skill" in changed
    assert len(up_to_date) == 0
    assert len(failed) == 0

    # Verify skill was installed
    skills_dir = get_workspace_skills_dir(temp_workspace)
    assert (skills_dir / "test-skill" / "SKILL.md").exists()
    assert (skills_dir / "test-skill" / "README.md").exists()
    assert (skills_dir / "test-skill" / "helpers.py").exists()


def test_install_or_upgrade_skills_already_up_to_date(temp_workspace, temp_skill, monkeypatch):
    """Test upgrade when skills are already up-to-date."""
    monkeypatch.setattr('devflow.utils.claude_commands.list_bundled_skills', lambda: [temp_skill])

    from unittest.mock import patch
    with patch('devflow.config.loader.ConfigLoader'):
        # First install
        changed1, _, _ = install_or_upgrade_skills(temp_workspace, quiet=True)
        assert len(changed1) == 1

        # Second install should show skill as up-to-date
        changed2, up_to_date2, failed2 = install_or_upgrade_skills(temp_workspace, quiet=True)
        assert len(changed2) == 0
        assert len(up_to_date2) == 1
        assert "test-skill" in up_to_date2
        assert len(failed2) == 0


def test_install_or_upgrade_skills_outdated(temp_workspace, temp_skill, monkeypatch):
    """Test upgrade when skills are outdated."""
    monkeypatch.setattr('devflow.utils.claude_commands.list_bundled_skills', lambda: [temp_skill])

    from unittest.mock import patch
    with patch('devflow.config.loader.ConfigLoader'):
        # Install skill first
        install_or_upgrade_skills(temp_workspace, quiet=True)

        # Modify installed skill to simulate outdated version
        skills_dir = get_workspace_skills_dir(temp_workspace)
        skill_file = skills_dir / "test-skill" / "SKILL.md"
        skill_file.write_text("OLD CONTENT")

        # Upgrade should detect the outdated skill
        changed, up_to_date, failed = install_or_upgrade_skills(temp_workspace, quiet=True)

        assert "test-skill" in changed
        assert len(failed) == 0

        # Verify skill was updated
        assert skill_file.read_text() != "OLD CONTENT"


def test_install_or_upgrade_skills_dry_run(temp_workspace, temp_skill, monkeypatch):
    """Test dry run mode doesn't actually install skills."""
    monkeypatch.setattr('devflow.utils.claude_commands.list_bundled_skills', lambda: [temp_skill])

    from unittest.mock import patch
    with patch('devflow.config.loader.ConfigLoader'):
        changed, up_to_date, failed = install_or_upgrade_skills(
            temp_workspace, dry_run=True, quiet=True
        )

        # Should report what would be changed
        assert len(changed) == 1
        assert "test-skill" in changed
        assert len(failed) == 0

        # But skills directory should not exist
        skills_dir = get_workspace_skills_dir(temp_workspace)
        assert not skills_dir.exists()


def test_get_skill_status_not_installed(temp_workspace, temp_skill, monkeypatch):
    """Test getting status of a skill that isn't installed yet."""
    # Create bundled skills dir with our test skill
    bundled_dir = Path(temp_workspace) / "bundled" / "cli_skills"
    bundled_dir.mkdir(parents=True)
    dest_skill = bundled_dir / "test-skill"
    shutil.copytree(temp_skill, dest_skill)

    monkeypatch.setattr('devflow.utils.claude_commands.get_bundled_skills_dir', lambda: bundled_dir)

    status = get_skill_status(temp_workspace, "test-skill")
    assert status == "not_installed"


def test_get_skill_status_up_to_date(temp_workspace, temp_skill, monkeypatch):
    """Test getting status of an up-to-date skill."""
    # Create bundled skills dir with our test skill
    bundled_dir = Path(temp_workspace) / "bundled" / "cli_skills"
    bundled_dir.mkdir(parents=True)
    bundled_skill = bundled_dir / "test-skill"
    shutil.copytree(temp_skill, bundled_skill)

    # Install the skill
    skills_dir = get_workspace_skills_dir(temp_workspace)
    skills_dir.mkdir(parents=True)
    installed_skill = skills_dir / "test-skill"
    shutil.copytree(temp_skill, installed_skill)

    monkeypatch.setattr('devflow.utils.claude_commands.get_bundled_skills_dir', lambda: bundled_dir)

    status = get_skill_status(temp_workspace, "test-skill")
    assert status == "up_to_date"


def test_get_skill_status_outdated(temp_workspace, temp_skill, monkeypatch):
    """Test getting status of an outdated skill."""
    # Create bundled skills dir with our test skill
    bundled_dir = Path(temp_workspace) / "bundled" / "cli_skills"
    bundled_dir.mkdir(parents=True)
    bundled_skill = bundled_dir / "test-skill"
    shutil.copytree(temp_skill, bundled_skill)

    # Install the skill
    skills_dir = get_workspace_skills_dir(temp_workspace)
    skills_dir.mkdir(parents=True)
    installed_skill = skills_dir / "test-skill"
    shutil.copytree(temp_skill, installed_skill)

    # Modify the installed skill to make it outdated
    (installed_skill / "SKILL.md").write_text("MODIFIED CONTENT")

    monkeypatch.setattr('devflow.utils.claude_commands.get_bundled_skills_dir', lambda: bundled_dir)

    status = get_skill_status(temp_workspace, "test-skill")
    assert status == "outdated"


def test_get_skill_status_not_in_bundle(temp_workspace):
    """Test getting status of a skill that doesn't exist in the bundle."""
    status = get_skill_status(temp_workspace, "nonexistent-skill")
    assert status is None


def test_get_all_skill_statuses_fresh_workspace(temp_workspace, temp_skill, monkeypatch):
    """Test getting statuses of all skills in fresh workspace."""
    # Create bundled skills dir with our test skill
    bundled_dir = Path(temp_workspace) / "bundled" / "cli_skills"
    bundled_dir.mkdir(parents=True)
    bundled_skill = bundled_dir / "test-skill"
    shutil.copytree(temp_skill, bundled_skill)

    monkeypatch.setattr('devflow.utils.claude_commands.list_bundled_skills', lambda: [bundled_skill])
    monkeypatch.setattr('devflow.utils.claude_commands.get_bundled_skills_dir', lambda: bundled_dir)

    statuses = get_all_skill_statuses(temp_workspace)

    assert len(statuses) == 1
    assert statuses["test-skill"] == "not_installed"


def test_get_all_skill_statuses_after_install(temp_workspace, temp_skill, monkeypatch):
    """Test getting statuses after skill installation."""
    # Create bundled skills dir
    bundled_dir = Path(temp_workspace) / "bundled" / "cli_skills"
    bundled_dir.mkdir(parents=True)
    bundled_skill = bundled_dir / "test-skill"
    shutil.copytree(temp_skill, bundled_skill)

    # Install the skill
    skills_dir = get_workspace_skills_dir(temp_workspace)
    skills_dir.mkdir(parents=True)
    installed_skill = skills_dir / "test-skill"
    shutil.copytree(temp_skill, installed_skill)

    monkeypatch.setattr('devflow.utils.claude_commands.list_bundled_skills', lambda: [bundled_skill])
    monkeypatch.setattr('devflow.utils.claude_commands.get_bundled_skills_dir', lambda: bundled_dir)

    statuses = get_all_skill_statuses(temp_workspace)

    assert len(statuses) == 1
    assert statuses["test-skill"] == "up_to_date"
