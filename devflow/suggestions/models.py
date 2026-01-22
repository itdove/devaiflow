"""Data models for repository suggestion system."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class RepositorySuggestion(BaseModel):
    """A single repository suggestion with confidence score."""

    repository: str
    confidence: float  # 0.0 to 1.0
    reasons: List[str] = Field(default_factory=list)  # Why this repo was suggested


class TicketMapping(BaseModel):
    """Historical mapping of a issue tracker ticket to a repository."""

    issue_key: str
    repository: str
    ticket_type: Optional[str] = None  # Story, Bug, Task, etc.
    keywords: List[str] = Field(default_factory=list)  # Extracted from ticket
    created: datetime = Field(default_factory=datetime.now)


class SuggestionHistory(BaseModel):
    """Historical data for learning-based suggestions.

    This model stores all past ticket-to-repository mappings to build
    a learning model for future suggestions.
    """

    # Ticket mappings: ordered list with most recent first
    mappings: List[TicketMapping] = Field(default_factory=list)

    # Keyword to repository frequency map
    # Maps lowercase keywords to dict of {repo: count}
    keyword_frequencies: Dict[str, Dict[str, int]] = Field(default_factory=dict)

    # Ticket type to repository frequency map
    # Maps ticket type to dict of {repo: count}
    type_frequencies: Dict[str, Dict[str, int]] = Field(default_factory=dict)

    # Last updated timestamp
    last_updated: datetime = Field(default_factory=datetime.now)

    def add_mapping(
        self,
        issue_key: str,
        repository: str,
        ticket_type: Optional[str] = None,
        keywords: Optional[List[str]] = None,
    ) -> None:
        """Add a new ticket-to-repository mapping and update frequencies.

        Args:
            issue_key: issue tracker key
            repository: Repository name
            ticket_type: Type of ticket (Story, Bug, Task, etc.)
            keywords: Extracted keywords from ticket
        """
        keywords = keywords or []

        # Create new mapping
        mapping = TicketMapping(
            issue_key=issue_key,
            repository=repository,
            ticket_type=ticket_type,
            keywords=keywords,
        )

        # Add to front of list (most recent first)
        self.mappings.insert(0, mapping)

        # Update keyword frequencies
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower not in self.keyword_frequencies:
                self.keyword_frequencies[keyword_lower] = {}

            repo_counts = self.keyword_frequencies[keyword_lower]
            repo_counts[repository] = repo_counts.get(repository, 0) + 1

        # Update type frequencies
        if ticket_type:
            if ticket_type not in self.type_frequencies:
                self.type_frequencies[ticket_type] = {}

            repo_counts = self.type_frequencies[ticket_type]
            repo_counts[repository] = repo_counts.get(repository, 0) + 1

        # Update timestamp
        self.last_updated = datetime.now()

        # Keep only last 1000 mappings to avoid unbounded growth
        if len(self.mappings) > 1000:
            # Remove oldest mapping
            old_mapping = self.mappings.pop()

            # Decrement its keyword frequencies
            for kw in old_mapping.keywords:
                kw_lower = kw.lower()
                if kw_lower in self.keyword_frequencies:
                    repo_counts = self.keyword_frequencies[kw_lower]
                    if old_mapping.repository in repo_counts:
                        repo_counts[old_mapping.repository] -= 1
                        if repo_counts[old_mapping.repository] <= 0:
                            del repo_counts[old_mapping.repository]
                        if not repo_counts:
                            del self.keyword_frequencies[kw_lower]

            # Decrement its type frequencies
            if old_mapping.ticket_type and old_mapping.ticket_type in self.type_frequencies:
                repo_counts = self.type_frequencies[old_mapping.ticket_type]
                if old_mapping.repository in repo_counts:
                    repo_counts[old_mapping.repository] -= 1
                    if repo_counts[old_mapping.repository] <= 0:
                        del repo_counts[old_mapping.repository]
                    if not repo_counts:
                        del self.type_frequencies[old_mapping.ticket_type]

    def get_repository_by_issue_key(self, issue_key: str) -> Optional[str]:
        """Get the repository for a specific issue key if it exists in history.

        Args:
            issue_key: issue tracker key

        Returns:
            Repository name if found, None otherwise
        """
        for mapping in self.mappings:
            if mapping.issue_key == issue_key:
                return mapping.repository
        return None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
