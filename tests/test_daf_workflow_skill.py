"""Regression tests for the bundled session-initialization workflow skill."""

from pathlib import Path

import pytest

SKILL_PATH = (
    Path(__file__).parents[1] / "devflow" / "cli_skills" / "daf-workflow" / "SKILL.md"
)


def _issue_lookup_section() -> str:
    """Return the issue lookup section from the bundled workflow skill."""
    content = SKILL_PATH.read_text(encoding="utf-8")
    start = content.index("### 2. Read Issue Tracker Ticket")
    end = content.index("### 3. Read Context Files", start)
    return content[start:end]


def _title_policy_section() -> str:
    """Return the title policy within session metadata initialization."""
    content = SKILL_PATH.read_text(encoding="utf-8")
    initialization = content.index("## Session Initialization")
    metadata = content.index("### 1. Read Session Metadata", initialization)
    start = content.index("#### DAF-managed conversation titles", metadata)
    end = content.index("### 2. Read Issue Tracker Ticket", metadata)
    return " ".join(content[start:end].split())


def test_github_issue_lookup_is_repo_qualified_and_structured() -> None:
    """Require one deterministic GitHub lookup when metadata includes a repo."""
    section = _issue_lookup_section()

    assert (
        "gh issue view <number> --repo <owner/repo> "
        "--json title,body,comments,labels,url"
    ) in section
    assert "gh issue view <number> --comments" not in section
    assert "Run only one lookup command for the ticket" in section
    assert "Empty `body` or `comments` fields" in section


def test_title_policy_distinguishes_names_goals_and_conversation_titles() -> None:
    """Use the exact current metadata name, not a description of the work."""
    section = _title_policy_section()

    assert (
        "**DAF session name** (`Name` in `daf info`) identifies the session" in section
    )
    assert "**goal** (`--goal`) describes the work" in section
    assert "**LLM conversation title** is separate display metadata" in section
    assert "**exact current DAF session name** from metadata" in section
    assert "not the goal, issue summary, or an agent-generated task summary" in section


def test_title_policy_leaves_launch_and_resume_title_setting_to_daf() -> None:
    """Initialization must not duplicate title propagation or rename DAF sessions."""
    section = _title_policy_section()

    assert (
        "DAF manages native title setting at launch and on supported resume paths"
        in section
    )
    assert (
        "Do not independently rename the conversation from `--goal`, rename the DAF session, "
        "or duplicate DAF's launch/resume title-setting operations"
    ) in section


def test_title_policy_preserves_backend_capabilities_and_reports_mismatches() -> None:
    """Keep unsupported titles agent-managed and report failures without fallbacks."""
    section = _title_policy_section()

    assert "For **Claude Code, Pi, and OpenCode**" in section
    assert "Other backends retain their normal agent-managed titles" in section
    assert (
        "If a supported backend's title does not match, report a **title-propagation problem**"
    ) in section
    assert (
        "do not invent rename commands, edit backend storage, "
        "or use an unverified skill-level fallback"
    ) in section
    assert "```" not in section


@pytest.mark.parametrize(
    "command", ["daf new", "daf open", "daf git new", "daf jira new", "daf investigate"]
)
def test_title_policy_applies_across_managed_workflows(command: str) -> None:
    """Apply one title policy across development, ticket creation, and investigation."""
    section = _title_policy_section()

    assert f"`{command}`" in section
    assert "read-only and ticket-creation constraints still apply" in section


@pytest.mark.parametrize(
    "heading",
    [
        "## GitHub/GitLab Issue Creation",
        "## JIRA Ticket Creation",
        "## Investigation",
    ],
)
def test_title_policy_preserves_analysis_only_workflow_constraints(
    heading: str,
) -> None:
    """Title guidance must not weaken the three analysis-only workflows."""
    content = SKILL_PATH.read_text(encoding="utf-8")
    start = content.index(heading)
    end = content.index("\n---", start)
    section = content[start:end]

    assert "DO NOT modify any code or create/checkout git branches" in section
    assert "DO NOT make any file changes — only READ and ANALYZE" in section


def test_issue_lookup_preserves_qualified_single_lookup_failure_handling() -> None:
    """Keep repository-qualified GitLab lookup and fail-once initialization guidance."""
    section = " ".join(_issue_lookup_section().split())

    assert "glab issue view <number> -R <owner/repo> --comments" in section
    assert "split at the final `#` and pass the repository explicitly" in section
    assert (
        "Do not first run an unqualified lookup and then retry with a repository"
        in section
    )
    assert (
        "If it exits non-zero, report the command and its error clearly, "
        "then continue initialization without ticket contents"
    ) in section
    assert (
        "do not retry with a different repository, output mode, or CLI command "
        "unless the user explicitly asks"
    ) in section
