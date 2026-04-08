# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-04-08T17:01:10.464Z
> Files: 506 tracked | Anatomy hits: 0 | Misses: 0

## ./

- `.coverage` (~14200 tok)
- `.gitignore` — Git ignore rules (~185 tok)
- `AGENTS.md` — Agent Instructions for DevAIFlow (~21442 tok)
- `CHANGELOG.md` — Change log (~4649 tok)
- `CLAUDE.md` — OpenWolf (~139 tok)
- `config.schema.json` (~9891 tok)
- `CONTRIBUTING.md` — Contributing to DevAIFlow (~2695 tok)
- `coverage.json` (~12790 tok)
- `demo_branch_selection.sh` — Demo script showing the new branch source selection feature (~846 tok)
- `LICENSE` — Project license (~3029 tok)
- `pyproject.toml` — Python project configuration (~702 tok)
- `QUICKREF.md` — DevAIFlow Quick Reference (~1384 tok)
- `README.md` — Project documentation (~6603 tok)
- `RELEASING.md` — Release Management Process (~3825 tok)
- `requirements-dev.txt` (~28 tok)
- `requirements.txt` — Python dependencies (~72 tok)
- `SECURITY.md` — Security Policy (~1380 tok)
- `setup.py` — Python package setup (~80 tok)
- `T-1.md` — Session: T-1 - G (~44 tok)

## .claude/

- `settings.json` (~441 tok)
- `settings.local.json` (~305 tok)

## .claude/rules/

- `openwolf.md` (~313 tok)

## .claude/skills/release/

- `EXAMPLE_USAGE.md` — Release Skill Usage Examples (~1906 tok)
- `README.md` — Project documentation (~858 tok)

## .github/

- `CODEOWNERS` — CODEOWNERS - Define code ownership and required reviewers (~222 tok)

## .github/ISSUE_TEMPLATE/

- `agent-validation.md` — Environment (~360 tok)

## .github/workflows/

- `integration-tests.yml` — GitHub Actions CI/CD - Integration Tests Workflow (~387 tok)
- `lint.yml` — GitHub Actions CI/CD - Lint Workflow (~534 tok)
- `publish-test.yml` — GitHub Actions CI/CD - TestPyPI Publish Workflow (~370 tok)
- `publish.yml` — GitHub Actions CI/CD - PyPI Publish Workflow (~582 tok)
- `tag-monitor.yml` — CI: Tag Creation Monitor (~1799 tok)
- `test.yml` — GitHub Actions CI/CD - Test Workflow (~467 tok)

## .pytest_cache/

- `.gitignore` — Git ignore rules (~10 tok)
- `CACHEDIR.TAG` (~51 tok)
- `README.md` — Project documentation (~76 tok)

## .pytest_cache/v/cache/

- `lastfailed` (~4066 tok)
- `nodeids` (~92590 tok)
- `stepwise` (~1 tok)

## demos/

- `demo-commands.txt` (~524 tok)
- `demo-github-workflow-20260308-172110.log` (~46804 tok)
- `demo-github-workflow-20260308-172750.log` (~45925 tok)
- `demo-github-workflow-20260308-173242.log` (~56119 tok)
- `demo-github-workflow-20260308-185816.log` (~58075 tok)
- `demo-github-workflow.sh` — Real demo using tmux to automate DevAIFlow GitHub workflow (~3720 tok)

## devflow/

- `__init__.py` — DevAIFlow - AI-Powered Development Workflow Manager with JIRA integration. (~31 tok)
- `exceptions.py` — Custom exceptions for daf tool. (~300 tok)

## devflow/agent/

- `__init__.py` — Agent interface abstraction for DevAIFlow. (~420 tok)
- `aider_agent.py` — Aider agent implementation. (~3231 tok)
- `claude_agent.py` — Claude Code agent implementation. (~7196 tok)
- `continue_agent.py` — Continue agent implementation. (~3229 tok)
- `crush_agent.py` — Crush agent implementation. (~3484 tok)
- `cursor_agent.py` — Cursor agent implementation. (~2906 tok)
- `factory.py` — Factory for creating AI agent clients. (~1097 tok)
- `github_copilot_agent.py` — GitHub Copilot agent implementation. (~2800 tok)
- `interface.py` — Abstract interface for AI agent backends. (~2273 tok)
- `ollama_claude_agent.py` — Ollama + Claude Code agent implementation. (~4956 tok)
- `skill_directories.py` — get_agent_global_skills_dir, get_agent_project_skills_dir, get_skill_install_paths, validate_agent_names (~2859 tok)
- `windsurf_agent.py` — Windsurf agent implementation. (~2906 tok)

## devflow/archive/

- `__init__.py` — Archive management for backup and export operations. (~42 tok)
- `base.py` — Base class for archive operations (backup/export). (~1155 tok)

## devflow/backup/

- `__init__.py` — Backup and restore functionality for DevAIFlow. (~16 tok)
- `manager.py` — Backup and restore manager for DevAIFlow. (~3370 tok)

## devflow/cli/

- `__init__.py` — CLI commands for DevAIFlow. (~10 tok)
- `completion.py` — Shell completion support for DevAIFlow. (~1235 tok)
- `main.py` — Main CLI entry point for DevAIFlow. (~47322 tok)
- `signal_handler.py` — Unified signal handler for CLI commands that launch Claude sessions. (~2578 tok)
- `skills_discovery.py` — Utility for discovering skills from all hierarchical locations. (~1331 tok)
- `utils.py` — Common utility functions for CLI commands. (~15760 tok)

## devflow/cli/commands/

