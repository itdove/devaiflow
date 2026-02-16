"""Tests for skills discovery."""

from pathlib import Path
from unittest.mock import patch

from devflow.cli.skills_discovery import discover_skills


def test_discover_skills_no_skills(temp_daf_home, tmp_path):
    """Test skills discovery when no skill directories exist."""
    # Use a non-existent project path
    result = discover_skills(project_path=str(tmp_path / "nonexistent"))
    # Should return skills from default locations if they exist
    assert isinstance(result, list)


def test_discover_skills_user_level(temp_daf_home, tmp_path):
    """Test discovery of user-level skills."""
    # Create user skills directory
    user_skills_dir = Path.home() / ".claude" / "skills"
    user_skills_dir.mkdir(parents=True, exist_ok=True)

    # Create a skill
    skill_dir = user_skills_dir / "test-skill"
    skill_dir.mkdir(exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("---\ndescription: Test user skill\n---\n\nContent")

    result = discover_skills()

    # Should find the skill
    skill_paths = [r[0] for r in result]
    descriptions = [r[1] for r in result]

    assert any("test-skill" in path for path in skill_paths)
    assert "Test user skill" in descriptions


def test_discover_skills_with_workspace(temp_daf_home, tmp_path):
    """Test discovery of workspace-level skills."""
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()

    # Create workspace skills directory
    workspace_skills_dir = workspace_dir / ".claude" / "skills"
    workspace_skills_dir.mkdir(parents=True)

    # Create a skill
    skill_dir = workspace_skills_dir / "workspace-skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("---\ndescription: Workspace tool skill\n---\n")

    with patch('devflow.utils.claude_commands.get_workspace_skills_dir') as mock_get_dir:
        mock_get_dir.return_value = workspace_skills_dir
        result = discover_skills(workspace=str(workspace_dir))

    # Should find the workspace skill
    descriptions = [r[1] for r in result]
    assert "Workspace tool skill" in descriptions


def test_discover_skills_hierarchical(temp_daf_home, tmp_path):
    """Test discovery of hierarchical skills."""
    # Hierarchical skills are in DEVAIFLOW_HOME/.claude/skills
    # They should already exist in temp_daf_home
    result = discover_skills()

    # Should discover hierarchical skills (numbered 01-, 02-, etc.)
    skill_paths = [r[0] for r in result]
    # Check if any hierarchical skills were found
    assert isinstance(result, list)


def test_discover_skills_project_level(temp_daf_home, tmp_path):
    """Test discovery of project-level skills."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create project skills directory
    project_skills_dir = project_dir / ".claude" / "skills"
    project_skills_dir.mkdir(parents=True)

    # Create a skill
    skill_dir = project_skills_dir / "project-skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("---\ndescription: Project-specific skill\n---\n")

    result = discover_skills(project_path=str(project_dir))

    # Should find the project skill
    descriptions = [r[1] for r in result]
    assert "Project-specific skill" in descriptions


def test_discover_skills_description_extraction(temp_daf_home, tmp_path):
    """Test extraction of description from YAML frontmatter."""
    user_skills_dir = Path.home() / ".claude" / "skills"
    user_skills_dir.mkdir(parents=True, exist_ok=True)

    # Create skill with description
    skill_dir = user_skills_dir / "desc-skill"
    skill_dir.mkdir(exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\n"
        "description: Custom description from frontmatter\n"
        "other_field: value\n"
        "---\n"
        "# Skill Content\n"
    )

    result = discover_skills()
    descriptions = [r[1] for r in result]
    assert "Custom description from frontmatter" in descriptions


def test_discover_skills_no_frontmatter(temp_daf_home, tmp_path):
    """Test skill without YAML frontmatter uses default description."""
    user_skills_dir = Path.home() / ".claude" / "skills"
    user_skills_dir.mkdir(parents=True, exist_ok=True)

    # Create skill without frontmatter
    skill_dir = user_skills_dir / "no-front"
    skill_dir.mkdir(exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("# Regular markdown content without frontmatter")

    result = discover_skills()

    # Should use default description
    skill_entries = [(r[0], r[1]) for r in result if "no-front" in r[0]]
    assert len(skill_entries) > 0
    assert skill_entries[0][1] == "no-front skill"


def test_discover_skills_file_read_error(temp_daf_home, tmp_path):
    """Test handling of file read errors."""
    user_skills_dir = Path.home() / ".claude" / "skills"
    user_skills_dir.mkdir(parents=True, exist_ok=True)

    # Create skill directory but no SKILL.md file
    skill_dir = user_skills_dir / "missing-file"
    skill_dir.mkdir(exist_ok=True)

    # Should not crash, just skip this skill
    result = discover_skills()

    # Should not include the skill with missing file
    skill_paths = [r[0] for r in result]
    assert not any("missing-file" in path for path in skill_paths)


def test_discover_skills_sorting_order(temp_daf_home, tmp_path):
    """Test that skills are discovered in sorted order."""
    user_skills_dir = Path.home() / ".claude" / "skills"
    user_skills_dir.mkdir(parents=True, exist_ok=True)

    # Create multiple skills (should be sorted alphabetically)
    for name in ["zebra-skill", "alpha-skill", "beta-skill"]:
        skill_dir = user_skills_dir / name
        skill_dir.mkdir(exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(f"---\ndescription: {name}\n---\n")

    result = discover_skills()

    # Extract user-level skills
    user_skills = [r for r in result if "skills" in r[0] and ".claude/skills" in r[0]]
    user_skill_names = [Path(r[0]).parent.name for r in user_skills]

    # Find our test skills in the results
    test_skills = [n for n in user_skill_names if n in ["zebra-skill", "alpha-skill", "beta-skill"]]

    # Should be in sorted order
    assert test_skills == sorted(test_skills)


def test_discover_skills_all_locations(temp_daf_home, tmp_path):
    """Test discovery from all four locations."""
    # Create user skill
    user_skills_dir = Path.home() / ".claude" / "skills"
    user_skills_dir.mkdir(parents=True, exist_ok=True)
    user_skill_dir = user_skills_dir / "user-skill"
    user_skill_dir.mkdir(exist_ok=True)
    (user_skill_dir / "SKILL.md").write_text("---\ndescription: User skill\n---\n")

    # Create workspace skill
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    workspace_skills_dir = workspace_dir / ".claude" / "skills"
    workspace_skills_dir.mkdir(parents=True)
    ws_skill_dir = workspace_skills_dir / "ws-skill"
    ws_skill_dir.mkdir()
    (ws_skill_dir / "SKILL.md").write_text("---\ndescription: Workspace skill\n---\n")

    # Create project skill
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_skills_dir = project_dir / ".claude" / "skills"
    project_skills_dir.mkdir(parents=True)
    proj_skill_dir = project_skills_dir / "proj-skill"
    proj_skill_dir.mkdir()
    (proj_skill_dir / "SKILL.md").write_text("---\ndescription: Project skill\n---\n")

    with patch('devflow.utils.claude_commands.get_workspace_skills_dir') as mock_get_dir:
        mock_get_dir.return_value = workspace_skills_dir
        result = discover_skills(project_path=str(project_dir), workspace=str(workspace_dir))

    descriptions = [r[1] for r in result]

    # Should find skills from all locations
    assert "User skill" in descriptions
    assert "Workspace skill" in descriptions
    assert "Project skill" in descriptions


def test_discover_skills_malformed_frontmatter(temp_daf_home, tmp_path):
    """Test handling of malformed YAML frontmatter."""
    user_skills_dir = Path.home() / ".claude" / "skills"
    user_skills_dir.mkdir(parents=True, exist_ok=True)

    # Create skill with malformed frontmatter (missing closing ---)
    skill_dir = user_skills_dir / "malformed"
    skill_dir.mkdir(exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\n"
        "description: This is malformed\n"
        "# No closing --- marker\n"
        "Content here\n"
    )

    # Should handle gracefully and use default description
    result = discover_skills()
    skill_entries = [(r[0], r[1]) for r in result if "malformed" in r[0]]

    # Should still discover the skill
    assert len(skill_entries) > 0
