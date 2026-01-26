# Personal Development Notes

This file contains your personal notes, preferences, and reminders for development work.

## Current Focus

### Active Projects
- List your current projects and priorities
- Track what you're working on
- Note dependencies or blockers

### Learning Goals
- Technologies or skills you're learning
- Books or courses in progress
- Certifications or training planned

## Personal Conventions

### Code Style Preferences
- Your preferred patterns or idioms
- Code organization preferences
- Naming conventions you favor

### Workflow Preferences
- Your preferred editor/IDE settings
- Keyboard shortcuts you use
- Tools and scripts you've created

## Reminders

### Before Committing
- Run tests: `pytest`
- Check formatting: `black .`
- Verify type hints: `mypy devflow/`
- Update CHANGELOG.md for user-facing changes

### Before Creating PR
- Review your own changes first
- Write clear commit messages
- Update documentation if needed
- Add tests for new features
- Run full test suite

### Regular Tasks
- Weekly: Review open PRs and issues
- Daily: Update JIRA tickets
- After meetings: Document decisions and action items

## Useful Commands

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_session_manager.py

# Run with coverage
pytest --cov=devflow --cov-report=html

# Run integration tests (outside Claude Code)
cd integration-tests && ./test_collaboration_workflow.sh
```

### Development
```bash
# Reinstall after changes
pip install --upgrade --force-reinstall .

# Format code
black devflow/ tests/

# Lint code
ruff check devflow/ tests/

# Type check
mypy devflow/
```

### Git
```bash
# Create feature branch
git checkout -b PROJ-XXXXX-description

# Update from main
git fetch origin
git rebase origin/main

# Interactive rebase (clean up commits)
git rebase -i HEAD~3
```

## Notes and Ideas

### Technical Debt
- Areas that need refactoring
- Known bugs or limitations
- Future improvements

### Ideas for Features
- Feature ideas to propose
- Improvements to existing functionality
- Developer experience enhancements

## Project-Specific Notes

### DevAIFlow
- Remember to run integration tests outside Claude Code
- Update both docs/ and dodevflow/ when documenting
- Use daf-cli skill for command reference
- Always test with both $DEVAIFLOW_HOME and $DEVAIFLOW_HOME

## Customization

Replace this template content with your personal notes, preferences, and reminders.
