# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **daf-workflow skill** for centralized workflow guidance (#263)
  - Global skill auto-loaded from `~/.claude/skills/daf-workflow/`
  - Comprehensive guidance for AI agents on development workflows
  - Issue tracker auto-detection (GitHub/GitLab/JIRA) based on git remote URLs
  - Guidance on when to use Atlassian MCP vs daf CLI commands (#242)
  - Multi-project session workflows and best practices
  - Standard development and ticket creation session patterns
  - Run `daf upgrade` to install the skill

### Changed
- **BREAKING**: Removed DAF_AGENTS.md in favor of daf-workflow skill (#263)
  - Workflow guidance now provided via global daf-workflow skill instead of per-project DAF_AGENTS.md files
  - Eliminates duplication across multiple repositories
  - Auto-migration: opening sessions with old DAF_AGENTS.md files prompts for deletion
  - All command prompts updated to reference daf-workflow skill instead of DAF_AGENTS.md
  - Run `daf upgrade` to install daf-workflow skill

### Removed
- DAF_AGENTS.md bundled file - replaced by daf-workflow skill (#263)
  - Session validation now offers to delete old DAF_AGENTS.md files found in repositories
  - Context file loading no longer includes DAF_AGENTS.md
  - All references removed from command prompts and documentation

### Fixed
- Parent field linking now works without `parent_field_mapping` configuration (#256)
  - `daf jira create --parent` now defaults to standard JIRA `parent` field
  - Previously failed silently when `parent_field_mapping` was not configured
  - Eliminates need to configure `parent_field_mapping` for modern JIRA instances
  - Maintains backward compatibility with legacy configurations using `epic_link`
  - Configuration is now truly optional (only needed for legacy custom fields)

## [2.0.0] - 2026-03-19

### Added
- Multi-project workflow support with shared context for cross-repository features (#149)
  - **Architecture:** Creates ONE conversation with SHARED CONTEXT across all selected projects
  - **Shared Context:** Claude can see and coordinate changes across all repositories simultaneously
  - Add `--projects` flag to `daf new` command (comma-separated list of repository names)
  - Requires `--workspace` flag to be specified
  - Prompts for base branch selection per project (e.g., backend from `main`, frontend from `develop`)
  - Creates branches with the same name across all specified projects by default
  - Tracks base branch per project in ConversationContext.projects dict
  - `daf complete` iterates through ALL projects and creates PR/MR for each
  - Each PR/MR uses the project's `base_branch` as the target branch
  - Launches Claude Code at workspace level with access to all projects
  - **Use Cases:** Update backend API + frontend client in coordinated way, maintain consistency across microservices
  - Maintains backward compatibility with single-project workflow and legacy multi-conversation sessions
  - Example: `daf new PROJ-123 -w primary --projects backend-api,frontend-app,shared-lib`
- Auto-suggest repository when opening GitHub/GitLab synced sessions (#146)
  - Automatically extracts repository name from GitHub/GitLab issue keys (e.g., `owner/repo#123`)
  - Highlights matching repository in working directory selection prompt with "(from issue)" label
  - Defaults to suggested repository if found in workspace
  - Improves UX by reducing manual repository selection for synced issues
  - Only affects GitHub/GitLab sessions; JIRA sessions behave as before
- Branch selection prompt when cloning to temporary directory (#128)
  - Interactive prompt to select which branch to checkout after cloning for analysis
  - Lists all available remote branches from `upstream` (preferred) or `origin`
  - Default branch priority: `upstream/main` > `upstream/master` > `origin/main` > `origin/master`
  - Select branch by number, name, or press Enter for default
  - Automatically skipped in non-interactive modes (`--json` flag, `DAF_MOCK_MODE=1`)
  - Applies to `daf git new`, `daf jira new`, and `daf investigate` commands
  - Gracefully falls back to auto-detection if branch selection fails
  - Useful for analyzing repositories with multiple active development branches
- Target branch selection when creating PRs/MRs (AAP-65187)
  - Interactive prompt to select which branch to target (e.g., `main`, `release/2.5`, `release/3.0`)
  - Adds `--base <branch>` flag for GitHub PRs or `--target-branch <branch>` flag for GitLab MRs
  - Configurable via `prompts.auto_select_target_branch` setting (null=prompt, true=auto-default, false=skip)
  - Lists all available remote branches with default branch highlighted
  - Eliminates need to manually change target branch in UI after PR creation
  - Useful for teams working on multiple release branches simultaneously
- JIRA API debug logging with `DEVAIFLOW_DEBUG=1` environment variable
  - Shows full request/response details for all JIRA API calls
  - Helps troubleshoot field validation and API errors
  - Automatically disabled in JSON output mode
- Claude Code 2.1.3+ version requirement for slash commands and skills support

### Changed
- **BREAKING**: Migrated from `.claude/commands/` to `.claude/skills/` directory structure
  - Skills now install globally to `~/.claude/skills/` instead of per-workspace
  - Slash commands now require `name:` field in YAML frontmatter
  - Reference skills (without `name:` field) are auto-loaded but not invokable
  - Workspace-level skills are no longer supported
  - Run `daf upgrade` to migrate to the new structure
- Renamed command files to skill directories (e.g., `daf-help.md` → `daf-help/SKILL.md`)
- Simplified upgrade command to install all skills globally in one operation
- Update checker now uses PyPI JSON API instead of GitLab/GitHub releases API (AAP-65842)
  - Follows standard Python package conventions
  - Works regardless of Git hosting platform
  - Maintains 24-hour cache behavior
  - Preserves non-intrusive notification banner
  - Development installation detection unchanged

### Improved
- Enhanced `daf init` wizard with better user guidance and explanations
  - Added welcome message explaining all settings can be changed later
  - Added comment visibility configuration (group/role based JIRA comment restrictions)
  - Added detailed help text for keyword mappings (multi-repo suggestions)
  - Added GitHub raw URL guidance for PR/MR templates
  - Improved clarity on optional vs required settings
- JIRA field validation now checks if custom fields are available for the issue type being created
  - Prevents cryptic JIRA errors when using `--field` with incompatible issue types
  - Shows clear warning and skips unavailable fields

### Fixed
- Test environment isolation for unit tests - added `parent_field_mapping` to test configurations
- Updated test fixtures to include new comment visibility prompts
- Mock mode now skips JIRA field auto-refresh to prevent network errors in tests
- Mock mode now uses default affected version ("v1.0.0") instead of prompting
- Custom field validation prevents sending fields that aren't available for the issue type

## [1.0.0] - 2026-01-23


### Added
- Core session management functionality for AI coding assistants
- Support for multiple AI assistants (Claude Code, GitHub Copilot, Cursor, Windsurf)
- JIRA integration for ticket management
- Automated git workflow management (branch creation, commits, PR/MR creation)
- Session types for different workflows (development, ticket_creation, investigation)
- Multi-repository session support
- Session export/import for team collaboration
- Time tracking for work sessions
- Interactive TUI for configuration management
- Custom field discovery for JIRA integration
- Automatic version checking against GitHub releases
- Session templates for reusable configurations
- Comprehensive documentation and user guides

### Changed
- Exception-based error handling for JIRA client operations
- Configuration architecture with separate files for different concerns

### Fixed
- Branch creation prompts for ticket creation sessions
- Session working directory handling
- JIRA auto-transition for analysis-only sessions
- Project path encoding for conversation files

[unreleased]: https://github.com/itdove/devaiflow/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/itdove/devaiflow/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/itdove/devaiflow/tags/v1.0.0
