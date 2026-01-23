"""Mock GitHub service for integration testing.

This module provides a mock implementation of GitHub API operations that uses
persistent storage. It's designed to be used for integration testing without
requiring a real GitHub instance.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from devflow.mocks.persistence import MockDataStore


class MockGitHubClient:
    """Mock GitHub client for PR operations.

    This client uses persistent storage to maintain PR data across
    command invocations. It mimics GitHub's PR API.
    """

    def __init__(self, token: str = None):
        """Initialize the mock GitHub client.

        Args:
            token: GitHub API token (ignored in mock)
        """
        self.store = MockDataStore()
        self.token = token or "mock-github-token"

    def list_prs(self, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        """List pull requests for a repository.

        Args:
            repo: Repository name (e.g., "owner/repo")
            state: PR state filter ("open", "closed", "all")

        Returns:
            List of PR data dicts
        """
        prs = self.store.list_github_prs(repo)

        # Filter by state
        if state != "all":
            prs = [pr for pr in prs if pr.get("state") == state]

        return prs

    def get_pr(self, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """Get a specific pull request.

        Args:
            repo: Repository name
            pr_number: PR number

        Returns:
            PR data dict or None if not found
        """
        return self.store.get_github_pr(repo, pr_number)

    def create_pr(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        draft: bool = False
    ) -> Dict[str, Any]:
        """Create a new pull request.

        Args:
            repo: Repository name
            title: PR title
            body: PR description
            head: Head branch name
            base: Base branch name (default: "main")
            draft: Whether PR is a draft

        Returns:
            Created PR data dict
        """
        # Generate PR number
        existing_prs = self.store.list_github_prs(repo)
        pr_number = len(existing_prs) + 1

        # Create PR data
        pr_data = {
            "number": pr_number,
            "title": title,
            "body": body,
            "state": "open",
            "draft": draft,
            "head": {"ref": head},
            "base": {"ref": base},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "html_url": f"https://github.com/{repo}/pull/{pr_number}",
            "user": {"login": "mock-user"},
            "mergeable": True,
            "merged": False,
        }

        # Store PR
        self.store.set_github_pr(repo, pr_number, pr_data)

        return pr_data

    def update_pr(
        self,
        repo: str,
        pr_number: int,
        title: str = None,
        body: str = None,
        state: str = None
    ) -> Optional[Dict[str, Any]]:
        """Update a pull request.

        Args:
            repo: Repository name
            pr_number: PR number
            title: New title (optional)
            body: New description (optional)
            state: New state ("open" or "closed") (optional)

        Returns:
            Updated PR data dict or None if not found
        """
        pr = self.store.get_github_pr(repo, pr_number)
        if not pr:
            return None

        # Update fields
        if title is not None:
            pr["title"] = title
        if body is not None:
            pr["body"] = body
        if state is not None:
            pr["state"] = state

        pr["updated_at"] = datetime.now().isoformat()

        # Store updated PR
        self.store.set_github_pr(repo, pr_number, pr)

        return pr

    def merge_pr(self, repo: str, pr_number: int, merge_method: str = "merge") -> bool:
        """Merge a pull request.

        Args:
            repo: Repository name
            pr_number: PR number
            merge_method: Merge method ("merge", "squash", "rebase")

        Returns:
            True if successful, False if PR not found or not mergeable
        """
        pr = self.store.get_github_pr(repo, pr_number)
        if not pr or not pr.get("mergeable", False):
            return False

        pr["state"] = "closed"
        pr["merged"] = True
        pr["merged_at"] = datetime.now().isoformat()
        pr["merge_commit_sha"] = f"mock-sha-{pr_number}"

        self.store.set_github_pr(repo, pr_number, pr)

        return True

    def close_pr(self, repo: str, pr_number: int) -> bool:
        """Close a pull request without merging.

        Args:
            repo: Repository name
            pr_number: PR number

        Returns:
            True if successful, False if PR not found
        """
        pr = self.store.get_github_pr(repo, pr_number)
        if not pr:
            return False

        pr["state"] = "closed"
        pr["closed_at"] = datetime.now().isoformat()

        self.store.set_github_pr(repo, pr_number, pr)

        return True

    def add_pr_comment(self, repo: str, pr_number: int, body: str) -> bool:
        """Add a comment to a pull request.

        Args:
            repo: Repository name
            pr_number: PR number
            body: Comment text

        Returns:
            True if successful, False if PR not found
        """
        pr = self.store.get_github_pr(repo, pr_number)
        if not pr:
            return False

        # Add comment to PR metadata
        if "comments" not in pr:
            pr["comments"] = []
        pr["comments"].append({
            "body": body,
            "created_at": datetime.now().isoformat(),
            "user": {"login": "mock-user"}
        })

        self.store.set_github_pr(repo, pr_number, pr)

        return True
