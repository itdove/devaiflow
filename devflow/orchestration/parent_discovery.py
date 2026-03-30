"""Parent ticket discovery for feature orchestration.

Auto-discovers child tickets from parent epics/stories and orders them by dependencies.
For GitHub/GitLab, parses issue references from description and comments.
"""

import re
from typing import Dict, List, Optional, Tuple

from rich.console import Console

console = Console()


class ParentTicketDiscovery:
    """Discover and order child tickets from a parent."""

    def __init__(self, issue_tracker_client):
        """Initialize discovery with issue tracker client.

        Args:
            issue_tracker_client: IssueTrackerClient instance (JIRA, GitHub, GitLab)
        """
        self.client = issue_tracker_client

    def discover_children(
        self,
        parent_key: str,
        sync_filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """Discover child tickets from parent.

        For JIRA: Uses get_children() to fetch epic children or sub-tasks
        For GitHub/GitLab: Parses issue references from description and comments

        Args:
            parent_key: Parent issue key (e.g., "PROJ-100" for epic, "owner/repo#123" for GitHub)
            sync_filters: Optional sync filters (assignee, status, required_fields)

        Returns:
            List of child ticket dictionaries (ordered by appearance in description/comments)
        """
        # Fetch parent ticket
        parent = self.client.get_ticket(parent_key)
        if not parent:
            raise ValueError(f"Parent ticket '{parent_key}' not found")

        # Detect backend type
        backend_type = self._detect_backend_type(parent_key)

        if backend_type == "jira":
            children = self._discover_jira_children(parent_key, parent)
        elif backend_type in ("github", "gitlab"):
            children = self._discover_github_gitlab_children(parent_key, parent)
        else:
            console.print(f"[yellow]Unknown backend type for {parent_key}[/yellow]")
            return []

        if not children:
            console.print(f"[yellow]No children found for {parent_key}[/yellow]")
            return []

        console.print(f"[dim]Found {len(children)} children for {parent_key}[/dim]")

        # Apply sync filters if provided
        if sync_filters:
            children = self._filter_children(children, sync_filters)
            console.print(f"[dim]After filtering: {len(children)} children[/dim]")

        return children

    def _detect_backend_type(self, issue_key: str) -> str:
        """Detect backend type from issue key format.

        Args:
            issue_key: Issue key

        Returns:
            "jira", "github", "gitlab", or "unknown"
        """
        # GitHub/GitLab: owner/repo#123 or #123
        if "#" in issue_key:
            return "github"  # Could be GitLab too, treating same

        # JIRA: PROJ-123
        if re.match(r"^[A-Z]+-\d+$", issue_key):
            return "jira"

        return "unknown"

    def _discover_jira_children(self, parent_key: str, parent: Dict) -> List[Dict]:
        """Discover JIRA children using get_child_issues() method.

        Args:
            parent_key: Parent JIRA key
            parent: Parent ticket data

        Returns:
            List of child ticket dictionaries (topologically sorted by dependencies)
        """
        try:
            # Get field_mappings from config if available
            field_mappings = None
            try:
                from devflow.config.loader import ConfigLoader
                config_loader = ConfigLoader()
                config = config_loader.load_config()
                if config and hasattr(config, 'jira') and config.jira:
                    field_mappings = config.jira.field_mappings
            except Exception:
                # If config loading fails, proceed without field_mappings
                pass

            # Use JIRA-specific method
            if hasattr(self.client, 'get_child_issues'):
                children = self.client.get_child_issues(
                    parent_key,
                    field_mappings=field_mappings,
                    include_links=True  # Include blocking relationships
                )
            else:
                # Fallback: try generic get_children
                children = self.client.get_children(parent_key)
        except AttributeError:
            console.print(
                f"[yellow]Warning:[/yellow] JIRA client doesn't support child discovery yet.\n"
                f"[dim]Please use --sessions flag to specify children manually[/dim]"
            )
            return []

        # Topologically sort children by blocking relationships
        if children:
            children = self._topological_sort(children)

        return children

    def _discover_github_gitlab_children(self, parent_key: str, parent: Dict) -> List[Dict]:
        """Discover GitHub/GitLab children by parsing issue references.

        Parses description and comments for issue references (#123, owner/repo#456).
        Orders by appearance: description first, then comments chronologically.

        Args:
            parent_key: Parent issue key
            parent: Parent ticket data

        Returns:
            List of child ticket dictionaries (ordered by mention)
        """
        # Parse issue references from description
        description = parent.get("description", "")
        description_refs = self._parse_issue_references(description, parent_key)

        # Parse issue references from comments
        comments_refs = []
        if hasattr(self.client, 'get_issue_comments'):
            try:
                comments = self.client.get_issue_comments(parent_key)
                # Sort by created timestamp
                comments.sort(key=lambda c: c.get("created_at", ""))

                for comment in comments:
                    body = comment.get("body", "")
                    refs = self._parse_issue_references(body, parent_key)
                    comments_refs.extend(refs)
            except:
                pass  # Comments not available

        # Combine: description first, then comments (preserving order)
        all_refs = description_refs + comments_refs

        # Remove duplicates while preserving order
        seen = set()
        unique_refs = []
        for ref in all_refs:
            if ref not in seen:
                seen.add(ref)
                unique_refs.append(ref)

        # Exclude parent itself
        unique_refs = [ref for ref in unique_refs if ref != parent_key]

        if not unique_refs:
            console.print(f"[dim]No issue references found in {parent_key}[/dim]")
            return []

        console.print(f"[dim]Parsed {len(unique_refs)} issue references from {parent_key}[/dim]")

        # Fetch each referenced issue
        children = []
        for ref in unique_refs:
            try:
                child = self.client.get_ticket(ref)
                if child:
                    children.append(child)
                else:
                    console.print(f"[dim]Skipping {ref}: not found[/dim]")
            except Exception as e:
                console.print(f"[dim]Skipping {ref}: {e}[/dim]")

        return children

    def _parse_issue_references(self, text: str, current_repo_key: str) -> List[str]:
        """Parse issue references from text.

        Supports:
        - #123 (same repo)
        - owner/repo#123 (cross-repo)
        - GH-123 (GitHub style)
        - Full URLs

        Args:
            text: Text to parse (description or comment)
            current_repo_key: Current repository key (for resolving #123 references)

        Returns:
            List of issue keys in order of appearance
        """
        if not text:
            return []

        refs = []

        # Pattern 1: owner/repo#123
        cross_repo_pattern = r'([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)#(\d+)'
        for match in re.finditer(cross_repo_pattern, text):
            repo = match.group(1)
            number = match.group(2)
            refs.append(f"{repo}#{number}")

        # Pattern 2: #123 (same repo)
        same_repo_pattern = r'(?:^|[^/])#(\d+)(?:\s|$|,|\.)'
        for match in re.finditer(same_repo_pattern, text):
            number = match.group(1)

            # Extract repo from current_repo_key (format: owner/repo#parent_num)
            if "#" in current_repo_key:
                repo_part = current_repo_key.split("#")[0]
                refs.append(f"{repo_part}#{number}")
            else:
                refs.append(f"#{number}")

        # Pattern 3: GH-123, GL-123
        prefix_pattern = r'\b(GH|GL)-(\d+)\b'
        for match in re.finditer(prefix_pattern, text, re.IGNORECASE):
            number = match.group(2)
            # Convert to #number format
            if "#" in current_repo_key:
                repo_part = current_repo_key.split("#")[0]
                refs.append(f"{repo_part}#{number}")
            else:
                refs.append(f"#{number}")

        return refs

    def _topological_sort(self, children: List[Dict]) -> List[Dict]:
        """Sort children by dependency order using topological sort.

        Uses Kahn's algorithm to order children based on "blocks"/"blocked_by" relationships.
        Issues with no dependencies come first, followed by issues that depend on them.

        Args:
            children: List of child dictionaries with 'key', 'blocks', and 'blocked_by' fields

        Returns:
            List of children sorted in execution order (dependencies first)
        """
        # Build dependency graph
        # in_degree: count of unresolved dependencies (how many issues block this one)
        # graph: maps issue_key -> list of issues it blocks
        in_degree = {}
        graph = {}
        key_to_child = {}

        # Initialize structures
        for child in children:
            child_key = child.get('key')
            key_to_child[child_key] = child
            in_degree[child_key] = 0
            graph[child_key] = []

        # Build graph from blocking relationships
        for child in children:
            child_key = child.get('key')
            blocked_by = child.get('blocked_by', [])

            # Only count blockers that are in our children list (ignore external dependencies)
            internal_blockers = [b for b in blocked_by if b in key_to_child]

            in_degree[child_key] = len(internal_blockers)

            # Add edges: blocker -> this issue
            for blocker in internal_blockers:
                graph[blocker].append(child_key)

        # Kahn's algorithm: start with issues that have no dependencies
        queue = [key for key in in_degree if in_degree[key] == 0]
        sorted_keys = []

        while queue:
            # Sort queue to ensure deterministic ordering when multiple issues have no dependencies
            queue.sort()

            current = queue.pop(0)
            sorted_keys.append(current)

            # Decrease in-degree for all issues blocked by current
            for blocked_issue in graph[current]:
                in_degree[blocked_issue] -= 1
                if in_degree[blocked_issue] == 0:
                    queue.append(blocked_issue)

        # Check for cycles
        if len(sorted_keys) != len(children):
            # Cycle detected - fall back to original order
            console.print("[yellow]Warning:[/yellow] Circular dependency detected in issue links, using key order")
            return children

        # Return children in sorted order
        return [key_to_child[key] for key in sorted_keys]

    def _filter_children(
        self,
        children: List[Dict],
        sync_filters: Dict,
    ) -> List[Dict]:
        """Annotate children with sync criteria validation.

        Checks each child against sync filters and adds 'meets_criteria' field
        and 'exclusion_reason' if criteria are not met.

        Args:
            children: List of child ticket dictionaries
            sync_filters: Sync filters configuration

        Returns:
            List of all children with 'meets_criteria' and 'exclusion_reason' annotations
        """
        for child in children:
            # Assume meets criteria until proven otherwise
            child['meets_criteria'] = True
            child['exclusion_reason'] = None

            # Check status
            status = child.get("status", "")
            if sync_filters.get("status"):
                if status not in sync_filters["status"]:
                    child['meets_criteria'] = False
                    child['exclusion_reason'] = f"status '{status}' not in {sync_filters['status']}"
                    continue

            # Check assignee (must match exactly)
            assignee = child.get("assignee")
            if sync_filters.get("assignee"):
                expected_assignee = sync_filters["assignee"]
                if assignee != expected_assignee:
                    child['meets_criteria'] = False
                    child['exclusion_reason'] = f"assignee '{assignee or 'unassigned'}' != '{expected_assignee}'"
                    continue

            # Check required fields (sprint, points, etc.)
            issue_type = child.get("type")
            if sync_filters.get("required_fields"):
                # Handle both dict (JIRA) and list (GitHub/GitLab) formats
                required_fields_config = sync_filters["required_fields"]

                try:
                    # Check type by name to avoid isinstance issues
                    type_name = type(required_fields_config).__name__
                    if type_name == 'dict':
                        # JIRA format: {Story: [sprint, points], Task: [assignee]}
                        required_fields = required_fields_config.get(issue_type, []) if issue_type else []
                    elif type_name in ('list', 'tuple'):
                        # GitHub/GitLab format: [assignee]
                        required_fields = required_fields_config
                    else:
                        required_fields = []
                except (TypeError, AttributeError):
                    # Handle unexpected type
                    required_fields = []

                for field in required_fields:
                    if not child.get(field):
                        child['meets_criteria'] = False
                        child['exclusion_reason'] = f"missing required field '{field}'"
                        break

        return children

    def order_by_dependencies(
        self,
        children: List[Dict],
    ) -> Tuple[List[Dict], List[str]]:
        """Order children by dependency relationships.

        Uses "blocks" and "is blocked by" links to determine execution order.

        Args:
            children: List of child ticket dictionaries

        Returns:
            Tuple of (ordered_children, warnings)
            - ordered_children: Children sorted by dependencies
            - warnings: List of warning messages (cycles, ambiguities)
        """
        # Build dependency graph
        # Format: {ticket_key: {blocks: [keys], blocked_by: [keys]}}
        graph = {}
        key_to_ticket = {}

        for child in children:
            key = child["key"]
            graph[key] = {
                "blocks": child.get("blocks", []),
                "blocked_by": child.get("blocked_by", []),
            }
            key_to_ticket[key] = child

        # Topological sort (Kahn's algorithm)
        # Calculate in-degree (number of dependencies)
        in_degree = {key: len(graph[key]["blocked_by"]) for key in graph}

        # Queue of tickets with no dependencies
        queue = [key for key, degree in in_degree.items() if degree == 0]
        ordered = []
        warnings = []

        while queue:
            # Sort queue to ensure deterministic ordering
            queue.sort()

            # Process ticket with no dependencies
            current = queue.pop(0)
            ordered.append(key_to_ticket[current])

            # Remove this ticket from dependencies of others
            for key in graph:
                if current in graph[key]["blocked_by"]:
                    graph[key]["blocked_by"].remove(current)
                    in_degree[key] -= 1

                    if in_degree[key] == 0:
                        queue.append(key)

        # Check for cycles (tickets that couldn't be ordered)
        if len(ordered) < len(children):
            unordered_keys = [k for k in graph.keys() if k not in [t["key"] for t in ordered]]
            warnings.append(
                f"Dependency cycle detected involving: {', '.join(unordered_keys)}. "
                f"These tickets will be added at the end."
            )

            # Add remaining tickets at the end
            for child in children:
                if child["key"] in unordered_keys:
                    ordered.append(child)

        return ordered, warnings

    def display_children(
        self,
        children: List[Dict],
        parent_key: str,
    ) -> None:
        """Display children with sync criteria status.

        Args:
            children: List of child ticket dictionaries (with meets_criteria annotations)
            parent_key: Parent issue key
        """
        from rich.table import Table

        # Count how many will be created
        valid_count = sum(1 for c in children if c.get('meets_criteria', True))
        excluded_count = len(children) - valid_count

        console.print(f"\n[bold]Found {len(children)} children for {parent_key}:[/bold]")
        if excluded_count > 0:
            console.print(f"[yellow]{excluded_count} will be excluded due to sync criteria[/yellow]\n")
        else:
            console.print()

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Title", style="white")
        table.add_column("Status", style="magenta")
        table.add_column("Type", style="blue")
        table.add_column("Will Create", style="green")

        for i, child in enumerate(children, 1):
            key = child.get("key", "")
            title = child.get("summary", "")
            status = child.get("status", "")
            issue_type = child.get("type", "")
            meets_criteria = child.get('meets_criteria', True)

            # Truncate long titles
            if len(title) > 50:
                title = title[:47] + "..."

            # Status indicator
            will_create = "[green]✓[/green]" if meets_criteria else "[red]✗[/red]"

            table.add_row(str(i), key, title, status, issue_type, will_create)

        console.print(table)

        # Show exclusion reasons
        excluded = [c for c in children if not c.get('meets_criteria', True)]
        if excluded:
            console.print("\n[yellow]Excluded (will not create sessions):[/yellow]")
            for child in excluded:
                reason = child.get('exclusion_reason', 'unknown reason')
                console.print(f"  • {child['key']}: {reason}")

        console.print()
