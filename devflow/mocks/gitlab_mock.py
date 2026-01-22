"""Mock GitLab service for integration testing.

This module provides a mock implementation of GitLab API operations that uses
persistent storage. It's designed to be used for integration testing without
requiring a real GitLab instance.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from devflow.mocks.persistence import MockDataStore


class MockGitLabClient:
    """Mock GitLab client for MR operations.

    This client uses persistent storage to maintain MR data across
    command invocations. It mimics GitLab's MR API.
    """

    def __init__(self, token: str = None, url: str = None):
        """Initialize the mock GitLab client.

        Args:
            token: GitLab API token (ignored in mock)
            url: GitLab URL (ignored in mock)
        """
        self.store = MockDataStore()
        self.token = token or "mock-gitlab-token"
        self.url = url or "https://gitlab.example.com"

    def list_mrs(self, project: str, state: str = "opened") -> List[Dict[str, Any]]:
        """List merge requests for a project.

        Args:
            project: Project name (e.g., "group/project")
            state: MR state filter ("opened", "closed", "merged", "all")

        Returns:
            List of MR data dicts
        """
        mrs = self.store.list_gitlab_mrs(project)

        # Filter by state
        if state != "all":
            mrs = [mr for mr in mrs if mr.get("state") == state]

        return mrs

    def get_mr(self, project: str, mr_number: int) -> Optional[Dict[str, Any]]:
        """Get a specific merge request.

        Args:
            project: Project name
            mr_number: MR IID (internal ID)

        Returns:
            MR data dict or None if not found
        """
        return self.store.get_gitlab_mr(project, mr_number)

    def create_mr(
        self,
        project: str,
        title: str,
        description: str,
        source_branch: str,
        target_branch: str = "main",
        draft: bool = False
    ) -> Dict[str, Any]:
        """Create a new merge request.

        Args:
            project: Project name
            title: MR title
            description: MR description
            source_branch: Source branch name
            target_branch: Target branch name (default: "main")
            draft: Whether MR is a draft (WIP)

        Returns:
            Created MR data dict
        """
        # Generate MR IID
        existing_mrs = self.store.list_gitlab_mrs(project)
        mr_iid = len(existing_mrs) + 1

        # Create MR data
        mr_data = {
            "iid": mr_iid,
            "title": f"Draft: {title}" if draft else title,
            "description": description,
            "state": "opened",
            "draft": draft,
            "work_in_progress": draft,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "web_url": f"{self.url}/{project}/-/merge_requests/{mr_iid}",
            "author": {"username": "mock-user"},
            "merge_status": "can_be_merged",
            "merged_at": None,
        }

        # Store MR
        self.store.set_gitlab_mr(project, mr_iid, mr_data)

        return mr_data

    def update_mr(
        self,
        project: str,
        mr_number: int,
        title: str = None,
        description: str = None,
        state_event: str = None
    ) -> Optional[Dict[str, Any]]:
        """Update a merge request.

        Args:
            project: Project name
            mr_number: MR IID
            title: New title (optional)
            description: New description (optional)
            state_event: State event ("close", "reopen") (optional)

        Returns:
            Updated MR data dict or None if not found
        """
        mr = self.store.get_gitlab_mr(project, mr_number)
        if not mr:
            return None

        # Update fields
        if title is not None:
            mr["title"] = title
        if description is not None:
            mr["description"] = description
        if state_event == "close":
            mr["state"] = "closed"
            mr["closed_at"] = datetime.now().isoformat()
        elif state_event == "reopen":
            mr["state"] = "opened"
            mr["closed_at"] = None

        mr["updated_at"] = datetime.now().isoformat()

        # Store updated MR
        self.store.set_gitlab_mr(project, mr_number, mr)

        return mr

    def merge_mr(
        self,
        project: str,
        mr_number: int,
        merge_commit_message: str = None,
        should_remove_source_branch: bool = False
    ) -> bool:
        """Merge a merge request.

        Args:
            project: Project name
            mr_number: MR IID
            merge_commit_message: Custom merge commit message (optional)
            should_remove_source_branch: Delete source branch after merge

        Returns:
            True if successful, False if MR not found or cannot be merged
        """
        mr = self.store.get_gitlab_mr(project, mr_number)
        if not mr or mr.get("merge_status") != "can_be_merged":
            return False

        mr["state"] = "merged"
        mr["merged_at"] = datetime.now().isoformat()
        mr["merge_commit_sha"] = f"mock-sha-{mr_number}"

        if merge_commit_message:
            mr["merge_commit_message"] = merge_commit_message

        self.store.set_gitlab_mr(project, mr_number, mr)

        return True

    def close_mr(self, project: str, mr_number: int) -> bool:
        """Close a merge request without merging.

        Args:
            project: Project name
            mr_number: MR IID

        Returns:
            True if successful, False if MR not found
        """
        mr = self.store.get_gitlab_mr(project, mr_number)
        if not mr:
            return False

        mr["state"] = "closed"
        mr["closed_at"] = datetime.now().isoformat()

        self.store.set_gitlab_mr(project, mr_number, mr)

        return True

    def add_mr_comment(self, project: str, mr_number: int, body: str) -> bool:
        """Add a comment (note) to a merge request.

        Args:
            project: Project name
            mr_number: MR IID
            body: Comment text

        Returns:
            True if successful, False if MR not found
        """
        mr = self.store.get_gitlab_mr(project, mr_number)
        if not mr:
            return False

        # Add comment to MR metadata
        if "notes" not in mr:
            mr["notes"] = []
        mr["notes"].append({
            "body": body,
            "created_at": datetime.now().isoformat(),
            "author": {"username": "mock-user"}
        })

        self.store.set_gitlab_mr(project, mr_number, mr)

        return True

    def mark_mr_as_draft(self, project: str, mr_number: int) -> bool:
        """Mark a merge request as draft (WIP).

        Args:
            project: Project name
            mr_number: MR IID

        Returns:
            True if successful, False if MR not found
        """
        mr = self.store.get_gitlab_mr(project, mr_number)
        if not mr:
            return False

        if not mr["title"].startswith("Draft: "):
            mr["title"] = f"Draft: {mr['title']}"
        mr["draft"] = True
        mr["work_in_progress"] = True
        mr["updated_at"] = datetime.now().isoformat()

        self.store.set_gitlab_mr(project, mr_number, mr)

        return True

    def unmark_mr_as_draft(self, project: str, mr_number: int) -> bool:
        """Remove draft (WIP) status from a merge request.

        Args:
            project: Project name
            mr_number: MR IID

        Returns:
            True if successful, False if MR not found
        """
        mr = self.store.get_gitlab_mr(project, mr_number)
        if not mr:
            return False

        if mr["title"].startswith("Draft: "):
            mr["title"] = mr["title"][7:]  # Remove "Draft: " prefix
        mr["draft"] = False
        mr["work_in_progress"] = False
        mr["updated_at"] = datetime.now().isoformat()

        self.store.set_gitlab_mr(project, mr_number, mr)

        return True
