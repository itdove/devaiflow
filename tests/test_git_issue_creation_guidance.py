"""Regression tests for GitHub/GitLab issue-creation guidance."""

from pathlib import Path

SOURCE_ROOT = Path(__file__).parents[1] / "devflow"
GIT_SKILL = SOURCE_ROOT / "cli_skills" / "daf-git" / "SKILL.md"
CLI_SKILL = SOURCE_ROOT / "cli_skills" / "daf-cli" / "SKILL.md"
WORKFLOW_SKILL = SOURCE_ROOT / "cli_skills" / "daf-workflow" / "SKILL.md"


def test_git_skill_does_not_describe_jira_linking_for_git_issues():
    """The GitHub/GitLab skill must document the supported post-creation flow."""
    content = GIT_SKILL.read_text(encoding="utf-8")

    assert "daf link" not in content
    assert "issue URL and key" in content
    assert "supported" in content
    assert "daf open <session-name>" in content


def test_cli_skill_keeps_jira_linking_separate_from_git_issue_creation():
    """The CLI skill retains valid JIRA linking while removing Git guidance."""
    content = CLI_SKILL.read_text(encoding="utf-8")

    assert "gh issue create` / `glab issue create` + `daf link`" not in content
    assert "`daf link <session> --jira" in content
    assert "not used with GitHub/GitLab issue URLs" in content


def test_workflow_skill_documents_git_issue_session_behavior():
    """The workflow skill must not promise an unsupported automatic rename."""
    content = WORKFLOW_SKILL.read_text(encoding="utf-8")
    start = content.index("## GitHub/GitLab Issue Creation")
    end = content.index("## JIRA Ticket Creation", start)
    section = content[start:end]

    assert "issue URL and key" in section
    assert "daf open <session-name>" in section
    assert "automatically renamed" not in section
