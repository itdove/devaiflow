# Feature Orchestration Implementation Summary

**Issue:** itdove/devaiflow#330
**Status:** ✅ Complete
**Date:** 2026-03-27

## Overview

Implemented multi-session feature orchestration with integrated verification. Allows users to execute multiple sessions sequentially on a shared branch with automated verification checkpoints between sessions.

## Key Features

### 1. Parent Ticket Auto-Discovery
- **JIRA**: Uses native `get_child_issues()` API to fetch epic children and sub-tasks
- **GitHub/GitLab**: Parses issue references from description and comments
  - Supported formats: `#123`, `owner/repo#456`, `GH-123`, `GL-123`
  - Order preservation: Description mentions first, then comments chronologically

### 2. Dependency-Based Ordering
- Topological sort using Kahn's algorithm
- Detects and warns about circular dependencies
- Falls back gracefully when cycles detected

### 3. Feature Sync and Dependency Ordering
- `daf feature sync --parent <parent> --auto-order` re-discovers children and reorders by dependencies
- Parses "Blocks"/"is blocked by" issue links for JIRA
- Adds new children that now meet sync criteria
- Reorders sessions based on current dependency state

### 4. Session Auto-Creation
- Detects missing sessions when creating feature
- Prompts user with 3 options:
  1. Auto-create sessions (recommended)
  2. Exit and run `daf sync` manually
  3. Cancel
- Applies sync criteria filtering (assignee, status, required_fields)

### 5. Verification System
- **Acceptance Criteria Checking**: Parses checkboxes and numbered lists from tickets
- **Test Suite Execution**: Auto-detects pytest, npm, go test, cargo test, etc.
- **Artifact Validation**: Verifies required files exist and are substantial
- **Verification Reports**: Generates detailed markdown reports

### 6. Workflow Integration
- `daf open`: Shows feature context (progress, status, next session)
- `daf complete`: Skips individual PRs, runs verification, auto-advances
- Final PR created when last session completes

### 7. Experimental Feature System
- Global `-e`/`--experimental` flag before command name
- Environment variable: `DEVAIFLOW_EXPERIMENTAL=1`
- Conditional command registration
- Clear error messages when flag missing

## Architecture

### Data Models (Pydantic)

```python
class FeatureOrchestration(BaseModel):
    name: str
    branch: str
    base_branch: str = "main"
    sessions: List[str]
    current_session_index: int = 0
    status: str = "created"
    verification_mode: str = "auto"
    session_statuses: Dict[str, str]
    verification_results: Dict[str, VerificationResult]

class VerificationResult(BaseModel):
    session_name: str
    status: str  # "passed", "gaps_found", "failed", "skipped"
    total_criteria: int = 0
    verified_criteria: int = 0
    unverified_criteria: List[str]
    test_command: Optional[str]
    tests_passed: bool
    required_artifacts: List[str]
    missing_artifacts: List[str]
    suggestions: List[str]

class FeatureIndex(BaseModel):
    features: Dict[str, FeatureOrchestration]
```

### Storage Structure

```
$DEVAIFLOW_HOME/
├── features.json              # Index of all features
└── features/
    └── <feature-name>/
        ├── metadata.json      # Feature configuration
        ├── state.md           # Current state (human-readable)
        ├── progress.md        # Session completion log
        └── verification/
            ├── session1.md    # Verification report
            ├── session2.md
            └── session3.md
```

### Core Components

1. **FeatureStorage** (`devflow/orchestration/storage.py`)
   - Persistence layer for features
   - JSON-based index + per-feature directories

2. **ParentTicketDiscovery** (`devflow/orchestration/parent_discovery.py`)
   - Auto-discover children from parent tickets
   - Backend detection (JIRA vs GitHub/GitLab)
   - Dependency ordering with topological sort
   - Sync criteria filtering

3. **FeatureManager** (`devflow/orchestration/feature.py`)
   - Orchestration engine
   - Session lifecycle management
   - Verification coordination
   - Feature state transitions

4. **Verification Modules**
   - `criteria_checker.py`: Parse acceptance criteria
   - `test_runner.py`: Auto-detect and run tests
   - `artifact_validator.py`: Validate required files

5. **Feature CLI** (`devflow/cli/commands/feature_command.py`)
   - 9 commands: create, list, delete, status, sync, run, resume, complete, reorder
   - Experimental feature gating
   - Rich terminal output

## CLI Commands

All commands require `-e` flag or `DEVAIFLOW_EXPERIMENTAL=1`:

```bash
# Create feature
daf -e feature create <name> --parent <parent-key> [--auto-order]
daf -e feature create <name> --sessions "s1,s2,s3"

# List features
daf -e feature list [--status <status>]

# Show status
daf -e feature status <name>

# Execute workflow
daf -e feature run <name>

# Resume paused
daf -e feature resume <name>

# Reorder sessions
daf -e feature reorder <name>                    # Interactive
daf -e feature reorder <name> <session> <pos>    # Move mode
daf -e feature reorder <name> --order "s2,s1,s3" # Direct mode

# Sync feature (add new children, reorder by dependencies)
daf -e feature sync <name> --parent <parent> [--auto-order]

# Delete feature
daf -e feature delete <name> [--delete-sessions] [--delete-branch]
```

