# Release Management Process

This document describes the release management process for DevAIFlow (daf tool).

> **💡 Recommended**: Use the automated `daf release` command instead of following these manual steps. See [docs/08-release-management.md](docs/08-release-management.md) for the automated workflow.
>
> This document is maintained as a reference for:
> - Understanding the release process details
> - Troubleshooting release issues
> - Custom scenarios not covered by automation

## Table of Contents

- [Version Numbering](#version-numbering)
- [Branch Strategy](#branch-strategy)
- [Release Workflow](#release-workflow)
- [Hotfix Workflow](#hotfix-workflow)
- [Release Checklist](#release-checklist)
- [Version Infrastructure](#version-infrastructure)

## Version Numbering

We follow [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes (incompatible API changes)
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)
- **Development**: X.Y.Z-dev (on main branch)

Examples:
- `1.0.0` - First stable release
- `1.1.0` - Added new features
- `1.1.1` - Bug fixes only
- `1.2.0-dev` - Development version on main branch

## Branch Strategy

### Main Branches

- **main**: Active development branch (latest features, version X.Y.0-dev)
- **release/X.Y**: Release branches (e.g., release/1.0, release/1.1)
- **hotfix/X.Y.Z**: Hotfix branches for critical fixes to released versions

### Tags

- **vX.Y.Z**: Git tags for each release (e.g., v1.0.0, v1.0.1, v1.1.0)

### Branch Lifecycle

```
main (v1.1.0-dev)
  |
  |--- release/1.0 (created from main when ready for v1.0.0)
  |      |
  |      |--- v1.0.0 (tagged after testing)
  |      |
  |      |--- hotfix/1.0.1 (created from v1.0.0 tag)
  |             |
  |             |--- v1.0.1 (tagged after fix)
  |             |
  |             (merged back to release/1.0 and cherry-picked to main)
  |
  |--- release/1.1 (created from main when ready for v1.1.0)
         |
         |--- v1.1.0 (tagged after testing)
```

## Release Workflow

### Prerequisites

1. All features for the release are merged to `main`
2. All tests pass on `main`
3. CHANGELOG.md is up-to-date in the Unreleased section
4. JIRA epic for the release is complete

### Step-by-Step Release Process

#### 1. Create Release Branch

```bash
# Ensure main is up-to-date
git checkout main
git pull origin main

# Create release branch (e.g., release/1.0)
git checkout -b release/1.0 main

# Push release branch
git push -u origin release/1.0
```

#### 2. Update Version Numbers

Update version in **devflow/__init__.py**:
```python
__version__ = "1.0.0"  # Remove -dev suffix
```

Update version in **setup.py**:
```python
setup(
    name="devaiflow",
    version="1.0.0",  # Remove -dev suffix
    ...
)
```

Commit the version bump:
```bash
git commit -m "$(cat <<'EOF'
chore: bump version to 1.0.0 for release

Prepare for v1.0.0 release:
- Update version in devflow/__init__.py
- Update version in setup.py

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

#### 3. Update CHANGELOG.md

Move Unreleased section entries to a new version section:

```markdown
## [1.0.0] - 2025-01-15

### Added
- Initial stable release
- [List of features added]

### Changed
- [List of changes]

### Fixed
- [List of bug fixes]

[1.0.0]: https://github.com/itdove/devaiflow/-/tags/v1.0.0
```

Commit the changelog:
```bash
git commit -m "$(cat <<'EOF'
docs: update CHANGELOG.md for v1.0.0 release

Move unreleased items to v1.0.0 section with release date.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

#### 4. Run Tests and Final Validation

```bash
# Run full test suite
pytest

# Run integration tests
cd integration-tests && ./test_collaboration_workflow.sh
cd integration-tests && ./test_jira_green_path.sh

# Verify version command
daf --version  # Should show: daf, version 1.0.0

# Test installation in clean environment
python -m venv /tmp/test-daf-install
source /tmp/test-daf-install/bin/activate
pip install .
daf --version
deactivate
rm -rf /tmp/test-daf-install
```

#### 5. Create Git Tag

```bash
# Create annotated tag
git tag -a v1.0.0 -m "Release version 1.0.0

See CHANGELOG.md for details.
"

# Push tag to remote
git push origin v1.0.0
```

#### 6. Create GitLab Release

Create a release on GitLab using the web UI or `glab` CLI:

```bash
# Get changelog content for this version
CHANGELOG_CONTENT=$(sed -n '/## \[1.0.0\]/,/## \[/p' CHANGELOG.md | head -n -1)

# Create GitLab release
glab release create v1.0.0 \
  --name "DevAIFlow v1.0.0" \
  --notes "$CHANGELOG_CONTENT"
```

Or use the GitLab web UI:
1. Go to Repository > Tags
2. Find v1.0.0 tag
3. Click "Create release"
4. Add release notes from CHANGELOG.md
5. Link to JIRA epic
6. Publish release

#### 7. Merge Back to Main and Bump Dev Version

```bash
# Switch to main
git checkout main

# Merge release branch
git merge release/1.0 --no-ff -m "Merge release/1.0 into main"

# Bump version to next dev cycle
# Update devflow/__init__.py to "1.1.0-dev"
# Update setup.py to "1.1.0-dev"

git commit -m "$(cat <<'EOF'
chore: bump version to 1.1.0-dev

Begin development cycle for v1.1.0.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# Push to remote
git push origin main
```

#### 8. (Optional) Publish to PyPI

**Note**: PyPI publishing is planned for the future. For now, skip this step.

When ready:
```bash
# Build distribution
python setup.py sdist bdist_wheel

# Upload to PyPI
twine upload dist/*
```

## Hotfix Workflow

### When to Use Hotfixes

Use hotfix branches for:
- Critical bugs in production releases
- Security vulnerabilities
- Data corruption issues
- Severe performance problems

**Do NOT use hotfixes for**:
- Minor bugs (wait for next minor release)
- New features
- Refactoring

### Step-by-Step Hotfix Process

#### 1. Create Hotfix Branch

```bash
# Checkout the release tag that needs the fix
git checkout -b hotfix/1.0.1 v1.0.0

# Alternatively, branch from the release branch
git checkout -b hotfix/1.0.1 release/1.0
```

#### 2. Fix the Bug

Make the necessary code changes to fix the critical bug.

```bash
# Make your fixes
# Write tests to verify the fix
pytest

# Commit the fix
git commit -m "$(cat <<'EOF'
fix: critical bug in backup operation

Fixes timeout issue when creating large backups.

Fixes: PROJ-12345

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

#### 3. Update Version Numbers

Update to patch version in **devflow/__init__.py**:
```python
__version__ = "1.0.1"
```

Update version in **setup.py**:
```python
setup(
    name="devaiflow",
    version="1.0.1",
    ...
)
```

#### 4. Update CHANGELOG.md

Add a new section for the hotfix:

```markdown
## [1.0.1] - 2025-01-20

### Fixed
- Critical timeout issue in backup operation (PROJ-12345)

[1.0.1]: https://github.com/itdove/devaiflow/-/tags/v1.0.1
```

#### 5. Tag and Release

```bash
# Create tag
git tag -a v1.0.1 -m "Hotfix release 1.0.1

Critical fix for backup timeout issue.
"

# Push tag
git push origin v1.0.1

# Create GitLab release
glab release create v1.0.1 \
  --name "DevAIFlow v1.0.1 (Hotfix)" \
  --notes "## Critical Bug Fixes\n\n- Fixed timeout issue in backup operation\n\nSee CHANGELOG.md for details."
```

#### 6. Merge Back to Release and Main

```bash
# Merge hotfix to release branch
git checkout release/1.0
git merge hotfix/1.0.1 --no-ff
git push origin release/1.0

# Cherry-pick the fix to main (NOT merge the version bumps)
git checkout main
git cherry-pick <commit-sha-of-the-fix>  # Only the fix commit, not version bumps
git push origin main

# Delete hotfix branch
git branch -d hotfix/1.0.1
git push origin --delete hotfix/1.0.1
```

## Release Checklist

Use this checklist for each release:

### Pre-Release
- [ ] All planned features merged to `main`
- [ ] All tests pass (`pytest`)
- [ ] Integration tests pass
- [ ] CHANGELOG.md updated with all changes
- [ ] Version bump PR reviewed and approved
- [ ] JIRA epic marked as complete

### Release Branch
- [ ] Create release branch (`release/X.Y`)
- [ ] Update version in `devflow/__init__.py` (remove `-dev`)
- [ ] Update version in `setup.py` (remove `-dev`)
- [ ] Update CHANGELOG.md (move Unreleased to version section)
- [ ] Run full test suite
- [ ] Test installation in clean environment
- [ ] Create and push git tag (`vX.Y.Z`)

### GitLab Release
- [ ] Create GitLab release from tag
- [ ] Add release notes from CHANGELOG.md
- [ ] Link to JIRA epic
- [ ] Verify release artifacts

### Post-Release
- [ ] Merge release branch back to `main`
- [ ] Bump version to next dev cycle (`X.Y+1.0-dev`)
- [ ] Update AGENTS.md "Completed Enhancements" section
- [ ] Announce release (if applicable)
- [ ] (Future) Publish to PyPI

### Hotfix (if needed)
- [ ] Create hotfix branch from release tag
- [ ] Fix bug and add tests
- [ ] Update version to patch level
- [ ] Update CHANGELOG.md
- [ ] Create and push tag
- [ ] Merge back to release branch
- [ ] Cherry-pick fix to `main`

## Version Infrastructure

### Version Storage

Version number is stored in two locations:
1. **devflow/__init__.py** - Single source of truth for runtime
   ```python
   __version__ = "1.0.0"
   ```

2. **setup.py** - Package metadata
   ```python
   version="1.0.0"
   ```

**Important**: Always keep these two files in sync during version bumps.

### Version Display

Users can check the version using:
```bash
daf --version
# Output: daf, version 1.0.0
```

This is implemented in `devflow/cli/main.py`:
```python
@click.version_option(version=__version__)
```

### Development Versions

Development versions on `main` branch always have the `-dev` suffix:
- `1.0.0-dev` - Developing towards v1.0.0
- `1.1.0-dev` - Developing towards v1.1.0

This helps distinguish development builds from stable releases.

## References

- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/)
- [Python Packaging](https://packaging.python.org/)

## Questions?

For questions about the release process:
1. Review this document
2. Check CHANGELOG.md for examples
3. See AGENTS.md for project-specific guidelines
