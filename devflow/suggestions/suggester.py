"""Repository suggestion engine with learning capabilities."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from devflow.utils.paths import get_cs_home

from .models import RepositorySuggestion, SuggestionHistory


class RepositorySuggester:
    """Suggests repositories based on issue tracker tickets and historical data."""

    # Common stop words to exclude from keywords
    STOP_WORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "he",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "that",
        "the",
        "to",
        "was",
        "will",
        "with",
        "should",
        "would",
        "could",
        "can",
        "need",
        "needs",
        "when",
        "where",
        "which",
        "who",
        "why",
        "how",
    }

    def __init__(self, history_file: Optional[Path] = None):
        """Initialize the repository suggester.

        Args:
            history_file: Path to suggestion history file. Defaults to DEVAIFLOW_HOME/suggestions.json
        """
        if history_file is None:
            history_file = get_cs_home() / "suggestions.json"

        self.history_file = history_file
        self.history = self._load_history()

    def _load_history(self) -> SuggestionHistory:
        """Load suggestion history from file.

        Returns:
            SuggestionHistory object (empty if file doesn't exist)
        """
        if not self.history_file.exists():
            return SuggestionHistory()

        try:
            with open(self.history_file, "r") as f:
                data = json.load(f)
            return SuggestionHistory(**data)
        except Exception:
            # If file is corrupted, start fresh
            return SuggestionHistory()

    def _save_history(self) -> None:
        """Save suggestion history to file."""
        # Ensure parent directory exists
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.history_file, "w") as f:
            json.dump(self.history.model_dump(), f, indent=2, default=str)

    def extract_keywords(
        self,
        summary: str,
        description: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> List[str]:
        """Extract meaningful keywords from issue tracker ticket content.

        Args:
            summary: issue tracker ticket summary
            description: issue tracker ticket description (optional)
            labels: issue tracker ticket labels (optional)

        Returns:
            List of extracted keywords (lowercase)
        """
        keywords: Set[str] = set()

        # Add labels directly (they're usually meaningful)
        if labels:
            for label in labels:
                # Split hyphenated or underscored labels
                parts = re.split(r"[-_]", label)
                for part in parts:
                    if part and len(part) > 2:
                        keywords.add(part.lower())

        # Extract from summary
        if summary:
            words = self._extract_words(summary)
            keywords.update(words)

        # Extract from description (if provided)
        if description:
            words = self._extract_words(description)
            keywords.update(words)

        return sorted(list(keywords))

    def _extract_words(self, text: str) -> Set[str]:
        """Extract meaningful words from text.

        Args:
            text: Input text

        Returns:
            Set of extracted keywords
        """
        keywords: Set[str] = set()

        # Split into words (alphanumeric with hyphens and underscores)
        words = re.findall(r"\b[a-zA-Z][\w-]*\b", text)

        for word in words:
            word_lower = word.lower()

            # Skip stop words
            if word_lower in self.STOP_WORDS:
                continue

            # Skip very short words (less than 3 chars)
            if len(word_lower) < 3:
                continue

            # Skip pure numbers
            if word_lower.isdigit():
                continue

            keywords.add(word_lower)

        return keywords

    def suggest_repositories(
        self,
        issue_key: Optional[str] = None,
        ticket_type: Optional[str] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        labels: Optional[List[str]] = None,
        available_repos: Optional[List[str]] = None,
        config_keywords: Optional[Dict[str, List[str]]] = None,
    ) -> List[RepositorySuggestion]:
        """Suggest repositories based on issue tracker ticket content and history.

        Args:
            issue_key: issue tracker key (optional - if provided, checks exact match first)
            ticket_type: Type of ticket (Story, Bug, Task, etc.)
            summary: issue tracker ticket summary
            description: issue tracker ticket description
            labels: issue tracker ticket labels
            available_repos: List of available repositories (optional - for filtering)
            config_keywords: Keyword mapping from config (optional - for fallback)

        Returns:
            List of RepositorySuggestion objects, sorted by confidence (highest first)
        """
        suggestions: Dict[str, RepositorySuggestion] = {}

        # 1. Check for exact issue key match in history (highest confidence)
        if issue_key:
            historical_repo = self.history.get_repository_by_issue_key(issue_key)
            if historical_repo:
                if historical_repo not in suggestions:
                    suggestions[historical_repo] = RepositorySuggestion(
                        repository=historical_repo,
                        confidence=0.0,
                        reasons=[],
                    )
                suggestions[historical_repo].confidence += 0.5
                suggestions[historical_repo].reasons.append("Previously used for this ticket")

        # 2. Extract keywords from ticket content
        keywords = self.extract_keywords(summary or "", description, labels)

        # 3. Score based on keyword matches in history
        if keywords:
            keyword_scores = self._score_by_keywords(keywords)
            for repo, score in keyword_scores.items():
                if repo not in suggestions:
                    suggestions[repo] = RepositorySuggestion(
                        repository=repo,
                        confidence=0.0,
                        reasons=[],
                    )
                suggestions[repo].confidence += score * 0.3  # Weight keyword matches
                if score > 0:
                    matching_kws = self._get_matching_keywords(repo, keywords)
                    kw_str = ", ".join(list(matching_kws)[:3])
                    suggestions[repo].reasons.append(f"Keyword matches: {kw_str}")

        # 4. Score based on ticket type in history
        if ticket_type:
            type_scores = self._score_by_ticket_type(ticket_type)
            for repo, score in type_scores.items():
                if repo not in suggestions:
                    suggestions[repo] = RepositorySuggestion(
                        repository=repo,
                        confidence=0.0,
                        reasons=[],
                    )
                suggestions[repo].confidence += score * 0.15  # Weight type matches
                if score > 0:
                    suggestions[repo].reasons.append(f"Commonly used for {ticket_type}s")

        # 5. Fallback to config keywords if provided and no historical data
        if config_keywords and not suggestions:
            config_scores = self._score_by_config_keywords(keywords, config_keywords)
            for repo, score in config_scores.items():
                if repo not in suggestions:
                    suggestions[repo] = RepositorySuggestion(
                        repository=repo,
                        confidence=0.0,
                        reasons=[],
                    )
                suggestions[repo].confidence += score * 0.2
                if score > 0:
                    suggestions[repo].reasons.append("Matches configured keywords")

        # 6. Boost recent usage (recency bias)
        recency_scores = self._score_by_recency()
        for repo, score in recency_scores.items():
            if repo in suggestions:
                suggestions[repo].confidence += score * 0.05  # Small recency boost
                if score > 0.5:  # Only mention if significant
                    suggestions[repo].reasons.append("Recently used")

        # Filter by available repos if provided
        if available_repos:
            suggestions = {
                repo: sug
                for repo, sug in suggestions.items()
                if repo in available_repos
            }

        # Normalize confidence scores to 0-1 range
        if suggestions:
            max_confidence = max(sug.confidence for sug in suggestions.values())
            if max_confidence > 0:
                for sug in suggestions.values():
                    sug.confidence = min(1.0, sug.confidence / max_confidence)

        # Sort by confidence (highest first) and return
        result = sorted(
            suggestions.values(),
            key=lambda x: x.confidence,
            reverse=True,
        )

        return result[:5]  # Return top 5 suggestions

    def _score_by_keywords(self, keywords: List[str]) -> Dict[str, float]:
        """Score repositories based on keyword frequency.

        Args:
            keywords: List of keywords to match

        Returns:
            Dictionary mapping repository to score (0.0-1.0)
        """
        repo_scores: Dict[str, int] = {}

        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in self.history.keyword_frequencies:
                repo_counts = self.history.keyword_frequencies[keyword_lower]
                for repo, count in repo_counts.items():
                    repo_scores[repo] = repo_scores.get(repo, 0) + count

        # Normalize scores
        if repo_scores:
            max_score = max(repo_scores.values())
            return {
                repo: score / max_score
                for repo, score in repo_scores.items()
            }

        return {}

    def _score_by_ticket_type(self, ticket_type: str) -> Dict[str, float]:
        """Score repositories based on ticket type frequency.

        Args:
            ticket_type: Ticket type (Story, Bug, Task, etc.)

        Returns:
            Dictionary mapping repository to score (0.0-1.0)
        """
        if ticket_type not in self.history.type_frequencies:
            return {}

        repo_counts = self.history.type_frequencies[ticket_type]

        # Normalize scores
        max_count = max(repo_counts.values())
        return {
            repo: count / max_count
            for repo, count in repo_counts.items()
        }

    def _score_by_config_keywords(
        self,
        keywords: List[str],
        config_keywords: Dict[str, List[str]],
    ) -> Dict[str, float]:
        """Score repositories based on configured keywords.

        Args:
            keywords: Extracted keywords from ticket
            config_keywords: Keyword mapping from config (repo -> keywords)

        Returns:
            Dictionary mapping repository to score (0.0-1.0)
        """
        repo_scores: Dict[str, int] = {}
        keywords_lower = {kw.lower() for kw in keywords}

        for repo, repo_keywords in config_keywords.items():
            matches = 0
            for repo_kw in repo_keywords:
                if repo_kw.lower() in keywords_lower:
                    matches += 1

            if matches > 0:
                repo_scores[repo] = matches

        # Normalize scores
        if repo_scores:
            max_score = max(repo_scores.values())
            return {
                repo: score / max_score
                for repo, score in repo_scores.items()
            }

        return {}

    def _score_by_recency(self) -> Dict[str, float]:
        """Score repositories based on recent usage.

        More recent mappings get higher scores.

        Returns:
            Dictionary mapping repository to score (0.0-1.0)
        """
        repo_scores: Dict[str, float] = {}

        # Look at last 20 mappings (most recent)
        recent_mappings = self.history.mappings[:20]

        for i, mapping in enumerate(recent_mappings):
            # Decay factor: more recent = higher score
            decay = (len(recent_mappings) - i) / len(recent_mappings)
            repo = mapping.repository
            repo_scores[repo] = max(repo_scores.get(repo, 0.0), decay)

        return repo_scores

    def _get_matching_keywords(self, repo: str, keywords: List[str]) -> Set[str]:
        """Get keywords that match for a specific repository.

        Args:
            repo: Repository name
            keywords: List of keywords

        Returns:
            Set of matching keywords
        """
        matches: Set[str] = set()

        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in self.history.keyword_frequencies:
                repo_counts = self.history.keyword_frequencies[keyword_lower]
                if repo in repo_counts and repo_counts[repo] > 0:
                    matches.add(keyword)

        return matches

    def record_selection(
        self,
        repository: str,
        issue_key: Optional[str] = None,
        ticket_type: Optional[str] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> None:
        """Record a repository selection to improve future suggestions.

        Args:
            repository: Selected repository name
            issue_key: issue tracker key
            ticket_type: Type of ticket (Story, Bug, Task, etc.)
            summary: issue tracker ticket summary
            description: issue tracker ticket description
            labels: issue tracker ticket labels
        """
        # Extract keywords
        keywords = self.extract_keywords(summary or "", description, labels)

        # Add mapping to history
        self.history.add_mapping(
            issue_key=issue_key or "unknown",
            repository=repository,
            ticket_type=ticket_type,
            keywords=keywords,
        )

        # Save to disk
        self._save_history()
