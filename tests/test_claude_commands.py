"""Tests for devflow/utils/claude_commands.py - bundled skills installation."""

import pytest
from pathlib import Path
import shutil

from devflow.utils.claude_commands import (
    get_bundled_skills_dir,
    get_workspace_skills_dir,
    list_bundled_skills,
    list_slash_command_skills,
    list_reference_skills,
    install_or_upgrade_slash_commands,
    install_or_upgrade_reference_skills,
    _are_skill_dirs_identical,
    get_skill_status,
    get_all_skill_statuses,
    build_claude_command,
)


@pytest.fixture
def temp_user_home(tmp_path, monkeypatch):
    """Create a temporary user home directory."""
    user_home = tmp_path / "home"
    user_home.mkdir()
    monkeypatch.setenv("HOME", str(user_home))
    # Also patch Path.home() to return our temp home
    monkeypatch.setattr(Path, "home", lambda: user_home)
    return user_home


# ============================================================================
# Bundled Skills Discovery Tests
# ============================================================================

def test_get_bundled_skills_dir():
    """Test getting the bundled skills directory path."""
    bundled_dir = get_bundled_skills_dir()
    assert bundled_dir.exists()
    assert bundled_dir.name == "cli_skills"
    assert bundled_dir.parent.name == "devflow"


def test_list_bundled_skills():
    """Test listing all bundled skills."""
    skills = list_bundled_skills()

    # Should have at least 15 skills (11 slash commands + 4 reference skills)
    assert len(skills) >= 15

    # All should be directories with SKILL.md
    for skill in skills:
        assert skill.is_dir()
        assert (skill / "SKILL.md").exists()


def test_list_slash_command_skills():
    """Test listing slash command skills (with 'name:' field)."""
    slash_commands = list_slash_command_skills()

    # Should have 11 daf-* slash commands
    assert len(slash_commands) >= 11

    # Check some expected slash commands
    skill_names = [s.name for s in slash_commands]
    assert "daf-active" in skill_names
    assert "daf-help" in skill_names
    assert "daf-list" in skill_names
    assert "daf-jira" in skill_names

    # All should have SKILL.md with name: field
    for skill in slash_commands:
        skill_md = skill / "SKILL.md"
        content = skill_md.read_text()
        assert "name:" in content


def test_list_reference_skills():
    """Test listing reference skills (without 'name:' field)."""
    reference_skills = list_reference_skills()

    # Should have 4 reference skills
    assert len(reference_skills) >= 4

    # Check expected reference skills
    skill_names = [s.name for s in reference_skills]
    assert "daf-cli" in skill_names
    assert "gh-cli" in skill_names
    assert "git-cli" in skill_names
    assert "glab-cli" in skill_names

    # None should have name: field in SKILL.md
    for skill in reference_skills:
        skill_md = skill / "SKILL.md"
        content = skill_md.read_text()
        # Check frontmatter doesn't have name: field
        if content.startswith("---\n"):
            frontmatter = content.split("---\n")[1]
            assert "name:" not in frontmatter


# ============================================================================
# Slash Commands Installation Tests
# ============================================================================

def test_install_slash_commands_fresh_install(temp_user_home):
    """Test installing slash commands to user home."""
    changed, up_to_date, failed = install_or_upgrade_slash_commands(quiet=True)

    # All slash commands should be installed
    assert len(changed) >= 11
    assert len(up_to_date) == 0
    assert len(failed) == 0

    # Verify files were created in ~/.claude/skills/
    skills_dir = temp_user_home / ".claude" / "skills"
    assert skills_dir.exists()
    assert (skills_dir / "daf-active").exists()
    assert (skills_dir / "daf-active" / "SKILL.md").exists()
    assert (skills_dir / "daf-help").exists()
    assert (skills_dir / "daf-list").exists()


def test_install_slash_commands_already_up_to_date(temp_user_home):
    """Test upgrade when slash commands are already up-to-date."""
    # First install
    changed1, _, _ = install_or_upgrade_slash_commands(quiet=True)
    assert len(changed1) >= 11

    # Second install should show all up-to-date
    changed2, up_to_date2, failed2 = install_or_upgrade_slash_commands(quiet=True)
    assert len(changed2) == 0
    assert len(up_to_date2) >= 11
    assert len(failed2) == 0


