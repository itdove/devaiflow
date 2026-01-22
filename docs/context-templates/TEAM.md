# Team Conventions and Workflows

This file contains team-specific conventions and workflows that apply to your team's projects.

## Team Workflow

### Daily Standup
- What you worked on yesterday
- What you're working on today
- Any blockers or concerns

### Sprint Planning
- Review backlog and prioritize tickets
- Estimate story points
- Assign work to team members
- Clarify requirements and acceptance criteria

## Development Practices

### Branch Strategy
- Create feature branch from main
- Branch naming: `<JIRA-KEY>-<description>`
- Always pull latest main before creating branch
- Keep branches short-lived (< 1 week)

### Code Review
- All code must be reviewed before merging
- At least one approval required
- Address all review comments
- Re-request review after changes

### Testing Strategy
- Write tests before or during implementation
- Run tests locally before pushing
- Ensure all tests pass in CI/CD
- Add integration tests for critical flows

## Communication

### Slack Channels
- #team-dev - Development discussions
- #team-alerts - Build/deployment notifications
- #team-support - User support and issues

### JIRA Updates
- Update ticket status when starting work (In Progress)
- Add comments for significant progress updates
- Update time estimates if needed
- Link PRs to tickets

### Documentation
- Update README when adding features
- Document architecture decisions
- Keep team wiki up-to-date
- Share knowledge in team meetings

## Tools and Resources

### Development Environment
- Python 3.10, 3.11, or 3.12 required (officially tested and supported)
- Use virtual environments (venv or conda)
- Install dev dependencies: `pip install -e .[dev]`

### Code Quality Tools
- Black for formatting
- Ruff for linting
- MyPy for type checking
- pytest for testing

### CI/CD Pipeline
- Tests run on every PR
- Coverage reports generated
- Linting and type checking enforced
- Deploy from main branch

## Team Conventions

### Code Style
- Use type hints consistently
- Keep functions small and focused
- Prefer composition over inheritance
- Use descriptive names (avoid abbreviations)

### PR/MR Template
- Always use the team PR template
- Include description of changes
- List testing performed
- Note any deployment considerations
- Add screenshots for UI changes

### Meeting Schedule
- Daily standup: 9:00 AM
- Sprint planning: First Monday of sprint
- Retrospective: Last Friday of sprint
- Team lunch: Every Thursday

## Customization

Replace this template content with your team's actual conventions, workflows, and practices.