## JIRA Integration Enhancements

### New Methods in `JiraClient`

1. **`_parse_issue_links(issuelinks: List[Dict])`**
   - Extracts blocking relationships from issue links
   - Returns tuple: `(blocks, blocked_by)`

2. **`get_blocking_relationships(issue_keys: List[str])`**
   - Fetches blocking relationships for multiple issues
   - Filters to only include relationships within the set
   - Returns: `Dict[str, Dict[str, List[str]]]`

3. **`get_child_issues(parent_key, include_links=False)`**
   - Enhanced to optionally include blocking relationships
   - When `include_links=True`, adds `blocks` and `blocked_by` fields

## Testing

Created comprehensive test suite: `tests/test_feature_orchestration.py`

**Test Coverage:**
- FeatureIndex operations (add, get, list, remove, duplicate detection)
- ParentTicketDiscovery (backend detection, ordering, filtering)
- JIRA issue link parsing (blocks, blocked_by, non-blocking)
- Pydantic models (FeatureOrchestration, VerificationResult)
- Dependency ordering (simple, cycles)
- Session context detection

**Results:** 20 tests, all passing ✅

## Documentation

### User Documentation
- `docs/experimental/README.md` - Experimental features overview
- `docs/experimental/feature-orchestration.md` - Complete user guide
- `docs/reference/commands.md` - Added experimental features section
- `docs/README.md` - Added experimental features to navigation

### Technical Documentation
- Inline code documentation (docstrings)
- Architecture comments in key modules
- This implementation summary

## Files Created

**Core Implementation:**
- `devflow/config/models.py` - Added FeatureOrchestration, VerificationResult, FeatureIndex
- `devflow/orchestration/storage.py` - FeatureStorage persistence
- `devflow/orchestration/parent_discovery.py` - ParentTicketDiscovery
- `devflow/orchestration/feature.py` - FeatureManager
- `devflow/verification/criteria_checker.py` - Acceptance criteria parser
- `devflow/verification/test_runner.py` - Test framework detection
- `devflow/verification/artifact_validator.py` - File validation
- `devflow/cli/commands/feature_command.py` - Feature CLI commands

**Testing:**
- `tests/test_feature_orchestration.py` - Comprehensive test suite

**Documentation:**
- `docs/experimental/README.md`
- `docs/experimental/feature-orchestration.md`
- `docs/experimental/IMPLEMENTATION.md` (this file)

## Files Modified

**CLI:**
- `devflow/cli/main.py` - Added `-e`/`--experimental` flag, conditional registration
- `devflow/cli/commands/open_command.py` - Feature context display
- `devflow/cli/commands/complete_command.py` - Feature-aware completion

**JIRA Client:**
- `devflow/jira/client.py` - Added blocking relationship methods

**Issue Tracker Clients:**
- `devflow/github/issues_client.py` - Added `get_issue_comments()`
- `devflow/gitlab/issues_client.py` - Added `get_issue_comments()`, fixed bug

**Documentation:**
- `README.md` - Added experimental features link
- `docs/README.md` - Added experimental features section
- `docs/reference/commands.md` - Added experimental features section

## Known Limitations

1. **Single-user**: Feature orchestration assumes single user (no concurrent work)
2. **Best-effort verification**: May have false positives/negatives
3. **GitHub/GitLab discovery**: Relies on issue references in text (no native API)
4. **No automatic rollback**: If verification fails, manual intervention required

## Automation Levels

Feature orchestration supports multiple levels of automation, from semi-automated workflow to fully autonomous execution.

### Level 1: Auto-Advance (✅ Implemented)

**Command:**
```bash
# Default mode: Prompts between sessions
daf -e feature run web-ui

# Auto-advance mode: No prompts between sessions
daf -e feature run web-ui --auto-advance
```

**Behavior (both modes):**
- **Automatically launches first session** (enforces execution order)
- User works with Claude interactively on each session
- Stops at verification failures
- Maintains human oversight on coding decisions

**Difference:**
- **Default mode**: Prompts "Open next session?" after each `daf complete`
- **Auto-advance mode**: Automatically opens next session (no prompt)

**Smart Resume:**
```bash
daf -e feature resume web-ui
```
- **If paused/failed**: Re-runs verification, then opens session (or next if passed)
- **If running/pending**: Opens current session
- **If completed**: Advances to next session and opens it
- **If all complete**: Shows "Feature complete!" message

**Use Case:** Reduces manual workflow overhead while keeping full control over implementation.

