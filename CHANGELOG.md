# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Field discovery now fetches all issue types** (itdove/devaiflow#361)
  - JIRA field discovery previously only fetched metadata for 4 hardcoded issue types (Bug, Story, Task, Epic)
  - Now fetches metadata for ALL issue types available in the project (Spike, Sub-task, Improvement, Enhancement, custom types)
  - Eliminates validation failures when creating issues with non-standard types
  - Removes need for manual `backend_overrides` workarounds in `enterprise.json`
  - Minimal performance impact: adds 2-6 API calls for typical JIRA projects
  - Field mappings now have complete `available_for` lists including all issue types

## [2.1.0] - 2026-04-02

### Added
- **Token usage tracking for AI agent sessions** (#259, #304)
  - Extract token statistics from Claude Code conversation files (.jsonl format)
  - Display token counts in `daf info`, `daf active`, and `daf list` commands
  - Show detailed token breakdown: input tokens, output tokens, cache creation, cache reads
  - Calculate cache efficiency percentage (cache reads / total cacheable tokens)
  - Estimate session cost based on model pricing (when configured in model provider profile)
  - Include token usage in markdown exports via `daf export`
  - Abstract `extract_token_usage()` method in `AgentInterface` for multi-agent support
  - Full implementation for Claude Code agent (parses .jsonl conversation files)
  - Stub implementations for other agents (GitHub Copilot, Cursor, Windsurf, Aider, Continue, Ollama, Crush)
  - Token display automatically hidden when agent backend doesn't support tracking
  - `daf list` shows tokens with K/M suffixes for readability (e.g., "1.2M", "850K")
  - Comprehensive cost estimation: `SessionSummary.estimate_cost()` with cache multipliers
  - Multi-conversation token aggregation with macOS symlink resolution (#317)
- **Ollama integration for local model support** (#241, #270, #271)
  - Native `OllamaClaudeAgent` backend using `ollama launch claude` command
  - Zero configuration required - works out of the box with Ollama
  - Automatic server management (no manual server start needed)
  - Model selection priority: config → `OLLAMA_MODEL` env var → Ollama default
  - Sessions stored in `~/.claude` (same as Claude Code for compatibility)
  - Full Claude Code features: session management, skills, conversation export, AI summaries
  - Configure via `agent_backend: "ollama"` in config or TUI (AI tab)
  - Optional `ollama.default_model` config setting (e.g., "qwen3-coder")
  - Simplest local model setup - one install command, no environment variables
  - See [Alternative Model Providers](docs/reference/alternative-model-providers.md) for setup guide
- **Additional AI agent support** (#274, #302)
  - Aider agent backend with session management and conversation tracking
  - Continue agent backend for VS Code integration
  - Crush AI agent backend with environment variable configuration
  - All agents support launch, resume, and basic session management
- **Enterprise model provider enforcement** (#248, #272)
  - Company-wide enforcement of approved AI model providers
  - Cost tracking and budget management per profile
  - Audit logging for compliance and cost attribution
  - Support for Vertex AI, llama.cpp, and custom providers
  - TUI integration with enforcement warnings
  - Model provider profile management commands (#269)
- **daf-workflow skill** for centralized workflow guidance (#263, #266)
  - Global skill auto-loaded from `~/.claude/skills/daf-workflow/`
  - Comprehensive guidance for AI agents on development workflows
  - Issue tracker auto-detection (GitHub/GitLab/JIRA) based on git remote URLs
  - Guidance on when to use Atlassian MCP vs daf CLI commands (#242)
  - Multi-project session workflows and best practices
  - Standard development and ticket creation session patterns
  - Run `daf upgrade` to install the skill
- **MCP JIRA integration documentation and skill** (#342)
  - Comprehensive skill for using Atlassian MCP JIRA tools
  - Field format requirements and validation guidance
  - Integration with daf CLI commands
  - Best practices for MCP vs CLI usage
- **daf skills command for discovery and inspection** (#340)
  - List all installed skills with metadata
  - Show skill content and source locations
  - Validate skill structure and configuration
  - Debug skill loading and precedence
- **Skill system improvements** (#338, #298, #288, #295)
  - Prevent duplicate skill loading in Claude agent
  - Multi-agent skill installation with directory mapping
  - Global and project-level skill installation support
  - Skills now install to `~/.claude/skills/` by default
- **Feature orchestration: Multi-session workflow** (#330, #334)
  - Create coordinated multi-session workflows for complex features
  - Integrated verification across related sessions
  - Session dependencies and ordering
  - Progress tracking and status synchronization
- **Enhanced CLI parameter support** (#278, #289)
  - Added CLI parameters for all interactive prompts in session creation
  - Non-interactive mode support for automation
  - Full command-line control without TUI prompts
- **Pre-flight GitHub CLI authentication check** (#277, #284)
  - Smart failure handling for missing or expired gh authentication
  - Clear error messages with remediation steps
  - Prevents cryptic errors during PR/MR creation
- **Repository selection improvements** (#282)
  - 3-tier priority system for repository selection
  - Default prompts with workspace-aware suggestions
  - Better UX for multi-workspace scenarios
- **Session goal file support** (#279)
  - `--goal-file` option to load session goals from files
  - Supports long-form requirements and specifications
  - Useful for complex features requiring detailed context
- **Unified agent management commands** (#251, #275)
  - Consistent command structure across all agent backends
  - Unified session management interface
  - Standardized configuration and status reporting
- **Agent abstraction with `launch_with_prompt()` method**
  - Added `launch_with_prompt()` to `AgentInterface` for initial prompt support
  - Implemented in all agents: Claude, Ollama, GitHub Copilot, Cursor, Windsurf, Aider, Continue, Crush
  - Enables launching agents with initial prompts and session IDs
  - Skills directories auto-discovery for Claude Code integration
- **CLAUDE_CONFIG_DIR environment variable support** (#294)
  - Override default `~/.claude` directory location
  - Useful for custom workspace configurations
  - Supports team-specific Claude Code setups

### Changed
- **BREAKING**: Removed DAF_AGENTS.md in favor of daf-workflow skill (#263)
  - Workflow guidance now provided via global daf-workflow skill instead of per-project DAF_AGENTS.md files
  - Eliminates duplication across multiple repositories
  - Auto-migration: opening sessions with old DAF_AGENTS.md files prompts for deletion
  - All command prompts updated to reference daf-workflow skill instead of DAF_AGENTS.md
  - Run `daf upgrade` to install daf-workflow skill
- **Simplified daf init wizard** (#329, #332)
  - Streamlined onboarding experience
  - Better user guidance and explanations
  - Clearer configuration options
  - Improved validation and error messages
- **Hierarchical context architecture simplification** (#314, #316)
  - Use skills-only approach instead of duplicate context files
  - Eliminates ENTERPRISE.md, ORGANIZATION.md, TEAM.md, USER.md duplication
  - Skills provide all hierarchical guidance and defaults
  - Cleaner configuration management
- **CLI simplification** (#283, #293)
  - Reduced command count from 73 to ~50 commands
  - Removed deprecated and redundant commands
  - Clearer command structure and organization
  - Better discoverability of available commands
- **Migrated to pyproject.toml for package configuration** (#261)
  - Modern Python packaging using PEP 517/518/621
  - setup.py kept for backward compatibility (no version information)
  - All package metadata now in pyproject.toml
  - Cleaner build configuration

### Improved
- **Branch workflow UX improvements** (#331, #333)
  - Added missing branch selection prompts
  - Updated base branch detection logic
  - Better handling of stale branches
  - Clearer branch status information

### Removed
- DAF_AGENTS.md bundled file - replaced by daf-workflow skill (#263)
  - Session validation now offers to delete old DAF_AGENTS.md files found in repositories
  - Context file loading no longer includes DAF_AGENTS.md
  - All references removed from command prompts and documentation
- Duplicate context files (ENTERPRISE.md, ORGANIZATION.md, TEAM.md, USER.md) - replaced by skills (#314, #316)

### Fixed
- **Session names truncated in daf list** (#358, #359)
  - Fixed truncation making sessions impossible to reopen on small terminals
  - Improved column width calculations
  - Better handling of long session names
- **Auto-convert ticket_creation sessions to development** (#356)
  - daf sync now automatically converts ticket_creation sessions
  - Prevents "Session already exists" errors
  - Smooth workflow transition after ticket creation
- **Command templates removed from analysis session prompts** (#345)
  - Analysis sessions no longer show inappropriate code modification commands
  - Clearer read-only session expectations
  - Better alignment with investigation/ticket_creation workflows
- **Branch checkout and sync operation safety checks** (#328)
  - Added validation before destructive git operations
  - Prevents accidental branch switches with uncommitted changes
  - Better error messages for common failure scenarios
- **Default to session's previous workspace on reopen** (#320, #321)
  - Session workspace selection now defaults to previous workspace
  - Improved consistency across session reopens
  - Better multi-workspace experience
- **Handle environment variables in complete-on-exit flow** (#318)
  - Fixed environment variable handling during session completion
  - Proper cleanup of temporary variables
  - More robust completion workflow
- **Resolve macOS symlinks and sum tokens across conversations** (#317)
  - Fixed token aggregation for sessions with symlinked directories
  - Proper handling of macOS-specific filesystem features
  - Accurate token counts in multi-conversation sessions
- **Skills command naming and type filtering** (#301, #303)
  - Renamed 'daf skills' to 'daf assets' where appropriate
  - Added --type parameter for filtering
  - Clearer command semantics
- **Remove JIRA-first bias in skills** (#299)
  - Balanced guidance for all issue tracker types
  - Equal treatment of GitHub Issues, GitLab Issues, and JIRA
  - Backend-agnostic workflow documentation
- **Format parent field as object for API compatibility** (#265)
  - Fixed JIRA API compatibility for parent field submissions
  - Proper JSON structure for relationship fields
  - Better error handling for field format mismatches
- **Parent field linking without configuration** (#256, #258)
  - `daf jira create --parent` now defaults to standard JIRA `parent` field
  - Previously failed silently when `parent_field_mapping` was not configured
  - Eliminates need to configure `parent_field_mapping` for modern JIRA instances
  - Maintains backward compatibility with legacy configurations using `epic_link`
  - Configuration is now truly optional (only needed for legacy custom fields)
- **daf complete prompts when no PR should be created** (#252)
  - Fixed inappropriate PR/MR prompts for ticket_creation and investigation sessions
  - Session type awareness in completion workflow
  - Cleaner completion UX

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

[unreleased]: https://github.com/itdove/devaiflow/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/itdove/devaiflow/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/itdove/devaiflow/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/itdove/devaiflow/tags/v1.0.0
