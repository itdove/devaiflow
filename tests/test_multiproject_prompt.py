"""Test for multi-project session initial prompt generation."""

import pytest
from devflow.cli.commands.new_command import _generate_initial_prompt


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
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


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
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


class TestMultiProjectFilePermissions:
    """Test file permission guidance in multi-project prompts (Issue #187)."""

    def test_new_mode_development_session_shows_edit_permissions(self):
        """Test new mode development session shows EDIT permissions."""
        prompt = _generate_initial_prompt(
            name="test-session",
            goal="Test development",
            session_type="development",
            is_multi_project=True,
            other_projects=["backend-api", "frontend-app"],
            workspace="/workspace",
        )

        # Should show multi-project session marker
        assert "⚠️  MULTI-PROJECT SESSION:" in prompt

        # Should show EDIT permissions for development sessions
        assert "File Permissions: You can EDIT files in any of these project directories" in prompt

        # Should NOT show read-only guidance
        assert "DO NOT edit any files" not in prompt

    def test_new_mode_ticket_creation_session_shows_read_only_permissions(self):
        """Test new mode ticket creation session shows READ-ONLY permissions."""
        prompt = _generate_initial_prompt(
            name="test-session",
            goal="Test ticket creation",
            session_type="ticket_creation",
            is_multi_project=True,
            other_projects=["backend-api", "frontend-app"],
            workspace="/workspace",
        )

        # Should show multi-project session marker
        assert "⚠️  MULTI-PROJECT SESSION:" in prompt

        # Should show READ-ONLY permissions for ticket_creation sessions
        assert "File Permissions: You can only READ files in these directories - DO NOT edit any files" in prompt

        # Should NOT show edit permissions
        assert "You can EDIT files" not in prompt

    def test_new_mode_investigation_session_shows_read_only_permissions(self):
        """Test new mode investigation session shows READ-ONLY permissions."""
        prompt = _generate_initial_prompt(
            name="test-session",
            goal="Test investigation",
            session_type="investigation",
            is_multi_project=True,
            other_projects=["backend-api", "frontend-app"],
            workspace="/workspace",
        )

        # Should show multi-project session marker
        assert "⚠️  MULTI-PROJECT SESSION:" in prompt

        # Should show READ-ONLY permissions for investigation sessions
        assert "File Permissions: You can only READ files in these directories - DO NOT edit any files" in prompt

        # Should NOT show edit permissions
        assert "You can EDIT files" not in prompt

    def test_old_mode_development_session_shows_edit_permissions(self):
        """Test old mode development session shows EDIT permissions."""
        prompt = _generate_initial_prompt(
            name="test-session",
            goal="Test development",
            session_type="development",
            current_project="backend-api",
            other_projects=["frontend-app", "database"],
            workspace="/workspace",
        )

        # Should show old mode multi-project marker
        assert "⚠️  MULTI-PROJECT SESSION SCOPE:" in prompt

        # Should show EDIT permissions for development sessions
        assert "File Permissions: You can EDIT files in 'backend-api' directory only" in prompt

        # Should NOT show read-only guidance
        assert "DO NOT edit any files" not in prompt

    def test_old_mode_ticket_creation_session_shows_read_only_permissions(self):
        """Test old mode ticket creation session shows READ-ONLY permissions."""
        prompt = _generate_initial_prompt(
            name="test-session",
            goal="Test ticket creation",
            session_type="ticket_creation",
            current_project="backend-api",
            other_projects=["frontend-app", "database"],
            workspace="/workspace",
        )

        # Should show old mode multi-project marker
        assert "⚠️  MULTI-PROJECT SESSION SCOPE:" in prompt

        # Should show READ-ONLY permissions for ticket_creation sessions
        assert "File Permissions: You can only READ files in 'backend-api' directory - DO NOT edit any files" in prompt

        # Should NOT show edit permissions
        assert "You can EDIT files" not in prompt

    def test_old_mode_investigation_session_shows_read_only_permissions(self):
        """Test old mode investigation session shows READ-ONLY permissions."""
        prompt = _generate_initial_prompt(
            name="test-session",
            goal="Test investigation",
            session_type="investigation",
            current_project="backend-api",
            other_projects=["frontend-app", "database"],
            workspace="/workspace",
        )

        # Should show old mode multi-project marker
        assert "⚠️  MULTI-PROJECT SESSION SCOPE:" in prompt

        # Should show READ-ONLY permissions for investigation sessions
        assert "File Permissions: You can only READ files in 'backend-api' directory - DO NOT edit any files" in prompt

        # Should NOT show edit permissions
        assert "You can EDIT files" not in prompt

    def test_single_project_does_not_show_file_permissions(self):
        """Test single-project sessions don't show file permission guidance."""
        prompt = _generate_initial_prompt(
            name="test-session",
            goal="Test single project",
            session_type="development",
            is_multi_project=False,
            project_path="/workspace/backend-api",
        )

        # Should NOT show multi-project markers or file permissions
        assert "⚠️  MULTI-PROJECT SESSION:" not in prompt
        assert "File Permissions:" not in prompt
