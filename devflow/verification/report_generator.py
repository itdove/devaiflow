"""Verification report generator for feature orchestration.

Generates detailed VERIFICATION.md reports from verification results.
"""

from datetime import datetime
from typing import Optional

from devflow.config.models import VerificationResult


class VerificationReportGenerator:
    """Generate VERIFICATION.md reports."""

    def generate_report(
        self,
        result: VerificationResult,
        feature_name: str,
        next_session: Optional[str] = None,
    ) -> str:
        """Create markdown report from verification results.

        Args:
            result: VerificationResult with all verification data
            feature_name: Name of the feature being verified
            next_session: Next session name (if any)

        Returns:
            Markdown-formatted report content
        """
        # Determine pass/fail symbol
        status_symbol = {
            "passed": "✓",
            "gaps_found": "⚠",
            "failed": "✗",
            "skipped": "⊘",
        }.get(result.status, "?")

        # Format timestamp
        timestamp = result.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build report sections
        sections = []

        # Header
        sections.append(f"# Verification Report: {result.session_name}\n")
        sections.append(f"**Session**: {result.session_name}")
        sections.append(f"**Feature**: {feature_name}")
        sections.append(f"**Status**: {result.status.upper()}")
        sections.append(f"**Timestamp**: {timestamp}")
        sections.append(f"**Duration**: {result.duration_seconds:.1f}s\n")

        # Acceptance Criteria Section
        sections.append("## Acceptance Criteria\n")

        if result.total_criteria == 0:
            sections.append("**No acceptance criteria found in ticket**\n")
        else:
            sections.append(f"**Progress**: {result.verified_criteria}/{result.total_criteria} criteria verified\n")

            # Verified criteria
            if result.verified_criteria > 0:
                sections.append("### ✓ Verified Criteria\n")
                verified_notes = [n for n in result.criteria_notes if n.startswith("✓")]
                for note in verified_notes:
                    sections.append(f"{note}")
                sections.append("")

            # Unverified criteria
            if result.unverified_criteria:
                sections.append("### ✗ Unverified Criteria\n")
                for criterion in result.unverified_criteria:
                    sections.append(f"- [ ] {criterion}")
                    sections.append(f"  - **ISSUE**: No evidence found")
                    # Add suggestions if available
                    suggestions = self._generate_criterion_suggestions(criterion)
                    for suggestion in suggestions:
                        sections.append(f"  - **Suggestion**: {suggestion}")
                sections.append("")

        # Test Suite Section
        if result.test_command:
            sections.append("## Test Suite\n")
            status_text = "PASSED" if result.tests_passed else "FAILED"
            sections.append(f"**Status**: {status_text}")
            sections.append(f"**Command**: {result.test_command}")

            if result.test_output:
                # Extract summary
                summary_line = self._extract_test_summary(result.test_output)
                sections.append(f"**Output**: {summary_line}\n")

                # Show failure details if tests failed
                if not result.tests_passed:
                    sections.append("### Test Failures\n")
                    sections.append("```")
                    sections.append(result.test_output)
                    sections.append("```\n")
            else:
                sections.append("")

        # Required Artifacts Section
        if result.required_artifacts:
            sections.append("## Required Artifacts\n")

            if result.missing_artifacts:
                sections.append(f"**Status**: INCOMPLETE ({len(result.missing_artifacts)} missing)\n")
                sections.append("### ✓ Files Verified\n")
                verified_artifacts = [
                    a for a in result.required_artifacts
                    if a not in result.missing_artifacts
                ]
                for artifact in verified_artifacts:
                    sections.append(f"- ✓ {artifact}")

                sections.append("\n### ✗ Missing Files\n")
                for artifact in result.missing_artifacts:
                    sections.append(f"- ✗ {artifact}")
                sections.append("")
            else:
                sections.append("**Status**: PASSED\n")
                sections.append("Files verified:")
                for artifact in result.required_artifacts:
                    sections.append(f"- ✓ {artifact}")
                sections.append("")

        # Overall Result Section
        sections.append("## Overall Result\n")

        if result.status == "passed":
            sections.append(f"**{status_symbol} VERIFICATION PASSED**\n")
            sections.append("All checks completed successfully. Feature orchestration will proceed to next session.\n")

        elif result.status == "gaps_found":
            sections.append(f"**{status_symbol} GAPS FOUND - FEATURE PAUSED**\n")
            gap_count = len(result.unverified_criteria)
            sections.append(f"{gap_count} of {result.total_criteria} acceptance criteria not verified.\n")

            if result.suggestions:
                sections.append("### To Fix:\n")
                for i, suggestion in enumerate(result.suggestions, 1):
                    sections.append(f"{i}. {suggestion}")
                sections.append("")

        elif result.status == "failed":
            sections.append(f"**{status_symbol} VERIFICATION FAILED**\n")
            sections.append("Critical failures detected:\n")

            if not result.tests_passed:
                sections.append("- Test suite failed")

            if result.total_criteria > 0 and result.verified_criteria == 0:
                sections.append("- No acceptance criteria verified")

            sections.append("")

        elif result.status == "skipped":
            sections.append(f"**{status_symbol} VERIFICATION SKIPPED**\n")
            sections.append("Verification was skipped for this session.\n")

        # Next Steps Section
        if result.status in ["gaps_found", "failed"]:
            sections.append("### Next Steps:\n")
            sections.append(f"1. Review verification failures above")
            sections.append(f"2. Fix issues and mark criteria as complete in ticket")
            sections.append(f"3. Resume feature: `daf feature resume {feature_name}`\n")
            sections.append("---")
            sections.append("Feature orchestration PAUSED until gaps resolved.")
        elif next_session:
            sections.append("---")
            sections.append(f"Next session: {next_session}")

        return "\n".join(sections)

    def _generate_criterion_suggestions(self, criterion: str) -> list[str]:
        """Generate actionable suggestions for unverified criterion.

        Args:
            criterion: Criterion text

        Returns:
            List of suggestions
        """
        suggestions = []

        # Check for common patterns
        if "test" in criterion.lower():
            suggestions.append("Add test coverage for this functionality")

        if "documentation" in criterion.lower() or "doc" in criterion.lower():
            suggestions.append("Update documentation with implementation details")

        if "endpoint" in criterion.lower() or "api" in criterion.lower():
            suggestions.append("Implement and test the API endpoint")

        # Generic suggestion
        if not suggestions:
            suggestions.append("Implement functionality described in criterion")

        return suggestions

    def _extract_test_summary(self, output: str) -> str:
        """Extract brief test summary from output.

        Args:
            output: Full test output

        Returns:
            Summary string
        """
        lines = [line.strip() for line in output.split("\n") if line.strip()]

        # Look for summary patterns
        for line in reversed(lines):
            if any(keyword in line.lower() for keyword in ["passed", "failed", "test"]):
                return line

        # Fallback to last line
        return lines[-1] if lines else "See full output above"
