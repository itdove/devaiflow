# Publishing DevAIFlow to PyPI

This guide documents the complete process for publishing the DevAIFlow package to PyPI (Python Package Index).

## Table of Contents

- [Prerequisites](#prerequisites)
- [Pre-Release Checklist](#pre-release-checklist)
- [Building the Package](#building-the-package)
- [Testing on TestPyPI](#testing-on-testpypi)
- [Publishing to Production PyPI](#publishing-to-production-pypi)
- [Post-Release Tasks](#post-release-tasks)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)

## Prerequisites

### 1. PyPI Accounts

You need accounts on both TestPyPI and production PyPI:

**Production PyPI:**
1. Register at https://pypi.org/account/register/
2. Verify your email address
3. Enable Two-Factor Authentication (2FA) - **Required**
4. Create an API token at https://pypi.org/manage/account/token/
   - Token name: "DevAIFlow Publishing" (or similar)
   - Scope: "Entire account" or limit to "devaiflow" project

**TestPyPI (for testing):**
1. Register at https://test.pypi.org/account/register/
2. Verify your email address
3. Enable Two-Factor Authentication (2FA) - **Required**
4. Create an API token at https://test.pypi.org/manage/account/token/
   - Token name: "DevAIFlow Testing"
   - Scope: "Entire account"

### 2. Install Build Tools

```bash
pip install --upgrade build twine
```

### 3. Configure Credentials

Create or edit `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
  username = __token__
  password = pypi-YOUR_PRODUCTION_TOKEN_HERE

[testpypi]
  repository = https://test.pypi.org/legacy/
  username = __token__
  password = pypi-YOUR_TESTPYPI_TOKEN_HERE
```

**Important:**
- Replace `YOUR_PRODUCTION_TOKEN_HERE` with your production PyPI token
- Replace `YOUR_TESTPYPI_TOKEN_HERE` with your TestPyPI token
- Keep this file secure (`chmod 600 ~/.pypirc`)

**Alternative (More Secure):** Use environment variables instead of storing tokens in `.pypirc`:

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-YOUR_TOKEN_HERE
```

## Pre-Release Checklist

Before building and publishing, ensure:

### 1. Version Numbers Are Correct

Check that version numbers match in both files:

```bash
# Check version in setup.py
grep "version=" setup.py

# Check version in devflow/__init__.py
grep "__version__" devflow/__init__.py
```

For a release, versions should **NOT** have the `-dev` suffix:
- ✅ Correct: `1.0.0`, `1.1.0`, `1.0.1`
- ❌ Wrong: `1.0.0-dev`, `1.1.0-dev`

### 2. Tests Pass

```bash
# Run full test suite
pytest

# Run integration tests
cd integration-tests
./run_all_integration_tests.sh
```

### 3. Verify You're on the Correct Branch

```bash
# For releases, use the release branch
git checkout release/1.0  # or appropriate release branch
git status  # Should show clean working tree
git pull origin release/1.0  # Ensure up-to-date with remote
```

### 4. Documentation Is Updated

Ensure these files reference PyPI installation:
- `README.md` - Quick Start section
- `docs/02-installation.md` - Installation Methods section

They should show:
```bash
pip install devaiflow
```

Not:
```bash
pip install .  # This is for local development only
```

## Building the Package

### 1. Clean Previous Builds

```bash
# Remove old build artifacts
rm -rf dist/ build/ *.egg-info
```

### 2. Build Distribution Packages

```bash
# Build both wheel and source distribution
python -m build
```

This creates:
- `dist/devaiflow-X.Y.Z-py3-none-any.whl` (wheel package)
- `dist/devaiflow-X.Y.Z.tar.gz` (source distribution)

### 3. Verify Package Quality

```bash
# Check package metadata and format
python -m twine check dist/*
```

Expected output:
```
Checking dist/devaiflow-X.Y.Z-py3-none-any.whl: PASSED
Checking dist/devaiflow-X.Y.Z.tar.gz: PASSED
```

### 4. Inspect Package Contents (Optional)

```bash
# View files in the tar.gz
tar -tzf dist/devaiflow-*.tar.gz | head -30

# View wheel contents
unzip -l dist/devaiflow-*.whl | head -30
```

Verify important files are included:
- `LICENSE`
- `README.md`
- `DAF_AGENTS.md`
- All Python modules in `devflow/`

## Testing on TestPyPI

**Always test on TestPyPI before publishing to production PyPI!**

### 1. Upload to TestPyPI

```bash
python -m twine upload --repository testpypi dist/*
```

If credentials are in `~/.pypirc`, it will upload automatically. Otherwise, you'll be prompted for:
- Username: `__token__`
- Password: Your TestPyPI API token

Expected output:
```
Uploading distributions to https://test.pypi.org/legacy/
Uploading devaiflow-X.Y.Z-py3-none-any.whl
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ XXX.X/XXX.X kB
Uploading devaiflow-X.Y.Z.tar.gz
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ XXX.X/XXX.X kB

View at:
https://test.pypi.org/project/devaiflow/X.Y.Z/
```

### 2. Verify TestPyPI Package Page

Visit: https://test.pypi.org/project/devaiflow/

Check:
- ✅ Package name is correct: `devaiflow`
- ✅ Version number is correct
- ✅ README renders correctly
- ✅ License shows: Apache 2.0
- ✅ Links work (Homepage, Bug Tracker, etc.)
- ✅ Classifiers are correct

### 3. Test Installation from TestPyPI

Create a clean test environment:

```bash
# Create test virtual environment
python -m venv /tmp/test-devaiflow
source /tmp/test-devaiflow/bin/activate

# Install from TestPyPI
# Note: --extra-index-url allows dependencies to come from regular PyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple devaiflow

# Verify installation
daf --version
# Expected: daf, version X.Y.Z

# Test basic functionality
daf --help
daf check

# Cleanup
deactivate
rm -rf /tmp/test-devaiflow
```

If installation fails or the command doesn't work, **DO NOT proceed to production PyPI**. Fix the issues first.

## Publishing to Production PyPI

**⚠️ WARNING:** Once published to PyPI, you **CANNOT** delete or re-upload the same version. Triple-check everything!

### 1. Final Verification

Before uploading:

```bash
# Verify version
grep "version=" setup.py
grep "__version__" devflow/__init__.py

# Verify git tag exists (should match version)
git tag -l "v*" | tail -5

# Verify clean working directory
git status

# Verify on correct branch
git branch --show-current  # Should be release/X.Y
```

### 2. Upload to Production PyPI

```bash
python -m twine upload dist/*
```

Expected output:
```
Uploading distributions to https://upload.pypi.org/legacy/
Uploading devaiflow-X.Y.Z-py3-none-any.whl
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ XXX.X/XXX.X kB
Uploading devaiflow-X.Y.Z.tar.gz
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ XXX.X/XXX.X kB

View at:
https://pypi.org/project/devaiflow/X.Y.Z/
```

### 3. Verify Production PyPI Package Page

Visit: https://pypi.org/project/devaiflow/

Perform the same checks as TestPyPI verification.

### 4. Test Production Installation

```bash
# Create fresh test environment
python -m venv /tmp/test-pypi-prod
source /tmp/test-pypi-prod/bin/activate

# Install from production PyPI
pip install devaiflow

# Verify
daf --version
daf --help

# Cleanup
deactivate
rm -rf /tmp/test-pypi-prod
```

## Post-Release Tasks

### 1. Update Documentation (If Not Already Done)

Ensure documentation shows PyPI installation:

```bash
# README.md should show:
pip install devaiflow

# docs/02-installation.md should have PyPI as Method 1
```

Commit any documentation updates:

```bash
git add README.md docs/02-installation.md
git commit -m "docs: update installation instructions for PyPI"
git push origin release/X.Y
```

### 2. Merge to Main Branch

```bash
# Switch to main
git checkout main
git pull origin main

# Merge release branch
git merge release/X.Y --no-ff -m "Merge release/X.Y into main"

# Push to remote
git push origin main
```

### 3. Verify Git Tag Exists

The git tag should have been created during the release process (see `RELEASING.md`):

```bash
# Check tag exists
git tag -l "vX.Y.Z"

# If not, create it now
git tag -a vX.Y.Z -m "Release version X.Y.Z"
git push origin vX.Y.Z
```

### 4. Update JIRA Ticket

Update the JIRA ticket that tracks this work:

```bash
# Update acceptance criteria
daf jira update AAP-XXXXX --acceptance-criteria "- [x] Published to PyPI
- [x] Installation tested
- [x] Documentation updated"

# Add completion comment
daf jira add-comment AAP-XXXXX "Package v<X.Y.Z> published to PyPI: https://pypi.org/project/devaiflow/X.Y.Z/"
```

### 5. Announce Release (Optional)

Consider announcing the release:
- GitHub Releases (create from git tag)
- Project documentation
- Team communication channels

### 6. Clean Up Local Build Artifacts

```bash
# Remove build artifacts (optional, but keeps repo clean)
rm -rf dist/ build/ *.egg-info
```

## Troubleshooting

### Authentication Error (403 Forbidden)

**Problem:**
```
ERROR    HTTPError: 403 Forbidden from https://test.pypi.org/legacy/
```

**Causes:**
1. Invalid or expired API token
2. Missing TestPyPI configuration in `~/.pypirc`
3. Using production token for TestPyPI (or vice versa)

**Solutions:**

1. **Verify token in `~/.pypirc`:**
   ```bash
   cat ~/.pypirc
   # Check that [testpypi] section exists with correct token
   ```

2. **Regenerate token:**
   - Go to https://test.pypi.org/manage/account/token/
   - Revoke old token
   - Create new token
   - Update `~/.pypirc` with new token

3. **Use environment variables instead:**
   ```bash
   export TWINE_USERNAME=__token__
   export TWINE_PASSWORD=pypi-YOUR_TOKEN_HERE
   python -m twine upload --repository testpypi dist/*
   ```

### Package Already Exists

**Problem:**
```
ERROR    File already exists. See https://pypi.org/help/#file-name-reuse
```

**Cause:** You're trying to upload a version that already exists on PyPI.

**Solution:** PyPI does not allow re-uploading the same version. You must:
1. Increment the version number in `setup.py` and `devflow/__init__.py`
2. Rebuild the package: `python -m build`
3. Upload the new version

**Note:** This is why testing on TestPyPI first is crucial!

### README Not Rendering on PyPI

**Problem:** README appears as plain text on PyPI package page.

**Causes:**
1. `long_description_content_type` not set in `setup.py`
2. Invalid markdown syntax in `README.md`

**Solutions:**

1. **Verify setup.py:**
   ```python
   setup(
       long_description=long_description,
       long_description_content_type="text/markdown",  # Must be present
       ...
   )
   ```

2. **Test README rendering locally:**
   ```bash
   pip install readme-renderer
   python -m readme_renderer README.md -o /tmp/output.html
   open /tmp/output.html  # On macOS
   ```

3. **Check with twine:**
   ```bash
   python -m twine check dist/*
   ```

### Missing Files in Package

**Problem:** Important files (like `LICENSE`, `DAF_AGENTS.md`) are missing from the uploaded package.

**Cause:** Files not included in package manifest.

**Solution:**

1. **Check MANIFEST.in (if it exists):**
   ```
   include LICENSE
   include README.md
   include DAF_AGENTS.md
   ```

2. **Verify with setup.py:**
   ```python
   setup(
       include_package_data=True,
       data_files=[
           ("", ["DAF_AGENTS.md"]),
       ],
       ...
   )
   ```

3. **Inspect package contents before uploading:**
   ```bash
   tar -tzf dist/devaiflow-*.tar.gz | grep LICENSE
   tar -tzf dist/devaiflow-*.tar.gz | grep DAF_AGENTS.md
   ```

### Command Not Found: twine

**Problem:**
```bash
twine upload dist/*
# zsh: command not found: twine
```

**Cause:** `twine` not in PATH (especially on macOS with pyenv).

**Solution:** Use `python -m twine` instead:
```bash
python -m twine upload --repository testpypi dist/*
python -m twine upload dist/*
```

## Security Considerations

### 1. Protect Your API Tokens

**Never commit API tokens to git!**

- Keep `~/.pypirc` out of version control
- Add `~/.pypirc` to global `.gitignore` if needed:
  ```bash
  echo "~/.pypirc" >> ~/.gitignore_global
  ```

### 2. Rotate Tokens When Exposed

If your token is ever exposed (e.g., shown in logs, shared accidentally):

1. **Immediately revoke the token:**
   - Production: https://pypi.org/manage/account/token/
   - TestPyPI: https://test.pypi.org/manage/account/token/

2. **Generate a new token**

3. **Update `~/.pypirc` with new token**

### 3. Use Environment Variables in CI/CD

For automated publishing in CI/CD pipelines, use environment variables:

```bash
# GitHub Actions example
- name: Publish to PyPI
  env:
    TWINE_USERNAME: __token__
    TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
  run: python -m twine upload dist/*
```

Store tokens in your CI/CD platform's secret management (GitHub Secrets, GitLab CI/CD Variables, etc.).

### 4. Limit Token Scope

When creating API tokens, limit scope to specific projects when possible:
- Instead of "Entire account"
- Select "Project: devaiflow"

This limits damage if the token is compromised.

### 5. Enable 2FA

Two-Factor Authentication is **required** by PyPI for creating API tokens. Keep your 2FA backup codes secure.

## Quick Reference

### Common Commands

```bash
# Install build tools
pip install --upgrade build twine

# Clean and build
rm -rf dist/ build/ *.egg-info
python -m build

# Verify package
python -m twine check dist/*

# Upload to TestPyPI
python -m twine upload --repository testpypi dist/*

# Upload to production PyPI
python -m twine upload dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple devaiflow
pip install devaiflow
```

### Version Checklist

Before publishing, verify:
- [ ] Version in `setup.py` is correct (no `-dev`)
- [ ] Version in `devflow/__init__.py` matches `setup.py`
- [ ] Git tag `vX.Y.Z` exists and matches version
- [ ] On correct git branch (`release/X.Y`)
- [ ] All tests pass (`pytest`)
- [ ] Documentation shows PyPI installation

## References

- [Python Packaging User Guide](https://packaging.python.org/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [PyPI Help](https://pypi.org/help/)
- [TestPyPI](https://test.pypi.org/)
- [Semantic Versioning](https://semver.org/)

## Related Documentation

- [RELEASING.md](../RELEASING.md) - Complete release process including git workflow
- [docs/08-release-management.md](08-release-management.md) - Automated release management with `daf release`
- [CHANGELOG.md](../CHANGELOG.md) - Version history and changes