- `__init__.py` — CLI command implementations. (~10 tok)
- `active_command.py` — Implementation of 'daf active' command. (~3418 tok)
- `agent_commands.py` — Agent management commands for DevAIFlow. (~5482 tok)
- `backup_command.py` — Implementation of 'daf backup' command. (~449 tok)
- `check_command.py` — Implementation of 'daf check' command. (~1058 tok)
- `cleanup_command.py` — Implementation of 'daf cleanup-conversation' command. (~6300 tok)
- `cleanup_sessions_command.py` — Implementation of 'daf cleanup-sessions' command. (~1484 tok)
- `complete_command.py` — Implementation of 'daf complete' command. (~51802 tok)
- `config_export_command.py` — Implementation of 'daf config export' command. (~476 tok)
- `config_import_command.py` — Implementation of 'daf config import' command. (~619 tok)
- `context_commands.py` — Implementation of 'daf config context' commands. (~2136 tok)
- `delete_command.py` — Implementation of 'daf delete' command. (~2272 tok)
- `discover_command.py` — Implementation of 'daf discover' command. (~1365 tok)
- `export_command.py` — Implementation of 'daf export' command. (~5784 tok)
- `export_md_command.py` — Implementation of 'daf export-md' command. (~917 tok)
- `feature_command.py` — Feature orchestration CLI commands. (~28130 tok)
- `git_add_comment_command.py` — Implementation of 'daf git add-comment' command. (~911 tok)
- `git_check_auth_command.py` — Implementation of 'daf git check-auth' command. (~1411 tok)
- `git_commands.py` — Git-based issue tracker CLI command group for DevAIFlow. (~164 tok)
- `git_create_command.py` — Implementation of 'daf git create' command. (~5406 tok)
- `git_new_command.py` — Command for daf git new - create GitHub/GitLab issue with session-type for ticket creation workflow. (~14122 tok)
- `git_open_command.py` — Command for daf git open - open or create session from GitHub/GitLab issue. (~2094 tok)
- `git_update_command.py` — Implementation of 'daf git update' command. (~2244 tok)
- `git_view_command.py` — Implementation of 'daf git view' command. (~2215 tok)
- `import_command.py` — Implementation of 'daf import' command. (~3262 tok)
- `import_session_command.py` — Implementation of 'daf import-session' command. (~2195 tok)
- `info_command.py` — Implementation of 'daf info' command. (~6561 tok)
- `investigate_command.py` — Command for daf investigate - create investigation-only session without ticket creation. (~12343 tok)
- `jira_add_comment_command.py` — Implementation of 'daf jira add-comment' command. (~1756 tok)
- `jira_create_commands.py` — Implementation of 'daf jira create' command. (~18107 tok)
- `jira_create_dynamic.py` — Dynamic command builder for daf jira create with field discovery. (~3074 tok)
- `jira_field_utils.py` — Common utilities for JIRA field processing in dynamic commands. (~1410 tok)
- `jira_new_command.py` — Command for daf jira new - create issue tracker ticket with session-type for ticket creation workflow. (~14348 tok)
- `jira_open_command.py` — Command for daf jira open - open or create session from issue tracker ticket. (~2270 tok)
- `jira_update_command.py` — Implementation of 'daf jira update' command. (~7088 tok)
- `jira_update_dynamic.py` — Dynamic command builder for daf jira update with field discovery. (~1988 tok)
- `jira_view_command.py` — Implementation of 'daf jira view' command. (~4432 tok)
- `link_command.py` — Implementation of 'daf link' command. (~2314 tok)
- `list_command.py` — Implementation of 'daf list' command. (~4987 tok)
- `new_command_multiproject.py` — Multi-project session creation logic for DevAIFlow (Issue #149). (~4292 tok)
- `new_command.py` — Implementation of 'daf new' command. (~27498 tok)
- `note_command.py` — Implementation of 'daf note' and 'daf notes' commands. (~1903 tok)
- `open_command.py` — Implementation of 'daf open' command. (~50903 tok)
- `pause_command.py` — Implementation of 'daf pause' command. (~619 tok)
- `provider_commands.py` — Implementation of 'daf model' commands for managing model provider profiles. (~6464 tok)
- `rebuild_index_command.py` — Implementation of 'daf rebuild-index' command. (~2992 tok)
- `release_command.py` — Implementation of 'daf release' command. (~7071 tok)
- `repair_conversation_command.py` — CLI command for repairing corrupted Claude Code conversation files. (~3410 tok)
- `restore_command.py` — Implementation of 'daf restore' command. (~485 tok)
- `resume_command.py` — Implementation of 'daf resume' command. (~603 tok)
- `search_command.py` — Implementation of 'daf search' command. (~959 tok)
- `session_project_command.py` — Commands for managing projects/conversations in sessions. (~3135 tok)
- `sessions_list_command.py` — Implementation of 'daf list' command (formerly 'daf sessions list'). (~1463 tok)
- `skills_command.py` — Implementation of 'daf skills' command group. (~8572 tok)
- `skills_discovery_command.py` — Implementation of 'daf skills' command for discovery and inspection. (~4658 tok)
- `status_command.py` — Implementation of 'daf status' command. (~3926 tok)
- `summary_command.py` — Implementation of 'daf summary' command. (~2358 tok)
- `sync_command.py` — Implementation of 'daf sync' command. (~16114 tok)
- `template_commands.py` — Implementation of template management commands. (~1880 tok)
- `ticket_creation_multiproject.py` — Multi-project ticket creation session logic for DevAIFlow (Issue #179). (~1273 tok)
- `time_command.py` — Implementation of 'daf time' command. (~982 tok)
- `update_command.py` — Implementation of 'daf update' command. (~656 tok)
- `upgrade_command.py` — Implementation of 'daf upgrade' command. (~2669 tok)
- `workspace_commands.py` — Implementation of 'daf workspace' commands (AAP-63377). (~4987 tok)

## devflow/cli_skills/daf-active/

- `SKILL.md` (~542 tok)

## devflow/cli_skills/daf-cli/

- `SKILL.md` — DAF Quick Reference (~1373 tok)

## devflow/cli_skills/daf-config/

- `SKILL.md` (~585 tok)

## devflow/cli_skills/daf-git/

- `SKILL.md` — Quick Start (~2060 tok)

## devflow/cli_skills/daf-help/

- `SKILL.md` — Work in current repository (~473 tok)

## devflow/cli_skills/daf-info/

- `SKILL.md` (~527 tok)

## devflow/cli_skills/daf-jira-fields/

- `SKILL.md` — JIRA Field Intelligence for DevAIFlow (~1813 tok)

## devflow/cli_skills/daf-jira-mcp/

- `SKILL.md` — MCP JIRA Integration with DevAIFlow Intelligence (~3420 tok)

## devflow/cli_skills/daf-jira/

- `SKILL.md` — MCP Alternative Available (~1489 tok)

## devflow/cli_skills/daf-list-conversations/

- `SKILL.md` (~209 tok)

## devflow/cli_skills/daf-list/

- `SKILL.md` (~381 tok)

## devflow/cli_skills/daf-notes/

- `SKILL.md` (~463 tok)

## devflow/cli_skills/daf-read-conversation/

- `SKILL.md` — Get session info to find conversation details (~502 tok)

## devflow/cli_skills/daf-status/

- `SKILL.md` (~463 tok)

## devflow/cli_skills/daf-workflow/

- `SKILL.md` — DevAIFlow Workflow Guide (~3832 tok)

## devflow/cli_skills/daf-workspace/

- `SKILL.md` (~407 tok)

## devflow/cli_skills/gh-cli/

- `SKILL.md` — GitHub CLI (gh) Reference for daf tool (~3332 tok)

## devflow/cli_skills/git-cli/

- `SKILL.md` — Git CLI Reference for daf tool (~2092 tok)

## devflow/cli_skills/glab-cli/

- `SKILL.md` — GitLab CLI (glab) Reference for daf tool (~3185 tok)

## devflow/config/

- `__init__.py` — Configuration management for DevAIFlow. (~14 tok)
- `exporter.py` — Configuration export functionality. (~2951 tok)
- `importer.py` — Configuration import functionality. (~2580 tok)
- `init_wizard.py` — Interactive configuration wizard for daf init. (~12648 tok)
- `loader.py` — Configuration file loading and management. (~11941 tok)
- `models.py` — Configuration models for DevAIFlow. (~21910 tok)
- `schema.py` — JSON Schema generation and validation for configuration. (~914 tok)
- `validator.py` — Configuration validation for detecting placeholder values and completeness issues. (~2212 tok)

## devflow/config/schemas/

- `__init__.py` (~0 tok)
- `enterprise.schema.json` (~949 tok)
- `organization.schema.json` (~1838 tok)
- `team.schema.json` (~931 tok)
- `user.schema.json` (~1809 tok)

## devflow/config/schemas/backends/

- `__init__.py` (~0 tok)
- `jira.schema.json` (~703 tok)

## devflow/config/templates/

- `__init__.py` — Model provider templates for DevAIFlow. (~113 tok)
- `model_providers.py` — Model provider templates for TUI configuration. (~4081 tok)

## devflow/config/validators/

- `__init__.py` — Configuration validators for DevAIFlow. (~187 tok)
- `base.py` — Base validator class for configuration files. (~3356 tok)
- `enterprise.py` — Validator for enterprise.json configuration file. (~564 tok)
- `organization.py` — Validator for organization.json configuration file. (~1409 tok)
- `team.py` — Validator for team.json configuration file. (~857 tok)
- `user.py` — Validator for config.json (user) configuration file. (~990 tok)

## devflow/config/validators/backends/

- `__init__.py` — Backend configuration validators. (~74 tok)
- `base.py` — Base validator for backend configuration files. (~146 tok)
- `jira.py` — Validator for backends/jira.json configuration file. (~1696 tok)

## devflow/export/

- `__init__.py` — Export and import functionality for DevAIFlow. (~16 tok)
- `manager.py` — Export and import manager for DevAIFlow. (~8292 tok)
- `markdown.py` — Markdown export functionality for DevAIFlow. (~5216 tok)

## devflow/git/

- `__init__.py` — Git integration utilities for DevAIFlow. (~14 tok)
- `pr_template.py` — AI-powered PR/MR template parsing and filling. (~2974 tok)
- `utils.py` — Git utilities for branch management. (~15440 tok)

## devflow/github/

- `__init__.py` — GitHub Issues integration for DevAIFlow. (~123 tok)
- `auth.py` — GitHub authentication and pre-flight checks. (~2001 tok)
- `field_mapper.py` — GitHub field mapper for converting between GitHub Issues and DevAIFlow interface. (~3675 tok)
- `issues_client.py` — GitHub Issues client implementing IssueTrackerClient interface. (~8675 tok)
- `transitions.py` — GitHub issue state transitions for DevAIFlow sessions. (~2728 tok)

## devflow/gitlab/

- `__init__.py` — GitLab integration for DevAIFlow. (~119 tok)
- `field_mapper.py` — GitLab field mapper for converting between GitLab Issues and DevAIFlow interface. (~4120 tok)
- `issues_client.py` — GitLab Issues client implementing IssueTrackerClient interface. (~9175 tok)

## devflow/issue_tracker/

- `__init__.py` — Issue tracker abstraction layer for DevAIFlow. (~231 tok)
- `exceptions.py` — Custom exceptions for issue tracker client operations. (~1788 tok)
- `factory.py` — Factory for creating issue tracker client instances. (~1531 tok)
- `interface.py` — Abstract interface for issue tracking systems. (~3578 tok)
- `mock_client.py` — Mock implementation of IssueTrackerClient for testing. (~3176 tok)
- `README.md` — Project documentation (~1449 tok)

## devflow/jira/

- `__init__.py` — JIRA integration for DevAIFlow. (~111 tok)
- `client.py` — JIRA REST API client for DevAIFlow. (~25990 tok)
- `exceptions.py` — Custom exceptions for JIRA client operations. (~485 tok)
- `field_mapper.py` — JIRA custom field mapper for discovering and caching field metadata. (~6763 tok)
- `transitions.py` — issue tracker ticket transition management. (~3618 tok)
- `utils.py` — Utility functions for JIRA operations. (~4182 tok)
- `validation.py` — JIRA field validation based on config.jira rules. (~4122 tok)

## devflow/mocks/

- `__init__.py` — Mock services infrastructure for integration testing. (~112 tok)
- `claude_mock.py` — Mock Claude Code service for integration testing. (~2230 tok)
- `github_mock.py` — Mock GitHub service for integration testing. (~1725 tok)
- `gitlab_mock.py` — Mock GitLab service for integration testing. (~2366 tok)
- `jira_mock.py` — Mock JIRA service for integration testing. (~3404 tok)
- `persistence.py` — Thread-safe persistent storage for mock services data. (~4392 tok)

## devflow/orchestration/

- `__init__.py` — Feature orchestration module for DevAIFlow. (~111 tok)
- `feature.py` — Feature orchestration manager for DevAIFlow. (~7221 tok)
- `parent_discovery.py` — Parent ticket discovery for feature orchestration. (~5487 tok)
- `storage.py` — Feature orchestration storage backend. (~2215 tok)

## devflow/release/

- `__init__.py` — Release management utilities. (~133 tok)
- `manager.py` — Release manager for automating release mechanics. (~14891 tok)
- `permissions.py` — Permission checking for release operations. (~2884 tok)
- `version.py` — Version parsing and comparison utilities for release management. (~1692 tok)

## devflow/session/

- `__init__.py` — Session management for Claude Code sessions. (~15 tok)
- `capture.py` — Session ID capture logic for detecting new AI agent sessions. (~1357 tok)
- `discovery.py` — Discover existing Claude Code sessions. (~1265 tok)
- `manager.py` — Session management for Claude Code sessions. (~5997 tok)
- `repair.py` — Conversation file repair utilities for Claude Code sessions. (~3704 tok)
- `summary.py` — Session summary extraction from Claude Code conversation files. (~7501 tok)

## devflow/storage/

- `__init__.py` — Storage abstraction layer for session persistence. (~66 tok)
- `base.py` — Abstract base class for storage backends. (~980 tok)
- `file_backend.py` — File-based storage backend for sessions. (~3352 tok)
- `filters.py` — Session filter criteria for querying sessions. (~286 tok)

## devflow/suggestions/

- `__init__.py` — Repository suggestion system for DevAIFlow. (~67 tok)
- `models.py` — Data models for repository suggestion system. (~1442 tok)
- `suggester.py` — Repository suggestion engine with learning capabilities. (~4212 tok)

## devflow/templates/

- `__init__.py` — Template management for DevAIFlow. (~89 tok)
- `manager.py` — Template manager for DevAIFlow. (~1390 tok)
- `models.py` — Template data models for DevAIFlow. (~1722 tok)

## devflow/ui/

- `__init__.py` — UI components for DevAIFlow. (~10 tok)
- `config_tui.py` — Text User Interface for DevAIFlow configuration. (~44286 tok)
- `session_editor_tui.py` — Text User Interface for editing Claude Session metadata. (~10933 tok)

## devflow/utils/

- `__init__.py` — Utility functions for DevAIFlow. (~60 tok)
- `audit_log.py` — Audit logging for DevAIFlow operations. (~1444 tok)
- `backend_detection.py` — Utilities for detecting issue tracker backend from session metadata and issue keys. (~1809 tok)
- `claude_commands.py` — Utilities for managing bundled Claude Code skills. (~6464 tok)
- `context_files.py` — Utility for loading hierarchical context files from DEVAIFLOW_HOME. (~931 tok)
- `daf_agents_validation.py` — Migration utilities for DAF_AGENTS.md to daf-workflow skill transition. (~4940 tok)
- `dependencies.py` — Dependency checking utilities for external tools. (~1072 tok)
- `git_remote.py` — Git remote detection utilities for issue tracker integration. (~2750 tok)
- `hierarchical_skills.py` — Utilities for managing hierarchical skills from config files. (~15589 tok)
- `model_provider.py` — Utilities for managing model provider configuration and profiles. (~1813 tok)
- `paths.py` — Path utilities for DevAIFlow. (~659 tok)
- `ssl_helper.py` — SSL verification helper for HTTP requests. (~840 tok)
- `temp_directory.py` — Temporary directory utilities for issue tracker ticket creation sessions. (~2726 tok)
- `time_parser.py` — Time expression parser for filtering. (~1026 tok)
- `update_checker.py` — Update checker for DevAIFlow. (~2612 tok)
- `url_parser.py` — URL parser for issue tracker URLs. (~1411 tok)
- `user.py` — User detection utilities. (~192 tok)
- `workspace_utils.py` — Utilities for workspace management and auto-upgrade. (~766 tok)

## devflow/verification/

- `__init__.py` — Verification module for feature orchestration. (~149 tok)
- `artifact_validator.py` — Artifact validator for feature verification. (~1004 tok)
- `criteria_checker.py` — Acceptance criteria checker for feature verification. (~2411 tok)
- `report_generator.py` — Verification report generator for feature orchestration. (~2438 tok)
- `test_runner.py` — Test runner for feature verification. (~1424 tok)

## docs/

- `experimental-agents-validation-tracking.md` — Experimental Agents Validation Tracking (~635 tok)
- `experimental-agents.md` — Experimental AI Agents (~4906 tok)
- `NON_INTERACTIVE_PARAMETERS.md` — Non-Interactive CLI Parameters (~2687 tok)
- `NOTEBOOKLM.md` — DevAIFlow - AI-Optimized Summary (~1840 tok)
- `README.md` — Project documentation (~1316 tok)

## docs/config-templates/

- `enterprise.json` (~452 tok)
- `organization.json` (~795 tok)
- `README.md` — Project documentation (~2101 tok)
- `team.json` — Declares is (~230 tok)
- `user.json` (~604 tok)

## docs/config-templates/backends/

- `jira.json` (~252 tok)

## docs/context-templates/

- `CONFIG.md` — Personal Development Notes (~615 tok)
- `JIRA.md` — JIRA Backend Integration Rules (~440 tok)
- `ORGANIZATION.md` — Organization Coding Standards (~1313 tok)
- `README.md` — Project documentation (~1910 tok)
- `TEAM.md` — Team Conventions and Workflows (~642 tok)

## docs/developer/

- `feature-orchestration-architecture.md` — Feature Orchestration Implementation Summary (~3896 tok)
- `feature-orchestration.md` — Feature Orchestration Flow (~4079 tok)
- `issue-tracker-architecture.md` — Issue Tracker Architecture (~2650 tok)
- `publishing-to-pypi.md` — Publishing DevAIFlow to PyPI (~4007 tok)
- `release-management.md` — Release Management (~4727 tok)

## docs/experimental/

- `feature-orchestration.md` — Feature Orchestration (EXPERIMENTAL) (~6420 tok)
- `README.md` — Project documentation (~867 tok)

## docs/getting-started/

- `installation.md` — Installation Guide (~6151 tok)
- `overview.md` — Overview (~4475 tok)
- `quick-start.md` — Quick Start Guide (~3849 tok)
- `uninstall.md` — Uninstall DevAIFlow (~1806 tok)

## docs/guides/

- `enterprise-model-provider-enforcement.md` — Enterprise Model Provider Enforcement Guide (~4231 tok)
- `hierarchical-skills.md` — Hierarchical Skills Architecture (~9300 tok)
- `multi-agent-skill-installation.md` — Multi-Agent Skill Installation Guide (~2690 tok)
- `session-management.md` — Session Management (~8306 tok)
- `skills-management.md` — Skills Management Guide (~2626 tok)
- `ssl-configuration.md` — SSL Certificate Verification Configuration (~1344 tok)
- `troubleshooting.md` — Troubleshooting Guide (~15008 tok)

## docs/reference/

- `ai-agent-support-matrix.md` — AI Agent Support Matrix (~7493 tok)
- `alternative-model-providers.md` — Alternative Model Providers (~11083 tok)
- `commands.md` — Commands Reference (~48930 tok)
- `configuration.md` — Configuration Reference (~16658 tok)

## docs/tutorials/

- `local-llama-cpp-setup.md` — Tutorial: Run Claude Code with Local Models Using llama.cpp (~3550 tok)
- `README.md` — Project documentation (~194 tok)

## docs/workflows/

- `github-gitlab-integration.md` — GitHub Issue Integration (~4604 tok)
- `jira-integration.md` — JIRA Integration (~10139 tok)
- `WORKFLOWS.md` — DevAIFlow Complete Workflows (~3100 tok)

## htmlcov/

- `.gitignore` — Git ignore rules (~8 tok)
- `class_index.html` — Coverage report (~42121 tok)
- `coverage_html_cb_bcae5fc4.js` — For details: https://github.com/coveragepy/coveragepy/blob/main/NOTICE.txt (~7272 tok)
- `function_index.html` — Coverage report (~177316 tok)
- `index.html` — Coverage report (~17252 tok)
- `status.json` (~13599 tok)
- `style_cb_8432e98f.css` — Styles: 116 rules, 51 media queries (~4553 tok)
- `z_06a117fdecd41ea4___init___py.html` — Coverage for devflow/cli/__init__.py: 100% (~1271 tok)
- `z_06a117fdecd41ea4_completion_py.html` — Coverage for devflow/cli/completion.py: 100% (~8842 tok)
- `z_06a117fdecd41ea4_main_py.html` — Coverage for devflow/cli/main.py: 55% (~223488 tok)
- `z_06a117fdecd41ea4_signal_handler_py.html` — Coverage for devflow/cli/signal_handler.py: 86% (~15496 tok)
- `z_06a117fdecd41ea4_skills_discovery_py.html` — Coverage for devflow/cli/skills_discovery.py: 85% (~8819 tok)
- `z_06a117fdecd41ea4_utils_py.html` — Coverage for devflow/cli/utils.py: 77% (~76642 tok)
- `z_07a4164db4a08fc5___init___py.html` — Coverage for devflow/agent/__init__.py: 100% (~3022 tok)
- `z_07a4164db4a08fc5_claude_agent_py.html` — Coverage for devflow/agent/claude_agent.py: 100% (~15514 tok)
- `z_07a4164db4a08fc5_cursor_agent_py.html` — Coverage for devflow/agent/cursor_agent.py: 85% (~15142 tok)
- `z_07a4164db4a08fc5_factory_py.html` — Coverage for devflow/agent/factory.py: 100% (~5635 tok)
- `z_07a4164db4a08fc5_github_copilot_agent_py.html` — Coverage for devflow/agent/github_copilot_agent.py: 78% (~14244 tok)
- `z_07a4164db4a08fc5_interface_py.html` — Coverage for devflow/agent/interface.py: 71% (~10062 tok)
- `z_07a4164db4a08fc5_windsurf_agent_py.html` — Coverage for devflow/agent/windsurf_agent.py: 85% (~15134 tok)
- `z_10fec4e5b72b7f39___init___py.html` — Coverage for devflow/jira/__init__.py: 100% (~1851 tok)
- `z_10fec4e5b72b7f39_client_py.html` — Coverage for devflow/jira/client.py: 77% (~130187 tok)
- `z_10fec4e5b72b7f39_exceptions_py.html` — Coverage for devflow/jira/exceptions.py: 98% (~10205 tok)
- `z_10fec4e5b72b7f39_field_mapper_py.html` — Coverage for devflow/jira/field_mapper.py: 89% (~38602 tok)
- `z_10fec4e5b72b7f39_transitions_py.html` — Coverage for devflow/jira/transitions.py: 95% (~19776 tok)
- `z_10fec4e5b72b7f39_utils_py.html` — Coverage for devflow/jira/utils.py: 95% (~23772 tok)
- `z_10fec4e5b72b7f39_validation_py.html` — Coverage for devflow/jira/validation.py: 88% (~27717 tok)
- `z_1949ad9a47d2925e___init___py.html` — Coverage for devflow/suggestions/__init__.py: 100% (~1632 tok)
- `z_1949ad9a47d2925e_models_py.html` — Coverage for devflow/suggestions/models.py: 100% (~11175 tok)
- `z_1949ad9a47d2925e_suggester_py.html` — Coverage for devflow/suggestions/suggester.py: 96% (~32285 tok)
- `z_2eb326c2d41ac0bc___init___py.html` — Coverage for devflow/config/schemas/__init__.py: 100% (~1231 tok)
- `z_3cdcc195ef6adc92___init___py.html` — Coverage for devflow/mocks/__init__.py: 100% (~2107 tok)
- `z_3cdcc195ef6adc92_claude_mock_py.html` — Coverage for devflow/mocks/claude_mock.py: 99% (~18365 tok)
- `z_3cdcc195ef6adc92_github_mock_py.html` — Coverage for devflow/mocks/github_mock.py: 97% (~15538 tok)
- `z_3cdcc195ef6adc92_gitlab_mock_py.html` — Coverage for devflow/mocks/gitlab_mock.py: 91% (~20201 tok)
- `z_3cdcc195ef6adc92_jira_mock_py.html` — Coverage for devflow/mocks/jira_mock.py: 87% (~26506 tok)
- `z_3cdcc195ef6adc92_persistence_py.html` — Coverage for devflow/mocks/persistence.py: 92% (~36444 tok)
- `z_506f96be02ce2c1e___init___py.html` — Coverage for devflow/config/validators/__init__.py: 100% (~2633 tok)
- `z_506f96be02ce2c1e_base_py.html` — Coverage for devflow/config/validators/base.py: 100% (~23998 tok)
- `z_506f96be02ce2c1e_enterprise_py.html` — Coverage for devflow/config/validators/enterprise.py: 88% (~4994 tok)
- `z_506f96be02ce2c1e_organization_py.html` — Coverage for devflow/config/validators/organization.py: 88% (~8442 tok)
- `z_506f96be02ce2c1e_team_py.html` — Coverage for devflow/config/validators/team.py: 85% (~6781 tok)
- `z_506f96be02ce2c1e_user_py.html` — Coverage for devflow/config/validators/user.py: 93% (~7743 tok)
- `z_5a3a4486c526beea___init___py.html` — Coverage for devflow/__init__.py: 100% (~1359 tok)
- `z_5a3a4486c526beea_exceptions_py.html` — Coverage for devflow/exceptions.py: 100% (~3165 tok)
- `z_5cd312b2b760ee18___init___py.html` — Coverage for devflow/archive/__init__.py: 100% (~1524 tok)
- `z_5cd312b2b760ee18_base_py.html` — Coverage for devflow/archive/base.py: 98% (~9448 tok)
- `z_69b1b828517c762c___init___py.html` — Coverage for devflow/ui/__init__.py: 100% (~1272 tok)
- `z_69b1b828517c762c_config_tui_py.html` — Coverage for devflow/ui/config_tui.py: 21% (~208454 tok)
- `z_69b1b828517c762c_session_editor_tui_py.html` — Coverage for devflow/ui/session_editor_tui.py: 49% (~82479 tok)
- `z_7ea0fb1e64e286a0___init___py.html` — Coverage for devflow/cli/commands/__init__.py: 100% (~1284 tok)
- `z_7ea0fb1e64e286a0_active_command_py.html` — Coverage for devflow/cli/commands/active_command.py: 100% (~18165 tok)
- `z_7ea0fb1e64e286a0_backup_command_py.html` — Coverage for devflow/cli/commands/backup_command.py: 100% (~4696 tok)
- `z_7ea0fb1e64e286a0_check_command_py.html` — Coverage for devflow/cli/commands/check_command.py: 100% (~9790 tok)
- `z_7ea0fb1e64e286a0_cleanup_command_py.html` — Coverage for devflow/cli/commands/cleanup_command.py: 19% (~45958 tok)
- `z_7ea0fb1e64e286a0_cleanup_sessions_command_py.html` — Coverage for devflow/cli/commands/cleanup_sessions_command.py: 98% (~11265 tok)
- `z_7ea0fb1e64e286a0_complete_command_py.html` — Coverage for devflow/cli/commands/complete_command.py: 46% (~185903 tok)
- `z_7ea0fb1e64e286a0_context_commands_py.html` — Coverage for devflow/cli/commands/context_commands.py: 85% (~16900 tok)
- `z_7ea0fb1e64e286a0_delete_command_py.html` — Coverage for devflow/cli/commands/delete_command.py: 86% (~16608 tok)
- `z_7ea0fb1e64e286a0_discover_command_py.html` — Coverage for devflow/cli/commands/discover_command.py: 99% (~11164 tok)
- `z_7ea0fb1e64e286a0_export_command_py.html` — Coverage for devflow/cli/commands/export_command.py: 93% (~19664 tok)
- `z_7ea0fb1e64e286a0_export_md_command_py.html` — Coverage for devflow/cli/commands/export_md_command.py: 86% (~8114 tok)
- `z_7ea0fb1e64e286a0_import_command_py.html` — Coverage for devflow/cli/commands/import_command.py: 92% (~8967 tok)
- `z_7ea0fb1e64e286a0_import_session_command_py.html` — Coverage for devflow/cli/commands/import_session_command.py: 98% (~15859 tok)
- `z_7ea0fb1e64e286a0_info_command_py.html` — Coverage for devflow/cli/commands/info_command.py: 83% (~37572 tok)
- `z_7ea0fb1e64e286a0_investigate_command_py.html` — Coverage for devflow/cli/commands/investigate_command.py: 45% (~33623 tok)
- `z_7ea0fb1e64e286a0_jira_add_comment_command_py.html` — Coverage for devflow/cli/commands/jira_add_comment_command.py: 90% (~14612 tok)
- `z_7ea0fb1e64e286a0_jira_create_commands_py.html` — Coverage for devflow/cli/commands/jira_create_commands.py: 54% (~104224 tok)
- `z_7ea0fb1e64e286a0_jira_create_dynamic_py.html` — Coverage for devflow/cli/commands/jira_create_dynamic.py: 87% (~16495 tok)
- `z_7ea0fb1e64e286a0_jira_field_utils_py.html` — Coverage for devflow/cli/commands/jira_field_utils.py: 87% (~10481 tok)
- `z_7ea0fb1e64e286a0_jira_new_command_py.html` — Coverage for devflow/cli/commands/jira_new_command.py: 59% (~66095 tok)
- `z_7ea0fb1e64e286a0_jira_open_command_py.html` — Coverage for devflow/cli/commands/jira_open_command.py: 86% (~14179 tok)
- `z_7ea0fb1e64e286a0_jira_update_command_py.html` — Coverage for devflow/cli/commands/jira_update_command.py: 59% (~46487 tok)
- `z_7ea0fb1e64e286a0_jira_update_dynamic_py.html` — Coverage for devflow/cli/commands/jira_update_dynamic.py: 73% (~12793 tok)
- `z_7ea0fb1e64e286a0_jira_view_command_py.html` — Coverage for devflow/cli/commands/jira_view_command.py: 94% (~33872 tok)
- `z_7ea0fb1e64e286a0_link_command_py.html` — Coverage for devflow/cli/commands/link_command.py: 85% (~18020 tok)
- `z_7ea0fb1e64e286a0_list_command_py.html` — Coverage for devflow/cli/commands/list_command.py: 88% (~31566 tok)
- `z_7ea0fb1e64e286a0_new_command_py.html` — Coverage for devflow/cli/commands/new_command.py: 68% (~92566 tok)
- `z_7ea0fb1e64e286a0_note_command_py.html` — Coverage for devflow/cli/commands/note_command.py: 89% (~11029 tok)
- `z_7ea0fb1e64e286a0_open_command_py.html` — Coverage for devflow/cli/commands/open_command.py: 57% (~250185 tok)
- `z_7ea0fb1e64e286a0_pause_command_py.html` — Coverage for devflow/cli/commands/pause_command.py: 100% (~5699 tok)
- `z_7ea0fb1e64e286a0_rebuild_index_command_py.html` — Coverage for devflow/cli/commands/rebuild_index_command.py: 0% (~22269 tok)
- `z_7ea0fb1e64e286a0_release_command_py.html` — Coverage for devflow/cli/commands/release_command.py: 53% (~51449 tok)
- `z_7ea0fb1e64e286a0_repair_conversation_command_py.html` — Coverage for devflow/cli/commands/repair_conversation_command.py: 98% (~25108 tok)
- `z_7ea0fb1e64e286a0_restore_command_py.html` — Coverage for devflow/cli/commands/restore_command.py: 97% (~4992 tok)
- `z_7ea0fb1e64e286a0_resume_command_py.html` — Coverage for devflow/cli/commands/resume_command.py: 100% (~5507 tok)
- `z_7ea0fb1e64e286a0_search_command_py.html` — Coverage for devflow/cli/commands/search_command.py: 94% (~8872 tok)
- `z_7ea0fb1e64e286a0_sessions_list_command_py.html` — Coverage for devflow/cli/commands/sessions_list_command.py: 100% (~11990 tok)
- `z_7ea0fb1e64e286a0_status_command_py.html` — Coverage for devflow/cli/commands/status_command.py: 92% (~29329 tok)
- `z_7ea0fb1e64e286a0_summary_command_py.html` — Coverage for devflow/cli/commands/summary_command.py: 100% (~15753 tok)
- `z_7ea0fb1e64e286a0_sync_command_py.html` — Coverage for devflow/cli/commands/sync_command.py: 86% (~18792 tok)
- `z_7ea0fb1e64e286a0_template_commands_py.html` — Coverage for devflow/cli/commands/template_commands.py: 91% (~16320 tok)
- `z_7ea0fb1e64e286a0_time_command_py.html` — Coverage for devflow/cli/commands/time_command.py: 100% (~9055 tok)
- `z_7ea0fb1e64e286a0_update_command_py.html` — Coverage for devflow/cli/commands/update_command.py: 94% (~5706 tok)
- `z_7ea0fb1e64e286a0_upgrade_command_py.html` — Coverage for devflow/cli/commands/upgrade_command.py: 99% (~17762 tok)
- `z_7ea0fb1e64e286a0_workspace_commands_py.html` — Coverage for devflow/cli/commands/workspace_commands.py: 0% (~37827 tok)
- `z_9071fac653a1ac58___init___py.html` — Coverage for devflow/config/__init__.py: 100% (~1277 tok)
- `z_9071fac653a1ac58_init_wizard_py.html` — Coverage for devflow/config/init_wizard.py: 57% (~28366 tok)
- `z_9071fac653a1ac58_loader_py.html` — Coverage for devflow/config/loader.py: 82% (~66203 tok)
- `z_9071fac653a1ac58_models_py.html` — Coverage for devflow/config/models.py: 94% (~80633 tok)
- `z_9071fac653a1ac58_schema_py.html` — Coverage for devflow/config/schema.py: 95% (~8094 tok)
- `z_9071fac653a1ac58_validator_py.html` — Coverage for devflow/config/validator.py: 94% (~16343 tok)
- `z_9b9d793c7de35baf___init___py.html` — Coverage for devflow/issue_tracker/__init__.py: 100% (~1792 tok)
- `z_9b9d793c7de35baf_factory_py.html` — Coverage for devflow/issue_tracker/factory.py: 100% (~7684 tok)
- `z_9b9d793c7de35baf_interface_py.html` — Coverage for devflow/issue_tracker/interface.py: 69% (~21176 tok)
- `z_9b9d793c7de35baf_mock_client_py.html` — Coverage for devflow/issue_tracker/mock_client.py: 96% (~22186 tok)
- `z_9bdbb123e371d481___init___py.html` — Coverage for devflow/config/validators/backends/__init__.py: 100% (~1830 tok)
- `z_9bdbb123e371d481_base_py.html` — Coverage for devflow/config/validators/backends/base.py: 100% (~2042 tok)
- `z_9bdbb123e371d481_jira_py.html` — Coverage for devflow/config/validators/backends/jira.py: 87% (~9804 tok)
- `z_abdf1e2aecaac275___init___py.html` — Coverage for devflow/backup/__init__.py: 100% (~1276 tok)
- `z_abdf1e2aecaac275_manager_py.html` — Coverage for devflow/backup/manager.py: 87% (~21029 tok)
- `z_af49c4d607f8b748___init___py.html` — Coverage for devflow/templates/__init__.py: 100% (~1745 tok)
- `z_af49c4d607f8b748_manager_py.html` — Coverage for devflow/templates/manager.py: 100% (~11559 tok)
- `z_af49c4d607f8b748_models_py.html` — Coverage for devflow/templates/models.py: 100% (~13438 tok)
- `z_b2fa99fdd7fa1861___init___py.html` — Coverage for devflow/git/__init__.py: 100% (~1277 tok)
- `z_b2fa99fdd7fa1861_pr_template_py.html` — Coverage for devflow/git/pr_template.py: 100% (~20316 tok)
- `z_b2fa99fdd7fa1861_utils_py.html` — Coverage for devflow/git/utils.py: 68% (~94883 tok)
- `z_b85cf9881b04dc76___init___py.html` — Coverage for devflow/storage/__init__.py: 100% (~1681 tok)
- `z_b85cf9881b04dc76_base_py.html` — Coverage for devflow/storage/base.py: 74% (~8717 tok)
- `z_b85cf9881b04dc76_file_backend_py.html` — Coverage for devflow/storage/file_backend.py: 94% (~22838 tok)
- `z_b85cf9881b04dc76_filters_py.html` — Coverage for devflow/storage/filters.py: 100% (~2794 tok)
- `z_bc5e5d4277adbed7___init___py.html` — Coverage for devflow/utils/__init__.py: 100% (~1673 tok)
- `z_bc5e5d4277adbed7_claude_commands_py.html` — Coverage for devflow/utils/claude_commands.py: 80% (~30805 tok)
- `z_bc5e5d4277adbed7_context_files_py.html` — Coverage for devflow/utils/context_files.py: 100% (~5508 tok)
- `z_bc5e5d4277adbed7_dependencies_py.html` — Coverage for devflow/utils/dependencies.py: 100% (~9700 tok)
- `z_bc5e5d4277adbed7_hierarchical_skills_py.html` — Coverage for devflow/utils/hierarchical_skills.py: 4% (~43936 tok)
- `z_bc5e5d4277adbed7_paths_py.html` — Coverage for devflow/utils/paths.py: 100% (~3782 tok)
- `z_bc5e5d4277adbed7_temp_directory_py.html` — Coverage for devflow/utils/temp_directory.py: 100% (~9719 tok)
- `z_bc5e5d4277adbed7_time_parser_py.html` — Coverage for devflow/utils/time_parser.py: 100% (~9634 tok)
- `z_bc5e5d4277adbed7_update_checker_py.html` — Coverage for devflow/utils/update_checker.py: 93% (~20242 tok)
- `z_bc5e5d4277adbed7_user_py.html` — Coverage for devflow/utils/user.py: 100% (~2819 tok)
- `z_bc5e5d4277adbed7_workspace_utils_py.html` — Coverage for devflow/utils/workspace_utils.py: 100% (~5932 tok)
- `z_c41e04e05e7d0bb4___init___py.html` — Coverage for devflow/export/__init__.py: 100% (~1279 tok)
- `z_c41e04e05e7d0bb4_manager_py.html` — Coverage for devflow/export/manager.py: 83% (~49323 tok)
- `z_c41e04e05e7d0bb4_markdown_py.html` — Coverage for devflow/export/markdown.py: 85% (~34916 tok)
- `z_c580db977815c015___init___py.html` — Coverage for devflow/session/__init__.py: 100% (~1278 tok)
- `z_c580db977815c015_capture_py.html` — Coverage for devflow/session/capture.py: 100% (~10159 tok)
- `z_c580db977815c015_discovery_py.html` — Coverage for devflow/session/discovery.py: 100% (~10158 tok)
- `z_c580db977815c015_manager_py.html` — Coverage for devflow/session/manager.py: 88% (~33842 tok)
- `z_c580db977815c015_repair_py.html` — Coverage for devflow/session/repair.py: 83% (~27875 tok)
- `z_c580db977815c015_summary_py.html` — Coverage for devflow/session/summary.py: 93% (~48874 tok)
- `z_c61090a831b66cbd___init___py.html` — Coverage for devflow/config/schemas/backends/__init__.py: 100% (~1242 tok)
- `z_ffa21e95d58bba3e___init___py.html` — Coverage for devflow/release/__init__.py: 100% (~2484 tok)
- `z_ffa21e95d58bba3e_manager_py.html` — Coverage for devflow/release/manager.py: 52% (~101372 tok)
- `z_ffa21e95d58bba3e_permissions_py.html` — Coverage for devflow/release/permissions.py: 84% (~22324 tok)
- `z_ffa21e95d58bba3e_version_py.html` — Coverage for devflow/release/version.py: 100% (~14305 tok)

## integration-tests/

- `configure_test_prompts.py` — Configure prompt settings for integration tests. (~867 tok)
- `README.md` — Project documentation (~2689 tok)
- `run_all_integration_tests.sh` — run_all_integration_tests.sh (~2656 tok)
- `setup_test_config.py` — Create a minimal test configuration for integration tests. (~1690 tok)
- `TEST_COLLABORATION_SCENARIO.md` — Testing Collaboration Workflow: 2-Developer Emulation (~7342 tok)
- `test_collaboration_workflow.sh` — Integration test for collaboration workflow (2-developer emulation) (~7786 tok)
- `test_config.sh` (~88 tok)
- `test_cursor_agent.sh` — test_cursor_agent.sh (~3228 tok)
- `test_devaiflow_home.sh` (~141 tok)
- `test_error_handling.sh` — test_error_handling.sh (~4812 tok)
- `test_feature_orchestration.sh` — test_feature_orchestration.sh (~2462 tok)
- `test_git_sync.sh` — test_git_sync.sh (~2555 tok)
- `test_github_copilot_agent.sh` — test_github_copilot_agent.sh (~3310 tok)
- `test_github_green_path.sh` — test_github_green_path.sh (~3646 tok)
- `test_installation_auto_close.sh` — test_installation_auto_close.sh (~10088 tok)
- `test_investigation.sh` — test_investigation.sh (~4549 tok)
- `TEST_JIRA_GREEN_PATH.md` — JIRA Green Path Integration Test (~2066 tok)
- `test_jira_green_path.sh` — test_jira_green_path.sh (~6030 tok)
- `test_jira_sync.sh` — test_jira_sync.sh (~4579 tok)
- `test_multi_project_workflow.sh` — test_multi_project_workflow.sh (~6131 tok)
- `test_multi_repo.sh` — test_multi_repo.sh (~3855 tok)
- `test_readonly_commands.sh` — test_readonly_commands.sh (~3678 tok)
- `test_session_lifecycle.sh` — test_session_lifecycle.sh (~3853 tok)
- `test_templates.sh` — test_templates.sh (~4062 tok)
- `test_time_tracking.sh` — test_time_tracking.sh (~3736 tok)
- `test_upgrade_project_path.sh` — Integration test for daf upgrade --project-path feature (~1860 tok)
- `test_windsurf_agent.sh` — test_windsurf_agent.sh (~3266 tok)
- `test_workspace_mismatch.sh` — test_workspace_mismatch.sh (~462 tok)

## tests/

- `__init__.py` — Tests for DevAIFlow. (~8 tok)
- `.coverage` (~22896 tok)
- `conftest.py` — Pytest configuration and fixtures. (~10028 tok)
- `coverage.json` (~233462 tok)
- `README.md` — Project documentation (~1090 tok)
- `test_active_command.py` — Tests for daf active command. (~5910 tok)
- `test_agent_commands.py` — Tests for agent management commands (Story 7). (~5984 tok)
- `test_agent_interface.py` — Tests for agent interface abstraction. (~17615 tok)
- `test_auto_create_pr_status.py` — Tests for auto_create_pr_status feature. (~432 tok)
- `test_auto_template.py` — Tests for auto-template creation and usage functionality. (~3330 tok)
- `test_backend_detection.py` — Tests for backend detection utilities. (~2987 tok)
- `test_backup_command.py` — Tests for daf backup command. (~2285 tok)
- `test_backup_manager.py` — Tests for backup/restore manager. (~4663 tok)
- `test_branch_conflict.py` — Tests for branch conflict resolution in _handle_branch_creation. (~4533 tok)
- `test_branch_creation_no_sync_prompt.py` — Tests for issue #139: Unnecessary sync strategy prompt after creating new branch. (~3359 tok)
- `test_branch_from_specific_source.py` — Tests for branch creation from specific source branch. (~3176 tok)
- `test_branch_import_sync.py` — Tests for PROJ-61023: Branch sync on import workflow. (~3361 tok)
- `test_branch_sync_fixes.py` — Tests for branch sync fixes from issue #324. (~3442 tok)
- `test_branch_workflow_ux_fixes.py` — Tests for issue #331: Branch workflow UX issues. (~5629 tok)
- `test_check_command.py` — Tests for daf check command. (~3490 tok)
- `test_claude_agent_skills_filtering.py` — Tests for Claude agent skills filtering in launch_with_prompt. (~4144 tok)
- `test_claude_commands.py` — Tests for devflow/utils/claude_commands.py - bundled skills installation. (~6382 tok)
- `test_claude_config_dir_integration.py` — Integration tests for CLAUDE_CONFIG_DIR environment variable support. (~1166 tok)
- `test_claude_mock.py` — Tests for MockClaudeCode. (~2214 tok)
- `test_cleanup_conversation.py` — Tests for cleanup_conversation command. (~1601 tok)
- `test_release_skill_helper.py` — create_test_repo, test_get_current_version, test_version_mismatch_detection, test_update_version (~2051 tok)

## tests/cli/commands/

- `test_export_command.py` — Tests for daf export command branch sync functionality (PROJ-60772). (~4725 tok)
- `test_feature_command.py` — Tests for daf feature CLI commands. (~9324 tok)
- `test_import_command.py` — Tests for daf import command with improved prompt clarity (PROJ-61022). (~2004 tok)
