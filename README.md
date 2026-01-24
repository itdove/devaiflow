# DevAIFlow (`daf`)

[![PyPI version](https://badge.fury.io/py/devaiflow.svg)](https://badge.fury.io/py/devaiflow)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![GitHub Issues](https://img.shields.io/github/issues/itdove/devaiflow.svg)](https://github.com/itdove/devaiflow/issues)
[![Build Status](https://github.com/itdove/devaiflow/actions/workflows/test.yml/badge.svg)](https://github.com/itdove/devaiflow/actions)

A CLI tool to manage AI coding assistant sessions with optional issue tracker integration.

![Alt DevAIFlow](images/daf-logo-160x160.png)

**AI Assistants:** Claude Code (fully tested) | GitHub Copilot, Cursor, Windsurf (experimental)
**Issue Trackers:** JIRA (currently supported) | Others (planned)

> **Note on Support Status:**
> - **Claude Code**: Fully tested and production-ready ✅
> - **Other AI Assistants**: Experimental - basic functionality works, full testing in progress ⚠️
> - **JIRA**: Currently the only supported issue tracker ✅
> - **Other Issue Trackers**: Planned for future releases 🔮

## Overview

DevAIFlow helps you organize your AI assistant development work into focused sessions. Each session can optionally link to an issue tracker ticket (JIRA currently supported), track time automatically, and maintain context across work sessions. Perfect for managing multiple features, bugs, or experiments without losing context.

The tool integrates seamlessly with GitHub and GitLab to automate PR/MR creation with AI-powered template filling, automatically linking pull requests to JIRA tickets and reducing manual overhead.

### The Problem

When working with AI coding assistants on multiple tasks, you quickly encounter these challenges:

- **Context Pollution** - Mixing conversations from different tickets makes each session less focused and effective
- **Lost History** - Hard to remember what was discussed for each specific task
- **Manual Ticket Updates** - Constantly switching between terminal and browser to update tickets
- **Time Tracking Gaps** - No automatic record of time spent per task
- **Branch Management** - Manually creating and switching branches for each piece of work

### The Solution

DevAIFlow creates a **one-to-one mapping** between your work and AI assistant sessions:

```
Issue Tracker → Session → Conversations → AI Assistant
(PROJ-12345)  (backup)  (#1 backend,   (isolated
                         #2 frontend)    .jsonl files)
```

Each session is an **isolated workspace** with its own:
- AI assistant conversation history
- Git branch
- Time tracking
- Progress notes
- Optional JIRA link

**Named workspaces** enable concurrent multi-branch development - work on the same project in different workspaces (e.g., main branch + experimental feature) without conflicts.

### Why Use This Tool?

**🎯 Stay Focused**
- One session per task means your AI assistant has full context for that specific work
- No more "Which ticket was that for?" confusion
- Resume exactly where you left off with complete conversation history

**⏱️ Save Time**
- Auto-creates git branches from JIRA keys
- Auto-transitions issue tracker tickets (JIRA) (New → In Progress → Done)
- Tracks time automatically when you open/close sessions
- Auto-creates PRs/MRs with AI-filled templates and JIRA linking
- No more manual ticket updates

**📤 Enable Collaboration**
- Export sessions with full conversation history for team handoffs
- Import teammate's sessions to see exactly what they discussed
- Share session templates for common workflows

**🔧 Works Your Way**
- JIRA integration is completely optional
- Use for personal experiments without any ticket
- Gradually adopt features as needed

**Key Features:**
- 🤖 **Multi-AI Support** - Works with Claude Code, GitHub Copilot, Cursor, Windsurf
- 📂 **Multi-Conversation Sessions** - Organize related work across multiple repositories
- 🏢 **Named Workspaces** - Multiple workspaces for concurrent multi-branch development
- 🎫 **Optional Issue Tracker** - Link issue tracker tickets (JIRA supported), or never (your choice)
- ⏱️ **Time Tracking** - Automatic tracking with pause/resume
- 🔄 **Context Loading** - Automatically reads AGENTS.md, CLAUDE.md, and issue tracker tickets
- 🌿 **Git Integration** - Auto-create branches and manage git workflow
- 🔗 **GitHub/GitLab Integration** - Automated PR/MR creation with AI-filled templates
- 📝 **Progress Notes** - Track progress with local-first notes
- 📤 **Export/Import** - Share sessions or backup your work
- ⚙️ **Interactive Configuration** - Full-featured TUI for easy configuration management

## Quick Start

```bash
# Install
pip install .

# Export environment variables for issue tracker (JIRA example)
export JIRA_URL=  # Currently supports JIRA only"https://jira.example.com"
export JIRA_API_TOKEN=<YOUR_JIRA_PAT>

# Initialization
daf init

# Sync JIRA tickets
daf sync

# Open a session for your ticket
daf open PROJ-12345

# Work in your AI assistant...
# Add progress notes
daf note PROJ-12345 "Completed API implementation"

# Complete the session
daf complete PROJ-12345
```

**Alternative:** Create sessions without JIRA:
```bash
daf new --name "fix-login-bug" --goal "Fix login timeout issue"
daf open fix-login-bug
daf complete fix-login-bug
```

**Workspaces:** Organize projects by product or work on same project with different branches:
```bash
# Configure workspaces - organize by product
daf workspace add ~/development/product-a          # Auto-derives name: product-a
daf workspace add ~/development/product-b          # Auto-derives name: product-b
daf workspace add primary ~/development --default

# Or organize for concurrent multi-branch work
daf workspace add experiments ~/experiments

# Work on different products
daf new --name PROJ-123 -w product-a --path ~/development/product-a/backend

# Work on experimental branch (no conflict with main workspace!)
daf new --name PROJ-456 -w experiments --path ~/experiments/myproject

# Sessions remember their workspace
daf open PROJ-123  # Prompts to select which workspace if ambiguous
```

**Configuration:** Use the interactive TUI for easy configuration:
```bash
# Launch the interactive configuration editor
daf config edit

# Or use the alias
daf config tui
```

The TUI provides:
- 📑 Tabbed interface for all configuration sections
- ✅ Input validation for URLs, paths, and required fields
- 💾 Automatic backup creation before saving
- 👀 Preview mode to review changes before saving
- ⌨️ Full keyboard navigation (Tab, Arrow keys, Ctrl+S to save)
- ❓ Built-in help screen (press `?`)

**Next Steps:** See the [Quick Start Guide](docs/03-quick-start.md) for a complete walkthrough.

## Documentation

**New to DevAIFlow?** Choose your path:

- **Quick Decision** (2 min): Read [What is DevAIFlow?](docs/01-overview.md) to see if this tool is right for you
- **Quick Start** (5 min): [Installation](docs/02-installation.md) → [Quick Start](docs/03-quick-start.md) → Create your first session
- **Complete Guide**: Read the documentation sections below in order

---

📚 **[Complete Documentation](docs/)** - Full guides, references, and troubleshooting


### Quick Links

**Core Documentation:**
- **[Installation Guide](docs/02-installation.md)** - Setup instructions and requirements
- **[Session Management](docs/04-session-management.md)** - Understanding sessions and lifecycle
- **[JIRA Integration](docs/05-jira-integration.md)** - Issue tracker integration (JIRA)
- **[Command Reference](docs/07-commands.md)** - Complete CLI command documentation
- **[Configuration](docs/06-configuration.md)** - Customizing the tool for your workflow (includes JSON Schema validation)
- **[Troubleshooting](docs/11-troubleshooting.md)** - Common issues and solutions
- **[Uninstall Guide](docs/uninstall.md)** - Complete uninstallation instructions
- **[AI Agent Support](docs/ai-agent-support-matrix.md)** - Compatibility matrix for different AI assistants


**Additional Resources:**
- **[Uninstall Guide](docs/uninstall.md)** - Complete uninstallation instructions
- **[AI Agent Support](docs/ai-agent-support-matrix.md)** - Compatibility matrix for different AI assistants

**Validation:**
- **[config.schema.json](config.schema.json)** - JSON Schema for validating config.json (use `daf config validate`)

## Supported Platforms

DevAIFlow officially supports:
- **macOS** (Intel and Apple Silicon)
- **Linux** (Ubuntu, Debian, Fedora, RHEL, etc.)
- **Windows 10/11** (see [Windows Installation](docs/02-installation.md#windows-installation))

All core features work across platforms with automatic platform-specific handling for:
- Signal handling (SIGTERM on Unix, SIGBREAK on Windows)
- File locking (fcntl on Unix, atomic writes on Windows)
- Path separators (automatically handled via pathlib)
- Line endings (CRLF on Windows, LF on Unix)

## Requirements

- **Python 3.10, 3.11, or 3.12** - For the `daf` tool (older versions like 3.9 may work but are not officially tested)
- **AI Assistant CLI** - At least one supported AI assistant (Claude Code, GitHub Copilot, Cursor, or Windsurf) must be installed
- **Git** - For branch management features
- **GitHub CLI (`gh`)** (optional) - Required for creating GitHub PRs and fetching PR templates from private repos
- **GitLab CLI (`glab`)** (optional) - Required for creating GitLab MRs and fetching MR templates from private repos
- **Issue Tracker API Token** (optional) - Only required if using issue tracker integration (JIRA currently supported)

See the [Installation Guide](docs/02-installation.md) for detailed setup instructions including issue tracker configuration.

## For Other Organizations

**DevAIFlow is fully generic and works with any JIRA instance.** Configuration is file-based and can be customized for your organization.

1. **Quick Setup**: Use configuration templates to get started
   ```bash
   # Copy templates to your workspace
   cp -r /path/to/devaiflow/docs/config-templates/* ~/workspace/myproject/

   # Customize for your team
   vim ~/workspace/myproject/backends/jira.json      # Set JIRA URL, transitions
   vim ~/workspace/myproject/organization.json       # Set project key
   vim ~/workspace/myproject/team.json              # Set team workstream

   # Commit to git for team sharing
   git add *.json backends/
   git commit -m "Add DevAIFlow workspace configuration"
   ```

2. **Interactive Config**: Use the TUI for easy configuration management
   ```bash
   daf config tui  # Launch interactive configuration editor
   ```

3. **Workspace Configuration** (Recommended for teams):
   - Place config files in workspace root for team sharing
   - Automatic discovery when running `daf` from any subdirectory
   - Version control your team's JIRA settings in git
   - See `docs/config-templates/README.md` for detailed guide

4. **User Configuration** (For personal use):
   - Run `daf init` to configure your JIRA instance
   - Settings stored in `~/.daf-sessions/` directory
   - Personal preferences only, no team sharing

5. **Copy DAF_AGENTS.md**: Copy the `DAF_AGENTS.md` file to your project roots for automatic daf tool guidance in AI assistant sessions
   - This file is automatically loaded when opening sessions
   - Provides complete command reference and best practices
   - Customize JIRA templates to match your organization's standards

**Configuration Files:**
- `backends/jira.json` - JIRA backend settings (URL, field mappings, transitions)
- `organization.json` - Organization-wide settings (project, field aliases)
- `team.json` - Team-specific settings (workstream, comment visibility)
- `config.json` - User personal preferences

See `docs/config-templates/` for complete templates with detailed comments and examples.

## Development

For developers working on the DevAIFlow codebase:

```bash
# Setup
pip install -e ".[dev]"

# Run unit tests
pytest

# Run with coverage
pytest --cov=devflow --cov-report=html

# Run integration tests (shell-based end-to-end tests)
cd integration-tests
./test_jira_green_path.sh

# Run with mock services (isolated from production)
DAF_MOCK_MODE=1 pytest
DAF_MOCK_MODE=1 daf list
```

### Testing

The project includes two types of tests:

**Unit Tests** (`tests/`):
- Python-based tests using pytest
- Test individual functions and classes
- Fast execution with mocks and fixtures
- Run with `pytest`

**Integration Tests** (`integration-tests/`):
- Shell-based end-to-end workflow tests
- Test complete CLI command workflows
- Run in mock mode for isolation
- See `integration-tests/README.md` for details

### Mock Services for Testing

The tool includes a comprehensive mock services infrastructure for integration testing without affecting production data:

```bash
# Enable mock mode
export DAF_MOCK_MODE=1

# All commands now use mock services with isolated data
daf list              # Shows mock sessions only
daf new my-test       # Creates mock session
daf purge-mock-data   # Clear all mock data

# Mock data is stored separately in ~/.daf-sessions/mocks/
```

Mock services include:
- **JIRA**: Tickets, comments, transitions, attachments
- **GitHub**: Pull requests
- **GitLab**: Merge requests
- **Sessions**: Completely isolated session index
- **Claude Code**: Skipped (not launched in mock mode)

#### Testing With and Without Mock Mode

**With Mock Mode** (`DAF_MOCK_MODE=1`):
- ✅ Fast and isolated testing
- ✅ No real JIRA tickets created
- ✅ Claude Code launch is skipped (faster)
- ✅ Perfect for CI/CD pipelines
- ❌ Doesn't test real Claude Code integration

**Without Mock Mode** (no `DAF_MOCK_MODE`):
- ✅ Tests real Claude Code integration
- ✅ Tests real JIRA API operations
- ✅ Validates conversation export/import
- ✅ More realistic end-to-end testing
- ⚠️ Creates real JIRA tickets (requires cleanup)
- ⚠️ Requires JIRA credentials and display environment

**For collaboration testing**, both approaches work:
- Use `DEVAIFLOW_HOME` to simulate multiple developers on one laptop
- See `integration-tests/TEST_COLLABORATION_SCENARIO.md` for detailed step-by-step guides
- Automated test available: `test_collaboration_workflow.sh` (with mock mode)
- Manual testing guide available for no-mock testing (see TEST_COLLABORATION_SCENARIO.md)

See [AGENTS.md](AGENTS.md) for complete development guidelines, architecture, and coding standards.

## Reporting Issues

Found a bug or have a feature request? Please report it on GitHub:

**[Report an Issue](https://github.com/itdove/devaiflow/issues)**

When reporting bugs, please include:
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, daf version)
- Relevant error messages or logs

For security vulnerabilities, please see [SECURITY.md](SECURITY.md) for responsible disclosure guidelines.

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Development setup
- Running tests
- Submitting pull requests
- Code style guidelines

## License

Apache License 2.0
