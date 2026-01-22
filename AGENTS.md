# Agent Instructions for DevAIFlow

## General Instructions

**IMPORTANT**: The following general instructions apply to the DevAIFlow project and MUST be followed when contributing to this codebase.

**For JIRA operations**: This project uses the `daf` tool for issue tracker integration. Always use `daf jira` commands (documented in DAF_AGENTS.md), NOT direct API calls.

---

### Git Workflow

**IMPORTANT**: Never commit directly to the `main` branch. Always create a feature branch before making any commits.

#### Creating Branches and Pull Requests

1. **Update main branch** before creating a new branch:
   ```bash
   git checkout main
   git pull origin main
   ```
   **IMPORTANT**: Always ensure your main branch is up-to-date before creating a new feature branch.

2. **Create a branch** from the updated main branch:
   ```bash
   git checkout -b <ISSUE-KEY>-<short-description>
   ```
   Example: `git checkout -b proj-12345-fix-validation`

3. **Make your changes** and commit them to the branch

4. **Push the branch** to remote:
   ```bash
   git push -u origin <branch-name>
   ```

5. **Create a draft PR** using the template from @.github/PULL_REQUEST_TEMPLATE.md using `gh` CLI

#### Creating Pull Requests

##### Installation

```bash
# macOS
brew install gh

# Linux (Debian/Ubuntu)
sudo apt install gh

# Windows
winget install GitHub.cli

# Other platforms: https://cli.github.com/
```

##### Authentication

```bash
# Interactive authentication
gh auth login

# Or with a token
export GITHUB_TOKEN="your-github-token"
gh auth login --with-token < <(echo $GITHUB_TOKEN)
```

**Note**: To create a personal access token for GitHub:
1. Go to GitHub Settings > Developer settings > Personal access tokens
2. Create a token with `repo` scope
3. Save the token securely

##### Creating a Pull Request

```bash
gh pr create --draft --title "PROJ-12345: Your PR Title" --body "$(cat <<'EOF'
## Description

[Describe your changes here]

## Testing

### Steps to test
1. Pull down the PR
2. [Add specific test steps]
3. [Additional steps]

### Scenarios tested
- [ ] Test scenario 1
- [ ] Test scenario 2

## Deployment considerations
- [ ] This code change is ready for deployment on its own
- [ ] This code change requires the following considerations before being deployed:

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

**Important Notes:**
- Always use the template format shown above
- Always include "Co-Authored-By: Claude <noreply@anthropic.com>" when AI assistance is used
- The PR body must follow the template structure

#### Commit Message Format

When creating commits, follow this format:

```bash
git commit -m "$(cat <<'EOF'
Brief summary of changes (imperative mood, < 50 chars)

More detailed explanation if needed. Explain what and why, not how.
- Bullet points are acceptable
- Use present tense

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

**IMPORTANT**:
- All commits made with AI assistance MUST include the `Co-Authored-By` field (GitHub standard)
- Format: `Co-Authored-By: <Name> <email>` (e.g., `Co-Authored-By: Claude <noreply@anthropic.com>`)

#### Updating Existing Pull Requests

**IMPORTANT**: When pushing additional commits to a branch that already has an open PR, you MUST update it to reflect the changes:

1. **Update the PR title** if the scope or focus of the changes has evolved
2. **Update the PR body** to document what functionality was:
   - Added (new features or capabilities)
   - Changed (modifications to existing functionality)
   - Deleted (removed features or code)

**The PR body MUST continue to follow the template structure**.

This ensures reviewers have a clear understanding of all changes without having to parse through individual commits.

```bash
# Update PR title
gh pr edit <PR-NUMBER> --title "Updated title reflecting all changes"

# Update PR body (use a file for complex updates)
# IMPORTANT: Maintain the template structure and include Co-Authored-By field
gh pr edit <PR-NUMBER> --body "$(cat <<'EOF'
## Description
- Added: New validation for instance names
- Changed: Refactored error handling in subscription service
- Deleted: Deprecated legacy API endpoints

[Additional context about the changes]

## Testing
### Steps to test
1. Pull down the PR
2. ...

### Scenarios tested
[Describe tested scenarios]

## Deployment considerations
- [ ] This code change is ready for deployment on its own
- [ ] This code change requires the following considerations before being deployed:

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

**IMPORTANT**: All PRs created with AI assistance MUST include the `Co-Authored-By:` field at the end of the description.

#### Branch Naming Convention

Format: `<ISSUE-KEY>-<short-description>`
- Use lowercase with hyphens
- Keep the description concise but meaningful
- Examples:
  - `proj-123-keep-reason-debugging`
  - `proj-456-instance-name-validation`
  - `proj-789-fix-subscription-status`

### GITHUB Pull Requests

The template @.github/PULL_REQUEST_TEMPLATE.md must be used to create pull requests.
The PR must be created as draft.

#### AI Assistant Attribution

When creating pull requests, the `Assisted-by: <name of code assistant>` field in the PR description must be updated with the name of the code assistant used (e.g., "Cursor AI", "GitHub Copilot", "Claude", etc.).

**Note**: Use the `Assisted-by:` tag instead of `Co-Authored-by:` for AI assistant attribution.


### DevAIFlow (daf tool)

**IMPORTANT**: For instructions on using the `daf` tool (DevAIFlow) for JIRA operations, session management, and workflows, see [DAF_AGENTS.md](DAF_AGENTS.md).

The DAF_AGENTS.md file is automatically loaded when you open sessions via `daf open` and contains:
- Complete `daf jira` command reference
- Session management workflows
- JIRA integration best practices
- Configuration and troubleshooting

**Quick reference:**
- View JIRA tickets: `daf jira view PROJ-12345`
- Create JIRA issues: `daf jira create {bug|story|task} --summary "..." --parent PROJ-12345`
- Update JIRA issues: `daf jira update PROJ-12345 --description "..."`
- Session management: `daf new`, `daf open`, `daf complete`
- Configuration: `daf config tui

For complete documentation, refer to DAF_AGENTS.md.

#### Safety Guards: Commands That Cannot Run Inside Claude Code

**CRITICAL**: Most `daf` commands are protected by safety guards to prevent data integrity issues from nested sessions, concurrent metadata modifications, and session state corruption.

**Commands BLOCKED inside Claude Code** (will exit with error):
- Session lifecycle: `daf new`, `daf open`, `daf complete`, `daf delete`
- Session metadata: `daf update`, `daf sync`, `daf link`, `daf note` (add notes)
- Session creation: `daf jira new` (creates sessions)
- Data operations: `daf export`, `daf import`, `daf backup`, `daf restore`
- Maintenance: `daf cleanup`, `daf cleanup-sessions`, `daf discover`, `daf repair`
- Configuration: `daf context add/remove/reset`, `daf template save/delete`
- Time tracking writes: `daf pause`, `daf resume`

**Commands ALLOWED inside Claude Code** (read-only or specifically designed for use inside sessions):
- Query commands: `daf active`, `daf status`, `daf list`, `daf info`
- Read-only JIRA: `daf jira view`, `daf jira create`, `daf jira update` (API operations only)
- Session notes: `daf notes` (view notes)
- Configuration: `daf config show`
- Templates: `daf template list`, `daf template show`
- Context: `daf context list`
- Time tracking: `daf time`
- Release: `daf release --dry-run`, `daf release --suggest`, `daf release <M.m.p> approve --dry-run` (read-only modes)

**Implementation**:
All blocked commands use the `@require_outside_claude` decorator from `devflow/cli/utils.py`. This decorator checks for the `DEVFLOW_IN_SESSION` environment variable and provides a clear error message if the command is run inside an AI agent session (Claude Code, Cursor, GitHub Copilot, Windsurf, etc.).