def test_install_slash_commands_outdated(temp_user_home):
    """Test upgrade when a slash command is outdated."""
    # Install first
    install_or_upgrade_slash_commands(quiet=True)

    # Modify one to simulate outdated version
    skills_dir = temp_user_home / ".claude" / "skills"
    skill_md = skills_dir / "daf-help" / "SKILL.md"
    skill_md.write_text("OLD CONTENT")

    # Upgrade should detect the change
    changed, up_to_date, failed = install_or_upgrade_slash_commands(quiet=True)

    assert "daf-help" in changed
    assert len(failed) == 0
    assert skill_md.read_text() != "OLD CONTENT"


def test_install_slash_commands_dry_run(temp_user_home):
    """Test dry run mode doesn't actually install."""
    changed, up_to_date, failed = install_or_upgrade_slash_commands(
        dry_run=True, quiet=True
    )

    # Should report what would change
    assert len(changed) >= 11
    assert len(failed) == 0

    # But directory should not exist
    skills_dir = temp_user_home / ".claude" / "skills"
    assert not skills_dir.exists()


def test_slash_commands_have_name_field(temp_user_home):
    """Test that installed slash commands have name: field in frontmatter."""
    install_or_upgrade_slash_commands(quiet=True)

    skills_dir = temp_user_home / ".claude" / "skills"
    help_skill = skills_dir / "daf-help" / "SKILL.md"
    content = help_skill.read_text()

    assert content.startswith("---\n")
    assert "name: daf-help" in content
    assert "description:" in content


# ============================================================================
# Reference Skills Installation Tests
# ============================================================================

def test_install_reference_skills_fresh_install(temp_user_home):
    """Test installing reference skills to user home."""
    changed, up_to_date, failed = install_or_upgrade_reference_skills(quiet=True)

    # All reference skills should be installed
    assert len(changed) >= 4
    assert len(up_to_date) == 0
    assert len(failed) == 0

    # Verify files were created in ~/.claude/skills/
    skills_dir = temp_user_home / ".claude" / "skills"
    assert skills_dir.exists()
    assert (skills_dir / "daf-cli").exists()
    assert (skills_dir / "daf-cli" / "SKILL.md").exists()
    assert (skills_dir / "gh-cli").exists()
    assert (skills_dir / "git-cli").exists()
    assert (skills_dir / "glab-cli").exists()


def test_install_reference_skills_already_up_to_date(temp_user_home):
    """Test upgrade when reference skills are already up-to-date."""
    # First install
    changed1, _, _ = install_or_upgrade_reference_skills(quiet=True)
    assert len(changed1) >= 4

    # Second install should show all up-to-date
    changed2, up_to_date2, failed2 = install_or_upgrade_reference_skills(quiet=True)
    assert len(changed2) == 0
    assert len(up_to_date2) >= 4
    assert len(failed2) == 0


def test_reference_skills_no_name_field(temp_user_home):
    """Test that installed reference skills don't have name: field in frontmatter."""
    install_or_upgrade_reference_skills(quiet=True)

    skills_dir = temp_user_home / ".claude" / "skills"
    daf_cli_skill = skills_dir / "daf-cli" / "SKILL.md"
    content = daf_cli_skill.read_text()

    assert content.startswith("---\n")
    assert "description:" in content
    # Verify frontmatter doesn't have name: field
    frontmatter = content.split("---\n")[1]
    assert "name:" not in frontmatter


# ============================================================================
# Helper Function Tests
# ============================================================================

def test_are_skill_dirs_identical_same(temp_user_home):
    """Test comparing identical skill directories."""
    # Create two identical directories
    dir1 = temp_user_home / "skill1"
    dir2 = temp_user_home / "skill2"

    dir1.mkdir()
    dir2.mkdir()

    (dir1 / "SKILL.md").write_text("Same content")
    (dir2 / "SKILL.md").write_text("Same content")

    assert _are_skill_dirs_identical(dir1, dir2)


def test_are_skill_dirs_identical_different(temp_user_home):
    """Test comparing different skill directories."""
    # Create two different directories
    dir1 = temp_user_home / "skill1"
    dir2 = temp_user_home / "skill2"

    dir1.mkdir()
    dir2.mkdir()

    (dir1 / "SKILL.md").write_text("Content 1")
    (dir2 / "SKILL.md").write_text("Content 2")

    assert not _are_skill_dirs_identical(dir1, dir2)


