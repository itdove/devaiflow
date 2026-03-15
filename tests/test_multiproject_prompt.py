"""Test for multi-project session initial prompt generation."""

from devflow.cli.commands.new_command import _generate_initial_prompt


def test_multiproject_prompt_includes_project_level_files():
    """Test that multi-project sessions include project-level context file instructions."""
    project_paths = {
        "backend-api": "/workspace/backend-api",
        "frontend-app": "/workspace/frontend-app",
    }

    prompt = _generate_initial_prompt(
        name="test-session",
        goal="Test multi-project",
        is_multi_project=True,
        other_projects=["backend-api", "frontend-app"],
        workspace="/workspace",
        project_paths=project_paths,
    )

    # Verify workspace-level files are included
    assert "AGENTS.md (agent-specific instructions)" in prompt
    assert "CLAUDE.md (project guidelines and standards)" in prompt
    assert "DAF_AGENTS.md (daf tool usage guide)" in prompt

    # Verify project-level files are included
    assert "Also read project-level context files for each project:" in prompt
    assert "backend-api:" in prompt
    assert "backend-api/AGENTS.md (agent-specific instructions)" in prompt
    assert "backend-api/CLAUDE.md (project guidelines and standards)" in prompt
    assert "backend-api/DAF_AGENTS.md (daf tool usage guide)" in prompt

    assert "frontend-app:" in prompt
    assert "frontend-app/AGENTS.md (agent-specific instructions)" in prompt
    assert "frontend-app/CLAUDE.md (project guidelines and standards)" in prompt
    assert "frontend-app/DAF_AGENTS.md (daf tool usage guide)" in prompt


def test_single_project_prompt_does_not_include_project_level_files():
    """Test that single-project sessions don't include project-level instructions."""
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="Test single project",
        is_multi_project=False,
        project_path="/workspace/backend-api",
    )

    # Verify workspace-level files are included
    assert "AGENTS.md (agent-specific instructions)" in prompt
    assert "CLAUDE.md (project guidelines and standards)" in prompt
    assert "DAF_AGENTS.md (daf tool usage guide)" in prompt

    # Verify NO project-level section
    assert "Also read project-level context files for each project:" not in prompt
    assert "backend-api/AGENTS.md" not in prompt


def test_multiproject_without_project_paths_falls_back():
    """Test that multi-project without project_paths doesn't fail."""
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="Test multi-project fallback",
        is_multi_project=True,
        other_projects=["backend-api", "frontend-app"],
        workspace="/workspace",
        project_paths=None,  # No project paths provided
    )

    # Should still have workspace-level files
    assert "AGENTS.md (agent-specific instructions)" in prompt

    # Should not crash or include project-level section
    assert "Also read project-level context files for each project:" not in prompt
