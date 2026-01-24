# Organization Coding Standards

This file contains organization-level coding standards and guidelines that apply to all projects within your organization.

## JIRA Integration (Optional)

If your organization uses JIRA with DevAIFlow, you can configure JIRA-specific guidelines here.

### Acceptance Criteria

**OPTIONAL**: Define your organization's requirements for acceptance criteria in JIRA tickets.

Example approach:
- Acceptance criteria should be in checkbox format: `- [] criterion`
- All criteria must be verified and tested before marking complete
- Update JIRA checkboxes as work progresses using `daf jira update`

#### Example Workflow
```bash
# 1. At session start, read the ticket
daf jira view PROJ-12345

# 2. During development, track progress
daf note PROJ-12345 "Completed acceptance criterion 1"

# 3. Before completing, update JIRA checkboxes
daf jira update PROJ-12345 --acceptance-criteria "- [x] criterion 1\n- [x] criterion 2"

# 4. Complete the session
daf complete PROJ-12345
```

### JIRA Wiki Markup (Optional)

**NOTE**: JIRA text fields require JIRA Wiki markup, not Markdown. This only applies when writing content that will be sent to JIRA.

Key differences from Markdown:

| Element | JIRA Wiki Markup | Markdown |
|---------|------------------|----------|
| Headers | `h2.` or `h3.` | `##` or `###` |
| Bold | `*text*` | `**text**` |
| Italic | `_text_` | `*text*` |
| Code blocks | `{code:bash}...{code}` | Triple backticks |
| Inline code | `{{code}}` | Single backticks |
| Lists | `*` or `#` | `-` or `1.` |
| Links | `[text\|url]` | `[text](url)` |

### JIRA Issue Templates (Optional)

Define standard templates for your organization's JIRA issue types. Customize these based on your team's needs.

#### Example Story Template
```
h3. *User Story*

As a [type of user], I want [goal] so that [reason]

h3. *Acceptance Criteria*

- [] Acceptance criterion 1
- [] Acceptance criterion 2
- [] Acceptance criterion 3

h3. *Technical Notes*

[Any technical implementation details]
```

#### Example Bug Template
```
*Description*
[What is happening]

*Steps to Reproduce*
# Step 1
# Step 2
# Step 3

*Expected Behavior*
[What should happen]

*Actual Behavior*
[What is currently happening]

*Acceptance Criteria*
- [] Bug fix verified
- [] No regression in related functionality
- [] Tests added to prevent recurrence
```

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