def test_are_skill_dirs_identical_missing_file(temp_user_home):
    """Test comparing when destination is missing a file."""
    dir1 = temp_user_home / "skill1"
    dir2 = temp_user_home / "skill2"

    dir1.mkdir()
    dir2.mkdir()

    (dir1 / "SKILL.md").write_text("Content")
    (dir1 / "extra.md").write_text("Extra")
    (dir2 / "SKILL.md").write_text("Content")
    # dir2 missing extra.md

    assert not _are_skill_dirs_identical(dir1, dir2)


def test_are_skill_dirs_identical_subdirectories(temp_user_home):
    """Test comparing skill directories with subdirectories."""
    dir1 = temp_user_home / "skill1"
    dir2 = temp_user_home / "skill2"

    dir1.mkdir()
    dir2.mkdir()
    (dir1 / "subdir").mkdir()
    (dir2 / "subdir").mkdir()

    (dir1 / "SKILL.md").write_text("Content")
    (dir1 / "subdir" / "file.txt").write_text("Subdir content")
    (dir2 / "SKILL.md").write_text("Content")
    (dir2 / "subdir" / "file.txt").write_text("Subdir content")

    assert _are_skill_dirs_identical(dir1, dir2)


def test_are_skill_dirs_identical_read_error(temp_user_home):
    """Test comparing when file cannot be read (treats as different)."""
    from unittest.mock import patch, Mock

    dir1 = temp_user_home / "skill1"
    dir2 = temp_user_home / "skill2"

    dir1.mkdir()
    dir2.mkdir()

    (dir1 / "SKILL.md").write_text("Content")
    (dir2 / "SKILL.md").write_text("Content")

    # Mock read_text to raise exception
    with patch.object(Path, 'read_text', side_effect=IOError("Read error")):
        assert not _are_skill_dirs_identical(dir1, dir2)


# ============================================================================
# Workspace Skills Directory Tests
# ============================================================================

def test_get_workspace_skills_dir(temp_user_home):
    """Test getting workspace-specific skills directory."""
    workspace = temp_user_home / "my-workspace"
    workspace.mkdir()

    skills_dir = get_workspace_skills_dir(str(workspace))

    assert skills_dir == workspace / ".claude" / "skills"
    assert skills_dir.parent.parent == workspace


def test_get_workspace_skills_dir_with_tilde(temp_user_home):
    """Test workspace skills dir with ~ in path."""
    # Create a mock workspace in user home
    workspace = temp_user_home / "workspace"
    workspace.mkdir()

    # Use ~ notation (will be expanded to temp_user_home)
    skills_dir = get_workspace_skills_dir("~/workspace")

    # Should expand to full path
    assert ".claude/skills" in str(skills_dir)
    assert skills_dir.is_absolute()


# ============================================================================
# Skill Status Tests
# ============================================================================

def test_get_skill_status_not_installed(temp_user_home):
    """Test getting status of skill that is not installed."""
    workspace = temp_user_home / "workspace"
    workspace.mkdir()

    # daf-help exists in bundled skills but not installed
    status = get_skill_status(str(workspace), "daf-help")

    assert status == "not_installed"


def test_get_skill_status_up_to_date(temp_user_home):
    """Test getting status of up-to-date skill."""
    workspace = temp_user_home / "workspace"
    workspace.mkdir()

    # Install slash commands first
    from unittest.mock import patch
    with patch('devflow.utils.claude_commands.Path.home', return_value=workspace):
        install_or_upgrade_slash_commands(quiet=True)

    # Check status - should be up-to-date
    status = get_skill_status(str(workspace), "daf-help")

    assert status == "up_to_date"


def test_get_skill_status_outdated(temp_user_home):
    """Test getting status of outdated skill."""
    workspace = temp_user_home / "workspace"
    workspace.mkdir()

    # Install slash commands first
    from unittest.mock import patch
    with patch('devflow.utils.claude_commands.Path.home', return_value=workspace):
        install_or_upgrade_slash_commands(quiet=True)

    # Modify skill to make it outdated
    skills_dir = workspace / ".claude" / "skills"
    skill_md = skills_dir / "daf-help" / "SKILL.md"
    skill_md.write_text("OUTDATED CONTENT")

    # Check status - should be outdated
    status = get_skill_status(str(workspace), "daf-help")

    assert status == "outdated"


