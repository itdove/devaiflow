# Release Skill Usage Examples

This document provides step-by-step examples of using the release skill for DevAIFlow.

## Example 1: Regular Minor Release

**Scenario**: You've added new features to main and want to release v2.3.0.

**Prerequisites**:
- On main branch
- All tests passing (`pytest`)
- CHANGELOG.md Unreleased section has content

**Steps**:

```bash
# In Claude Code, invoke the skill
/release minor
```

**What happens**:

1. Skill validates prerequisites (clean working directory, tests pass, CHANGELOG has content)
2. Creates `release-2.3` branch from main
3. Updates version: `2.2.0-dev` → `2.3.0` in:
   - `pyproject.toml` (line 6)
   - `devflow/__init__.py` (line 18)
4. Updates CHANGELOG.md:
   - Moves Unreleased content to `## [2.3.0] - 2026-04-08`
   - Updates version comparison links
5. Creates commit with proper message format
6. Provides tag creation command:
   ```bash
   git tag -a v2.3.0 -m "Release version 2.3.0

   See CHANGELOG.md for details."
   git push origin v2.3.0
   ```
7. Provides post-release checklist

**Expected output**:
```
✓ Prerequisites validated
✓ Version updated: 2.2.0-dev → 2.3.0
  - pyproject.toml: 2.3.0
  - devflow/__init__.py: 2.3.0
✓ CHANGELOG.md updated for v2.3.0
✓ Changes committed to release-2.3 branch

⚠️  MAINTAINERS ONLY - Authorization Check
This repository uses fork-based workflow.
Only @itdove can push production tags.

Next steps:
1. Review the changes on release-2.3 branch
2. Run tests: pytest
3. Create tag: git tag -a v2.3.0 -m "Release version 2.3.0"
4. Push tag: git push origin v2.3.0
5. Monitor GitHub Actions: https://github.com/itdove/devaiflow/actions
6. Verify PyPI publication: https://pypi.org/project/devaiflow/
7. Merge release branch back to main
8. Bump version to 2.4.0-dev on main
```

## Example 2: Patch Release

**Scenario**: You need to release v2.2.1 with bug fixes.

```bash
/release patch
```

**Result**: 
- Version updated `2.2.0-dev` → `2.2.1`
- CHANGELOG.md updated with fixes section
- Tag: `v2.2.1`

## Example 3: Hotfix Release

**Scenario**: Critical bug in production v2.2.0 needs immediate fix.

```bash
/release hotfix v2.2.0
```

**What happens**:

1. Validates v2.2.0 tag exists
2. Creates `hotfix-2.2.1` branch from v2.2.0 tag
3. Waits for you to implement the fix
4. Updates version: `2.2.0` → `2.2.1`
5. Updates CHANGELOG.md with hotfix entry
6. Provides tag and merge-back commands

**Workflow**:
```bash
# 1. Skill creates hotfix branch
# 2. You fix the bug
git add .
git commit -m "fix: critical bug description"

# 3. Update version and CHANGELOG
# (skill handles this after you confirm fix is complete)

# 4. Tag the hotfix
git tag -a v2.2.1 -m "Hotfix release 2.2.1"
git push origin v2.2.1

# 5. Merge back
git checkout release-2.2
git merge hotfix-2.2.1 --no-ff
git push origin release-2.2

# 6. Cherry-pick to main
git checkout main
git cherry-pick <commit-sha-of-fix>
git push origin main
```

## Example 4: TestPyPI Release

**Scenario**: Test release workflow before production.

```bash
/release test
```

**What happens**:

1. Creates `release-2.3-test` branch
2. Updates version: `2.3.0-dev` → `2.3.0-test1`
3. Creates commit
4. Creates test tag: `v2.3.0-test1`
5. Provides TestPyPI verification steps

**Verification**:
```bash
# After pushing test tag, verify on TestPyPI
python -m venv /tmp/test-devaiflow
source /tmp/test-devaiflow/bin/activate
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  devaiflow==2.3.0-test1

daf --version
# Should show: daf, version 2.3.0-test1

deactivate
rm -rf /tmp/test-devaiflow
```

## Example 5: Using Helper Script Directly

