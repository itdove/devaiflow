"""Regression tests for the bundled session-initialization workflow skill."""

from pathlib import Path


SKILL_PATH = Path(__file__).parents[1] / "devflow" / "cli_skills" / "daf-workflow" / "SKILL.md"


def _issue_lookup_section() -> str:
    """Return the issue lookup section from the bundled workflow skill."""
    content = SKILL_PATH.read_text(encoding="utf-8")
    start = content.index("### 2. Read Issue Tracker Ticket")
    end = content.index("### 3. Read Context Files", start)
    return content[start:end]


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
