"""Git utilities for branch management."""

import re
import subprocess
from pathlib import Path
from typing import Optional

from devflow.utils.dependencies import require_tool


class GitUtils:
    """Utilities for git operations."""

    @staticmethod
    def is_git_repository(path: Path) -> bool:
        """Check if path is inside a git repository.

        Args:
            path: Directory path to check

        Returns:
            True if path is in a git repository, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def get_current_branch(path: Path) -> Optional[str]:
        """Get the current branch name.

        Args:
            path: Repository path

        Returns:
            Current branch name or None if not in a git repo
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    @staticmethod
    def get_current_commit_sha(path: Path) -> Optional[str]:
        """Get the current commit SHA (HEAD).

        Args:
            path: Repository path

        Returns:
            Current commit SHA or None if not in a git repo
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    @staticmethod
    def get_default_branch(path: Path) -> Optional[str]:
        """Get the default branch (main/master/develop).

        Args:
            path: Repository path

        Returns:
            Default branch name or None if not found
        """
        try:
            # Try to get remote HEAD
            result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Output is like: refs/remotes/origin/main
                return result.stdout.strip().split("/")[-1]

            # Fallback: check common names
            for branch in ["main", "master", "develop"]:
                result = subprocess.run(
                    ["git", "rev-parse", "--verify", branch],
                    cwd=path,
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return branch

            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    @staticmethod
    def branch_exists(path: Path, branch_name: str) -> bool:
        """Check if a branch exists.

        Args:
            path: Repository path
            branch_name: Branch name to check

        Returns:
            True if branch exists, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", branch_name],
                cwd=path,
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def create_branch(path: Path, branch_name: str, from_branch: Optional[str] = None) -> bool:
        """Create a new branch.

        Args:
            path: Repository path
            branch_name: Name of new branch
            from_branch: Branch to create from (None = current HEAD)

        Returns:
            True if successful, False otherwise

        Raises:
            ToolNotFoundError: If git is not installed
        """
        require_tool("git", "create branch")

        try:
            cmd = ["git", "checkout", "-b", branch_name]
            if from_branch:
                cmd.append(from_branch)

            result = subprocess.run(
                cmd,
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def checkout_branch(path: Path, branch_name: str) -> bool:
        """Switch to an existing branch.

        Args:
            path: Repository path
            branch_name: Branch name to checkout

        Returns:
            True if successful, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "checkout", branch_name],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def fetch_origin(path: Path) -> bool:
        """Fetch latest from origin.

        Args:
            path: Repository path

        Returns:
            True if successful, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "fetch", "origin"],
                cwd=path,
                capture_output=True,
                timeout=30,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def pull_current_branch(path: Path) -> bool:
        """Pull latest for current branch.

        Args:
            path: Repository path

        Returns:
            True if successful, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "pull"],
                cwd=path,
                capture_output=True,
                timeout=30,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def slugify(text: str) -> str:
        """Convert text to a git branch-safe slug.

        Args:
            text: Text to slugify

        Returns:
            Slugified text suitable for branch names
        """
        # Convert to lowercase
        text = text.lower()
        # Replace spaces and underscores with hyphens
        text = re.sub(r"[\s_]+", "-", text)
        # Remove non-alphanumeric characters except hyphens
        text = re.sub(r"[^a-z0-9\-]", "", text)
        # Remove leading/trailing hyphens
        text = text.strip("-")
        # Collapse multiple hyphens
        text = re.sub(r"-+", "-", text)
        # Limit length
        return text[:50]

    @staticmethod
    def generate_branch_name(issue_key: str, goal: Optional[str] = None, pattern: str = "{issue_key}-{goal_slug}") -> str:
        """Generate a branch name from issue key and goal.

        Args:
            issue_key: issue tracker key (e.g., PROJ-58868)
            goal: Session goal (optional)
            pattern: Branch naming pattern

        Returns:
            Generated branch name
        """
        # If no goal provided, use just the issue key
        if not goal:
            return issue_key.lower()

        # Strip issue key prefix from goal if present (e.g., "PROJ-12345: Fix bug" -> "Fix bug")
        # Pattern matches: <PROJECT>-<NUMBER>: at the start of the goal
        goal_cleaned = re.sub(r'^[A-Z]+-\d+:\s*', '', goal)

        goal_slug = GitUtils.slugify(goal_cleaned)
        branch_name = pattern.format(
            issue_key=issue_key.lower(),
            goal_slug=goal_slug,
        )
        return branch_name

    @staticmethod
    def has_uncommitted_changes(path: Path) -> bool:
        """Check if there are uncommitted changes in the repository.

        Args:
            path: Repository path

        Returns:
            True if there are uncommitted changes (staged or unstaged), False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Output is non-empty if there are changes
                return bool(result.stdout.strip())
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def get_status_summary(path: Path) -> str:
        """Get a human-readable summary of git status.

        Args:
            path: Repository path

        Returns:
            Git status summary (empty string if no changes or error)
        """
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return ""
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    @staticmethod
    def get_uncommitted_diff(path: Path) -> Optional[str]:
        """Get diff of all uncommitted changes (both staged and unstaged).

        This includes both staged changes (git diff --cached) and unstaged changes (git diff).

        Args:
            path: Repository path

        Returns:
            Unified diff of all uncommitted changes, or None if no changes or error
        """
        try:
            # Get staged changes (what would be committed with git commit)
            staged_result = subprocess.run(
                ["git", "diff", "--cached"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Get unstaged changes (modified files not yet staged)
            unstaged_result = subprocess.run(
                ["git", "diff"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if staged_result.returncode != 0 or unstaged_result.returncode != 0:
                return None

            # Combine both diffs
            staged_diff = staged_result.stdout.strip()
            unstaged_diff = unstaged_result.stdout.strip()

            # Return combined diff (both staged and unstaged)
            if staged_diff and unstaged_diff:
                return f"{staged_diff}\n\n{unstaged_diff}"
            elif staged_diff:
                return staged_diff
            elif unstaged_diff:
                return unstaged_diff
            else:
                return None

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    @staticmethod
    def commit_all(path: Path, message: str) -> bool:
        """Stage all changes and create a commit.

        Args:
            path: Repository path
            message: Commit message

        Returns:
            True if successful, False otherwise

        Raises:
            ToolNotFoundError: If git is not installed
        """
        require_tool("git", "commit changes")

        try:
            # Stage all changes
            add_result = subprocess.run(
                ["git", "add", "-A"],
                cwd=path,
                capture_output=True,
                timeout=10,
            )
            if add_result.returncode != 0:
                return False

            # Create commit
            commit_result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=path,
                capture_output=True,
                timeout=10,
            )
            return commit_result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def detect_repo_type(path: Path) -> Optional[str]:
        """Detect if repository is GitHub or GitLab based on remote URL.

        Args:
            path: Repository path

        Returns:
            "github" | "gitlab" | None
        """
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip().lower()
                if "github.com" in remote_url:
                    return "github"
                elif "gitlab" in remote_url:
                    return "gitlab"
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    @staticmethod
    def is_branch_pushed(path: Path, branch_name: str) -> bool:
        """Check if a branch exists on remote.

        Args:
            path: Repository path
            branch_name: Branch name to check

        Returns:
            True if branch exists on remote, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--heads", "origin", branch_name],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Output is non-empty if branch exists on remote
                return bool(result.stdout.strip())
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def has_unpushed_commits(path: Path, branch_name: str) -> bool:
        """Check if a branch has local commits that haven't been pushed to remote.

        Args:
            path: Repository path
            branch_name: Branch name to check

        Returns:
            True if there are unpushed commits, False otherwise
        """
        try:
            # First check if the branch exists on remote
            if not GitUtils.is_branch_pushed(path, branch_name):
                # If branch doesn't exist on remote and we have commits, they're unpushed
                # Check if we have any commits on this branch
                result = subprocess.run(
                    ["git", "rev-parse", "--verify", branch_name],
                    cwd=path,
                    capture_output=True,
                    timeout=5,
                )
                return result.returncode == 0  # True if branch exists locally

            # Branch exists on remote, check for unpushed commits
            # Use git log to count commits ahead of remote
            result = subprocess.run(
                ["git", "log", f"origin/{branch_name}..{branch_name}", "--oneline"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Output is non-empty if there are unpushed commits
                return bool(result.stdout.strip())
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def push_branch(path: Path, branch_name: str, set_upstream: bool = True) -> bool:
        """Push a branch to remote.

        Args:
            path: Repository path
            branch_name: Branch name to push
            set_upstream: Set upstream tracking (default: True)

        Returns:
            True if successful, False otherwise

        Raises:
            ToolNotFoundError: If git is not installed
        """
        require_tool("git", "push branch")

        try:
            cmd = ["git", "push"]
            if set_upstream:
                cmd.extend(["-u", "origin", branch_name])
            else:
                cmd.extend(["origin", branch_name])

            result = subprocess.run(
                cmd,
                cwd=path,
                capture_output=True,
                timeout=30,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def get_commit_log(path: Path, base_branch: Optional[str] = None, current_branch: Optional[str] = None) -> Optional[str]:
        """Get commit log from base branch to current branch.

        Args:
            path: Repository path
            base_branch: Base branch to compare from (e.g., 'main')
            current_branch: Current branch (defaults to HEAD)

        Returns:
            Commit log output or None if error
        """
        try:
            if not base_branch:
                base_branch = GitUtils.get_default_branch(path)
            if not base_branch:
                return None

            if not current_branch:
                current_branch = "HEAD"

            # Get commits from base branch to current branch
            result = subprocess.run(
                ["git", "log", f"{base_branch}..{current_branch}", "--pretty=format:%s"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    @staticmethod
    def get_diff_summary(path: Path, base_branch: Optional[str] = None, current_branch: Optional[str] = None) -> Optional[str]:
        """Get diff summary showing changed files from base branch to current branch.

        Args:
            path: Repository path
            base_branch: Base branch to compare from (e.g., 'main')
            current_branch: Current branch (defaults to HEAD)

        Returns:
            Diff summary (stat) or None if error
        """
        try:
            if not base_branch:
                base_branch = GitUtils.get_default_branch(path)
            if not base_branch:
                return None

            if not current_branch:
                current_branch = "HEAD"

            # Get diff stat showing which files changed
            result = subprocess.run(
                ["git", "diff", f"{base_branch}...{current_branch}", "--stat"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    @staticmethod
    def get_changed_files(path: Path, base_branch: Optional[str] = None, current_branch: Optional[str] = None) -> list[str]:
        """Get list of files changed from base branch to current branch.

        Args:
            path: Repository path
            base_branch: Base branch to compare from (e.g., 'main')
            current_branch: Current branch (defaults to HEAD)

        Returns:
            List of changed file paths (empty list if error)
        """
        try:
            if not base_branch:
                base_branch = GitUtils.get_default_branch(path)
            if not base_branch:
                return []

            if not current_branch:
                current_branch = "HEAD"

            # Get list of changed files
            result = subprocess.run(
                ["git", "diff", f"{base_branch}...{current_branch}", "--name-only"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                files = result.stdout.strip().split("\n")
                return [f for f in files if f]
            return []
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    @staticmethod
    def commits_behind(path: Path, branch: str, base_branch: str) -> int:
        """Count commits the current branch is behind the base branch.

        Args:
            path: Repository path
            branch: Current branch name
            base_branch: Base branch to compare against (e.g., 'main')

        Returns:
            Number of commits behind (0 if up-to-date or error)
        """
        try:
            # Use origin/{base_branch} to check against remote
            result = subprocess.run(
                ["git", "rev-list", "--count", f"HEAD..origin/{base_branch}"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                count_str = result.stdout.strip()
                return int(count_str) if count_str.isdigit() else 0
            return 0
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            return 0

    @staticmethod
    def merge_branch(path: Path, branch: str) -> bool:
        """Merge a branch into the current branch.

        Args:
            path: Repository path
            branch: Branch name to merge (e.g., 'main')

        Returns:
            True if successful, False if conflicts or error occurred
        """
        try:
            result = subprocess.run(
                ["git", "merge", branch],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Check if merge was successful
            if result.returncode == 0:
                return True

            # If merge failed (likely conflicts), abort it
            subprocess.run(
                ["git", "merge", "--abort"],
                cwd=path,
                capture_output=True,
                timeout=10,
            )
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Try to abort merge in case of error
            try:
                subprocess.run(
                    ["git", "merge", "--abort"],
                    cwd=path,
                    capture_output=True,
                    timeout=10,
                )
            except:
                pass
            return False

    @staticmethod
    def rebase_branch(path: Path, base_branch: str) -> bool:
        """Rebase current branch onto base branch.

        Args:
            path: Repository path
            base_branch: Base branch to rebase onto (e.g., 'main')

        Returns:
            True if successful, False if conflicts or error occurred
        """
        try:
            result = subprocess.run(
                ["git", "rebase", base_branch],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Check if rebase was successful
            if result.returncode == 0:
                return True

            # If rebase failed (likely conflicts), abort it
            subprocess.run(
                ["git", "rebase", "--abort"],
                cwd=path,
                capture_output=True,
                timeout=10,
            )
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Try to abort rebase in case of error
            try:
                subprocess.run(
                    ["git", "rebase", "--abort"],
                    cwd=path,
                    capture_output=True,
                    timeout=10,
                )
            except:
                pass
            return False

    @staticmethod
    def fetch_and_checkout_branch(path: Path, branch_name: str) -> bool:
        """Fetch a branch from remote and checkout as local branch.

        Args:
            path: Repository path
            branch_name: Branch name to fetch and checkout

        Returns:
            True if successful, False otherwise
        """
        try:
            # First, fetch the branch from remote
            fetch_result = subprocess.run(
                ["git", "fetch", "origin", branch_name],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if fetch_result.returncode != 0:
                return False

            # Checkout the remote branch as a local tracking branch
            checkout_result = subprocess.run(
                ["git", "checkout", "-b", branch_name, f"origin/{branch_name}"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return checkout_result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def remote_branch_exists(path: Path, branch_name: str) -> bool:
        """Check if a branch exists on remote.

        Args:
            path: Repository path
            branch_name: Branch name to check

        Returns:
            True if branch exists on remote, False otherwise
        """
        try:
            # Same as is_branch_pushed but more clearly named
            result = subprocess.run(
                ["git", "ls-remote", "--heads", "origin", branch_name],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return bool(result.stdout.strip())
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def has_merge_conflicts(path: Path) -> bool:
        """Check if there are unresolved merge conflicts.

        Args:
            path: Repository path

        Returns:
            True if there are unresolved merge conflicts, False otherwise
        """
        try:
            # Check for files with merge conflicts using git diff
            # Files with conflicts will show up with "U" (unmerged) status
            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=U"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Non-empty output means there are unmerged files (conflicts)
                return bool(result.stdout.strip())
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def get_conflicted_files(path: Path) -> list[str]:
        """Get list of files with unresolved merge conflicts.

        Args:
            path: Repository path

        Returns:
            List of file paths with merge conflicts (empty list if none or error)
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=U"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                files = result.stdout.strip().split("\n")
                return [f for f in files if f]
            return []
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    @staticmethod
    def get_conflict_details(path: Path, file_path: str) -> Optional[dict]:
        """Get details about conflicts in a specific file.

        Args:
            path: Repository path
            file_path: Path to the conflicted file (relative to repo root)

        Returns:
            Dictionary with conflict details or None if error:
            {
                'conflict_count': int,
                'preview': str,  # First few lines of first conflict
                'file_size': int,
                'ours_branch': str,
                'theirs_branch': str
            }
        """
        try:
            full_path = path / file_path
            if not full_path.exists():
                return None

            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Count conflict markers
            conflict_count = content.count('<<<<<<< ')

            if conflict_count == 0:
                return None

            # Extract first conflict preview
            lines = content.split('\n')
            preview_lines = []
            in_conflict = False
            conflict_start = 0
            ours_branch = "HEAD"
            theirs_branch = "incoming"

            for i, line in enumerate(lines):
                if line.startswith('<<<<<<< '):
                    in_conflict = True
                    conflict_start = i
                    ours_branch = line.replace('<<<<<<< ', '').strip()
                    preview_lines.append(line)
                elif in_conflict:
                    preview_lines.append(line)
                    if line.startswith('>>>>>>> '):
                        theirs_branch = line.replace('>>>>>>> ', '').strip()
                        # Include a few lines of context
                        if i - conflict_start > 15:
                            preview_lines.append("... (conflict continues)")
                        break

            preview = '\n'.join(preview_lines[:20])  # Limit to 20 lines

            return {
                'conflict_count': conflict_count,
                'preview': preview,
                'file_size': len(lines),
                'ours_branch': ours_branch,
                'theirs_branch': theirs_branch
            }
        except Exception:
            return None

    @staticmethod
    def get_merge_head_info(path: Path) -> Optional[dict]:
        """Get information about the current merge operation.

        Args:
            path: Repository path

        Returns:
            Dictionary with merge info or None:
            {
                'merge_msg': str,  # The merge message
                'merge_head': str,  # The commit being merged
                'merge_mode': str  # 'merge' or 'rebase'
            }
        """
        try:
            git_dir = path / ".git"
            merge_msg_file = git_dir / "MERGE_MSG"
            merge_head_file = git_dir / "MERGE_HEAD"
            rebase_dir = git_dir / "rebase-merge"

            merge_mode = "merge"
            if rebase_dir.exists():
                merge_mode = "rebase"

            merge_msg = ""
            if merge_msg_file.exists():
                with open(merge_msg_file, 'r') as f:
                    merge_msg = f.read().strip()

            merge_head = ""
            if merge_head_file.exists():
                with open(merge_head_file, 'r') as f:
                    merge_head = f.read().strip()[:8]  # Short hash

            if not merge_msg and not merge_head:
                return None

            return {
                'merge_msg': merge_msg,
                'merge_head': merge_head,
                'merge_mode': merge_mode
            }
        except Exception:
            return None

    @staticmethod
    def get_remote_url(path: Path, remote: str = "origin") -> Optional[str]:
        """Get the remote URL of the repository.

        Args:
            path: Repository path
            remote: Remote name (default: "origin")

        Returns:
            Remote URL or None if not a git repo or remote doesn't exist
        """
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", remote],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    @staticmethod
    def get_branch_remote_url(path: Path, branch: str) -> Optional[str]:
        """Get the remote URL for a specific branch's upstream.

        Args:
            path: Repository path
            branch: Branch name

        Returns:
            Remote URL where branch is pushed, or None if no upstream set
        """
        try:
            # Get the upstream remote name for the branch
            result = subprocess.run(
                ["git", "config", f"branch.{branch}.remote"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                remote_name = result.stdout.strip()
                # Now get the URL for that remote
                return GitUtils.get_remote_url(path, remote_name)
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    @staticmethod
    def add_remote(path: Path, remote_name: str, remote_url: str) -> bool:
        """Add a new git remote.

        Args:
            path: Repository path
            remote_name: Name for the remote
            remote_url: URL of the remote

        Returns:
            True if successful, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "remote", "add", remote_name, remote_url],
                cwd=path,
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def get_remote_name_for_url(path: Path, url: str) -> Optional[str]:
        """Find the remote name for a given URL.

        Args:
            path: Repository path
            url: Remote URL to find

        Returns:
            Remote name if found, None otherwise
        """
        try:
            # List all remotes with URLs
            result = subprocess.run(
                ["git", "remote", "-v"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse output: "origin  https://github.com/user/repo.git (fetch)"
                for line in result.stdout.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 2:
                        remote_name = parts[0]
                        remote_url = parts[1]
                        # Normalize URLs (remove .git suffix, handle ssh vs https)
                        if GitUtils._normalize_git_url(remote_url) == GitUtils._normalize_git_url(url):
                            return remote_name
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    @staticmethod
    def _normalize_git_url(url: str) -> str:
        """Normalize git URL for comparison.

        Args:
            url: Git URL

        Returns:
            Normalized URL
        """
        # Remove .git suffix
        normalized = url.rstrip('/')
        if normalized.endswith('.git'):
            normalized = normalized[:-4]

        # Convert SSH to HTTPS for comparison
        # git@github.com:user/repo -> https://github.com/user/repo
        if normalized.startswith('git@'):
            normalized = normalized.replace('git@', 'https://').replace(':', '/', 1)

        return normalized.lower()

    @staticmethod
    def clone_repository(remote_url: str, target_path: Path, branch: Optional[str] = None) -> bool:
        """Clone a git repository to a target directory.

        Args:
            remote_url: Git remote URL to clone from
            target_path: Target directory path (will be created)
            branch: Optional branch to checkout after cloning

        Returns:
            True if successful, False otherwise
        """
        try:
            # Clone the repository
            cmd = ["git", "clone", remote_url, str(target_path)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minutes timeout for clone
            )
            if result.returncode != 0:
                return False

            # If a specific branch was requested, checkout that branch
            if branch:
                checkout_result = subprocess.run(
                    ["git", "checkout", branch],
                    cwd=target_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return checkout_result.returncode == 0

            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def get_remote_names(path: Path) -> list[str]:
        """Get list of all remote names in a repository.

        Args:
            path: Repository path

        Returns:
            List of remote names (e.g., ['origin', 'upstream', 'alice'])
        """
        try:
            result = subprocess.run(
                ["git", "remote"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                remotes = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                return remotes
            return []
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    @staticmethod
    def get_fork_upstream_info(path: Path, prompt_for_remote: bool = False) -> Optional[dict]:
        """Get upstream repository information for a fork.

        Detects if the current repository is a fork and returns information
        about the upstream (parent) repository.

        Git Remote Conventions:
        - 'origin' typically points to your fork
        - 'upstream' typically points to the parent/upstream repository
        These are common conventions but not enforced by git.

        Args:
            path: Repository path
            prompt_for_remote: If True and no upstream detected, prompt user for remote name

        Returns:
            Dictionary with upstream info or None:
            {
                'upstream_url': str,  # URL of upstream repository
                'upstream_owner': str,  # Owner/org of upstream
                'upstream_repo': str,  # Repository name
                'detection_method': str  # How upstream was detected
            }
        """
        # Method 1: Try GitHub CLI (fastest and most reliable for GitHub repos)
        try:
            result = subprocess.run(
                ["gh", "repo", "view", "--json", "parent"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                import json
                data = json.loads(result.stdout)
                if data.get("parent"):
                    parent = data["parent"]
                    url = parent.get("url")
                    if url:
                        # Extract owner and repo from URL
                        import re
                        match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', url)
                        if match:
                            return {
                                'upstream_url': url,
                                'upstream_owner': match.group(1),
                                'upstream_repo': match.group(2),
                                'detection_method': 'gh_cli'
                            }
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

        # Method 2: Try GitLab CLI
        try:
            result = subprocess.run(
                ["glab", "repo", "view", "--json"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                import json
                data = json.loads(result.stdout)
                forked_from = data.get("forked_from_project")
                if forked_from:
                    url = forked_from.get("web_url")
                    path_with_namespace = forked_from.get("path_with_namespace", "")
                    if url and "/" in path_with_namespace:
                        owner, repo = path_with_namespace.split("/", 1)
                        return {
                            'upstream_url': url,
                            'upstream_owner': owner,
                            'upstream_repo': repo,
                            'detection_method': 'glab_cli'
                        }
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

        # Method 3: Check for 'upstream' remote (common git convention)
        upstream_url = GitUtils.get_remote_url(path, "upstream")
        if upstream_url:
            # Extract owner and repo from URL
            import re
            # Try GitHub/GitLab pattern
            match = re.search(r'[:/]([^/]+)/([^/.]+?)(?:\.git)?$', upstream_url)
            if match:
                return {
                    'upstream_url': upstream_url,
                    'upstream_owner': match.group(1),
                    'upstream_repo': match.group(2),
                    'detection_method': 'upstream_remote'
                }

        # Method 4: If prompt_for_remote=True, ask user which remote is upstream
        if prompt_for_remote:
            from rich.console import Console
            from rich.prompt import Prompt
            console = Console()

            # Get list of available remotes
            remotes = GitUtils.get_remote_names(path)
            if len(remotes) > 1:
                console.print("\n[yellow]Could not auto-detect upstream repository for fork[/yellow]")
                console.print("[dim]Available remotes:[/dim]")
                for remote in remotes:
                    remote_url = GitUtils.get_remote_url(path, remote)
                    console.print(f"  - {remote}: {remote_url}")

                console.print("\n[cyan]Which remote points to the upstream (parent) repository?[/cyan]")
                console.print("[dim]Common convention: 'upstream' for parent repo, 'origin' for your fork[/dim]")
                remote_name = Prompt.ask("Upstream remote name", choices=remotes + ["none"], default="none")

                if remote_name != "none":
                    remote_url = GitUtils.get_remote_url(path, remote_name)
                    if remote_url:
                        import re
                        match = re.search(r'[:/]([^/]+)/([^/.]+?)(?:\.git)?$', remote_url)
                        if match:
                            return {
                                'upstream_url': remote_url,
                                'upstream_owner': match.group(1),
                                'upstream_repo': match.group(2),
                                'detection_method': 'user_prompt'
                            }

        # No upstream detected
        return None