**Get current version**:
```bash
python .claude/skills/release/release_helper.py get-version
# Output:
# pyproject.toml: 2.2.0-dev
# devflow/__init__.py: 2.2.0-dev
# Match: True
```

**Calculate next version**:
```bash
python .claude/skills/release/release_helper.py calc-version 2.2.0-dev minor
# Output: 2.3.0
```

**Validate prerequisites**:
```bash
python .claude/skills/release/release_helper.py validate --type regular
# Output:
# ✓ All prerequisites validated
# OR
# ✗ Validation failed:
#   - CHANGELOG.md [Unreleased] section is empty
```

## Troubleshooting

### Issue: "Version mismatch between files"

**Cause**: pyproject.toml and devflow/__init__.py have different versions.

**Solution**:
```bash
# Check current versions
python .claude/skills/release/release_helper.py get-version

# Manually sync them to match, then retry
```

### Issue: "CHANGELOG.md [Unreleased] section is empty"

**Cause**: No changes documented for release.

**Solution**:
```bash
# Edit CHANGELOG.md and add your changes under [Unreleased]
## [Unreleased]

### Added
- New feature X

### Fixed
- Bug fix Y

# Then retry /release
```

### Issue: "Uncommitted changes detected"

**Cause**: Working directory has uncommitted changes.

**Solution**:
```bash
# Commit or stash your changes first
git add .
git commit -m "chore: prepare for release"

# Then retry /release
```

### Issue: "Tests failing"

**Cause**: Test suite not passing.

**Solution**:
```bash
# Fix failing tests first
pytest

# Ensure all tests pass before releasing
```

### Issue: "Not authorized to push tags"

**Cause**: You're not a repository maintainer.

**Solution**:
- ✅ Create PR with the release branch
- ✅ Notify @itdove that release is ready
- ✅ Include the tag command in PR description
- ❌ DO NOT push the tag yourself

See [CONTRIBUTING.md](../../../CONTRIBUTING.md) for fork-based workflow.

### Issue: "Tag already exists"

**Cause**: Version tag already exists (maybe from failed release).

**Solution**:
```bash
# Check existing tags
git tag | grep v2.3.0

# If tag exists locally but not on remote, delete it
git tag -d v2.3.0

# If tag exists on remote, increment version
/release patch  # Instead of minor
```

## Best Practices

### 1. Always Test Before Releasing

```bash
# Run full test suite
pytest

# Run integration tests
cd integration-tests && ./run_all_integration_tests.sh
```

### 2. Review CHANGELOG Before Release

Ensure all changes are documented:
- New features under `### Added`
- Breaking changes under `### Changed`
- Bug fixes under `### Fixed`

### 3. Use Test Releases for Major Changes

```bash
# Test the release process first
/release test

# After verification, do production release
/release major
```

### 4. Follow Semantic Versioning

- **Major** (3.0.0): Breaking changes
- **Minor** (2.3.0): New features (backward compatible)
- **Patch** (2.2.1): Bug fixes (backward compatible)

### 5. Coordinate with Team

Before releasing:
- ✅ Notify team in Slack/email
- ✅ Ensure no conflicting work in progress
- ✅ Schedule during low-traffic period
- ✅ Have rollback plan ready

## Authorization Checklist

Before pushing tags (maintainers only):

- [ ] Confirmed you are authorized (@itdove)
- [ ] All changes reviewed on release branch
- [ ] All tests pass: `pytest`
- [ ] Version correct in both files (pyproject.toml, devflow/__init__.py)
- [ ] CHANGELOG.md updated with proper format
- [ ] Tag created with proper format: `git tag -a vX.Y.Z -m "..."`
- [ ] Monitoring setup for GitHub Actions
- [ ] Ready to verify PyPI publication
- [ ] Plan for post-release merge to main

## References

- **RELEASING.md** - Complete release process documentation
- **CONTRIBUTING.md** - Fork-based workflow and authorization
- **.github/workflows/publish.yml** - Production PyPI workflow
- **.github/workflows/publish-test.yml** - TestPyPI workflow
- **.github/workflows/tag-monitor.yml** - Tag creation monitoring
- **CHANGELOG.md** - Changelog format and history
