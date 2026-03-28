"""Test runner for feature verification.

Executes test commands and captures results for verification reports.
"""

import subprocess
from pathlib import Path
from typing import Optional, Tuple


class TestRunner:
    """Run test suite and capture results."""

    def __init__(self, project_path: str):
        """Initialize the test runner.

        Args:
            project_path: Path to the project directory
        """
        self.project_path = Path(project_path)

    def detect_test_command(self) -> Optional[str]:
        """Auto-detect the appropriate test command for the project.

        Checks for common test frameworks and configuration files.

        Returns:
            Test command string or None if not detected
        """
        # Python projects
        if (self.project_path / "pytest.ini").exists() or \
           (self.project_path / "setup.py").exists() or \
           (self.project_path / "pyproject.toml").exists():
            return "pytest"

        # Node.js projects
        if (self.project_path / "package.json").exists():
            # Check if npm test is configured
            try:
                import json
                with open(self.project_path / "package.json") as f:
                    pkg = json.load(f)
                    if "scripts" in pkg and "test" in pkg["scripts"]:
                        return "npm test"
            except (json.JSONDecodeError, FileNotFoundError):
                pass

        # Go projects
        if list(self.project_path.glob("*.go")):
            return "go test ./..."

        # Rust projects
        if (self.project_path / "Cargo.toml").exists():
            return "cargo test"

        # Java/Maven projects
        if (self.project_path / "pom.xml").exists():
            return "mvn test"

        # Java/Gradle projects
        if (self.project_path / "build.gradle").exists() or \
           (self.project_path / "build.gradle.kts").exists():
            return "gradle test"

        return None

    def run_tests(
        self,
        test_command: Optional[str] = None,
        timeout: int = 300
    ) -> Tuple[bool, str]:
        """Execute test command and capture output.

        Args:
            test_command: Test command to run (auto-detected if None)
            timeout: Timeout in seconds (default: 5 minutes)

        Returns:
            Tuple of (success: bool, output: str)
        """
        # Auto-detect if not provided
        if test_command is None:
            test_command = self.detect_test_command()

        if test_command is None:
            return False, "No test command configured and auto-detection failed"

        try:
            # Run test command
            result = subprocess.run(
                test_command,
                shell=True,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # Combine stdout and stderr
            output = result.stdout
            if result.stderr:
                output += "\n\n=== STDERR ===\n" + result.stderr

            # Check if tests passed
            success = result.returncode == 0

            # Truncate output if too long (keep last 2000 chars for report)
            if len(output) > 2000:
                output = "... (truncated)\n\n" + output[-2000:]

            return success, output

        except subprocess.TimeoutExpired:
            return False, f"Tests timed out after {timeout} seconds"

        except Exception as e:
            return False, f"Failed to run tests: {str(e)}"

    def parse_test_summary(self, output: str) -> str:
        """Extract test summary from output.

        Args:
            output: Full test output

        Returns:
            Summary line (e.g., "12 passed in 2.3s")
        """
        # pytest format
        pytest_match = [
            line for line in output.split("\n")
            if " passed" in line or " failed" in line
        ]
        if pytest_match:
            return pytest_match[-1].strip()

        # npm test / jest format
        jest_match = [
            line for line in output.split("\n")
            if "Tests:" in line or "Test Suites:" in line
        ]
        if jest_match:
            return " | ".join(jest_match).strip()

        # Go test format
        go_match = [
            line for line in output.split("\n")
            if line.startswith("PASS") or line.startswith("FAIL")
        ]
        if go_match:
            return go_match[-1].strip()

        # cargo test format
        cargo_match = [
            line for line in output.split("\n")
            if "test result:" in line
        ]
        if cargo_match:
            return cargo_match[-1].strip()

        # Default: return last non-empty line
        lines = [line.strip() for line in output.split("\n") if line.strip()]
        if lines:
            return lines[-1]

        return "No summary available"