**Why this matters**:
Running metadata-modifying commands inside Claude Code can cause:
- Nested session creation and confusion
- Concurrent modifications to session metadata
- Session state corruption
- Lost work from conflicting updates

If you encounter this error, exit Claude Code and run the command from a regular terminal.

Use the GitHub REST API to fetch files when:
1. Reading referenced documentation from other private repositories
2. Retrieving templates or configuration files from organization repositories
3. Accessing files that are referenced in project-specific AGENT.md files
4. Any automated operation that needs to read files from private GitHub repositories

**Do NOT** use this for public repositories where direct URL fetching would work without authentication.

---

## Project-Specific Instructions for DevAIFlow

This file provides additional project-specific guidance for working with the DevAIFlow codebase.

## Overview

A Python CLI/TUI tool to manage AI coding assistant sessions with issue tracker integration. This tool helps developers manage one focused session per issue, avoiding context pollution and enabling easy session resumption. Supports Claude Code, GitHub Copilot, Cursor, and Windsurf.

## Architecture

### Core Components
- **CLI Layer** (`devflow/cli/`) - Command-line interface using Click
- **Session Management** (`devflow/session/`) - Core session CRUD operations, session ID capture
- **JIRA Integration** (`devflow/jira/`) - JIRA REST API client for ticket operations
- **Configuration** (`devflow/config/`) - Config file loading and validation
- **UI Components** (`devflow/ui/`) - TUI using Textual (Phase 4)
- **Utilities** (`devflow/utils/`) - Helper functions (file ops, formatting, time tracking)

### Data Flow
1. User runs `daf open PROJ-12345`
2. CLI parses command → calls session manager
3. Session manager checks `~/.daf-sessions/sessions.json`
4. If exists: load session metadata, resume AI assistant
5. If not: fetch issue, create session, launch AI assistant
6. Issue tracker integration handles status transitions
7. Time tracking starts/resumes

## Key Design Decisions