**Implementation:**
- `daf feature run` always opens first session (with or without `--auto-advance`)
- Stores `--auto-advance` preference in `feature.metadata['auto_advance']`
- `daf complete` checks flag and skips confirmation prompt if enabled
- `daf feature resume` intelligently handles different session statuses
- Enforces execution order (can't skip sessions)

### Level 2: Autonomous Agent Loop (⏳ Future)

**Command:**
```bash
daf -e feature run web-ui --autonomous
```

**Proposed Behavior:**
```python
for session in feature.sessions:
    # Auto-open session with goal from ticket
    goal = f"{session.issue_key}: {session.summary}"

    # Launch Claude Code in autonomous mode
    subprocess.run([
        "claude",
        "--autonomous",  # Hypothetical flag - not yet implemented
        "--goal", goal,
        "--acceptance-criteria", session.acceptance_criteria,
        "--max-turns", "50",  # Limit iterations
        "--auto-complete",  # Auto-run daf complete when done
    ])

    # Auto-complete when Claude finishes
    result = verify_session(session)

    if result.status != "passed":
        # Retry once, then pause
        if retry_count < 1:
            retry_session(session)
        else:
            pause_feature(reason="Verification failed after retry")
            break
```

**Challenges:**
1. **Claude Code lacks autonomous mode**: No `--autonomous` or `--auto-complete` flag exists
2. **Completion detection**: How does Claude know when it's "done"?
   - Could check acceptance criteria after each change
   - Could have turn limit (e.g., 50 iterations max)
   - Could detect "no more changes needed" signal
3. **Verification failures**: Auto-retry logic needed
   - How many retries before pausing?
   - Should Claude see previous verification results?
4. **Architecture decisions**: Claude needs to make design choices autonomously
   - May need human input for ambiguous requirements
   - Risk of suboptimal architectural decisions
5. **Testing/debugging loops**: Claude needs to fix failing tests without human help
   - May get stuck in infinite retry loops
   - Need circuit breakers and fallback strategies

**Implementation Requirements:**
- Claude Code `--autonomous` mode with:
  - Goal-driven completion detection
  - Turn/time limits
  - Auto-verification after changes
  - Acceptance criteria-based progress tracking
- Retry logic with limits (max 1-2 retries per session)
- Pause mechanism with reason tracking
- Notification system for human intervention

**Risk Mitigation:**
- Start with "supervised autonomous" mode (Level 3)
- Require explicit opt-in per feature
- Add kill switch for runaway sessions
- Log all autonomous decisions for review

### Level 3: Supervised Automation (⏳ Future)

**Command:**
```bash
daf -e feature run web-ui --watch
```

**Proposed Behavior:**
- Launches live dashboard showing all sessions
- Auto-executes each session in sequence (like Level 2)
- **Pauses and alerts user** when:
  - Verification fails
  - Tests fail after 3 retries
  - Session exceeds time/turn limit (e.g., 1 hour or 100 turns)
  - Architecture decision needed (detected via uncertainty signals)
- User can:
  - Skip session and move to next
  - Retry with different approach
  - Take over manually
  - Abort entire feature

**Dashboard Display:**
```
Feature: web-ui (8 sessions)
Progress: █████████░░░░░░░░ 3/8 (37%)

✓ itdove/devaiflow#306: Infrastructure    [15 min] [8 commits] [12/12 criteria]
✓ itdove/devaiflow#307: Flask backend     [22 min] [6 commits] [10/10 criteria]
⧗ itdove/devaiflow#308: JIRA tab          [running] [Turn 23/50]
  └─ Current: Implementing JIRA field validation...
○ itdove/devaiflow#309: Repository tab    [pending]
○ itdove/devaiflow#310: Model Provider    [pending]
○ itdove/devaiflow#311: Prompts tab       [pending]
○ itdove/devaiflow#312: UI detection      [pending]
○ itdove/devaiflow#313: Documentation     [pending]

[Skip] [Retry] [Manual] [Abort]
```

**Implementation Requirements:**
- Real-time dashboard with rich/textual TUI
- Session monitoring with live progress
- Pause/resume controls
- Turn and time tracking
- Notification system (desktop, Slack, etc.)

**Benefits:**
- Best of both worlds: automation + oversight
- Early error detection
- Human intervention only when needed
- Audit trail of autonomous decisions

## Future Enhancements (Potential)

1. **Multi-user support**: Coordinate multiple developers on same feature
2. **Verification refinement**: Improve accuracy, reduce false positives
3. **GitHub Projects integration**: Use GitHub Projects API for native child discovery
4. **Automatic rollback**: Revert changes when verification fails
5. **Feature templates**: Pre-defined feature configurations
6. **Parallel sessions**: Run independent sessions concurrently
7. **Feature analytics**: Track metrics (time, completion rate, verification success)

## Migration to Stable

Feature will graduate from experimental when it meets:

1. **Stability**: No critical bugs for 2+ releases
2. **Documentation**: Comprehensive docs and examples ✅
3. **Testing**: Good test coverage (unit + integration) ✅
4. **User Feedback**: Positive feedback from early adopters
5. **API Stability**: No breaking changes planned

Timeline: TBD based on user feedback

## Contributors

- Implementation: Claude Code (AI Assistant)
- Design & Requirements: @dvernier
- Testing: Automated test suite + manual testing

---

**Related Issues:**
- itdove/devaiflow#330 - Feature orchestration: Multi-session workflow with integrated verification

**See Also:**
- [Feature Orchestration User Guide](feature-orchestration.md)
- [Experimental Features Overview](README.md)
