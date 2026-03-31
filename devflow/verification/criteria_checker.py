"""Acceptance criteria checker for feature verification.

Parses acceptance criteria from issue tracker tickets and attempts to verify
them against code changes and test results.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from devflow.config.models import VerificationResult


class AcceptanceCriteriaChecker:
    """Check acceptance criteria for a session."""

    def __init__(self, project_path: str):
        """Initialize the criteria checker.

        Args:
            project_path: Path to the project directory
        """
        self.project_path = Path(project_path)

    def parse_criteria_from_ticket(self, ticket_description: str) -> List[str]:
        """Parse acceptance criteria checkboxes from ticket description.

        Supports multiple formats:
        - JIRA: - [ ] criterion or - [x] criterion
        - GitHub/GitLab: - [ ] criterion or - [x] criterion
        - Numbered: 1. criterion or 1. [x] criterion

        Args:
            ticket_description: Full ticket description text

        Returns:
            List of acceptance criteria strings (without checkboxes)
        """
        criteria = []

        # Common patterns for acceptance criteria sections
        # Supports both Markdown (##) and JIRA Wiki markup (h3.)
        section_patterns = [
            r"(?:^|\n)(?:##?|h[1-3]\.)\s*\*?\s*Acceptance Criteria\s*\*?\s*\n(.*?)(?=\n(?:##?|h[1-3]\.|\Z))",
            r"(?:^|\n)(?:##?|h[1-3]\.)\s*\*?\s*Success Criteria\s*\*?\s*\n(.*?)(?=\n(?:##?|h[1-3]\.|\Z))",
            r"(?:^|\n)(?:##?|h[1-3]\.)\s*\*?\s*Definition of Done\s*\*?\s*\n(.*?)(?=\n(?:##?|h[1-3]\.|\Z))",
            r"(?:^|\n)(?:##?|h[1-3]\.)\s*\*?\s*Requirements\s*\*?\s*\n(.*?)(?=\n(?:##?|h[1-3]\.|\Z))",
            r"<!--\s*ACCEPTANCE_CRITERIA_START\s*-->(.*?)<!--\s*ACCEPTANCE_CRITERIA_END\s*-->",
        ]

        # Try to find acceptance criteria section
        criteria_section = None
        for pattern in section_patterns:
            match = re.search(pattern, ticket_description, re.DOTALL | re.MULTILINE | re.IGNORECASE)
            if match:
                criteria_section = match.group(1)
                break

        # If no section found, search entire description
        if not criteria_section:
            criteria_section = ticket_description

        # Parse criteria from section
        # Patterns: - [ ] text, - [x] text, 1. text, * text
        checkbox_patterns = [
            r"^[\s]*[-*]\s*\[[x\s]\]\s*(.+)$",  # - [ ] or - [x]
            r"^[\s]*\d+\.\s*\[[x\s]\]\s*(.+)$",  # 1. [ ] or 1. [x]
            r"^[\s]*\d+\.\s*(.+)$",  # 1. text
            r"^[\s]*[-*]\s+(.+)$",  # - text or * text
        ]

        lines = criteria_section.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            for pattern in checkbox_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    criterion = match.group(1).strip()
                    # Skip empty or header-like lines
                    if criterion and not criterion.lower().startswith(("acceptance", "criteria", "success")):
                        criteria.append(criterion)
                    break

        return criteria

    def verify_criterion(self, criterion: str, session_name: str) -> Tuple[bool, Optional[str]]:
        """Attempt to verify a single acceptance criterion.

        This is a basic implementation that checks for related files and tests.
        More sophisticated verification would use AI/semantic analysis.

        Args:
            criterion: The criterion text to verify
            session_name: Session name for context

        Returns:
            Tuple of (verified: bool, note: Optional[str])
            - verified: True if criterion appears to be met
            - note: Verification details or None
        """
        # For MVP, we use simple heuristics:
        # 1. Check if keywords appear in recently modified files
        # 2. Check if related test files exist

        # Extract keywords from criterion
        keywords = self._extract_keywords(criterion)

        # Search for implementation evidence
        evidence = []

        # Check for related source files
        for keyword in keywords:
            # Search for files containing keyword
            matching_files = list(self.project_path.rglob(f"*{keyword}*.py"))
            matching_files.extend(list(self.project_path.rglob(f"*{keyword}*.ts")))
            matching_files.extend(list(self.project_path.rglob(f"*{keyword}*.js")))

            if matching_files:
                evidence.append(f"Found files related to '{keyword}': {len(matching_files)} files")

        # Check for test files
        test_keywords = keywords + [session_name.lower()]
        for keyword in test_keywords:
            test_files = list(self.project_path.rglob(f"*test*{keyword}*.py"))
            test_files.extend(list(self.project_path.rglob(f"*{keyword}*test*.py")))
            test_files.extend(list(self.project_path.rglob(f"*test*{keyword}*.ts")))
            test_files.extend(list(self.project_path.rglob(f"*{keyword}*test*.ts")))

            if test_files:
                evidence.append(f"Found test files for '{keyword}': {len(test_files)} tests")

        # Determine if verified
        verified = len(evidence) > 0

        # Create note
        note = " | ".join(evidence) if evidence else None

        return verified, note

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from criterion text.

        Args:
            text: Criterion text

        Returns:
            List of keywords
        """
        # Remove common words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "up", "about", "into", "through", "during",
            "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
            "do", "does", "did", "will", "would", "should", "could", "may", "might",
            "must", "can", "shall", "it", "its", "as", "when", "where", "why", "how",
            "that", "this", "these", "those", "what", "which", "who", "whom"
        }

        # Split into words
        words = re.findall(r'\b[a-z_][a-z0-9_]*\b', text.lower())

        # Filter out stop words and short words
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        # Return unique keywords (limit to top 5 for performance)
        return list(dict.fromkeys(keywords))[:5]

    def check_criteria(
        self,
        session_name: str,
        ticket_description: str,
    ) -> VerificationResult:
        """Check acceptance criteria for a session.

        Args:
            session_name: Session to verify
            ticket_description: Full ticket description with criteria

        Returns:
            VerificationResult with criteria verification status
        """
        from datetime import datetime
        import time

        start_time = time.time()

        # Parse criteria from ticket
        criteria = self.parse_criteria_from_ticket(ticket_description)

        # Verify each criterion
        verified_count = 0
        unverified_criteria = []
        notes = []

        for criterion in criteria:
            verified, note = self.verify_criterion(criterion, session_name)

            if verified:
                verified_count += 1
                if note:
                    notes.append(f"✓ {criterion}: {note}")
            else:
                unverified_criteria.append(criterion)
                notes.append(f"✗ {criterion}: No evidence found")

        # Determine overall status
        if not criteria:
            status = "skipped"  # No criteria to verify
        elif verified_count == len(criteria):
            status = "passed"
        elif verified_count > 0:
            status = "gaps_found"
        else:
            status = "failed"

        duration = time.time() - start_time

        return VerificationResult(
            session_name=session_name,
            status=status,
            duration_seconds=duration,
            total_criteria=len(criteria),
            verified_criteria=verified_count,
            unverified_criteria=unverified_criteria,
            criteria_notes=notes,
        )