def test_get_skill_status_nonexistent_skill(temp_user_home):
    """Test getting status of skill that doesn't exist in bundle."""
    workspace = temp_user_home / "workspace"
    workspace.mkdir()

    status = get_skill_status(str(workspace), "nonexistent-skill")

    assert status is None


def test_get_all_skill_statuses_mixed(temp_user_home):
    """Test getting status of all skills with mixed states."""
    workspace = temp_user_home / "workspace"
    workspace.mkdir()

    # Install only slash commands
    from unittest.mock import patch
    with patch('devflow.utils.claude_commands.Path.home', return_value=workspace):
        install_or_upgrade_slash_commands(quiet=True)

    # Make one skill outdated
    skills_dir = workspace / ".claude" / "skills"
    skill_md = skills_dir / "daf-help" / "SKILL.md"
    skill_md.write_text("OUTDATED")

    # Get all statuses
    statuses = get_all_skill_statuses(str(workspace))

    # Should have entries for all bundled skills
    assert len(statuses) >= 15

    # daf-help should be outdated
    assert statuses.get("daf-help") == "outdated"

    # daf-cli (reference skill) should be not_installed
    assert statuses.get("daf-cli") == "not_installed"

    # Other slash commands should be up_to_date
    assert statuses.get("daf-list") == "up_to_date"


def test_get_all_skill_statuses_empty_workspace(temp_user_home):
    """Test getting all skill statuses for workspace with no skills."""
    workspace = temp_user_home / "empty-workspace"
    workspace.mkdir()

    statuses = get_all_skill_statuses(str(workspace))

    # All should be not_installed
    assert len(statuses) >= 15
    for status in statuses.values():
        assert status == "not_installed"


# ============================================================================
# Build Claude Command Tests
# ============================================================================

def test_build_claude_command_basic(temp_user_home):
    """Test building basic Claude command with session ID and prompt."""
    cmd = build_claude_command(
        session_id="test-session-123",
        initial_prompt="Hello Claude"
    )

    assert cmd[0] == "claude"
    assert "--session-id" in cmd
    assert "test-session-123" in cmd
    assert "Hello Claude" in cmd


def test_build_claude_command_with_user_skills(temp_user_home):
    """Test building command includes user-level skills."""
    # Install user-level skills
    from unittest.mock import patch
    with patch('devflow.utils.claude_commands.Path.home', return_value=temp_user_home):
        install_or_upgrade_slash_commands(quiet=True)

    # Build command
    with patch('devflow.utils.claude_commands.Path.home', return_value=temp_user_home):
        cmd = build_claude_command(
            session_id="test-session",
            initial_prompt="Test"
        )

    # Should include user skills directory
    user_skills = str(temp_user_home / ".claude" / "skills")
    assert "--add-dir" in cmd
    assert user_skills in cmd


def test_build_claude_command_with_workspace_skills(temp_user_home):
    """Test building command includes workspace-level skills."""
    workspace = temp_user_home / "workspace"
    workspace.mkdir()
    workspace_skills_dir = workspace / ".claude" / "skills"
    workspace_skills_dir.mkdir(parents=True)

    cmd = build_claude_command(
        session_id="test-session",
        initial_prompt="Test",
        workspace_path=str(workspace)
    )

    # Should include workspace skills directory
    assert "--add-dir" in cmd
    assert str(workspace_skills_dir) in cmd


def test_build_claude_command_with_project_skills(temp_user_home):
    """Test building command includes project-level skills."""
    project = temp_user_home / "project"
    project.mkdir()
    project_skills_dir = project / ".claude" / "skills"
    project_skills_dir.mkdir(parents=True)

    cmd = build_claude_command(
        session_id="test-session",
        initial_prompt="Test",
        project_path=str(project)
    )

    # Should include project skills directory
    assert "--add-dir" in cmd
    assert str(project_skills_dir) in cmd


