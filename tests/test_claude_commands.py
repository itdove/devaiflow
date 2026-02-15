"""Tests for devflow/utils/claude_commands.py - bundled skills installation."""

import pytest
from pathlib import Path
import shutil

from devflow.utils.claude_commands import (
    get_bundled_skills_dir,
    list_bundled_skills,
    list_slash_command_skills,
    list_reference_skills,
    install_or_upgrade_slash_commands,
    install_or_upgrade_reference_skills,
    _are_skill_dirs_identical,
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
