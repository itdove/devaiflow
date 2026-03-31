"""Feature orchestration manager for DevAIFlow.

Manages multi-session workflows with integrated verification between sessions.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from devflow.config.loader import ConfigLoader
from devflow.config.models import FeatureOrchestration, VerificationResult
from devflow.orchestration.storage import FeatureStorage
from devflow.session.manager import SessionManager
from devflow.verification import (
    AcceptanceCriteriaChecker,
    ArtifactValidator,
    TestRunner,
    VerificationReportGenerator,
)


class FeatureManager:
    """Manage feature orchestrations."""

    def __init__(
        self,
        config_loader: Optional[ConfigLoader] = None,
        session_manager: Optional[SessionManager] = None,
        storage: Optional[FeatureStorage] = None,
    ):
        """Initialize feature manager.

        Args:
            config_loader: ConfigLoader instance
            session_manager: SessionManager instance
            storage: FeatureStorage instance
        """
        self.config_loader = config_loader or ConfigLoader()
        self.session_manager = session_manager or SessionManager(config_loader=self.config_loader)
        self.storage = storage or FeatureStorage()

    def create_feature(
        self,
        name: str,
        sessions: List[str],
        branch: str,
        base_branch: str = "main",
        verification_mode: str = "auto",
        workspace_name: Optional[str] = None,
        parent_issue_key: Optional[str] = None,
        external_sessions: Optional[List[Dict]] = None,
        metadata: Optional[Dict] = None,
    ) -> FeatureOrchestration:
        """Create a new feature orchestration.

        Args:
            name: Feature name (unique identifier)
            sessions: List of session names in execution order
            branch: Shared git branch for all sessions
            base_branch: Base branch (default: "main")
            verification_mode: "auto", "manual", or "skip"
            workspace_name: Workspace for all sessions
            parent_issue_key: Parent issue key for sync operations (optional)
            external_sessions: List of sessions not assigned to current user (optional)
            metadata: Additional metadata (blocking_relationships, etc.) (optional)

        Returns:
            Created FeatureOrchestration object

        Raises:
            ValueError: If feature already exists or sessions don't exist
        """
        # Load index
        index = self.storage.load_index()

        # Check if feature already exists
        if index.get_feature(name):
            raise ValueError(f"Feature '{name}' already exists")

        # Validate all sessions exist
        for session_name in sessions:
            session = self.session_manager.get_session(session_name)
            if not session:
                raise ValueError(f"Session '{session_name}' not found")

        # Auto-detect issue tracker from sessions
        issue_tracker = None
        linked_issues = []
        for session_name in sessions:
            session = self.session_manager.get_session(session_name)
            if session and session.issue_key:
                linked_issues.append(session.issue_key)
                if not issue_tracker and session.issue_tracker:
                    issue_tracker = session.issue_tracker

        # Create feature
        feature = FeatureOrchestration(
            name=name,
            branch=branch,
            base_branch=base_branch,
            sessions=sessions,
            verification_mode=verification_mode,
            workspace_name=workspace_name,
            issue_tracker=issue_tracker,
            linked_issues=linked_issues,
            session_statuses={s: "pending" for s in sessions},
            parent_issue_key=parent_issue_key,
            external_sessions=external_sessions or [],
            metadata=metadata or {},
        )

        # Save to storage
        index.add_feature(feature)
        self.storage.save_index(index)
        self.storage.save_feature_metadata(feature)

        # Generate initial STATE.md
        self._generate_state_file(feature)

        return feature

    def get_feature(self, name: str) -> Optional[FeatureOrchestration]:
        """Get a feature by name.

        Args:
            name: Feature name

        Returns:
            FeatureOrchestration or None if not found
        """
        index = self.storage.load_index()
        return index.get_feature(name)

    def find_feature_by_session(self, session_name: str) -> Optional[FeatureOrchestration]:
        """Find a feature that contains the specified session.

        Args:
            session_name: Session name to search for

        Returns:
            FeatureOrchestration containing the session, or None if not found
        """
        index = self.storage.load_index()

        # Search through all features
        for feature in index.features.values():
            if session_name in feature.sessions:
                return feature

        return None

    def get_session_context(self, session_name: str) -> Optional[Dict]:
        """Get feature context for a session.

        Args:
            session_name: Session name

        Returns:
            Dict with feature context or None if session is not part of a feature
            {
                'feature_name': str,
                'feature_status': str,
                'current_index': int,  # 0-based index of session in feature
                'total_sessions': int,
                'is_current': bool,  # True if this is the active session in the feature
                'is_complete': bool,  # True if session already completed in feature
                'next_session': Optional[str],
                'previous_session': Optional[str],
            }
        """
        feature = self.find_feature_by_session(session_name)
        if not feature:
            return None

        try:
            session_index = feature.sessions.index(session_name)
        except ValueError:
            return None

        # Determine if this is the current active session
        current_session = feature.get_current_session()
        is_current = (current_session == session_name)

        # Determine if session is complete
        complete_sessions = feature.get_complete_sessions()
        is_complete = (session_name in complete_sessions)

        # Get next/previous sessions
        next_session = None
        if session_index < len(feature.sessions) - 1:
            next_session = feature.sessions[session_index + 1]

        previous_session = None
        if session_index > 0:
            previous_session = feature.sessions[session_index - 1]

        return {
            'feature': feature,  # Add the feature object itself
            'feature_name': feature.name,
            'feature_status': feature.status,
            'current_index': session_index,
            'total_sessions': len(feature.sessions),
            'is_current': is_current,
            'is_complete': is_complete,
            'next_session': next_session,
            'previous_session': previous_session,
        }

    def update_feature(self, feature: FeatureOrchestration) -> None:
        """Update a feature.

        Args:
            feature: FeatureOrchestration object to update
        """
        feature.last_active = datetime.now()

        # Update index
        index = self.storage.load_index()
        index.features[feature.name] = feature
        self.storage.save_index(index)

        # Save metadata
        self.storage.save_feature_metadata(feature)

    def list_features(
        self,
        status: Optional[str] = None,
        workspace_name: Optional[str] = None,
    ) -> List[FeatureOrchestration]:
        """List features with optional filters.

        Args:
            status: Filter by feature status
            workspace_name: Filter by workspace

        Returns:
            List of FeatureOrchestration objects
        """
        index = self.storage.load_index()
        return index.list_features(status=status, workspace_name=workspace_name)

    def verify_session(
        self,
        feature: FeatureOrchestration,
        session_name: str,
    ) -> VerificationResult:
        """Verify a completed session.

        Args:
            feature: Feature orchestration
            session_name: Session to verify

        Returns:
            VerificationResult with verification status
        """
        # Get session
        session = self.session_manager.get_session(session_name)
        if not session:
            raise ValueError(f"Session '{session_name}' not found")

        # Get project path from session
        active_conv = session.active_conversation
        if not active_conv or not active_conv.project_path:
            raise ValueError(f"Session '{session_name}' has no project path")

        project_path = active_conv.project_path

        # Skip verification if mode is "skip"
        if feature.verification_mode == "skip":
            result = VerificationResult(
                session_name=session_name,
                status="skipped",
            )
            return result

        # Manual verification mode
        if feature.verification_mode == "manual":
            # This would be handled in the CLI with user prompts
            # For now, return a placeholder
            result = VerificationResult(
                session_name=session_name,
                status="passed",  # Assume passed for manual verification
                total_criteria=0,
                verified_criteria=0,
            )
            return result

        # Auto-AI mode: Use configured AI agent to verify acceptance criteria
        if feature.verification_mode == "auto-ai":
            result = self._run_ai_verification(
                feature=feature,
                session_name=session_name,
                project_path=project_path,
            )
            return result

        # Auto verification mode (evidence-based)
        result = self._run_auto_verification(
            feature=feature,
            session_name=session_name,
            project_path=project_path,
        )

        # Store verification result
        feature.verification_results[session_name] = result

        # Generate verification report
        report_generator = VerificationReportGenerator()
        next_session = self._get_next_session(feature, session_name)
        report_content = report_generator.generate_report(
            result=result,
            feature_name=feature.name,
            next_session=next_session,
        )

        # Save report
        report_path = self.storage.save_verification_report(
            feature_name=feature.name,
            session_name=session_name,
            report_content=report_content,
        )

        result.report_path = str(report_path)

        return result

    def _get_ticket_description(self, session) -> str:
        """Get ticket description with proper formatting.

        Re-fetches from JIRA to get original formatting (not ADF-converted).
        Falls back to cached description if JIRA fetch fails.

        Args:
            session: Session object

        Returns:
            Ticket description with formatting preserved
        """
        # Try to fetch fresh description from JIRA with original formatting
        if session and session.issue_key and session.issue_tracker == "jira":
            try:
                from devflow.jira.client import JiraClient

                client = JiraClient()
                # Use raw API to get description with JIRA Wiki markup preserved
                response = client._api_request("GET", f"/rest/api/2/issue/{session.issue_key}?fields=description")
                if response.status_code == 200:
                    data = response.json()
                    description = data.get('fields', {}).get('description')
                    if description:
                        return description
            except Exception:
                # Fall back to cached description if JIRA fetch fails
                pass

        # Fallback: use cached description from issue_metadata
        return session.issue_metadata.get("description", "") if session else ""

    def _run_auto_verification(
        self,
        feature: FeatureOrchestration,
        session_name: str,
        project_path: str,
    ) -> VerificationResult:
        """Run automatic verification for a session.

        Args:
            feature: Feature orchestration
            session_name: Session name
            project_path: Project directory path

        Returns:
            VerificationResult
        """
        import time

        start_time = time.time()

        # Get ticket description for acceptance criteria (re-fetch from JIRA for proper formatting)
        session = self.session_manager.get_session(session_name)
        ticket_description = self._get_ticket_description(session)

        # Initialize verification components
        criteria_checker = AcceptanceCriteriaChecker(project_path)
        test_runner = TestRunner(project_path)
        artifact_validator = ArtifactValidator(project_path)

        # Check acceptance criteria
        criteria_result = criteria_checker.check_criteria(
            session_name=session_name,
            ticket_description=ticket_description,
        )

        # Run tests
        test_command = test_runner.detect_test_command()
        tests_passed = False
        test_output = None

        if test_command:
            tests_passed, test_output = test_runner.run_tests(test_command=test_command)

        # Validate artifacts
        criteria = criteria_checker.parse_criteria_from_ticket(ticket_description)
        required_artifacts = artifact_validator.extract_artifacts_from_criteria(criteria)
        validated_artifacts, missing_artifacts = artifact_validator.validate_artifacts(required_artifacts)

        # Combine results
        duration = time.time() - start_time

        # Determine overall status
        if criteria_result.status == "passed" and (not test_command or tests_passed):
            overall_status = "passed"
        elif criteria_result.status == "failed" or (test_command and not tests_passed):
            overall_status = "failed"
        else:
            overall_status = "gaps_found"

        # Generate suggestions
        suggestions = []
        if criteria_result.unverified_criteria:
            suggestions.append(f"Verify {len(criteria_result.unverified_criteria)} unverified acceptance criteria")
        if test_command and not tests_passed:
            suggestions.append("Fix failing tests")
        if missing_artifacts:
            suggestions.append(f"Create {len(missing_artifacts)} missing artifact files")

        result = VerificationResult(
            session_name=session_name,
            status=overall_status,
            duration_seconds=duration,
            total_criteria=criteria_result.total_criteria,
            verified_criteria=criteria_result.verified_criteria,
            unverified_criteria=criteria_result.unverified_criteria,
            criteria_notes=criteria_result.criteria_notes,
            test_command=test_command,
            tests_passed=tests_passed,
            test_output=test_output,
            required_artifacts=required_artifacts,
            missing_artifacts=missing_artifacts,
            suggestions=suggestions,
        )

        return result

    def _run_ai_verification(
        self,
        feature: FeatureOrchestration,
        session_name: str,
        project_path: str,
    ) -> VerificationResult:
        """Run AI-powered verification using configured agent backend.

        Spawns an AI agent (Claude, Copilot, etc.) to verify acceptance criteria.
        The agent reads files, checks conditions, and reports results.

        Args:
            feature: Feature orchestration
            session_name: Session name
            project_path: Project directory path

        Returns:
            VerificationResult
        """
        import time
        import uuid
        from devflow.agent.factory import create_agent_client

        start_time = time.time()

        # Get ticket description for acceptance criteria (re-fetch from JIRA for proper formatting)
        session = self.session_manager.get_session(session_name)
        ticket_description = self._get_ticket_description(session)

        # Parse acceptance criteria
        criteria_checker = AcceptanceCriteriaChecker(project_path)
        criteria = criteria_checker.parse_criteria_from_ticket(ticket_description)

        if not criteria:
            # No criteria to verify
            return VerificationResult(
                session_name=session_name,
                status="passed",
                duration_seconds=time.time() - start_time,
                total_criteria=0,
                verified_criteria=0,
            )

        # Build verification prompt for AI agent
        prompt_parts = [
            f"# Verification Task for {session.issue_key if session else session_name}",
            "",
            "Please verify the following acceptance criteria by executing the necessary checks:",
            ""
        ]

        for i, criterion in enumerate(criteria, 1):
            prompt_parts.append(f"{i}. [ ] {criterion}")

        prompt_parts.extend([
            "",
            "Instructions:",
            "- For each criterion, perform the actual verification (read files, check values, run commands, etc.)",
            "- Mark each criterion as [x] when verified",
            "- If a criterion cannot be verified, explain why",
            "- Provide a summary of verification results at the end",
            "",
            f"Working directory: {project_path}",
        ])

        verification_prompt = "\n".join(prompt_parts)

        # Get configured agent backend
        config_loader = ConfigLoader()
        config = config_loader.load_config()
        agent_backend = "claude"  # Default
        if config and hasattr(config, 'agent_backend'):
            agent_backend = config.agent_backend

        # Create agent client
        agent = create_agent_client(agent_backend)

        # Generate unique session ID for verification
        verification_session_id = str(uuid.uuid4())

        # Launch AI agent with verification prompt
        try:
            process = agent.launch_with_prompt(
                project_path=project_path,
                initial_prompt=verification_prompt,
                session_id=verification_session_id,
                config=config,
            )

            # Wait for agent to complete
            # Note: This blocks until user exits the agent
            process.wait()

            # Parse agent's session to check verification results
            # Look for checked boxes [x] in the conversation
            session_file = agent.get_session_file_path(verification_session_id, project_path)

            if session_file.exists():
                # Count how many criteria were checked
                content = session_file.read_text()
                raw_count = content.count("[x]") + content.count("[X]")

                # Cap verified count at total criteria (AI might write [x] multiple times)
                verified_count = min(raw_count, len(criteria))

                # Determine status
                if verified_count >= len(criteria):
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
                    unverified_criteria=[c for i, c in enumerate(criteria) if i >= verified_count],
                )

        except Exception as e:
            # Agent launch failed
            duration = time.time() - start_time
            return VerificationResult(
                session_name=session_name,
                status="failed",
                duration_seconds=duration,
                total_criteria=len(criteria),
                verified_criteria=0,
                unverified_criteria=criteria,
                suggestions=[f"AI verification failed: {str(e)}"],
            )

        # Fallback if session file not found
        duration = time.time() - start_time
        return VerificationResult(
            session_name=session_name,
            status="failed",
            duration_seconds=duration,
            total_criteria=len(criteria),
            verified_criteria=0,
            unverified_criteria=criteria,
        )

    def _get_next_session(self, feature: FeatureOrchestration, current_session: str) -> Optional[str]:
        """Get the next session name after current_session.

        Args:
            feature: Feature orchestration
            current_session: Current session name

        Returns:
            Next session name or None if no more sessions
        """
        try:
            current_index = feature.sessions.index(current_session)
            if current_index < len(feature.sessions) - 1:
                return feature.sessions[current_index + 1]
        except ValueError:
            pass
        return None

    def _generate_state_file(self, feature: FeatureOrchestration) -> None:
        """Generate STATE.md file for a feature.

        Args:
            feature: Feature orchestration
        """
        sections = []

        sections.append(f"# Feature: {feature.name}\n")
        sections.append(f"**Status**: {feature.status}")
        sections.append(f"**Branch**: {feature.branch}")
        completed_count = len(feature.get_complete_sessions())
        sections.append(f"**Progress**: {completed_count}/{len(feature.sessions)} sessions completed")
        sections.append(f"**Last Updated**: {feature.last_active.strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Completed sessions
        complete_sessions = feature.get_complete_sessions()
        if complete_sessions:
            sections.append("## Completed Sessions\n")
            for session_name in complete_sessions:
                sections.append(f"### ✓ {session_name}")
                sections.append(f"- **Status**: complete")

                # Verification results
                if session_name in feature.verification_results:
                    result = feature.verification_results[session_name]
                    sections.append(f"- **Acceptance Criteria**: {result.verified_criteria}/{result.total_criteria} verified")
                    sections.append(f"- **Verification**: {result.status.upper()}")

                sections.append("")

        # Current session
        current_session = feature.get_current_session()
        if current_session:
            status = feature.session_statuses.get(current_session, "pending")
            sections.append("## Current Session\n")
            sections.append(f"### ⧗ {current_session}")
            sections.append(f"- **Status**: {status}")

            if status == "paused":
                sections.append(f"- **Reason**: Verification failed")
                if current_session in feature.verification_results:
                    result = feature.verification_results[current_session]
                    if result.unverified_criteria:
                        sections.append(f"- **Missing Criteria**:")
                        for criterion in result.unverified_criteria:
                            sections.append(f"  - {criterion}")

            sections.append("")

        # Pending sessions
        pending_sessions = feature.get_pending_sessions()
        if pending_sessions:
            sections.append("## Pending Sessions\n")
            for session_name in pending_sessions:
                sections.append(f"### ○ {session_name}")
                sections.append(f"- **Status**: pending")
                sections.append("")

        # Next steps
        sections.append("## Next Steps\n")
        if feature.status == "paused":
            sections.append(f"1. Fix verification issues in {current_session}")
            sections.append(f"2. Resume feature: `daf feature resume {feature.name}`")
        elif feature.status == "running":
            sections.append(f"1. Complete current session: {current_session}")
            sections.append(f"2. Verification will run automatically")
        elif feature.status == "created":
            sections.append(f"1. Start feature execution: `daf feature run {feature.name}`")
        elif feature.status == "complete":
            sections.append(f"1. Feature complete! All sessions verified.")
            if feature.pr_url:
                sections.append(f"2. PR created: {feature.pr_url}")

        content = "\n".join(sections)
        self.storage.save_state_file(feature.name, content)
