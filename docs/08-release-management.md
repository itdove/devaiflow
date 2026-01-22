# Release Management

This guide shows how to create releases for the DevAIFlow using the automated `daf release` command or manual processes.

## Table of Contents

- [Quick Start](#quick-start)
- [daf release Command (Recommended)](#cs-release-command)
- [Manual Release Process](#manual-release-process)
- [Claude-Assisted Releases](#claude-assisted-releases)

## Quick Start

**Recommended**: Use the `daf release` command for automated, consistent releases:

```bash
# Get a suggestion first (analyzes commits)
daf release --suggest

# Minor release (new features)
daf release 1.1.0

# Review the changes
git log -3
git show v1.1.0

# Approve and complete (pushes, creates release, merges to main)
daf release 1.1.0 approve

# Major release (breaking changes)
daf release 1.0.0
daf release 1.0.0 approve

# Patch release (bug fixes)
daf release 0.1.1 --from v0.1.0
daf release 0.1.1 approve

# Preview first (recommended)
daf release 1.1.0 --dry-run
daf release 1.1.0 approve --dry-run
```

**Alternative**: Follow manual steps in [RELEASING.md](../RELEASING.md) or use [Claude-assisted workflow](#claude-assisted-releases) for complex scenarios.

---

## daf release Command (Recommended)

The `daf release` command automates the mechanical parts of the release process, ensuring consistency and reducing human error.

**See full documentation below**: [Detailed daf release Guide](#cs-release-command)

**Why use daf release?**
- ✅ Automated version file updates
- ✅ **Auto-generated CHANGELOG from PR/MR metadata**
- ✅ Runs all tests (unit + integration)
- ✅ Permission checking (Maintainer/Owner only)
- ✅ Prevents common mistakes
- ✅ Saves 10-30 minutes per release
- ✅ Consistent process every time

---

## Manual Release Process

For detailed manual steps, see [RELEASING.md](../RELEASING.md). The manual process gives you complete control but requires careful attention to every step.

**When to use manual process:**
- Learning the release process
- Troubleshooting release issues
- Custom release scenarios not supported by automation
- When `daf release` command is unavailable

---

## Claude-Assisted Releases

You can also ask Claude Code to execute the release process by reading RELEASING.md. This is useful for complex scenarios or when you want Claude's assistance.

### Prompts for Claude

### Minor Release

```
I need to create minor release v1.1.0 of the DevAIFlow.

Please read and follow RELEASING.md section "Release Workflow":
1. Read RELEASING.md to understand the complete workflow
2. Verify we're ready (tests pass, CHANGELOG updated, etc.)
3. Execute all steps from RELEASING.md
4. Do NOT push to remote until I review

Context:
- Current main version: 1.1.0-dev
- JIRA Epic: PROJ-XXXXX

After completing, show me:
- Summary of changes
- Test results
- What branches/tags were created
```

**Key Points:**
- Reference RELEASING.md explicitly so Claude reads the latest process
- Specify NOT to push (you review first)
- Provide context (current version, JIRA epic)

### Major Release

```
I need to create major release v2.0.0 with breaking changes.

Please read and follow RELEASING.md section "Release Workflow":
1. Read RELEASING.md for the complete process
2. Pay special attention to breaking changes in CHANGELOG
3. Run extra tests (this is a major version!)
4. Do NOT push until I review

Context:
- Current main version: 2.0.0-dev
- Breaking changes: [list major changes]
- JIRA Epic: PROJ-XXXXX

Show me all changes before I push.
```

**Key Points:**
- Emphasize breaking changes
- Request extra testing
- List what's breaking for CHANGELOG

### Patch/Hotfix Release

```
I need to create hotfix v0.1.1 to fix [brief bug description].

Please read and follow RELEASING.md section "Hotfix Workflow":
1. Read RELEASING.md "Hotfix Workflow" section
2. Create hotfix from tag v0.1.0
3. Fix the bug: [detailed description]
4. Add tests for the fix
5. Do NOT push or merge until I review

Context:
- Bug affects: v0.1.0 (released)
- Current release/0.1 version: 0.1.1-dev
- JIRA Issue: PROJ-XXXXX

Show me the fix and test results.
```

**Key Points:**
- Reference "Hotfix Workflow" specifically
- Describe the bug to fix
- Request test coverage

## Workflow Integration

### Option 1: Using daf jira new (Recommended)

Create a dedicated session for the release:

```bash
# For minor/major release
daf jira new story \
  --parent PROJ-XXXXX \
  --goal "Release version 1.1.0 of DevAIFlow"

# For hotfix
daf jira new bug \
  --parent PROJ-XXXXX \
  --goal "Create hotfix v0.1.1 for timeout bug"
```

Then provide Claude with the appropriate prompt from above.

**Benefits:**
- Session is tracked in JIRA
- Can resume if interrupted
- All release work documented
- Easy handoff to reviewers

### Option 2: Direct Claude Session

If not using JIRA:

```bash
# Start Claude in project directory
cd /path/to/devaiflow
claude code

# Then provide release prompt
```

### Review Checklist

Before pushing Claude's changes:

```bash
# 1. Verify versions
cat devflow/__init__.py  # Should be X.Y.Z (no -dev for release)
cat setup.py        # Should match __init__.py

# 2. Check CHANGELOG
cat CHANGELOG.md    # Should have new version section with date

# 3. Verify tests passed
pytest              # Run again to be sure

# 4. Check git state
git log --oneline -5            # Review commits
git tag -l | tail -3             # Verify tag created
git show v1.1.0                 # Review tag annotation

# 5. For release branches
git checkout release/1.1
cat devflow/__init__.py  # Should be X.Y.Z+1-dev (e.g., 0.2.1-dev)

# 6. Check main branch
git checkout main
cat devflow/__init__.py  # Should be X.Y+1.0-dev (e.g., 1.2.0-dev)
```

### Pushing to Remote

After review, push in this order:

```bash
# 1. Push release branch
git push origin release/1.1

# 2. Push tag
git push origin v1.1.0

# 3. Push main (with bumped version)
git checkout main
git push origin main

# 4. Create GitHub release
glab release create v1.1.0 \
  --name "DevAIFlow v1.1.0" \
  --notes "$(sed -n '/## \[1.1.0\]/,/## \[/p' CHANGELOG.md | head -n -1)"
```

## Prompt Templates

### Minimal Prompt (Experienced Users)

```
Create v{X.Y.Z} {minor|major|patch} release per RELEASING.md. Don't push.
```

Claude will read RELEASING.md and execute all steps.

### Detailed Prompt (First Time or Complex Release)

```
Create {minor|major|patch} release v{X.Y.Z} following RELEASING.md.

Read RELEASING.md section "{Release Workflow | Hotfix Workflow}".

Context:
- Current {main|release/X.Y} version: {X.Y.Z-dev}
- JIRA Epic/Issue: PROJ-XXXXX
- {Additional context specific to this release}

{For hotfix: Describe bug to fix}
{For major: List breaking changes}

Execute all steps from RELEASING.md:
- {Highlight any special considerations}

Do NOT push to remote.

Show me:
- All changes made
- Test results
- Branches/tags created
- Any warnings or issues
```

### Prompt for Troubleshooting

```
The release process failed at {step description}.

Error: {paste error message}

Please:
1. Diagnose the issue
2. Recommend how to fix it
3. If safe, fix it and continue
4. If not safe, explain what I need to do manually

Reference RELEASING.md for correct process.
```

## Common Scenarios

### First Release Ever

```bash
daf jira new story --parent PROJ-XXXXX --goal "Create first release v0.1.0"

# Prompt:
Create first release v0.1.0 following RELEASING.md.
Current main: 0.1.0-dev. No release branches exist yet.
Don't push.
```

### Security Hotfix (Urgent)

```bash
daf jira new bug --parent PROJ-XXXXX --goal "URGENT: Security hotfix v1.0.1"

# Prompt:
URGENT security hotfix v1.0.1 from v1.0.0 per RELEASING.md.
Vulnerability: [CVE or description]
Fix: [security patch details]
Add tests, run full suite. Don't push yet.
```

### Skipping a Version (e.g., 1.1.0 → 1.2.0)

```
# Normal process - just bump to desired version
Create v1.2.0 minor release from main (currently 1.2.0-dev).
Skipping 1.1.0 was intentional. Follow RELEASING.md.
```

## daf release Command

The `daf release` command automates the mechanical parts of the release process, ensuring consistency and reducing human error.

### Basic Usage

```bash
# Auto-detects release type from version numbers
daf release 1.1.0                    # Minor release (1.1.0-dev → 1.1.0)
daf release 1.0.0                    # Major release (0.x.x → 1.0.0)
daf release 0.1.1 --from v0.1.0      # Patch release from tag

# Preview changes without executing
daf release 1.1.0 --dry-run

# Emergency release (bypass test failure prompts)
daf release 1.1.0 --force
```

### What the Command Does

The command **automates the mechanical steps** from RELEASING.md:

1. **Checks permissions** - Requires Maintainer or Owner access (GitLab 40/50, GitHub maintain/admin)
2. **Creates appropriate branch** - `release/X.Y` for minor/major, `hotfix/X.Y.Z` for patches
3. **Updates version files** - `devflow/__init__.py` and `setup.py`
4. **Updates CHANGELOG.md** - Adds new version section with current date and auto-generated content from PR/MR metadata
5. **Commits changes** - Professional commit message with co-authorship
6. **Runs unit tests** - Full pytest suite (blocks release if failed)
7. **Runs integration tests** - Prompts if failed (can continue with confirmation or `--force`)
8. **Creates git tag** - Annotated tag `vX.Y.Z`
9. **Bumps dev version** - Next patch dev on release branch
10. **Shows summary** - Next steps for pushing and creating releases

### Approving and Completing a Release

After running `daf release`, you can use `daf release <M.m.p> approve` to complete the post-release steps:

```bash
# 1. Prepare release
daf release 1.1.0

# 2. Review the changes
git log -3
git show v1.1.0
git diff main..release/1.1

# 3. Approve and complete
daf release 1.1.0 approve
```

**What `daf release approve` does:**

1. **Validates release preparation** - Verifies tag exists and versions are correct
2. **Pushes to remote** - Pushes release branch (if exists) and tag
3. **Creates platform release** - Creates GitLab or GitHub release with CHANGELOG content
4. **Merges to main** - For minor/major releases only: merges release branch to main and bumps to next minor dev version

**For minor/major releases (1.1.0):**
- Pushes `release/1.1` and `v1.1.0`
- Creates GitLab/GitHub release
- Merges `release/1.1` to `main`
- Bumps `main` to `1.2.0-dev`

**For patch releases (0.1.1):**
- Pushes `v0.1.1`
- Creates GitLab/GitHub release
- No main branch changes

**Options:**
- `--dry-run` - Preview all actions without executing

### Security & Permissions

The command includes **cross-platform permission checking**:

- **GitLab**: Requires Maintainer (level 40) or Owner (level 50)
- **GitHub**: Requires "maintain" role or "admin" permission
- Works with both GitLab (including self-hosted) and GitHub
- Cannot be run from inside Claude Code sessions (`@require_outside_claude`)

### Integration Tests

Integration tests **always run** to ensure release quality:

- Automatically discovers and runs:
  - `integration-tests/test_collaboration_workflow.sh`
  - `integration-tests/test_jira_green_path.sh`
- If tests **fail**:
  - Shows which tests failed
  - Prompts: "Continue with release despite test failures?"
  - User can abort or proceed
  - Use `--force` to skip prompt (emergency only)

### Release Type Suggestion

Not sure which release type to use? The `--suggest` flag analyzes your commits:

```bash
daf release --suggest
```

**What it does:**
- Analyzes commits since last release
- Looks for conventional commit prefixes (`feat:`, `fix:`, `BREAKING CHANGE:`)
- Suggests appropriate release type (major, minor, or patch)
- Shows breakdown of changes with examples
- Provides exact command to run

**Example output:**
```
═══ Release Type Suggestion ═══

Recommendation: MINOR release

Found 5 new feature(s) and 3 fix(es) since v0.1.0.
Minor release recommended for new features.

┌─ Commit Analysis ─────────────────────────────┐
│ Type              Count    Impact              │
├───────────────────────────────────────────────┤
│ New Features         5    → Requires MINOR     │
│ Bug Fixes            3    → Allows PATCH       │
└───────────────────────────────────────────────┘

Suggested Command:
  daf release 1.1.0
```

### Changelog Auto-Generation

The `daf release` command automatically generates changelog content from merged PR/MR metadata:

**How it works:**
- Analyzes git commits since the last release tag
- Extracts PR/MR numbers from merge commits (GitHub: `#123`, GitLab: `!281`)
- Fetches PR/MR metadata using `gh` (GitHub) or `glab` (GitLab) CLI tools
- Parses PR/MR descriptions for categorized changelog sections
- Extracts JIRA ticket references (e.g., `PROJ-12345`)
- Generates formatted changelog following Keep a Changelog standard

**PR/MR Description Format:**

For best results, structure your PR/MR descriptions with category headers:

```markdown
## Added
- New validation for user input
- Enhanced UI with dark mode support

## Fixed
- Bug in processing timeout
- Memory leak in cache handler
```

**Supported Categories:**
- `Added` - New features
- `Changed` - Changes to existing functionality
- `Fixed` - Bug fixes
- `Deprecated` - Features marked for removal
- `Removed` - Removed features
- `Security` - Security fixes

**Fallback Behavior:**

If no category headers are found, the command categorizes based on conventional commit prefixes:
- `feat:` or `feature:` → **Added**
- `fix:` → **Fixed**
- `refactor:` or `chore:` → **Changed**

**Example Generated Changelog:**

```markdown
## [1.1.0] - 2026-01-20

### Added
- Version reference links in changelog [#281](https://gitlab.com/test/repo/-/merge_requests/281)
- Dark mode toggle support [#282](https://gitlab.com/test/repo/-/merge_requests/282)

### Fixed
- Timeout issue in API calls [#283](https://gitlab.com/test/repo/-/merge_requests/283)
```

**Offline Mode:**

If you're working offline or the `gh`/`glab` CLI tools are unavailable, use the `--skip-pr-fetch` flag:

```bash
daf release 1.1.0 --skip-pr-fetch
```

This creates the version section header without auto-generated content (original behavior).

### Options

```bash
--suggest           # Suggest release type based on commits (no version needed)
--from TAG          # Base tag for patches (e.g., --from v0.1.0)
--dry-run           # Preview all changes without executing
--auto-push         # Push to remote without confirmation (use with caution)
--force             # Force release even if tests fail (emergency use only)
--skip-pr-fetch     # Skip PR/MR metadata fetching (offline mode, no auto-generated changelog)
```

### Example Workflows

#### Minor Release

```bash
# Current state: main at 1.1.0-dev, all features merged, tests pass

# 1. Run release command
daf release 1.1.0

# 2. Review the plan, confirm

# Output shows:
# ✓ Permission check passed
# ✓ Created release/1.1
# ✓ Updated versions to 1.1.0
# ✓ Updated CHANGELOG.md
# ✓ Committed changes
# ✓ All unit tests passed
# ✓ All integration tests passed
# ✓ Created tag v1.1.0
# ✓ Bumped release/1.1 to 0.2.1-dev

# 3. Review changes
git log -3
git show v1.1.0
git diff main..release/1.1

# 4. Approve and complete
daf release 1.1.0 approve

# Output shows:
# ✓ Release preparation validated
# ✓ Pushed release/1.1 to remote
# ✓ Pushed tag v1.1.0 to remote
# ✓ Created GitHub release v1.1.0
# ✓ Merged release/1.1 to main and bumped to 1.2.0-dev
```

#### Patch Release

```bash
# Fix bug on hotfix branch
git checkout -b hotfix/0.1.1 v0.1.0
# ... make fixes, commit ...

# Run release
daf release 0.1.1

# Review
git show v0.1.1

# Approve and complete
daf release 0.1.1 approve

# Output shows:
# ✓ Release preparation validated
# ✓ Pushed tag v0.1.1 to remote
# ✓ Created GitHub release v0.1.1
# Note: Patch release - main branch not modified
```

#### Dry Run (Preview)

```bash
# See what would happen without making changes
daf release 1.1.0 --dry-run

# Shows complete plan:
# - Release type detected
# - Branches that would be created
# - Version changes
# - CHANGELOG updates
# - All steps that would execute
```

### What the Command Does NOT Do

The command **does not replace human judgment**:

- ❌ Does NOT fix bugs (you fix bugs first)
- ❌ Does NOT push to remote (you review first)
- ❌ Does NOT create GitLab/GitHub releases (done via UI or glab/gh)
- ❌ Does NOT merge back to main (you do manually after review)
- ❌ Does NOT make architectural decisions

### Comparison: Manual vs Automated

| Step | Manual (RELEASING.md) | Automated (daf release)|
|------|----------------------|------------------------|
| Create branch | Manual git commands | ✅ Automated |
| Update versions | Manual file editing | ✅ Automated |
| Update CHANGELOG | Manual editing | ✅ **Auto-generated from PRs/MRs** |
| Extract changelog from PRs | Manual review | ✅ Automated |
| Run tests | Manual pytest | ✅ Automated |
| Run integration tests | Manual scripts | ✅ Automated |
| Create tag | Manual git tag | ✅ Automated |
| Bump dev version | Manual editing | ✅ Automated |
| Review changes | ✅ Required | ✅ Required |
| Push to remote | ✅ Manual | ✅ Manual |
| Create release | ✅ Manual | ✅ Manual |

## Best Practices

1. **Always use version control** - Work in a session, commit often
2. **Let Claude read RELEASING.md** - Don't repeat steps, reference the doc
3. **Review before pushing** - Tag is permanent, get it right
4. **Test thoroughly** - Run full suite before release
5. **Document in JIRA** - Track releases as stories/bugs
6. **Use semantic versioning** - Follow MAJOR.MINOR.PATCH strictly
7. **Update CHANGELOG** - Users need to know what changed

## Troubleshooting

### "Claude didn't follow RELEASING.md correctly"

```
Please re-read RELEASING.md section "{specific section}" and correct the process.
You missed step {X}: {describe what's wrong}.
```

### "Tests failed during release"

```
Don't proceed with release. Tests are failing:
{paste test output}

Please fix the failing tests first, then restart release process.
```

### "Forgot to bump release branch"

See [PROJ-61121](https://jira.example.com/browse/PROJ-61121) - this was fixed by updating RELEASING.md to include explicit step 7.

```
Please bump release/{X.Y} branch to {X.Y.Z+1-dev} per RELEASING.md step 7.
```

## Related Documentation

- **[RELEASING.md](../RELEASING.md)** - Complete technical release process (Claude reads this)
- **[CHANGELOG.md](../CHANGELOG.md)** - Version history and release notes
- **[AGENTS.md](../AGENTS.md)** - Development and release guidelines
- **[docs/07-commands.md](07-commands.md)** - daf command reference

## Questions?

- Check [RELEASING.md](../RELEASING.md) for detailed steps
- Ask team in Slack/Teams channel
- Create JIRA issue with label `release-management`
- Review previous releases for examples

---

**Remember**: The detailed process is in RELEASING.md. This guide shows you how to use Claude to execute that process efficiently.