def test_build_claude_command_skills_load_order(temp_user_home, monkeypatch):
    """Test that skills are added in correct load order."""
    from unittest.mock import patch

    # Create all skill directories
    user_skills = temp_user_home / ".claude" / "skills"
    user_skills.mkdir(parents=True)

    workspace = temp_user_home / "workspace"
    workspace_skills = workspace / ".claude" / "skills"
    workspace_skills.mkdir(parents=True)

    project = temp_user_home / "project"
    project_skills = project / ".claude" / "skills"
    project_skills.mkdir(parents=True)

    # Mock get_cs_home to return temp path
    cs_home = temp_user_home / "daf-home"
    hierarchical_skills = cs_home / ".claude" / "skills"
    hierarchical_skills.mkdir(parents=True)

    with patch('devflow.utils.claude_commands.Path.home', return_value=temp_user_home):
        with patch('devflow.utils.paths.get_cs_home', return_value=cs_home):
            cmd = build_claude_command(
                session_id="test-session",
                initial_prompt="Test",
                workspace_path=str(workspace),
                project_path=str(project)
            )

    # Extract --add-dir arguments
    add_dir_indices = [i for i, arg in enumerate(cmd) if arg == "--add-dir"]
    add_dir_paths = [cmd[i + 1] for i in add_dir_indices]

    # Should have all 4 directories in correct order:
    # 1. user, 2. workspace, 3. hierarchical, 4. project
    assert len(add_dir_paths) >= 4
    assert str(user_skills) in add_dir_paths
    assert str(workspace_skills) in add_dir_paths
    assert str(hierarchical_skills) in add_dir_paths
    assert str(project_skills) in add_dir_paths

    # Verify order (user before workspace before hierarchical before project)
    user_idx = add_dir_paths.index(str(user_skills))
    workspace_idx = add_dir_paths.index(str(workspace_skills))
    hierarchical_idx = add_dir_paths.index(str(hierarchical_skills))
    project_idx = add_dir_paths.index(str(project_skills))

    assert user_idx < workspace_idx < hierarchical_idx < project_idx


def test_build_claude_command_with_config_hierarchical_files(temp_user_home, monkeypatch):
    """Test building command with hierarchical context files."""
    from unittest.mock import patch, MagicMock

    # Mock config with context files
    mock_config = MagicMock()

    # Mock get_cs_home
    cs_home = temp_user_home / "daf-home"
    cs_home.mkdir(parents=True)

    with patch('devflow.utils.paths.get_cs_home', return_value=cs_home):
        with patch('devflow.utils.context_files.load_hierarchical_context_files', return_value=["ENTERPRISE.md"]):
            cmd = build_claude_command(
                session_id="test-session",
                initial_prompt="Test",
                config=mock_config
            )

    # Should include cs_home directory for hierarchical files
    assert str(cs_home) in cmd


def test_build_claude_command_no_duplicate_dirs(temp_user_home):
    """Test that duplicate directories are not added."""
    from unittest.mock import patch, MagicMock

    # Mock get_cs_home to return same as user home
    with patch('devflow.utils.paths.get_cs_home', return_value=temp_user_home):
        with patch('devflow.utils.context_files.load_hierarchical_context_files', return_value=["file.md"]):
            cmd = build_claude_command(
                session_id="test-session",
                initial_prompt="Test",
                config=MagicMock()
            )

    # Count occurrences of each path after --add-dir
    add_dir_indices = [i for i, arg in enumerate(cmd) if arg == "--add-dir"]
    add_dir_paths = [cmd[i + 1] for i in add_dir_indices]

    # No path should appear twice
    assert len(add_dir_paths) == len(set(add_dir_paths))


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_install_slash_commands_copy_error(temp_user_home):
    """Test handling of copy error during installation."""
    from unittest.mock import patch

    with patch('devflow.utils.claude_commands.shutil.copytree', side_effect=PermissionError("Permission denied")):
        changed, up_to_date, failed = install_or_upgrade_slash_commands(quiet=True)

    # Should report failures
    assert len(failed) > 0


def test_install_reference_skills_copy_error(temp_user_home):
    """Test handling of copy error during reference skill installation."""
    from unittest.mock import patch

    with patch('devflow.utils.claude_commands.shutil.copytree', side_effect=OSError("Disk full")):
        changed, up_to_date, failed = install_or_upgrade_reference_skills(quiet=True)

    # Should report failures
    assert len(failed) > 0
