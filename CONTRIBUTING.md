# Contributing to DevAIFlow

Thank you for your interest in contributing to DevAIFlow! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Code Style](#code-style)
- [Documentation](#documentation)
- [Community](#community)
- [Security](#security)

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- A GitHub account
- Claude Code (for testing session management features)
- Optional: JIRA account (for testing JIRA integration)

### Find an Issue

Good first contributions:
- Look for issues labeled `good first issue`
- Documentation improvements
- Bug fixes
- Test coverage improvements

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/devaiflow.git
cd devaiflow

# Add upstream remote
git remote add upstream https://github.com/itdove/devaiflow.git
```

### 2. Create a Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows
```

### 3. Install Development Dependencies

```bash
# Install the package in editable mode with dev dependencies
pip install -e ".[dev]"

# Or install from requirements files
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Verify Installation

```bash
# Verify daf command works
daf --version

# Run tests to ensure everything works
pytest
```

## Making Changes

### 1. Create a Feature Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test additions or changes

### 2. Make Your Changes

- Write clear, concise code
- Follow the existing code style
- Add tests for new functionality
- Update documentation as needed
- Keep commits focused and atomic

### 3. Commit Your Changes

```bash
# Stage your changes
git add .

# Commit with a clear message
git commit -m "feat: add support for custom JIRA fields"
```

**Commit Message Format:**

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Test additions or changes
- `chore`: Build process or tooling changes

Examples:
```
feat(jira): add support for custom field discovery

Implements automatic field discovery for JIRA projects,
allowing users to update any editable field dynamically.

Closes #123
```

```
fix(session): prevent race condition in session updates

Multiple processes could simultaneously update session metadata,
causing data loss. Added file locking mechanism.

Fixes #456
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=devflow --cov-report=html

# Run specific test file
pytest tests/test_session_manager.py

# Run specific test
pytest tests/test_session_manager.py::test_create_session

# Run tests matching a pattern
pytest -k "jira"
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use descriptive test names that explain what is being tested
- Use fixtures for common setup
- Mock external dependencies (JIRA API, Git commands, etc.)

Example test:
```python
def test_session_creation_with_issue_key(session_manager, mock_jira):
    """Test creating a session with a JIRA ticket key."""
    session = session_manager.create_session(
        name="test-session",
        issue_key="PROJ-123",
        goal="Test goal"
    )

    assert session.name == "test-session"
    assert session.issue_key == "PROJ-123"
    assert session.goal == "Test goal"
    assert session.status == "active"
```

### Integration Tests

Integration tests are in `integration-tests/`:

```bash
# Run integration tests (requires actual git setup)
cd integration-tests
./test_collaboration_workflow.sh
```

## Submitting Changes

### 1. Push Your Changes

```bash
# Push your branch to your fork
git push origin feature/your-feature-name
```

### 2. Create a Pull Request

1. Go to your fork on GitHub
2. Click "New Pull Request"
3. Select your feature branch
4. Fill in the PR template:
   - Clear description of changes
   - Link to related issues
   - Screenshots (if UI changes)
   - Testing performed
   - Breaking changes (if any)

### 3. PR Review Process

- Maintainers will review your PR
- Address any feedback or requested changes
- Keep your PR up to date with main branch:
  ```bash
  git checkout main
  git pull upstream main
  git checkout feature/your-feature-name
  git rebase main
  git push --force-with-lease origin feature/your-feature-name
  ```

### 4. After Merge

```bash
# Update your main branch
git checkout main
git pull upstream main

# Delete your feature branch
git branch -d feature/your-feature-name
git push origin --delete feature/your-feature-name
```

## Code Style

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line length**: 120 characters (not 79)
- **Imports**: Group in order - stdlib, third-party, local
- **Docstrings**: Use Google-style docstrings
- **Type hints**: Use type hints for function signatures

### Linting and Formatting

```bash
# Format code with black
black devflow/ tests/

# Check code style with flake8
flake8 devflow/ tests/

# Type checking with mypy (optional)
mypy devflow/

# Sort imports
isort devflow/ tests/
```

### Pre-commit Hooks (Recommended)

```bash
# Install pre-commit
pip install pre-commit

# Set up hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### Example Code Style

```python
from typing import Optional, List
import os
from pathlib import Path

from rich.console import Console

from devflow.session.manager import SessionManager


def create_session(
    name: str,
    goal: Optional[str] = None,
    issue_key: Optional[str] = None,
    working_directory: Optional[str] = None,
) -> Session:
    """Create a new session with the given parameters.

    Args:
        name: Session name (unique identifier)
        goal: Optional session goal description
        issue_key: Optional JIRA ticket key (e.g., "PROJ-123")
        working_directory: Optional working directory path

    Returns:
        Created Session object

    Raises:
        SessionError: If session creation fails

    Example:
        >>> session = create_session(
        ...     name="my-feature",
        ...     goal="Implement new API endpoint",
        ...     issue_key="PROJ-456"
        ... )
    """
    session_manager = SessionManager()

    # Create session with provided parameters
    session = session_manager.create_session(
        name=name,
        goal=goal,
        issue_key=issue_key,
        working_directory=working_directory,
    )

    return session
```

## Documentation

### Updating Documentation

- Update docstrings when changing function signatures
- Update README.md for user-facing changes
- Update relevant docs in `docs/` directory
- Add examples for new features
- Keep documentation clear and concise

### Documentation Style

- Use Markdown for all documentation
- Use code blocks with language specification
- Include examples for complex features
- Link to related documentation

### Building Documentation

```bash
# Install documentation dependencies
pip install -e ".[docs]"

# Build documentation
cd docs
make html

# View documentation
open _build/html/index.html
```

## Community

### Getting Help

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Documentation**: Check the docs first

### Reporting Bugs

When reporting bugs, include:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment (OS, Python version, daf version)
- Relevant logs or error messages

Use this template:
```markdown
**Description:**
Brief description of the bug

**Steps to Reproduce:**
1. Run command `daf new ...`
2. ...

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happens

**Environment:**
- OS: macOS 14.0
- Python: 3.11.5
- daf version: 1.0.0

**Logs/Error Messages:**
```
paste error message here
```
```

### Suggesting Features

When suggesting features, include:
- Clear use case
- Why this feature is needed
- How it should work
- Example usage

## Additional Resources

- [GitHub Flow Guide](https://guides.github.com/introduction/flow/)
- [How to Write a Git Commit Message](https://chris.beams.io/posts/git-commit/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Python PEP 8 Style Guide](https://pep8.org/)

## Security

### Reporting Security Vulnerabilities

If you discover a security vulnerability, please do **not** create a public issue. Instead:

1. Report it privately through [GitHub Security Advisories](https://github.com/itdove/devaiflow/security/advisories/new)
2. Include details about the vulnerability and steps to reproduce
3. We will respond within 48 hours

See [SECURITY.md](SECURITY.md) for complete security reporting guidelines and best practices.

## License

By contributing to DevAIFlow, you agree that your contributions will be licensed under the Apache License 2.0.

---

Thank you for contributing! 🎉
