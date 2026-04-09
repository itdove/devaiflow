# Release Skill

This skill automates the release management workflow for DevAIFlow using semantic versioning.

## Features

- **Version management**: Updates version in pyproject.toml and devflow/__init__.py
- **CHANGELOG automation**: Updates CHANGELOG.md following Keep a Changelog format
- **Git operations**: Creates release branches, commits, and tags
- **Safety checks**: Validates prerequisites before starting
- **Authorization**: Enforces fork-based workflow with maintainer-only releases

## Location

This skill is placed in `.claude/skills/release/` (version controlled with DevAIFlow project).

Project-specific installation provides:
- ✅ Version controlling the skill with the project
- ✅ Customized for DevAIFlow workflows
- ✅ Available to all contributors
- ✅ Enforces fork-based workflow authorization

## Files

- **SKILL.md** - Skill documentation (invoked by Claude Code)
- **release_helper.py** - Python automation utilities
- **README.md** - This file
- **EXAMPLE_USAGE.md** - Usage examples and troubleshooting

## Usage

In Claude Code, invoke the skill with:

```bash
/release minor              # Create minor version release (2.1.0 -> 2.2.0)
/release patch              # Create patch version release (2.2.0 -> 2.2.1)
/release major              # Create major version release (2.0.0 -> 3.0.0)
/release hotfix v2.1.0      # Create hotfix from v2.1.0 tag
/release test               # Create TestPyPI test release
```

## Helper Script

The `release_helper.py` script can also be used standalone:

```bash
# Get current version
python .claude/skills/release/release_helper.py get-version

# Calculate next version
python .claude/skills/release/release_helper.py calc-version 2.1.0-dev minor
# Output: 2.2.0

# Update version in all files
python .claude/skills/release/release_helper.py update-version 2.2.0

# Update CHANGELOG.md
python .claude/skills/release/release_helper.py update-changelog 2.2.0

# Validate prerequisites
python .claude/skills/release/release_helper.py validate --type regular
```

## Authorization

**IMPORTANT**: This repository uses a fork-based workflow.

- **Maintainers** (@itdove): Can create and push releases
- **Contributors**: Should NOT create or push production tags
  - Fork the repository instead
  - Submit pull requests with changes
  - Maintainers will handle releases

See [CONTRIBUTING.md](../../../CONTRIBUTING.md) and [RELEASING.md](../../../RELEASING.md) for details.

## Version Files

DevAIFlow stores version in two locations that must stay synchronized:

1. **pyproject.toml** - Line 6: `version = "X.Y.Z"`
2. **devflow/__init__.py** - Line 18: `__version__ = "X.Y.Z"`

The skill automatically updates both files and validates they match.

## CHANGELOG Format

Location: `CHANGELOG.md`

Format: [Keep a Changelog](https://keepachangelog.com/)

The skill moves `[Unreleased]` content to a new version section with the current date.

## Testing

Run the helper script tests:

```bash
pytest tests/test_release_helper.py -v
```

## Troubleshooting

See [EXAMPLE_USAGE.md](EXAMPLE_USAGE.md) for common scenarios and solutions.

## References

- [RELEASING.md](../../../RELEASING.md) - Complete release process
- [CONTRIBUTING.md](../../../CONTRIBUTING.md) - Fork-based workflow
- `.github/workflows/tag-monitor.yml` - Tag creation monitoring
- `.github/workflows/publish.yml` - PyPI publication
- `.github/workflows/publish-test.yml` - TestPyPI publication
