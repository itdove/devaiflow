"""Release manager for automating release mechanics."""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass

from devflow.release.version import Version, detect_release_type, get_next_dev_version


@dataclass
class ReleaseContext:
    """Context information for a release."""

    current_version: Version
    target_version: Version
    release_type: str
    repo_path: Path
    current_branch: str
    dry_run: bool = False

    # Calculated fields
    release_branch: Optional[str] = None
    hotfix_branch: Optional[str] = None
    tag_name: Optional[str] = None
    next_dev_version: Optional[Version] = None


class ReleaseManager:
    """Manages release operations."""

    def __init__(self, repo_path: Path):
        """Initialize release manager.

        Args:
            repo_path: Path to git repository
        """
        self.repo_path = repo_path
        self.init_file = repo_path / "devflow" / "__init__.py"
        self.setup_file = repo_path / "setup.py"
        self.changelog_file = repo_path / "CHANGELOG.md"

    def read_current_version(self) -> Tuple[str, str]:
        """Read current version from version files.

        Returns:
            Tuple of (init_version, setup_version)

        Raises:
            FileNotFoundError: If version files don't exist
            ValueError: If version cannot be extracted
        """
        # Read from devflow/__init__.py
        if not self.init_file.exists():
            raise FileNotFoundError(f"Version file not found: {self.init_file}")

        init_content = self.init_file.read_text()
        init_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_content)
        if not init_match:
            raise ValueError(f"Could not find __version__ in {self.init_file}")
        init_version = init_match.group(1)

        # Read from setup.py
        if not self.setup_file.exists():
            raise FileNotFoundError(f"Setup file not found: {self.setup_file}")

        setup_content = self.setup_file.read_text()
        setup_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', setup_content)
        if not setup_match:
            raise ValueError(f"Could not find version in {self.setup_file}")
        setup_version = setup_match.group(1)

        return init_version, setup_version

    def update_version_files(self, new_version: Version, dry_run: bool = False) -> None:
        """Update version in devflow/__init__.py and setup.py.

        Args:
            new_version: New version to set
            dry_run: If True, don't actually write files
        """
        version_str = str(new_version)

        # Update devflow/__init__.py
        init_content = self.init_file.read_text()
        new_init_content = re.sub(
            r'(__version__\s*=\s*["\'])[^"\']+(["\'])',
            rf'\g<1>{version_str}\g<2>',
            init_content
        )

        if not dry_run:
            self.init_file.write_text(new_init_content)

        # Update setup.py
        setup_content = self.setup_file.read_text()
        new_setup_content = re.sub(
            r'(version\s*=\s*["\'])[^"\']+(["\'])',
            rf'\g<1>{version_str}\g<2>',
            setup_content
        )

        if not dry_run:
            self.setup_file.write_text(new_setup_content)

    def update_changelog(
        self,
        version: Version,
        release_date: Optional[str] = None,
        auto_generate: bool = True,
        dry_run: bool = False
    ) -> None:
        """Update CHANGELOG.md with new version section and reference link.

        Args:
            version: Version being released
            release_date: Release date (defaults to today)
            auto_generate: If True, generate changelog content from PR/MR metadata
            dry_run: If True, don't actually write file
        """
        from devflow.release.permissions import get_git_remote_url, parse_git_remote, Platform

        if not self.changelog_file.exists():
            raise FileNotFoundError(f"CHANGELOG not found: {self.changelog_file}")

        if release_date is None:
            release_date = datetime.now().strftime("%Y-%m-%d")

        changelog_content = self.changelog_file.read_text()

        # Check if version already exists in CHANGELOG
        version_str = str(version)
        if f"## [{version_str}]" in changelog_content:
            raise ValueError(f"Version {version_str} already exists in CHANGELOG.md")

        # Find the [Unreleased] section
        unreleased_pattern = r'## \[Unreleased\]'
        if not re.search(unreleased_pattern, changelog_content):
            raise ValueError("Could not find [Unreleased] section in CHANGELOG.md")

        # Generate changelog content if requested
        changelog_body = ""
        if auto_generate:
            # Get latest tag to find commits since last release
            latest_tag = self.get_latest_tag()
            if latest_tag:
                # Get commits with PR/MR info
                commits = self.get_commits_with_prs(latest_tag)

                # Fetch PR/MR metadata
                pr_mr_metadata = []
                for commit in commits:
                    if commit.get('pr_mr'):
                        pr_mr_info = commit['pr_mr']
                        metadata = None

                        if pr_mr_info['type'] == 'github_pr':
                            metadata = self.fetch_pr_metadata(pr_mr_info['number'])
                        elif pr_mr_info['type'] == 'gitlab_mr':
                            metadata = self.fetch_mr_metadata(pr_mr_info['number'])

                        if metadata:
                            pr_mr_metadata.append(metadata)

                # Generate changelog content from PR/MR metadata
                if pr_mr_metadata:
                    changelog_body = self.generate_changelog_content(pr_mr_metadata)

        # Add new version section after [Unreleased]
        new_section = f"\n## [{version_str}] - {release_date}{changelog_body}\n"
        new_changelog = re.sub(
            unreleased_pattern,
            f"## [Unreleased]\n{new_section}",
            changelog_content,
            count=1
        )

        # Add version reference link at the bottom
        # Get git remote URL and parse platform
        remote_url = get_git_remote_url(self.repo_path)
        if remote_url:
            platform, path, repo = parse_git_remote(remote_url)

            # Build tag URL based on platform
            tag_url = None
            tag_name = f"v{version_str}"

            if platform == Platform.GITHUB:
                tag_url = f"https://github.com/{path}/{repo}/tags/{tag_name}"
            elif platform == Platform.GITLAB:
                # Extract hostname from remote URL for self-hosted GitLab instances
                if remote_url.startswith("git@"):
                    # git@gitlab.example.com:path/repo.git
                    hostname_match = re.match(r"git@([^:]+):", remote_url)
                    if hostname_match:
                        hostname = hostname_match.group(1)
                        tag_url = f"https://{hostname}/{path}/{repo}/-/tags/{tag_name}"
                elif remote_url.startswith("https://"):
                    # https://gitlab.example.com/path/repo.git
                    hostname_match = re.match(r"https://([^/]+)/", remote_url)
                    if hostname_match:
                        hostname = hostname_match.group(1)
                        tag_url = f"https://{hostname}/{path}/{repo}/-/tags/{tag_name}"

            if tag_url:
                # Find existing reference links section (lines starting with [version]:)
                # Insert new link at the top of the reference links section to maintain reverse chronological order
                ref_link_pattern = r'^(\[\d+\.\d+\.\d+\]:.*?)$'
                ref_match = re.search(ref_link_pattern, new_changelog, re.MULTILINE)

                new_ref_link = f"[{version_str}]: {tag_url}"

                if ref_match:
                    # Insert before the first existing reference link
                    insert_pos = ref_match.start()
                    new_changelog = new_changelog[:insert_pos] + new_ref_link + "\n" + new_changelog[insert_pos:]
                else:
                    # No existing reference links, add at the end
                    if not new_changelog.endswith("\n"):
                        new_changelog += "\n"
                    new_changelog += "\n" + new_ref_link + "\n"

        if not dry_run:
            self.changelog_file.write_text(new_changelog)

    def run_tests(self, dry_run: bool = False) -> Tuple[bool, str]:
        """Run the test suite.

        Args:
            dry_run: If True, skip running tests

        Returns:
            Tuple of (success, output)
        """
        if dry_run:
            return True, "Skipped (dry-run mode)"

        try:
            result = subprocess.run(
                ["pytest"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            success = result.returncode == 0
            output = result.stdout + result.stderr

            return success, output

        except subprocess.TimeoutExpired:
            return False, "Test suite timed out after 5 minutes"
        except FileNotFoundError:
            return False, "pytest not found. Install with: pip install pytest"
        except Exception as e:
            return False, f"Unexpected error running tests: {e}"

    def run_integration_tests(self, dry_run: bool = False) -> Tuple[bool, str, List[str]]:
        """Run integration tests.

        Args:
            dry_run: If True, skip running tests

        Returns:
            Tuple of (success, summary, failed_tests)
        """
        if dry_run:
            return True, "Skipped (dry-run mode)", []

        integration_dir = self.repo_path / "integration-tests"
        if not integration_dir.exists():
            return True, "No integration tests directory found", []

        # Find all test scripts
        test_scripts = [
            "test_collaboration_workflow.sh",
            "test_jira_green_path.sh"
        ]

        failed_tests = []
        passed_tests = []
        outputs = []

        for script_name in test_scripts:
            script_path = integration_dir / script_name
            if not script_path.exists():
                continue

            try:
                # Run the test script
                result = subprocess.run(
                    ["bash", str(script_path)],
                    cwd=integration_dir,
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minute timeout for integration tests
                )

                if result.returncode == 0:
                    passed_tests.append(script_name)
                else:
                    failed_tests.append(script_name)
                    outputs.append(f"\n=== {script_name} FAILED ===\n{result.stdout}\n{result.stderr}")

            except subprocess.TimeoutExpired:
                failed_tests.append(script_name)
                outputs.append(f"\n=== {script_name} TIMED OUT ===\nTest timed out after 10 minutes")
            except Exception as e:
                failed_tests.append(script_name)
                outputs.append(f"\n=== {script_name} ERROR ===\n{e}")

        # Build summary
        total = len(passed_tests) + len(failed_tests)
        if total == 0:
            return True, "No integration tests found", []

        if failed_tests:
            summary = f"{len(failed_tests)}/{total} integration tests failed"
            output = "\n".join(outputs)
            return False, summary, failed_tests
        else:
            summary = f"All {total} integration tests passed"
            return True, summary, []

    def create_branch(self, branch_name: str, from_branch: Optional[str] = None, dry_run: bool = False) -> Tuple[bool, str]:
        """Create a new git branch.

        Args:
            branch_name: Name of branch to create
            from_branch: Branch to create from (None = current HEAD)
            dry_run: If True, skip creating branch

        Returns:
            Tuple of (success, message)
        """
        if dry_run:
            return True, f"Would create branch '{branch_name}'"

        try:
            cmd = ["git", "checkout", "-b", branch_name]
            if from_branch:
                cmd.append(from_branch)

            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return True, f"Created branch '{branch_name}'"
            else:
                return False, f"Failed to create branch: {result.stderr}"

        except Exception as e:
            return False, f"Error creating branch: {e}"

    def checkout_branch(self, branch_name: str, dry_run: bool = False) -> Tuple[bool, str]:
        """Checkout an existing git branch.

        Args:
            branch_name: Name of branch to checkout
            dry_run: If True, skip checkout

        Returns:
            Tuple of (success, message)
        """
        if dry_run:
            return True, f"Would checkout branch '{branch_name}'"

        try:
            result = subprocess.run(
                ["git", "checkout", branch_name],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return True, f"Checked out branch '{branch_name}'"
            else:
                return False, f"Failed to checkout branch: {result.stderr}"

        except Exception as e:
            return False, f"Error checking out branch: {e}"

    def commit_changes(self, message: str, dry_run: bool = False) -> Tuple[bool, str]:
        """Commit staged changes.

        Args:
            message: Commit message
            dry_run: If True, skip commit

        Returns:
            Tuple of (success, message)
        """
        if dry_run:
            return True, f"Would commit with message: {message[:50]}..."

        try:
            # Stage all changes
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.repo_path,
                check=True,
                timeout=10,
            )

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return True, "Changes committed"
            else:
                return False, f"Failed to commit: {result.stderr}"

        except Exception as e:
            return False, f"Error committing changes: {e}"

    def create_tag(self, tag_name: str, message: str, dry_run: bool = False) -> Tuple[bool, str]:
        """Create an annotated git tag.

        Args:
            tag_name: Tag name (e.g., "v1.0.0")
            message: Tag annotation message
            dry_run: If True, skip creating tag

        Returns:
            Tuple of (success, message)
        """
        if dry_run:
            return True, f"Would create tag '{tag_name}'"

        try:
            result = subprocess.run(
                ["git", "tag", "-a", tag_name, "-m", message],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return True, f"Created tag '{tag_name}'"
            else:
                return False, f"Failed to create tag: {result.stderr}"

        except Exception as e:
            return False, f"Error creating tag: {e}"

    def get_current_branch(self) -> Optional[str]:
        """Get current git branch name.

        Returns:
            Current branch name or None if not in a git repo

        Raises:
            subprocess.TimeoutExpired: If git command times out
            FileNotFoundError: If git is not installed
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,  # Don't raise on non-zero exit
            )

            if result.returncode == 0:
                return result.stdout.strip()
            # Non-zero exit (not a git repo) - return None
            return None

        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Re-raise these - they indicate real problems
            raise

    def has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes.

        Returns:
            True if there are uncommitted changes

        Raises:
            subprocess.TimeoutExpired: If git command times out
            FileNotFoundError: If git is not installed
            subprocess.CalledProcessError: If git command fails
        """
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,  # Raise on non-zero exit
        )

        # If output is non-empty, there are changes
        return bool(result.stdout.strip())

    def get_latest_tag(self) -> Optional[str]:
        """Get the latest git tag.

        Returns:
            Latest tag name or None if no tags exist

        Raises:
            subprocess.TimeoutExpired: If git command times out
            FileNotFoundError: If git is not installed
        """
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,  # Don't raise on non-zero exit (no tags is normal)
            )

            if result.returncode == 0:
                tag = result.stdout.strip()
                return tag if tag else None
            # Non-zero exit (no tags) - return None
            return None

        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Re-raise these - they indicate real problems
            raise

    def analyze_commits_since_tag(self, tag: str) -> Dict[str, List[str]]:
        """Analyze commits since a given tag using conventional commit format.

        Args:
            tag: Git tag to compare from

        Returns:
            Dictionary with keys: 'breaking', 'features', 'fixes', 'other'

        Raises:
            subprocess.TimeoutExpired: If git command times out
            FileNotFoundError: If git is not installed
        """
        analysis = {
            'breaking': [],
            'features': [],
            'fixes': [],
            'other': []
        }

        result = subprocess.run(
            ["git", "log", f"{tag}..HEAD", "--oneline"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,  # Don't raise on non-zero exit
        )

        if result.returncode != 0:
            return analysis

        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            # Parse conventional commit format
            # Git log --oneline format: "<hash> <message>"
            # Split to get message part after hash
            parts = line.split(None, 1)  # Split on first whitespace
            if len(parts) < 2:
                analysis['other'].append(line)
                continue

            message = parts[1]
            message_lower = message.lower()

            # Check for breaking changes (! in type or BREAKING CHANGE in message)
            if 'breaking change' in message_lower or ('!' in message and ':' in message and message.index('!') < message.index(':')):
                analysis['breaking'].append(line)
            # Check for features
            elif message_lower.startswith(('feat:', 'feat(', 'feature:', 'feature(')):
                analysis['features'].append(line)
            # Check for fixes
            elif message_lower.startswith(('fix:', 'fix(')):
                analysis['fixes'].append(line)
            else:
                analysis['other'].append(line)

        return analysis

    def suggest_release_type(self) -> Tuple[Optional[str], str, Dict[str, List[str]]]:
        """Suggest release type based on commits since last release.

        Returns:
            Tuple of (suggested_type, explanation, commit_analysis)
            suggested_type can be: "major", "minor", "patch", or None
        """
        # Get latest tag
        latest_tag = self.get_latest_tag()
        if not latest_tag:
            return (
                "minor",
                "No previous releases found. Suggesting minor release for first release.",
                {'breaking': [], 'features': [], 'fixes': [], 'other': []}
            )

        # Analyze commits
        analysis = self.analyze_commits_since_tag(latest_tag)

        # Determine suggestion
        if analysis['breaking']:
            suggestion = "major"
            explanation = (
                f"Found {len(analysis['breaking'])} breaking change(s) since {latest_tag}. "
                "Major release recommended for breaking changes."
            )
        elif analysis['features']:
            suggestion = "minor"
            explanation = (
                f"Found {len(analysis['features'])} new feature(s) and "
                f"{len(analysis['fixes'])} fix(es) since {latest_tag}. "
                "Minor release recommended for new features."
            )
        elif analysis['fixes']:
            suggestion = "patch"
            explanation = (
                f"Found {len(analysis['fixes'])} bug fix(es) since {latest_tag}. "
                "Patch release recommended for bug fixes only."
            )
        else:
            suggestion = None
            explanation = (
                f"Found {len(analysis['other'])} commit(s) since {latest_tag}, "
                "but no clear conventional commits (feat:, fix:, BREAKING:). "
                "Unable to suggest release type automatically."
            )

        return suggestion, explanation, analysis

    def prepare_release(self, target_version: str, dry_run: bool = False) -> ReleaseContext:
        """Prepare a release by validating and creating release context.

        Args:
            target_version: Target version string (e.g., "1.0.0")
            dry_run: If True, perform validation only

        Returns:
            ReleaseContext with all release information

        Raises:
            ValueError: If validation fails
        """
        # Read current versions
        init_version, setup_version = self.read_current_version()

        # Validate versions are in sync
        if init_version != setup_version:
            raise ValueError(
                f"Version mismatch: devflow/__init__.py has {init_version}, "
                f"setup.py has {setup_version}. Fix before releasing."
            )

        # Parse versions
        current = Version.parse(init_version)
        target = Version.parse(target_version)

        # Detect release type
        release_type = detect_release_type(current, target)

        # Get current branch
        current_branch = self.get_current_branch()
        if not current_branch:
            raise ValueError("Could not determine current git branch")

        # Check for uncommitted changes (only for minor/major releases, skip in dry-run)
        if release_type in ["minor", "major"] and not dry_run and self.has_uncommitted_changes():
            raise ValueError(
                "You have uncommitted changes. Commit or stash them before creating a release."
            )

        # Create release context
        context = ReleaseContext(
            current_version=current,
            target_version=target,
            release_type=release_type,
            repo_path=self.repo_path,
            current_branch=current_branch,
            dry_run=dry_run
        )

        # Calculate branch names and next versions
        if release_type == "patch":
            # Patch releases use hotfix branches
            context.hotfix_branch = f"hotfix/{target_version}"
        else:
            # Minor/major releases use release branches
            context.release_branch = f"release/{target.major}.{target.minor}"

        context.tag_name = f"v{target_version}"
        context.next_dev_version = get_next_dev_version(target, release_type)

        return context

    def get_commits_with_prs(self, from_tag: str, to_ref: str = "HEAD") -> List[Dict]:
        """Get commits with associated PR/MR information.

        Args:
            from_tag: Starting tag to compare from
            to_ref: Ending ref to compare to (default: HEAD)

        Returns:
            List of commit dictionaries with PR/MR information

        Raises:
            subprocess.TimeoutExpired: If git command times out
            FileNotFoundError: If git is not installed
        """
        # Use a unique delimiter that's unlikely to appear in commit messages
        delimiter = "|||COMMIT_DELIMITER|||"
        result = subprocess.run(
            ["git", "log", f"{from_tag}..{to_ref}", f"--format=%H|||%s|||%b{delimiter}"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,  # Don't raise on non-zero exit
        )

        if result.returncode != 0:
            return []

        commits = []
        # Split by our unique delimiter to separate commits
        commit_blocks = result.stdout.strip().split(delimiter)

        for block in commit_blocks:
            block = block.strip()
            if not block:
                continue

            # Now split by ||| to get hash, subject, and body
            # Only split on the first two occurrences to preserve ||| in the body
            parts = block.split('|||', 2)
            if len(parts) < 2:
                continue

            commit_hash = parts[0]
            subject = parts[1]
            body = parts[2] if len(parts) > 2 else ""

            # Extract PR number from GitHub merge commit
            # Format: "Merge pull request #123 from user/branch"
            github_pr = re.search(r'Merge pull request #(\d+)', subject)

            # Extract MR number from GitLab merge commit
            # Format in body: "See merge request !123" or "See merge request owner/repo!123"
            gitlab_mr = re.search(r'See merge request (?:[\w-]+/[\w-]+)?!(\d+)', body)

            pr_mr_info = None
            if github_pr:
                pr_mr_info = {'type': 'github_pr', 'number': github_pr.group(1)}
            elif gitlab_mr:
                pr_mr_info = {'type': 'gitlab_mr', 'number': gitlab_mr.group(1)}

            commits.append({
                'hash': commit_hash,
                'subject': subject,
                'body': body,
                'pr_mr': pr_mr_info
            })

        return commits

    def fetch_pr_metadata(self, pr_number: str) -> Optional[Dict]:
        """Fetch GitHub PR metadata using gh CLI.

        Args:
            pr_number: GitHub PR number

        Returns:
            PR metadata dictionary or None if fetch fails
        """
        try:
            result = subprocess.run(
                ["gh", "pr", "view", pr_number, "--json", "title,body,labels,url,number"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                return {
                    'number': data.get('number', pr_number),
                    'title': data.get('title', ''),
                    'body': data.get('body', ''),
                    'url': data.get('url', ''),
                    'type': 'github_pr'
                }
            return None

        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, Exception):
            return None

    def fetch_mr_metadata(self, mr_number: str) -> Optional[Dict]:
        """Fetch GitLab MR metadata using glab CLI.

        Args:
            mr_number: GitLab MR number

        Returns:
            MR metadata dictionary or None if fetch fails
        """
        try:
            result = subprocess.run(
                ["glab", "mr", "view", mr_number, "-F", "json"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                return {
                    'number': data.get('iid', mr_number),
                    'title': data.get('title', ''),
                    'body': data.get('description', ''),
                    'url': data.get('web_url', ''),
                    'type': 'gitlab_mr'
                }
            return None

        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, Exception):
            return None

    def generate_changelog_content(self, pr_mr_list: List[Dict]) -> str:
        """Generate formatted changelog content from PR/MR metadata.

        Args:
            pr_mr_list: List of PR/MR metadata dictionaries

        Returns:
            Formatted changelog content string following Keep a Changelog format
        """
        categories = {
            'Added': [],
            'Changed': [],
            'Fixed': [],
            'Deprecated': [],
            'Removed': [],
            'Security': []
        }

        for item in pr_mr_list:
            title = item.get('title', '')
            body = item.get('body', '')
            url = item.get('url', '')
            number = item.get('number', '')

            # Extract issue ticket from title or body (e.g., PROJ-1234, ABC-567)
            # Match common issue tracker patterns: PROJECT-NUMBER
            issue_match = re.search(r'([A-Z]+-\d+)', title + ' ' + body)
            issue_ref = f" ({issue_match.group(1)})" if issue_match else ""

            # Build reference with PR/MR number and URL
            pr_mr_ref = f" [#{number}]({url})" if url else f" #{number}"

            # Parse body for category sections
            # Look for markdown headers like "### Added" or "## Added" in PR/MR description
            found_in_body = False
            for category in categories.keys():
                # Match both ### and ## for headers
                pattern = rf'##\s*{category}\s*\n(.*?)(?=##|\Z)'
                matches = re.findall(pattern, body, re.DOTALL | re.IGNORECASE)
                if matches:
                    found_in_body = True
                    for match in matches:
                        # Split by lines and clean up
                        lines = [line.strip() for line in match.strip().split('\n') if line.strip()]
                        for line in lines:
                            # Remove existing bullet points/list markers
                            line = re.sub(r'^\s*[-*•]\s*', '', line)
                            # Remove existing numbered list markers
                            line = re.sub(r'^\s*\d+\.\s*', '', line)
                            if line:
                                categories[category].append(f"{line}{issue_ref}{pr_mr_ref}")

            # If no categories found in body, categorize by title prefix (conventional commits)
            if not found_in_body:
                title_lower = title.lower()
                entry = f"{title}{issue_ref}{pr_mr_ref}"

                # Try to categorize by conventional commit prefix
                if title_lower.startswith(('feat:', 'feat(', 'feature:', 'feature(')):
                    # Remove the feat: prefix for cleaner changelog
                    clean_title = re.sub(r'^(feat|feature)(\([^)]+\))?:\s*', '', title, flags=re.IGNORECASE)
                    categories['Added'].append(f"{clean_title}{issue_ref}{pr_mr_ref}")
                elif title_lower.startswith(('fix:', 'fix(')):
                    # Remove the fix: prefix
                    clean_title = re.sub(r'^fix(\([^)]+\))?:\s*', '', title, flags=re.IGNORECASE)
                    categories['Fixed'].append(f"{clean_title}{issue_ref}{pr_mr_ref}")
                elif title_lower.startswith(('refactor:', 'refactor(', 'chore:', 'chore(')):
                    # Remove the prefix
                    clean_title = re.sub(r'^(refactor|chore)(\([^)]+\))?:\s*', '', title, flags=re.IGNORECASE)
                    categories['Changed'].append(f"{clean_title}{issue_ref}{pr_mr_ref}")
                elif 'deprecat' in title_lower:
                    categories['Deprecated'].append(entry)
                elif 'remov' in title_lower or 'delet' in title_lower:
                    categories['Removed'].append(entry)
                elif 'security' in title_lower or 'vulnerab' in title_lower:
                    categories['Security'].append(entry)
                else:
                    # Default to Changed for unclassified items
                    categories['Changed'].append(entry)

        # Format output
        content = ""
        for category, items in categories.items():
            if items:
                content += f"\n### {category}\n"
                for item in items:
                    content += f"- {item}\n"

        return content

    def validate_release_prepared(self, version: Version) -> Tuple[bool, str, Optional[str]]:
        """Validate that a release has been prepared and is ready for approval.

        Args:
            version: Version to validate

        Returns:
            Tuple of (success, message, release_branch_or_none)
            release_branch_or_none is the release branch name for minor/major, None for patch
        """
        version_str = str(version)
        tag_name = f"v{version_str}"

        # Check if tag exists
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", tag_name],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return False, f"Tag '{tag_name}' does not exist. Run 'daf release {version_str}' first.", None

        except Exception as e:
            return False, f"Error checking tag: {e}", None

        # Detect release type to determine if we have a release branch
        release_type = None
        release_branch = None

        if version.patch == 0 and version.minor > 0:
            release_type = "minor"
            release_branch = f"release/{version.major}.{version.minor}"
        elif version.patch == 0 and version.minor == 0:
            release_type = "major"
            release_branch = f"release/{version.major}.{version.minor}"
        else:
            release_type = "patch"
            release_branch = None

        # Calculate the next dev version that 'daf release' would have set
        next_dev_version = get_next_dev_version(version, release_type)
        next_dev_version_str = str(next_dev_version)

        # Verify version files match acceptable versions
        # Accept: version_str (1.0.0), version_str-dev (1.0.0-dev), or next_dev_version (1.1.0-dev)
        try:
            init_version, setup_version = self.read_current_version()
            acceptable_versions = [version_str, f"{version_str}-dev", next_dev_version_str]

            if init_version not in acceptable_versions:
                return False, f"Version mismatch: devflow/__init__.py has {init_version}, expected one of {', '.join(acceptable_versions)}", None
            if setup_version not in acceptable_versions:
                return False, f"Version mismatch: setup.py has {setup_version}, expected one of {', '.join(acceptable_versions)}", None
        except Exception as e:
            return False, f"Error reading version files: {e}", None

        # If release branch expected, verify it exists
        if release_branch:
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--verify", release_branch],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode != 0:
                    return False, f"Release branch '{release_branch}' does not exist", None

            except Exception as e:
                return False, f"Error checking release branch: {e}", None

        return True, "Release preparation validated", release_branch

    def push_to_remote(self, ref: str, dry_run: bool = False) -> Tuple[bool, str]:
        """Push a branch or tag to remote origin.

        Args:
            ref: Branch or tag name to push
            dry_run: If True, skip push

        Returns:
            Tuple of (success, message)
        """
        if dry_run:
            return True, f"Would push '{ref}' to remote"

        try:
            result = subprocess.run(
                ["git", "push", "origin", ref],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return True, f"Pushed '{ref}' to remote"
            else:
                # Check if already pushed
                if "already up-to-date" in result.stderr.lower() or "everything up-to-date" in result.stderr.lower():
                    return True, f"'{ref}' already up-to-date on remote"
                return False, f"Failed to push: {result.stderr}"

        except Exception as e:
            return False, f"Error pushing to remote: {e}"

    def extract_changelog_for_version(self, version: Version) -> Optional[str]:
        """Extract CHANGELOG content for a specific version.

        Args:
            version: Version to extract changelog for

        Returns:
            Changelog content for the version, or None if not found

        Raises:
            OSError: If changelog file cannot be read
        """
        if not self.changelog_file.exists():
            return None

        changelog_content = self.changelog_file.read_text()
        version_str = str(version)

        # Find the version section: ## [X.Y.Z] - YYYY-MM-DD
        pattern = rf'## \[{re.escape(version_str)}\].*?\n(.*?)(?=\n## \[|$)'
        match = re.search(pattern, changelog_content, re.DOTALL)

        if match:
            content = match.group(1).strip()
            return content if content else None

        return None

    def create_github_release(
        self,
        version: Version,
        release_notes: Optional[str] = None,
        dry_run: bool = False
    ) -> Tuple[bool, str, Optional[str]]:
        """Create a GitHub release using gh CLI.

        Args:
            version: Version for the release
            release_notes: Release notes content (uses CHANGELOG if not provided)
            dry_run: If True, skip creating release

        Returns:
            Tuple of (success, message, release_url)
        """
        version_str = str(version)
        tag_name = f"v{version_str}"

        # Use provided release notes or extract from CHANGELOG
        notes = release_notes or self.extract_changelog_for_version(version) or f"Release {version_str}\n\nSee CHANGELOG.md for details."

        if dry_run:
            return True, f"Would create GitHub release for {tag_name}", None

        try:
            # Create release
            result = subprocess.run(
                [
                    "gh", "release", "create", tag_name,
                    "--title", f"Release {version_str}",
                    "--notes", notes
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Extract URL from output
                release_url = result.stdout.strip()
                return True, f"Created GitHub release {tag_name}", release_url
            else:
                # Check if release already exists
                if "already_exists" in result.stderr.lower() or "already exists" in result.stderr.lower():
                    # Get release URL
                    try:
                        view_result = subprocess.run(
                            ["gh", "release", "view", tag_name, "--json", "url", "-q", ".url"],
                            cwd=self.repo_path,
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        release_url = view_result.stdout.strip() if view_result.returncode == 0 else None
                        return True, f"GitHub release {tag_name} already exists", release_url
                    except Exception:
                        return True, f"GitHub release {tag_name} already exists", None

                return False, f"Failed to create GitHub release: {result.stderr}", None

        except FileNotFoundError:
            return False, "GitHub CLI (gh) not found. Install from https://cli.github.com/", None
        except Exception as e:
            return False, f"Error creating GitHub release: {e}", None

    def create_gitlab_release(
        self,
        version: Version,
        release_notes: Optional[str] = None,
        dry_run: bool = False
    ) -> Tuple[bool, str, Optional[str]]:
        """Create a GitLab release using glab CLI.

        Args:
            version: Version for the release
            release_notes: Release notes content (uses CHANGELOG if not provided)
            dry_run: If True, skip creating release

        Returns:
            Tuple of (success, message, release_url)
        """
        version_str = str(version)
        tag_name = f"v{version_str}"

        # Use provided release notes or extract from CHANGELOG
        notes = release_notes or self.extract_changelog_for_version(version) or f"Release {version_str}\n\nSee CHANGELOG.md for details."

        if dry_run:
            return True, f"Would create GitLab release for {tag_name}", None

        try:
            # Create release
            result = subprocess.run(
                [
                    "glab", "release", "create", tag_name,
                    "--name", f"Release {version_str}",
                    "--notes", notes
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Extract URL from output or construct it
                # glab outputs the release URL in the output
                release_url = None
                for line in result.stdout.split('\n'):
                    if 'http' in line:
                        # Try to extract URL
                        url_match = re.search(r'(https://[^\s]+)', line)
                        if url_match:
                            release_url = url_match.group(1)
                            break

                return True, f"Created GitLab release {tag_name}", release_url
            else:
                # Check if release already exists
                if "already exists" in result.stderr.lower() or "release already exists" in result.stderr.lower():
                    return True, f"GitLab release {tag_name} already exists", None

                return False, f"Failed to create GitLab release: {result.stderr}", None

        except FileNotFoundError:
            return False, "GitLab CLI (glab) not found. Install from https://gitlab.com/gitlab-org/cli", None
        except Exception as e:
            return False, f"Error creating GitLab release: {e}", None

    def merge_to_main_and_bump(
        self,
        release_branch: str,
        version: Version,
        dry_run: bool = False
    ) -> Tuple[bool, str]:
        """Merge release branch to main and bump main to next minor dev version.

        This is for minor/major releases only.

        Args:
            release_branch: Release branch to merge (e.g., "release/0.2")
            version: Version that was just released
            dry_run: If True, skip merge and bump

        Returns:
            Tuple of (success, message)
        """
        if dry_run:
            next_minor_dev = version.bump_minor().with_dev()
            return True, f"Would merge {release_branch} to main and bump to {next_minor_dev}"

        try:
            # Save current branch to return to it later
            current_branch = self.get_current_branch()

            # Checkout main
            success, msg = self.checkout_branch("main")
            if not success:
                return False, f"Failed to checkout main: {msg}"

            # Pull latest main
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Restore original branch
                self.checkout_branch(current_branch)
                return False, f"Failed to pull main: {result.stderr}"

            # Merge release branch with --no-ff
            result = subprocess.run(
                ["git", "merge", release_branch, "--no-ff", "-m",
                 f"Merge branch '{release_branch}' into main\n\nRelease v{version}\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n\nCo-Authored-By: Claude <noreply@anthropic.com>"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Check for conflicts
                conflicts_result = subprocess.run(
                    ["git", "diff", "--name-only", "--diff-filter=U"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                conflicted_files = conflicts_result.stdout.strip().split('\n') if conflicts_result.stdout.strip() else []

                # Abort merge
                subprocess.run(
                    ["git", "merge", "--abort"],
                    cwd=self.repo_path,
                    capture_output=True,
                    timeout=10,
                )

                # Restore original branch
                self.checkout_branch(current_branch)

                if conflicted_files:
                    return False, f"Merge conflicts in: {', '.join(conflicted_files)}. Resolve manually."
                return False, f"Failed to merge: {result.stderr}"

            # Bump to next minor dev version
            next_minor_dev = version.bump_minor().with_dev()
            try:
                self.update_version_files(next_minor_dev, dry_run=False)
                commit_msg = f"""chore: bump version to {next_minor_dev}

Begin development cycle for next minor release.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

                success, msg = self.commit_changes(commit_msg, dry_run=False)
                if not success:
                    # Restore original branch
                    self.checkout_branch(current_branch)
                    return False, f"Failed to commit version bump: {msg}"

            except Exception as e:
                # Restore original branch
                self.checkout_branch(current_branch)
                return False, f"Failed to bump version: {e}"

            # Push main
            result = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                # Restore original branch
                self.checkout_branch(current_branch)
                return False, f"Failed to push main: {result.stderr}"

            # Restore original branch
            self.checkout_branch(current_branch)

            return True, f"Merged {release_branch} to main and bumped to {next_minor_dev}"

        except Exception as e:
            # Try to restore original branch
            try:
                current_branch = self.get_current_branch()
                if current_branch and current_branch != "main":
                    self.checkout_branch(current_branch)
            except Exception:
                pass

            return False, f"Error during merge: {e}"
