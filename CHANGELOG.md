# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2026-01-24

### Fixed
- AAP-64027: Use default workspace from config for jira new command
  - Replace direct workspace field access with get_default_workspace() method
  - Use workspace_path for skills discovery instead of workspace name
  - Add workspace selection prompt with priority resolution in repository selection
  - Replace is_default with last_used_workspace in workspace config
  - Update all commands to use get_default_workspace_path() helper method

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

[unreleased]: https://github.com/itdove/devaiflow/compare/v1.0.1...HEAD

[1.0.1]: https://github.com/itdove/devaiflow/compare/v1.0.0...v1.0.1

[1.0.0]: https://github.com/itdove/devaiflow/tags/v1.0.0