If you need details on the Design, you can be follow this link [Design](./design/*.md)

### Python-First
- **Language**: Python 3.10, 3.11, or 3.12 (officially tested and supported; 3.9 may work but is not tested)
- **CLI Framework**: Click (simple, widely used, excellent docs)
- **TUI Framework**: Textual (modern, rich features, beautiful output)
- **Config**: Pydantic (type-safe config validation)
- **Packaging**: pip (standard Python package installation)

### Session Storage
- `~/.daf-sessions/sessions.json` - Main index (JIRA key → Claude UUID mapping)
- `~/.daf-sessions/sessions/{JIRA-KEY}/` - Per-session data
  - `metadata.json` - Session details
  - `notes.md` - Progress notes
  - `memory.md` - Optional context hints

### JIRA Integration
- Uses JIRA REST API directly (via `requests` library)
- No external CLI dependencies required
- Requires JIRA API token (set via `JIRA_API_TOKEN` environment variable)
- Graceful degradation on failures (warn but continue)
- **User Identification:**
  - JIRA queries use `currentUser()` JQL function (auto-resolved by JIRA from Bearer token)
  - Time tracking uses system username from `getpass.getuser()` (for multi-user machines)

### Session ID Capture
- Monitor `~/.claude/projects/{encoded-path}/` for new `.jsonl` files
- Poll every 500ms with 10-second timeout
- Fallback: prompt user to enter session ID

## Coding Standards

### Python Style
- Follow PEP 8 (enforced by Black formatter)
- Line length: 100 characters
- Use type hints for all function signatures
- Docstrings for all public functions (Google style)

### Project Structure
```python
devflow/
├── __init__.py
├── cli/
│   ├── __init__.py
│   └── main.py         # Click CLI entry point
├── session/
│   ├── __init__.py
│   ├── manager.py      # Session CRUD operations
│   └── capture.py      # Session ID capture logic
├── jira/
│   ├── __init__.py
│   └── client.py       # JIRA REST API client
├── config/
│   ├── __init__.py
│   └── models.py       # Pydantic config models
├── ui/
│   ├── __init__.py
│   └── tui.py          # Textual TUI (Phase 4)
├── cli_skills/         # Bundled skills (source of truth)
│   └── daf-cli/
│       └── SKILL.md    # daf CLI skill definition
├── claude_commands/    # Bundled Claude commands (source of truth)
│   ├── daf-*.md        # daf-specific commands
│   └── *.md            # Other project commands
└── utils/
    ├── __init__.py
    ├── file_ops.py     # File operations
    ├── time_tracking.py
    └── formatting.py   # Rich console formatting
```

### Skills and Claude Commands Locations

**IMPORTANT**: When updating skills or Claude commands, you must update files in MULTIPLE locations:

#### Skills
There are THREE locations for skill files:

1. **Bundled skills (PRIMARY SOURCE OF TRUTH)**: `devflow/cli_skills/daf-cli/SKILL.md`
   - This is the authoritative version that ships with the pip package
   - Updated via `daf upgrade` command to install/upgrade to user's workspace
   - **ALWAYS update this file first when making changes**

2. **Development workspace**: `.claude/skills/daf-cli/SKILL.md` (in this repository)
   - Local copy used during development of the DevAIFlow tool itself
   - Allows immediate testing without running `daf upgrade`
   - Should be kept in sync with bundled version for consistency

3. **User home directory**: `~/.claude/skills/daf-cli/SKILL.md`
   - User's local copy installed via `daf upgrade`
   - Gets updated when users run `daf upgrade` (auto-copies from bundled version)
   - End users interact with this file

**When to update skills:**
- After adding/modifying daf CLI commands
- After changing command options or behavior
- After updating command examples or usage patterns

**Update workflow:**
1. Edit `devflow/cli_skills/daf-cli/SKILL.md` (bundled/primary version)
2. Edit `.claude/skills/daf-cli/SKILL.md` (development copy for immediate testing)
3. Users run `daf upgrade` to sync to their `~/.claude/skills/` directory
4. Verify changes appear in all three locations

#### Claude Commands
1. **Bundled commands (source of truth)**: `devflow/claude_commands/*.md`
   - Authoritative versions that ship with the package
   - Updated via `daf upgrade` command

2. **User workspace**: `~/.claude/commands/*.md`
   - User's local copies installed via `daf upgrade`
   - Gets updated when user runs `daf upgrade`

**When to update Claude commands:**
- After adding new daf-specific workflows
- After changing command patterns or best practices
- When adding new automation capabilities

**Update workflow:**
1. Edit files in `devflow/claude_commands/` (bundled versions)
2. Users run `daf upgrade` to sync to their workspace
3. During development, also update `~/.claude/commands/*.md` for immediate testing

### Error Handling

**Exception-Based Error Handling:**
The project uses exception-based error handling for all JIRA operations. This provides:
- Clean architectural separation: client handles API, commands handle presentation
- Rich error information preserved through exception attributes
- Detailed JSON error responses with error codes and context
- Better error handling and debugging capabilities

**JIRA Exception Hierarchy:**
```python
from daf.jira.exceptions import (
    JiraError,           # Base exception for all JIRA errors
    JiraAuthError,       # Authentication failures (401/403, missing API token)
    JiraApiError,        # General API errors (HTTP errors, unexpected responses)
    JiraNotFoundError,   # Resource not found (404)
    JiraValidationError, # Validation errors (400 with field errors)
    JiraConnectionError  # Network/connection failures
)
```

**Exception Attributes:**
- `JiraAuthError`: `status_code`
- `JiraApiError`: `status_code`, `response_text`, `error_messages`, `field_errors`
- `JiraNotFoundError`: `resource_type`, `resource_id`
- `JiraValidationError`: `field_errors`, `error_messages`

**Client Layer (devflow/jira/client.py):**
- All methods raise exceptions instead of returning False or None
- Methods that returned `bool` now return `None` and raise exceptions on failure
- Methods that returned `Optional[X]` now return `X` and raise `JiraNotFoundError` for 404
- NO console.print() calls in client layer - exceptions carry all error context

**Command Layer (devflow/cli/commands/):**
- Commands catch exceptions and decide JSON vs text output
- Display rich error information to users (field errors, status codes, etc.)
- Use console.print() for user-facing error messages
- Example pattern:
```python
try:
    jira_client.update_issue(key, payload)
    # Success handling
except JiraValidationError as e:
    if output_json:
        json_output(success=False, error={
            "code": "VALIDATION_ERROR",
            "field_errors": e.field_errors,
            "error_messages": e.error_messages
        })
    else:
        console.print(f"[red]✗[/red] {e}")
        for field, msg in e.field_errors.items():
            console.print(f"  [red]• {field}: {msg}[/red]")
except JiraNotFoundError as e:
    # Handle not found...
except JiraAuthError as e:
    # Handle auth error...
```

**General Error Handling:**
- Use custom exceptions for domain errors
- Graceful degradation for external dependencies (JIRA, git)
- Rich error messages with actionable suggestions

### Testing
- Unit tests for all modules (pytest)
- Integration tests for critical flows
- Mock external dependencies (JIRA REST API, Claude Code)
- Target: >80% code coverage
- **Run tests using `pytest` command** (not `python -m pytest`)

### Testing Guidelines

**Integration Tests**: Can be run from inside AI agent sessions using the test runner script `./run_all_integration_tests.sh`, which uses environment isolation (unsets `DEVFLOW_IN_SESSION` and `AI_AGENT_SESSION_ID`, sets temporary `DEVFLOW_HOME`) to avoid conflicts. Individual test scripts still require running outside AI agent sessions unless you manually set up the isolated environment.

**Debug Mode for Integration Tests**: All integration test scripts support a `--debug` flag that enables verbose bash output (`set -x`) for easier troubleshooting:
```bash
# Run all integration tests with debug output
cd integration-tests
./run_all_integration_tests.sh --debug

# Run a single test with debug output
./test_jira_green_path.sh --debug
```
When `--debug` is used with the test runner, it automatically propagates to all sub-test scripts, showing detailed command execution traces to help identify where tests are hanging or failing.

**⚠️ CRITICAL TESTING REQUIREMENT**: ALL TESTS MUST BE SUCCESSFUL before marking any task as complete. When tests fail:
- **DO NOT** ask the user for permission to continue fixing tests
- **DO NOT** stop after fixing some tests - continue fixing ALL failing tests
- **ALWAYS** run the full test suite (`pytest`) after every change
- **ONLY** mark the task as complete when ALL 2000+ tests pass
- If you encounter test failures, continue fixing them systematically until every test passes

**IMPORTANT**: These testing requirements must be followed for all code changes:

1. **Create Tests for New Methods**
   - When creating any new method or function, **always create a corresponding test**
   - Test files should mirror the structure of the source code (e.g., `devflow/session/manager.py` → `tests/test_session_manager.py`)
   - Tests must cover:
     - Happy path (expected behavior)
     - Error cases (exceptions, edge cases)
     - Boundary conditions
     - Integration with other components (using mocks)

2. **Run Full Test Suite After Each Task**
   - **After completing each task**, run the complete test suite using `pytest`
   - Verify that all tests pass before marking a task as complete
   - This ensures that new changes don't break existing functionality
   - If any tests fail:
     - Fix the failing tests immediately
     - Investigate whether the failure indicates a regression
     - Update tests if the new behavior is intentional

3. **Run Integration Tests**
   - Integration tests are located in `integration-tests/` directory
   - **Run all tests**: Use `./run_all_integration_tests.sh` to run the complete test suite
     - **Can be run from inside Claude Code** - uses environment isolation to avoid conflicts
     - Normal mode: `./run_all_integration_tests.sh`
     - Debug mode: `./run_all_integration_tests.sh --debug` (enables `set -x`)
     - Output saved to `/tmp/daf_integration_tests_YYYYMMDD_HHMMSS.log`
     - Fails fast (exits on first test failure)
   - **Environment isolation**: The test runner automatically:
     - Unsets `DEVFLOW_IN_SESSION` to bypass safety guards
     - Unsets `AI_AGENT_SESSION_ID` to isolate from parent session
     - Sets `DEVFLOW_HOME` to `/tmp/daf-integration-tests-$$` for data isolation
     - Restores original environment variables on exit
     - Cleans up temporary data directory
     - This ensures integration tests don't interfere with your actual session
   - Available integration tests:
     - `./test_jira_green_path.sh` - Complete JIRA workflow (new → update → open → complete)
     - `./test_collaboration_workflow.sh` - Export/import and multi-session support
     - `./test_time_tracking.sh` - Time tracking features (pause, resume, time command)
     - `./test_templates.sh` - Template system (save, list, use, delete)
     - `./test_jira_sync.sh` - JIRA sync features (sprint sync, ticket sync)
     - `./test_readonly_commands.sh` - Read-only commands that work inside Claude Code
     - `./test_multi_repo.sh` - Multi-repository workflow (cross-repo features, conversation isolation)
     - `./test_session_lifecycle.sh` - Session lifecycle (link, unlink, delete operations)
     - `./test_investigation.sh` - Investigation-only sessions (read-only mode, no branch)
     - `./test_error_handling.sh` - Error handling and validation (edge cases, graceful failures)
   - Integration tests validate end-to-end workflows and catch issues that unit tests miss
   - **Do not mark work as complete** until integration tests pass
   - If integration tests fail:
     - Review the test output carefully
     - Fix any issues in your implementation
     - Update integration test expectations if behavior changed intentionally

4. **Testing Best Practices**
   - Use `monkeypatch` for mocking in pytest
   - Mock external dependencies (JIRA API, subprocess calls, file system operations)
   - Use `temp_cs_home` fixture for tests that need a clean session directory
   - Name test functions descriptively: `test_<function_name>_<scenario>`
   - Keep tests focused and independent (each test should be runnable in isolation)

**Example Testing Workflow**:
```bash
# 1. Implement new method in devflow/session/manager.py
# 2. Create test in tests/test_session_manager.py
# 3. Run tests to verify new functionality (can run inside Claude Code)
pytest tests/test_session_manager.py

# 4. Run full test suite before completing task (can run inside Claude Code)
pytest

# 5. Run integration tests (can run inside Claude Code with test runner)
cd integration-tests && ./run_all_integration_tests.sh

# 6. Only mark task as complete if ALL tests pass (unit + integration)
```

### Documentation Updates

**IMPORTANT**: When completing a task that adds new features or changes existing functionality, you MUST update the relevant documentation:

1. **Update README.md** if the changes affect:
   - Core features or key functionality
   - Installation or setup process
   - Quick start examples
   - High-level overview of the tool

2. **Update dodevflow/** files when:
   - Adding new commands → update `dodevflow/07-commands.md`
   - Changing command behavior → update relevant docs file
   - Adding new workflows → update `dodevflow/14-workflows.md`
   - Changing configuration → update `dodevflow/06-configuration.md`
   - Adding troubleshooting info → update `dodevflow/11-troubleshooting.md`

3. **Update design/** files when:
   - Changing architecture or design decisions → update `design/` files
   - Adding new integration points → update relevant design docs
   - Modifying data models or schemas → update technical design docs

4. **Update AGENT.md** when:
   - Completing a feature tracked in JIRA → add to "Completed Enhancements" section
   - Adding new coding standards or best practices
   - Changing development workflows or testing requirements

**Documentation Update Checklist:**
```bash
# After completing a task, check:
- [ ] Is this a user-facing feature? → Update dodevflow/07-commands.md
- [ ] Does this change how users interact with the tool? → Update relevant dodevflow/
- [ ] Is this tracked in JIRA and now complete? → Update AGENT.md "Completed Enhancements"
- [ ] Does this change core architecture? → Update design/ files
- [ ] Does this affect the README overview? → Update README.md
```

**Example Workflow:**
```bash
# 1. Complete feature (e.g., daf jira view command)
# 2. Update documentation:
#    - Add command to dodevflow/07-commands.md
#    - Add to quick reference table in dodevflow/07-commands.md
#    - Update relevant design docs
#    - Add to AGENT.md "Completed Enhancements" section if applicable
# 3. Verify all tests pass
# 4. Mark task as complete
```

### JSON Output Implementation

**IMPORTANT**: All CLI commands support `--json` flag for machine-readable output. When implementing or modifying commands, you MUST ensure clean JSON output without mixed text.

#### The Problem

Commands that output both informational text AND JSON break JSON parsing for automation:

```bash
# BAD - Mixed text and JSON
$ daf jira create bug --summary "Test" --json
Using project from config: "PROJ"
Discovering JIRA custom field mappings...
{"success": true, "data": {...}}
```

This mixed output cannot be parsed as JSON.

#### The Solution: `console_print()` Pattern

Use the `console_print()` wrapper function that automatically suppresses output when `--json` mode is active:

```python
from daf.cli.utils import console_print

# This will only print if NOT in JSON mode
console_print("[green]✓[/green] Operation successful")
console_print(f"[dim]Using config value: {value}[/dim]")
```

#### Implementation Steps

**1. Import the Helper** (in CLI command files: `devflow/cli/commands/*.py`):

```python
from daf.cli.utils import console_print
```

**2. Replace console.print() Calls**:

```python
# Before
if not is_json_mode():
    console.print("[dim]Using cached field mappings from config[/dim]")

# After
console_print("[dim]Using cached field mappings from config[/dim]")
```

**3. For Lower-Level Modules** (e.g., `devflow/jira/client.py`):

Lower-level modules can't import from `daf.cli.utils` due to circular dependencies. Use local wrappers:

```python
def _is_json_mode() -> bool:
    """Check if --json flag is active."""
    return "--json" in sys.argv

def _console_print(*args, **kwargs) -> None:
    """Print to console only if not in JSON mode."""
    if not _is_json_mode():
        console.print(*args, **kwargs)
```

#### Best Practices

**DO** ✅:
- Wrap ALL informational output with `console_print()`
- Wrap success and error messages
- Keep prompts conditional (check `is_json_mode()` before prompting)
- Use standardized `json_output()` function for JSON responses

**DON'T** ❌:
- Don't use bare `console.print()` in JSON-enabled commands
- Don't forget error handling output
- Don't output JSON without the wrapper

#### Testing JSON Output

**NOTE FOR AI ASSISTANTS**: The examples below use `DAF_MOCK_MODE=1` for developer testing only. When working in AI assistant sessions, NEVER use `DAF_MOCK_MODE=1` - always run commands without this prefix (e.g., `daf jira view PROJ-12345`, not `DAF_MOCK_MODE=1 daf jira view PROJ-12345`).

Verify clean JSON output (for developers testing the tool):

```bash
# Should output ONLY valid JSON, no text
# NOTE: DAF_MOCK_MODE=1 is ONLY for testing the daf tool itself, NOT for use in AI assistant sessions
DAF_MOCK_MODE=1 daf jira create bug --summary "Test" --description "Test" --priority Major --json
DAF_MOCK_MODE=1 daf jira view PROJ-12345 --json
DAF_MOCK_MODE=1 daf sync --json
```

For complete implementation details, see [JSON_OUTPUT_GUIDE.md](JSON_OUTPUT_GUIDE.md).

## Context Files for Initial Prompts

The tool supports configurable context files that are automatically included in the initial prompt when creating or opening sessions. This helps Claude understand your project's context, standards, and architecture.

### Default Context Files

Two files are always included (if they exist):
- **AGENT.md** - Agent-specific instructions
- **CLAUDE.md** - Project guidelines and standards

### Additional Context Files

You can configure additional context files using `daf config context` commands. Context files can be:
- **Local files** (e.g., `ARCHITECTURE.md`, `DESIGN.md`) - Claude will use the Read tool
- **URLs** (e.g., GitHub/GitLab raw URLs) - Claude will use the WebFetch tool

### Managing Context Files

```bash
# List all configured context files
daf config context list

# Add a local file
daf config context add ARCHITECTURE.md "system architecture"

# Add a URL
daf config context add https://github.com/org/repo/blob/main/STANDARDS.md "coding standards"

# Remove a context file
daf config context remove ARCHITECTURE.md

# Reset to defaults (removes all configured files)
daf config context reset
```

### How It Works

When you create or open a session:
1. The initial prompt includes instructions to read default files (AGENT.md, CLAUDE.md)
2. Any configured additional files are also included
3. Claude automatically detects whether to use Read (local) or WebFetch (URL) based on the path

This ensures Claude has all necessary context before starting work on your task.

## Common Tasks

### Development

**IMPORTANT**: This project uses pip for installation. The `daf` command is installed globally via pip.

```bash
# Install locally for development (from project root)
pip install -e .

# Reinstall after making changes
pip install --upgrade --force-reinstall .

# Run tests
pytest

# Run with coverage
pytest --cov=devflow --cov-report=html

# Format code
black devflow/ tests/

# Lint
ruff check devflow/ tests/

# Type check
mypy devflow/

# Run CLI (after pip install)
daf --help
```

### Installation

```bash
# Install from local directory
pip install .

# Install in editable mode (for development)
pip install -e .

# Uninstall
pip uninstall devaiflow

# Upgrade to latest version
pip install --upgrade .
```

## Implementation Phases

### Phase 1: MVP (Core Functionality)
- Basic CLI structure (Click)
- Session creation and storage
- Simple session list/open commands
- File-based session ID capture

### Phase 2: JIRA Integration
- JIRA REST API client
- Auto status transitions
- `daf sync` command
- Time tracking

### Phase 3: Enhanced UX
- Rich console output
- Smart repo detection
- Export functionality
- Context injection on resume

### Phase 4: TUI
- Textual-based interactive UI
- Keyboard navigation
- Real-time JIRA sync
- Session timeline view

## Dependencies

### Core
- `click` - CLI framework
- `pydantic` - Config validation
- `rich` - Beautiful terminal output
- `requests` - HTTP client for JIRA REST API

### Development
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `black` - Code formatter
- `ruff` - Fast Python linter
- `mypy` - Static type checker

### Future
- `textual` - TUI framework (Phase 4)

## Integration Points

### Claude Code
- Session files: `~/.claude/projects/{encoded-path}/{session-uuid}.jsonl`
- Resume command: `claude --resume {uuid}`
- Launch command: `claude code` (in project directory)

### JIRA REST API
- Authentication: API token via `JIRA_API_TOKEN` environment variable
- Base URL: Configurable via `JIRA_URL` (e.g., `https://jira.example.com`)
- Endpoints used:
  - GET `/rest/api/2/issue/{key}` - Fetch ticket details
  - POST `/rest/api/2/issue/{key}/comment` - Add comments
  - POST `/rest/api/2/issue/{key}/transitions` - Transition status
  - POST `/rest/api/2/issue/{key}/attachments` - Upload files
  - POST `/rest/api/2/search` - Search/list tickets

### Git
- Create branch: `git checkout -b {branch-name}`
- Check status: `git status --porcelain`

## Configuration Schema

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class JiraTransitionConfig(BaseModel):
    from_status: List[str] = Field(alias="from")
    to: str
    prompt: bool = False
    on_fail: str = "warn"

class JiraConfig(BaseModel):
    url: str
    user: str
    transitions: Dict[str, JiraTransitionConfig]
    auto_comment: bool = True
    time_tracking: bool = True

class RepoConfig(BaseModel):
    workspace: str
    detection: Dict[str, str]
    keywords: Dict[str, List[str]]

class Config(BaseModel):
    jira: JiraConfig
    repos: RepoConfig
```

## Session Data Models

```python
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class WorkSession(BaseModel):
    start: datetime
    end: Optional[datetime] = None
    duration: Optional[str] = None
    user: Optional[str] = None  # Username of person who worked on this session

class ConversationContext(BaseModel):
    """Context for a single Claude Code conversation within a session.

    Each conversation represents work in one repository/directory for a session.
    A session can have multiple conversations (one per repository) when working
    on cross-repository features.
    """
    ai_agent_session_id: str  # UUID for Claude Code conversation
    project_path: Optional[str] = None  # Full path to repo
    branch: Optional[str] = None  # Git branch for this repo
    base_branch: str = "main"  # Base branch
    remote_url: Optional[str] = None  # Git remote URL (for fork support)
    created: datetime = Field(default_factory=datetime.now)
    last_active: datetime = Field(default_factory=datetime.now)
    message_count: int = 0
    prs: List[str] = Field(default_factory=list)
    repo_name: Optional[str] = None  # Repository directory name
    relative_path: Optional[str] = None  # Path relative to workspace root
    temp_directory: Optional[str] = None  # For ticket_creation sessions
    original_project_path: Optional[str] = None  # Original path before temp clone

class Session(BaseModel):
    """DevAIFlow session tracking JIRA ticket work.

    IMPORTANT: Multi-conversation architecture
    - Sessions can have multiple conversations (one per repository)
    - Use session.active_conversation to get current conversation
    - Use session.conversations dict to access all conversations by working_dir
    - Per-conversation data: ai_agent_session_id, project_path, branch, message_count, prs
    - Session-level data: issue_key, goal, status, work_sessions
    """
    issue_key: str
    goal: str
    working_directory: str  # Active repository name
    status: str  # created, in_progress, paused, complete
    created: datetime
    last_active: datetime
    conversations: Dict[str, ConversationContext] = {}  # Key: working_dir
    work_sessions: List[WorkSession] = []
    time_tracking_state: str = "paused"
    tags: List[str] = []
    session_type: str = "development"  # development, ticket_creation, investigation

    @property
    def active_conversation(self) -> Optional[ConversationContext]:
        """Get the active conversation based on working_directory.

        Returns None if no conversation exists for current working_directory.
        """
        return self.conversations.get(self.working_directory)
```

## Best Practices

1. **Always use type hints** - Makes code self-documenting and catches errors early
2. **Validate inputs with Pydantic** - Catch configuration errors immediately
3. **Use Rich for output** - Consistent, beautiful terminal UI
4. **Test with mocks** - Don't rely on external services in tests
5. **Log errors, don't swallow** - Help users debug issues
6. **Graceful degradation** - Tool should work even if JIRA/git fails

## Completed Enhancements

- ✓ Learning-based repo suggestions (track which repos are used for which ticket types)
- ✓ Markdown export for session documentation
- ✓ Session templates for reusable configurations
- ✓ AI-powered session summaries
- ✓ Automatic context loading (AGENT.md, CLAUDE.md, JIRA tickets)
- ✓ Store concatenated goal (JIRA key + title) in session.goal field
- ✓ daf sync includes tickets in 'In Progress' status
- ✓ daf open pulls latest changes when creating branch from default
- ✓ daf jira view command for reliable JIRA ticket reading
- ✓ Initial prompt uses daf jira view instead of curl
- ✓ JiraClient uses JIRA_AUTH_TYPE environment variable
- ✓ Comprehensive user documentation and guides
- ✓ Prompt to create PR/MR during daf complete with auto-commit and JIRA linking
- ✓ Custom field discovery for JIRA integration
\- ✓ daf jira update command to update issue fields
- ✓ daf jira create command with project/workstream configuration - Fix for missing project parameter
- ✓ daf config tui
- ✓ Auto-transition JIRA ticket to In Progress when reopening closed session
- ✓ Configurable context files for initial prompts
- ✓ Enhanced daf jira update to support all editable fields with dynamic discovery
  - Editable field discovery using /rest/api/2/issue/{key}/editmeta
  - Support for update-only fields like git-pull-request
  - --git-pull-request option with auto-append functionality
  - daf jira view displays PR links
  - Dynamic CLI option generation for both create and update commands
  - `daf jira update PROJ-12345 --help` discovers and shows all editable fields for that specific issue
  - `daf jira create --help` shows dynamically generated options from cached creation fields
  - Universal --field option for both create and update commands
  - Field type handling for multiurl, option, array, priority, user, version fields
  - Improved formatting for complex fields (version fields show names instead of JSON)
  - Lazy on-demand discovery for update command (no caching, fresh per issue)
  - Cached discovery for create command (stored in config.json, refreshable)
- ✓ Prompt to sync feature branch with base branch when opening sessions
  - Check if branch is behind base branch before opening session
  - Display number of commits behind
  - Prompt user to update with latest changes
  - Support for merge or rebase strategy
  - Graceful conflict handling with clear instructions
  - Auto-fetch from remote for up-to-date comparisons
  - Skip check if branch is up-to-date or not in git repository
- ✓ Session export/import handles git branch synchronization for team handoff
  - Export (daf complete --attach-to-jira): Prompts to commit uncommitted changes and push branch to remote
  - WIP commits created with proper attribution when exporting
  - Import (daf open): Automatically fetches branch from remote if missing
  - Merges remote changes if local branch is behind
  - Graceful handling of missing remote branches
  - Added git utility functions: fetch_and_checkout_branch(), remote_branch_exists()
- ✓ Automated release management with daf release command
  - Auto-detects release type (major, minor, patch) from version numbers
  - Cross-platform permission checking (GitLab 40/50 or GitHub maintain/admin required)
  - Automated version file updates (devflow/__init__.py, setup.py)
  - Automated CHANGELOG.md updates with new version sections
  - Runs complete unit test suite (blocks if failed)
  - Runs integration tests with user confirmation if failed
  - Creates git branches (release/X.Y or hotfix/X.Y.Z)
  - Creates annotated git tags (vX.Y.Z)
  - Automatic dev version bumping for next release
  - Dry-run mode for preview without execution
- ✓ Release approval workflow with daf release approve command
  - Validates release preparation (tag exists, versions correct)
  - Pushes release branch and tag to remote
  - Creates GitLab/GitHub release with CHANGELOG content
  - For minor/major: merges release branch to main and bumps to next minor dev version
  - For patch: pushes tag only, no main branch changes
  - Supports dry-run mode for preview
  - Complete post-release automation (push, release, merge)
  - Force mode for emergency releases
  - Protected from running inside AI assistant sessions
  - Works with both GitHub and GitLab (including self-hosted)
  - Comprehensive test coverage: 60 tests (version parsing, permissions, workflows)
  - Comprehensive test coverage for export/import branch sync
- ✓ Sprint detection type safety improvements in JiraClient
  - Added isinstance() checks before string operations on sprint data
  - Fixed potential None/non-string handling in sprint field extraction
  - Applied to get_ticket(), get_ticket_detailed(), and list_tickets() methods
  - Ensures robust handling of various sprint data formats from JIRA API
- ✓ daf config tui
  - Set workspace directory for repository discovery in daf new/open commands
  - Interactive prompt with current value display
  - Path validation and tilde expansion support
  - Shows count of discovered directories in workspace
  - Documentation added to dodevflow/06-configuration.md and dodevflow/07-commands.md
- ✓ Configurable JIRA comment visibility
  - Added comment_visibility_type and comment_visibility_value config fields
  - JiraClient loads visibility settings from config
  - daf config tui
  - Removed misleading warning in complete_command.py
  - Comprehensive test coverage with 11 tests
  - Documentation added to dodevflow/06-configuration.md and dodevflow/07-commands.md
- ✓ Session info display command
  - daf info command displays detailed session information
  - Shows Claude Code session UUID for manual resumption
  - Displays session metadata, work sessions, and time tracking
  - Useful for debugging and session inspection
- ✓ Repair tool for corrupted Claude Code conversations
  - daf repair command to fix corrupted .jsonl conversation files
  - Handles malformed JSON lines in Claude Code session files
  - Validates and repairs conversation file structure
  - Preserves valid messages while removing corrupted entries
- ✓ Changelog history display in JIRA view
  - daf jira view now displays ticket changelog/history
  - Shows status transitions, assignee changes, and field updates
  - Helps track ticket progress and changes over time
  - Formatted display with timestamps and change details
- ✓ Configurable prompt defaults for session workflow
  - Added prompts configuration section in config
  - auto_commit_on_complete: Skip commit prompt during completion
  - auto_accept_ai_commit_message: Auto-accept AI-generated commit messages
  - auto_add_issue_summary: Auto-add session summary to JIRA
  - auto_create_pr_on_complete: Auto-create PR/MR on completion
  - Reduces repetitive prompts for power users
  - Documentation added to dodevflow/06-configuration.md
- ✓ Git hosting platform detection improvements
  - Improved command syntax for merge/pull request detection
  - Enhanced error handling and messaging
  - Better diagnostics when PR/MR detection fails
- ✓ Comprehensive conflict resolution guidance for daf open
  - Enhanced conflict detection when opening sessions with branch sync
  - Displays detailed conflict information (file count, preview)
  - Provides step-by-step resolution instructions
  - Shows merge vs rebase context in error messages
  - Prevents silent continuation after merge conflicts
- ✓ Interactive TUI for configuration
  - daf config tui command launches interactive configuration interface
  - Built with Textual framework for rich terminal UI
  - Supports all config fields with validation
  - Tab navigation between sections
  - Real-time validation and error feedback
  - Save/cancel workflow
- ✓ Configuration UI enhancements
  - Multi-model dropdown for selecting AI models
  - Improved patch system documentation link in UI
  - Enhanced user experience for patch configuration
- ✓ Branch verification before commit in daf complete
  - Prevents committing to wrong branch if user manually switched branches
  - Checks current branch matches session branch BEFORE marking complete
  - Auto-checkout session branch if no uncommitted changes exist
  - Clear error and abort if uncommitted changes prevent branch switch
  - Comprehensive test coverage for all branch mismatch scenarios
  - Ensures data integrity and prevents accidental commits to wrong branches
- ✓ Session types for specialized workflows
  - Added `session_type` field to Session model (default: "development")
  - Implemented `daf jira new` command for ticket creation workflow
  - Session type "ticket_creation" skips branch creation automatically
  - Analysis-only constraints enforced in initial prompt and on reopen
  - Prevents accidental code modifications during JIRA ticket creation
  - Auto-generates session names from goal description
  - Supports all issue types: epic, story, task, bug
  - Comprehensive test coverage for session types
  - Documentation added to dodevflow/07-commands.md
  - **IMPORTANT for agents**: When in ticket_creation sessions, use the parent value from session goal as `--parent` parameter in `daf jira create` command
- ✓ Fixed branch creation prompt for reopened ticket_creation sessions
  - Fixed bug where reopening a ticket_creation session would incorrectly prompt to create a git branch
  - Session type check now happens BEFORE is_first_launch condition to prevent prompt
  - Ticket creation sessions never prompt for branch creation regardless of session state
  - Test added: test_reopen_ticket_creation_session_never_prompts_for_branch
  - Ensures consistent analysis-only behavior for ticket_creation sessions
- ✓ Parent field mapping system for JIRA issue creation
  - Replaced --epic with --parent parameter in all daf jira create commands
  - Config patch 004-parent-field-mapping.json maps issue types to logical field names
  - Automatic field resolution: story/task/bug → epic_link, sub-task → parent
  - Uses existing field_mappings system (no hardcoded field IDs)
  - Backward compatible with fallback to epic_link
  - Single consistent --parent interface across all commands
  - Ready for future sub-task support
- ✓ Optional Claude prompt to run unit tests and verify they pass
  - Added show_prompt_unit_tests field to PromptsConfig (default: true)
  - Testing instructions shown in initial Claude prompt for development sessions
  - Instructs Claude to run pytest after code changes, create tests for new methods, and fix failures
  - Only shown for development sessions (not ticket_creation or other types)
  - Configurable via daf config tui
  - Can be disabled with daf config tui
  - Integrated into TUI configuration editor
  - Comprehensive test coverage for all scenarios
- ✓ Context file management UI in TUI
  - Interactive context file management directly in the TUI (Context Files tab)
  - Add/Edit/Remove context files with full UI workflow
  - Path validation for local files and URLs (http/https)
  - Required field validation (path and description)
  - Real-time list refresh after add/edit/remove operations
  - Clear visual feedback with notifications for all operations
  - Edit button opens pre-filled modal for modifying existing files
  - Remove button with confirmation via list refresh
  - Keyboard navigation supported (Tab, Enter, Escape)
  - Eliminates need to use CLI commands for context file management
  - Comprehensive test coverage (6 new tests)
  - Documentation updated in dodevflow/06-configuration.md
- ✓ daf complete skips git operations for ticket_creation sessions
  - Added session_type check before commit block (lines 131-185 in complete_command.py)
  - Added session_type check before PR/MR block (lines 187-262 in complete_command.py)
  - Ticket creation sessions skip all git operations (commit, PR/MR)
  - Development sessions continue to perform full git workflow
  - Session still marks as complete and adds JIRA summary for all session types
  - Comprehensive test coverage (new test: test_complete_ticket_creation_session_skips_git_operations)
  - Documentation updated in dodevflow/07-commands.md with session type behavior
- ✓ Portable session export/import with relative repository paths
  - Sessions now store both absolute (project_path) and relative paths (relative_path + repo_name)
  - New sessions automatically compute relative paths from workspace configuration
  - Export/import reconstructs full paths using importer's workspace configuration
  - Enables portable session handoff between team members with different workspace structures
  - Auto-migration converts existing sessions to relative paths when loaded
  - Backward compatible: sessions without relative paths continue to work
  - Comprehensive test coverage (9 new tests in test_portable_paths.py)
  - All existing tests pass (926 tests total)
- ✓ Diagnostic logs included in session export/import for better debugging
  - Export includes all diagnostic logs from ~/.daf-sessions/logs/
  - Import restores logs to namespaced location ~/.daf-sessions/logs/imported/{timestamp}/
  - Logs namespaced by timestamp to avoid conflicts with current logs
  - Preserves diagnostic history for debugging issues across team handoffs
  - Shared implementation in ArchiveManagerBase for both export/import and backup/restore
  - Backup/restore also includes diagnostic logs automatically
  - Comprehensive test coverage (7 new tests: 4 for export/import, 3 for backup/restore)
  - All existing tests pass (984 tests total)
  - Documentation updated in dodevflow/07-commands.md
- ✓ daf notes command to view session notes
  - New `daf notes` command displays all notes for a session in chronological order
  - Supports filtering by session name or JIRA key
  - Supports --latest flag to view notes for most recently active session
  - Displays notes in formatted markdown with timestamps
  - Shows JIRA key if associated with session
  - Comprehensive test coverage (8 new tests for view_notes function)
  - Updated integration tests to use correct syntax (daf note for add, daf notes for view)
  - All tests pass (1028 tests total)
  - Documentation updated in dodevflow/07-commands.md with examples and quick reference table
- ✓ Branch conflict resolution for daf new and daf open commands
  - Detects when suggested branch name already exists before attempting to create
  - Interactive menu with 4 resolution options: add suffix, use existing, custom name, or skip
  - Suffix option automatically validates new name doesn't exist
  - Custom name option allows retry if name conflicts
  - Empty name validation prevents invalid branches
  - Consistent UX between daf new (interactive) and daf open (auto mode for synced sessions)
  - Supports using existing branches (option 2) for continuing work on merged branches
  - Never deletes existing branches to preserve history
  - Comprehensive test coverage (12 new tests in test_branch_conflict.py)
  - All tests pass (1054 tests total)
  - Documentation updated in dodevflow/07-commands.md with examples and use cases
  - Design document updated (design/05-git-integration.md) to mark as implemented
- ✓ Session exports exclude diagnostic logs for privacy
  - Diagnostic logs (complete.log, open.log) are global files containing info from ALL sessions
  - Session exports are for team handoffs and should only include session-specific data
  - Removed _add_diagnostic_logs() call from ExportManager.export_sessions()
  - Removed _restore_diagnostic_logs() call from ExportManager.import_sessions()
  - Backup/restore operations still include diagnostic logs (full system state)
  - Updated tests: test_export_excludes_diagnostic_logs(), test_import_without_diagnostic_logs_succeeds()
  - Documentation updated in dodevflow/07-commands.md with privacy note and comparison table
  - Privacy protection: prevents leaking information about other sessions/tickets during team handoffs
- ✓ Conversation file persistence for temp directory sessions
  - Fixed issue where reopening daf jira new sessions would generate new session IDs instead of resuming
  - Root cause: Temp directories are deleted and recreated on reopen, changing the conversation file path
  - Solution: Backup conversation file before deleting old temp directory, restore to new temp directory
  - Modified conversation file check in open_command.py to skip "new session ID" logic for temp directory sessions
  - Conversation files are now preserved when temp directories are recreated
  - Edge case handling: Works even if temp directory was deleted by system cleanup (conversation file persists in ~/.claude/projects/)
  - Added tests: test_temp_directory_conversation_file_persistence() and test_temp_directory_conversation_file_persistence_when_temp_dir_deleted()
  - All 1083 tests pass
  - Documentation: Conversation files stored at ~/.claude/projects/<encoded_path>/<uuid>.jsonl
  - For temp directory sessions, files are backed up and restored during temp directory recreation
  - Key insight: Conversation files are stored separately from temp directories, so they persist even if temp dir is deleted
- ✓ Import workflow: Branch sync before checkout
  - Fixed issue where daf open prompts to create branch instead of fetching from remote for imported sessions
  - Root cause: _handle_branch_checkout() ran before _sync_branch_for_import(), so it prompted to create before checking remote
  - Solution: Reordered function calls in open_command.py - _sync_branch_for_import() now runs BEFORE _handle_branch_checkout()
  - When opening imported session, if branch doesn't exist locally but exists on remote: automatically fetches and checks out
  - If branch exists locally but is behind remote: prompts to merge/rebase with clear conflict handling
  - Only prompts to create new branch if it doesn't exist on remote either
  - Preserves fork support with remote URL detection for cross-organization collaboration
  - Maintains backward compatibility for daf sync sessions (no branch initially)
  - Added comprehensive test suite: test_branch_import_sync.py with 6 new tests
  - All 1131 tests pass
  - Documentation updated in dodevflow/07-commands.md with explicit reference
- ✓ Version 0.1.0 Release
  - First official release of DevAIFlow
  - Created long-lived release/0.1 branch from main
  - Git tag v0.1.0 created and pushed
  - GitLab release created with changelog and JIRA epic link
  - Merged release branch back to main with --no-ff
  - Version bumped to 0.2.0-dev on main for next development cycle
  - Release management process documented in RELEASING.md
  - Update checker module validates version notifications from GitLab releases
  - All 1224 tests pass on release branch
- ✓ Enhanced slash commands with proper plugin structure and metadata
  - Added YAML frontmatter with description field to daf-list-conversations.md
  - Added YAML frontmatter with description field to daf-read-conversation.md
  - Commands now follow Claude Code plugin documentation standards
  - daf upgrade command preserves frontmatter during installation
  - Commands execute correctly in Claude Code with frontmatter
  - Commands appear in /help with proper descriptions
  - Added 2 new tests to verify frontmatter preservation during install and upgrade
  - All 1226 tests pass
- ✓ Exception-based error handling for JIRA client
  - Replaced boolean return values with exception-based error handling in JiraClient
  - Created custom exception hierarchy (JiraError, JiraAuthError, JiraApiError, JiraNotFoundError, JiraValidationError, JiraConnectionError)
  - All JIRA client methods now raise exceptions instead of returning False or None
  - Exception attributes carry full error context (status_code, field_errors, error_messages, resource_type, resource_id)
  - Removed all console.print() calls from client layer (45 total removed)
  - Command layer now catches exceptions and handles JSON vs text output separation
  - Clean architectural separation: client handles API, commands handle presentation
  - Rich error information preserved through exception attributes
  - Detailed JSON error responses with error codes and field-specific details
  - Updated 13 command files to handle new exception patterns
  - Updated 157+ tests to expect exceptions instead of boolean returns
  - All 1225 tests pass
  - Documentation added to AGENTS.md with exception hierarchy and usage patterns
- ✓ JIRA Wiki markup documentation in daf-cli skill
  - Added comprehensive JIRA Wiki markup requirements to daf-cli skill (devflow/cli_skills/daf-cli/SKILL.md)
  - Syntax comparison table showing Markdown vs JIRA Wiki markup differences
  - Common mistakes section with wrong/correct examples
  - Prominent placement in JIRA Integration section of skill
  - Updated "Tips for Claude Code Sessions" to lead with Wiki markup requirement
  - Skills deployed to workspace via daf upgrade command
  - Makes Wiki markup requirement more visible than DAF_AGENTS.md alone
  - Addresses issue of Claude forgetting to use JIRA Wiki markup in daf jira new sessions
  - All 1229 tests pass
- ✓ Automatic version check and upgrade prompt for DAF_AGENTS.md
  - Added `_get_bundled_daf_agents_content()` to read bundled file content for comparison
  - Added `_check_and_upgrade_daf_agents()` to detect outdated installations and prompt for upgrade
  - Modified `_validate_context_files()` to call upgrade check after finding DAF_AGENTS.md
  - Content comparison detects when installed file differs from bundled version
  - Prompts user: "DAF_AGENTS.md has been updated. Would you like to upgrade to the latest version?"
  - User can accept (upgrade), decline (continue with current), or auto-upgrade in mock mode
  - Upgrade works for both repository and workspace installations
  - Non-blocking: session continues if upgrade declined or if bundled file cannot be read
  - Follows same pattern as `devflow/utils/claude_commands.py` for consistency
  - Comprehensive test coverage: 10 new tests covering all scenarios
  - All 1556 tests pass
  - Documentation updated in docs/02-installation.md with upgrade behavior explanation
- ✓ Official Windows OS support for DevAIFlow
  - Fixed SIGTERM signal handling in 4 command files (new_command.py, investigate_command.py, open_command.py, jira_new_command.py)
  - Windows uses SIGBREAK instead of Unix SIGTERM for graceful shutdown
  - Platform detection automatically selects correct signal handler (sys.platform != "win32")
  - File locking already handled: fcntl skipped on Windows, atomic writes used instead
  - Path handling already cross-platform via pathlib.Path throughout codebase
  - Comprehensive Windows installation documentation added to docs/02-installation.md
    - Prerequisites for Windows (Python, Claude Code CLI, Git installation via winget)
    - PowerShell and Command Prompt installation instructions
    - Environment variable configuration for Windows
    - PATH configuration for Python Scripts directory
    - Windows-specific behaviors documented (file locking, path separators, signal handling)
  - Windows troubleshooting section added to docs/11-troubleshooting.md
    - Command not found in PowerShell
    - Python module not found
    - Git commands failures
    - Permission denied errors
    - Path with spaces issues
    - Claude Code launch failures
    - Line ending issues (CRLF vs LF)
    - Integration tests on Windows (WSL/Git Bash required)
    - PowerShell execution policy
    - File locking issues
    - Unicode/encoding errors
    - Antivirus false positives
    - Windows Defender SmartScreen
  - README.md updated with Supported Platforms section
  - All 1566 unit tests pass (3 skipped)
  - Integration tests require WSL or Git Bash on Windows (documented)
  - Windows 10 and Windows 11 officially supported
- ✓ Remove deprecated fields from Session model after multi-conversation migration
  - Removed backward-compatible properties from Session model that were added during migration
  - Deprecated fields removed: ai_agent_session_id, project_path, branch, message_count, prs, current_* computed properties
  - All code now uses session.active_conversation API for per-conversation data
  - Updated commands: complete_command.py, delete_command.py, import_session_command.py, jira_new_command.py
  - Fixed null checks throughout codebase - all active_conversation accesses now guarded with null checks
  - Updated test fixtures to use add_conversation() API instead of deprecated fields
  - Migration ensures sessions without conversations (e.g., ticket_creation) work correctly
  - All 1566 tests pass (3 skipped)
  - Data model now fully aligned with multi-conversation architecture.
- ✓ Interface abstraction for JiraClient to support multiple issue tracking systems
  - Created IssueTrackerClient interface in devflow/issue_tracker/interface.py
  - JiraClient now implements IssueTrackerClient interface
  - Factory pattern for backend selection (create_issue_tracker_client)
  - Configuration support via issue_tracker_backend field (defaults to "jira")
  - MockIssueTrackerClient for testing without external dependencies
  - All 25 public methods abstracted with clear contracts
  - Fully backward compatible - existing JiraClient imports continue to work
  - Comprehensive test coverage (44 new tests in test_issue_tracker_interface.py)
  - All 1660 tests pass (3 skipped)
  - Architecture ready for GitHub Issues, GitLab Issues, or custom backends
  - Documentation added in docs/issue-tracker-architecture.md
- ✓ Interface abstraction for AI agents to support multiple AI backends
  - Created AgentInterface abstract base class in devflow/agent/interface.py
  - ClaudeAgent implements AgentInterface and encapsulates all Claude Code-specific logic
  - Factory pattern for backend selection (create_agent_client)
  - Configuration support via agent_backend field (defaults to "claude")
  - All 10 agent operations abstracted (launch, resume, capture, session management)
  - SessionCapture refactored to use AgentInterface for backward compatibility
  - Updated PromptsConfig with auto_launch_agent field (backward compatible with auto_launch_claude)
  - should_launch_claude_code() updated with backward compatibility for both config fields
  - Fully backward compatible - existing SessionCapture usage continues to work
  - Comprehensive test coverage (22 new tests in test_agent_interface.py)
  - All 1685 tests pass (3 skipped)
  - Architecture ready for GitHub Copilot, ChatGPT, or custom AI agent backends
  - No breaking changes to public APIs
- ✓ Multi-AI assistant support (GitHub Copilot, Cursor, Windsurf)
  - Implemented GitHubCopilotAgent for VS Code with GitHub Copilot integration
  - Implemented CursorAgent for Cursor AI editor
  - Implemented WindsurfAgent for Windsurf (Codeium) editor
  - Updated factory to support "github-copilot"/"copilot", "cursor", and "windsurf" backends
  - Configuration field agent_backend accepts all new backend types
  - Each agent supports launch, resume, and session ID capture (with limitations)
  - Warning documentation: Only Claude Code fully tested, others experimental
  - Comprehensive test coverage (48 total tests in test_agent_interface.py)
  - All 2039 tests pass (3 skipped)
  - Feature support matrix documented with known limitations
  - Ready for community testing and feedback

## Release Management

### Overview

The DevAIFlow follows a structured release management process to ensure stable releases while enabling continuous development. The project uses semantic versioning and git flow branching strategy.

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):
- **MAJOR.MINOR.PATCH** (e.g., 1.0.0, 1.1.0, 1.1.1)
- **Development**: X.Y.Z-dev (on main branch)

### Branch Strategy

- **main**: Active development (version X.Y.0-dev)
- **release/X.Y**: Stable release branches (e.g., release/1.0, release/1.1)
- **hotfix/X.Y.Z**: Critical fixes for released versions
- **Tags**: vX.Y.Z for each release

### Quick Reference

```bash
# Check version
daf --version

# Release workflow (see RELEASING.md for details)
git checkout -b release/1.0 main    # Create release branch
# Update versions, CHANGELOG.md, run tests
git tag -a v1.0.0 -m "Release 1.0.0"
git push origin v1.0.0

# Hotfix workflow (see RELEASING.md for details)
git checkout -b hotfix/1.0.1 v1.0.0
# Fix bug, update version, update CHANGELOG.md
git tag -a v1.0.1 -m "Hotfix 1.0.1"
```

### Documentation

- **RELEASING.md**: Complete step-by-step release and hotfix procedures
- **CHANGELOG.md**: All notable changes, following [Keep a Changelog](https://keepachangelog.com/) format
- Version stored in `devflow/__init__.py` as `__version__` variable

See [RELEASING.md](RELEASING.md) for detailed instructions.

### Update Notifications

The tool automatically checks for new versions from GitLab releases:
- **Automatic checks**: Runs once per 24 hours (cached)
- **Non-intrusive**: Shows a notification banner if newer version available
- **Development mode**: Skipped for editable/development installations
- **No slowdown**: Uses cached results, network call only when cache is stale
- **Privacy-first**: No telemetry or usage tracking

When a new version is available, you'll see:
```
╭─ Update Available ──────────────────────────────────────────╮
│  A new version of daf is available: 1.1.0 (current: 1.0.0)  │
│  Run pip install --upgrade --force-reinstall .               │
╰─────────────────────────────────────────────────────────────╯
```

**For developers**: If you're running daf in development mode (editable install), update checks are automatically disabled. This ensures developers always follow the main branch without notification spam.

## Future Enhancements

- PR integration (auto-populate PR descriptions from session summaries)
- Multi-session support (parallel sessions for same ticket)
- Auto-pause on inactivity (detect when Claude Code is idle)
- Session archiving and cleanup
- Export to various formats (PDF, HTML)
