# Organization Coding Standards

This file contains organization-level coding standards and guidelines that apply to all projects within your organization.

## Coding Standards

### Python
- Follow PEP 8 for Python code
- Use type hints for all function signatures
- Docstrings required for all public functions (Google style)
- Line length: 100 characters
- Use Black formatter for consistent formatting

### Code Quality
- Test coverage target: >80%
- All tests must pass before merging
- Use descriptive variable and function names
- Avoid magic numbers - use named constants

## Architecture Principles

### Separation of Concerns
- Keep CLI layer separate from business logic
- Session management should be independent of JIRA integration
- Use dependency injection for testability

### Error Handling
- Use exception-based error handling
- Create custom exceptions for domain errors
- Provide clear, actionable error messages
- Log errors with context for debugging

### Testing
- Unit tests for all modules
- Integration tests for critical flows
- Mock external dependencies (JIRA API, subprocess calls)
- Name test functions descriptively: `test_<function_name>_<scenario>`

## Git Workflow

### Branch Naming
- Format: `<JIRA-KEY>-<short-description>`
- Use lowercase with hyphens
- Keep description concise but meaningful
- Examples: `PROJ-12345-add-caching`, `PROJ-67890-fix-timeout`

### Commit Messages
- Format: `<type>: <subject>` (e.g., `feat: add user authentication`)
- Types: feat, fix, docs, refactor, test, chore
- Subject: imperative mood, lowercase, no period
- Include detailed body for complex changes
- Always include Co-Authored-By for AI-assisted commits

### Pull Requests
- Never commit directly to main/master
- Always create a PR/MR for review
- Use draft PRs while work is in progress
- Include tests for new functionality
- Update documentation when adding features

## Documentation

### Code Documentation
- Docstrings for all public functions (Google style)
- Inline comments for complex logic
- Keep comments up-to-date with code changes

### Project Documentation
- README.md for project overview
- ARCHITECTURE.md for design decisions
- CHANGELOG.md for user-facing changes
- Keep documentation in sync with code

## Security

### Best Practices
- Never commit secrets (API tokens, passwords, keys)
- Use environment variables for sensitive data
- Validate all user input
- Use parameterized queries to prevent SQL injection
- Follow OWASP Top 10 guidelines

### Code Review
- Security review for authentication/authorization changes
- Check for common vulnerabilities (XSS, CSRF, etc.)
- Review dependency updates for security patches

## Performance

### Optimization Guidelines
- Profile before optimizing
- Focus on algorithmic improvements first
- Cache expensive computations
- Use async/await for I/O-bound operations
- Monitor memory usage for large datasets

## Customization

Replace this template content with your organization's actual coding standards, architecture principles, and workflows.
