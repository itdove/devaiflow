# Installation Guide

## Supported Platforms

DevAIFlow officially supports:
- **macOS** (Intel and Apple Silicon)
- **Linux** (Ubuntu, Debian, Fedora, RHEL, etc.)
- **Windows 10/11** (see [Windows Installation](#windows-installation) below)

## Prerequisites

### Required

- **Python 3.10, 3.11, or 3.12**
  ```bash
  python --version  # Check your version
  ```

  **Note:** Python 3.9 may work but is not officially tested. Python 3.13+ has not been tested yet.

- **Claude Code CLI**
  - Install from: https://docs.claude.com/en/docs/claude-code/installation
  - Verify: `claude --version`

- **Git**
  ```bash
  git --version  # Should be 2.x or higher
  ```

### Optional (for PR/MR Creation and Template Fetching)

- **GitHub CLI (`gh`)**
  - Install from: https://cli.github.com/
  - Verify: `gh --version`
  - Required for:
    - Creating GitHub pull requests via `daf complete`
    - Fetching PR templates from private GitHub repositories
  - Setup: `gh auth login`

- **GitLab CLI (`glab`)**
  - Install from: https://gitlab.com/gitlab-org/cli
  - Verify: `glab --version`
  - Required for:
    - Creating GitLab merge requests via `daf complete`
    - Fetching MR templates from private GitLab repositories
  - Setup: `glab auth login`

### Optional (for JIRA Integration)

- **JIRA API Token**
  - Only needed if you want JIRA integration
  - Without it, the tool works for local session management only

## Installation Methods

### Method 1: From PyPI (Recommended)

Install the latest stable release from PyPI:

```bash
pip install devaiflow
```

**Verify installation:**
```bash
daf --version
daf --help
```

**Check dependencies:**
```bash
daf check
```

This will verify all required and optional tools are installed. See [Verifying Dependencies](#verifying-dependencies) below.

### Method 2: From Source (Development)

For development or contributing:

```bash
# Clone the repository
git clone https://github.com/itdove/devaiflow.git
cd devaiflow

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

## Windows Installation

DevAIFlow is fully supported on Windows 10 and Windows 11. Follow these steps for Windows-specific installation.

### Prerequisites for Windows

1. **Python 3.10, 3.11, or 3.12**
   ```powershell
   # Check if Python is installed
   python --version

   # If not installed, download from python.org or use winget:
   winget install Python.Python.3.12
   ```

2. **Claude Code CLI**
   ```powershell
   # Install using winget
   winget install Anthropic.Claude

   # Verify installation
   claude --version
   ```

3. **Git for Windows**
   ```powershell
   # Install using winget
   winget install Git.Git

   # Verify installation
   git --version
   ```

4. **Optional: GitHub CLI**
   ```powershell
   # Install using winget
   winget install GitHub.cli

   # Verify and authenticate
   gh --version
   gh auth login
   ```

5. **Optional: GitLab CLI**
   - Download from: https://gitlab.com/gitlab-org/cli/-/releases
   - Extract to a directory in your PATH
   - Or use scoop: `scoop install glab`

### Installing DevAIFlow on Windows

**Using PowerShell:**

```powershell
# Navigate to the repository
cd C:\Users\YourUsername\development\devaiflow

# Install using pip
pip install .

# Verify installation
daf --version
daf check
```

**Using Command Prompt:**

```cmd
# Navigate to the repository
cd C:\Users\YourUsername\development\devaiflow

# Install using pip
pip install .

# Verify installation
daf --version
daf check
```

### Windows-Specific Configuration

**Environment Variables:**

Set environment variables in PowerShell (add to your PowerShell profile for persistence):

```powershell
# Edit your PowerShell profile
notepad $PROFILE

# Add these lines:
$env:JIRA_API_TOKEN = "your-api-token-here"
$env:JIRA_URL = "https://jira.example.com"

# Save and reload:
. $PROFILE
```

Or set them permanently via System Properties:
1. Search for "Environment Variables" in Windows Start menu
2. Click "Environment Variables" button
3. Add new User variables:
   - Name: `JIRA_API_TOKEN`, Value: your token
   - Name: `JIRA_URL`, Value: your JIRA URL

### Windows Path Configuration

Ensure Python Scripts directory is in your PATH:

```powershell
# Check if Python Scripts is in PATH
$env:PATH -split ';' | Select-String "Python.*Scripts"

# If not found, add it (typical location):
$env:PATH += ";C:\Users\YourUsername\AppData\Local\Programs\Python\Python312\Scripts"
```

To make it permanent:
1. Search for "Environment Variables" in Windows Start menu
2. Edit the "Path" variable
3. Add: `C:\Users\YourUsername\AppData\Local\Programs\Python\Python312\Scripts`

### Windows Testing Requirements

**Integration Tests on Windows:**

Integration tests (`test_collaboration_workflow.sh`, `test_jira_green_path.sh`) require bash and are not supported natively on Windows. Options:

1. **WSL (Windows Subsystem for Linux)** - Recommended
   ```powershell
   # Install WSL
   wsl --install

   # Run tests in WSL
   wsl
   cd /mnt/c/Users/YourUsername/development/devaiflow
   ./integration-tests/test_collaboration_workflow.sh
   ```

2. **Git Bash**
   - Comes with Git for Windows
   - Open Git Bash terminal
   - Navigate to repository
   - Run: `./integration-tests/test_collaboration_workflow.sh`

3. **Skip Integration Tests**
   - Unit tests work natively on Windows
   - Integration tests are optional for development
   - CI/CD covers integration testing

### Known Windows-Specific Behaviors

**File Locking:**
- Windows file locking works differently from Unix systems
- DevAIFlow automatically disables fcntl-based file locking on Windows
- Session files use atomic write operations instead
- No action required - handled automatically

**Path Separators:**
- DevAIFlow uses `pathlib.Path` for cross-platform path handling
- Both forward slashes (`/`) and backslashes (`\`) work correctly
- Long path support (>260 characters) is automatically handled

**Signal Handling:**
- Windows uses `SIGBREAK` instead of Unix `SIGTERM`
- DevAIFlow automatically uses the correct signal for your platform
- Ctrl+C works as expected to interrupt operations

### Troubleshooting Windows Installation

**Problem:** `daf: command not found`

**Solution:**
```powershell
# Ensure Python Scripts is in PATH
python -m pip show devaiflow
# Note the "Location" path
# Add Location\Scripts to your PATH environment variable
```

**Problem:** `ModuleNotFoundError: No module named 'devflow'`

**Solution:**
```powershell
# Reinstall the package
pip uninstall devaiflow
pip install .
```

**Problem:** Permission errors during installation

**Solution:**
```powershell
# Install for current user only
pip install --user .
```

**Problem:** Git commands fail with "git: command not found"

**Solution:**
```powershell
# Ensure Git is in PATH
git --version

# If not found, add Git to PATH:
# Typical location: C:\Program Files\Git\cmd
```

**Problem:** Claude Code doesn't launch from PowerShell

**Solution:**
```powershell
# Verify Claude is in PATH
claude --version

# If not found, find installation directory:
Get-Command claude -ErrorAction SilentlyContinue

# Add to PATH if needed
```

For more troubleshooting, see [Windows Troubleshooting Guide](11-troubleshooting.md#windows-specific-issues).

## Setting Up JIRA Integration (Optional)

Skip this section if you don't plan to use JIRA integration.

The tool uses the JIRA REST API directly - no additional CLI tools are needed!

### 1. Get JIRA API Token

**For Atlassian Cloud:**
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a name (e.g., "DevAIFlow")
4. Copy the token (you won't see it again!)

**For Enterprise JIRA or Self-Hosted:**
1. Go to your JIRA instance → Profile → Personal Access Tokens
2. Create a new token
3. Copy the token value

### 2. Configure Environment Variables

Add these to your shell profile (`~/.bashrc`, `~/.zshrc`, `~/.profile`, etc.):

```bash
# Required: JIRA API Token
export JIRA_API_TOKEN="your-api-token-here"

# Optional: JIRA URL (defaults to https://jira.example.com)
export JIRA_URL="https://jira.example.com"

# Optional: Enable debug logging for JIRA API calls (troubleshooting)
export DEVAIFLOW_DEBUG=1
```

**For jira-cli config fallback:**
The tool can also read the JIRA URL from `~/.config/.jira/.config.yml` if you have jira-cli installed, but this is not required.

**Reload your shell:**
```bash
source ~/.zshrc  # or ~/.bashrc, ~/.profile, etc.
```

### 3. Verify JIRA Setup

```bash
# Test by listing your sessions
daf sync --dry-run
```

If this shows your JIRA tickets, the integration is working!

## Configuring DevAIFlow

### 1. Initialize Configuration

```bash
daf init
```

This launches an interactive wizard that prompts for:
- **JIRA URL and project key** - Your JIRA instance details
- **Comment visibility** - Control who can see DevAIFlow's JIRA comments (group or role)
- **Workspace path** - Your main development directory
- **Optional settings** - Keyword mappings for multi-repo suggestions, PR template URL

All settings can be changed later using `daf config tui`.

### 2. Install Claude Code Commands

After initializing configuration, install the DevAIFlow slash commands and skills into Claude Code:

```bash
daf upgrade
```

This installs:
- **Slash commands** (`/daf-*`) into `<workspace>/.claude/commands/`
- **Skills** into `<workspace>/.claude/skills/`

These enable you to use DevAIFlow features directly within Claude Code sessions.

**Example usage:**
```bash
# Preview what would be installed
daf upgrade --dry-run

# Install both commands and skills
daf upgrade

# Install only commands
daf upgrade --commands-only
```

### 3. Edit Configuration (Optional)

Edit `$DEVAIFLOW_HOME/config.json`:

```json
{
  "jira": {
    "url": "https://jira.example.com",
    "user": "your-username",
    "transitions": {
      "on_start": {
        "from": ["New", "To Do"],
        "to": "In Progress",
        "prompt": false,
        "on_fail": "warn"
      },
      "on_complete": {
        "prompt": true
      }
    },
    "time_tracking": true
  },
  "repos": {
    "workspace": "/Users/your-username/development/workspace",
    "detection": {
      "method": "keyword_match",
      "fallback": "prompt"
    },
    "keywords": {
      "workspace-management-service": ["backup", "restore", "subscription"],
      "workspace-sops": ["terraform", "github", "custom-properties"]
    }
  }
}
```

**Key Settings:**

- `jira.url` - Your JIRA instance URL
- `jira.user` - Your JIRA username
- `jira.transitions` - Auto-transition configuration
- `repos.workspace` - Your main development directory
- `repos.keywords` - Keywords for smart repository detection

See [Configuration Reference](06-configuration.md) for detailed configuration options.

### 3. Set Up Shell Completion (Optional)

Enable tab completion for the `daf` command:

**Bash:**
```bash
# Add to ~/.bashrc
eval "$(_DAF_COMPLETE=bash_source daf)"

# Reload
source ~/.bashrc
```

**Zsh:**
```bash
# Add to ~/.zshrc
eval "$(_DAF_COMPLETE=zsh_source daf)"

# Reload
source ~/.zshrc
```

**Fish:**
```bash
# Save to completion file
_DAF_COMPLETE=fish_source daf > ~/.config/fish/completions/daf.fish
```

## Verifying Installation

### Check Dependencies

After installation, verify all required and optional tools are installed:

```bash
daf check
```

**Expected output:**
```
Checking dependencies for DevAIFlow...

Required Dependencies:
┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Tool   ┃ Status ┃ Version         ┃ Description          ┃
┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ git    │ ✓      │ git version ... │ Git version control  │
│ claude │ ✓      │ claude 1.2.3    │ Claude Code CLI      │
└────────┴────────┴─────────────────┴──────────────────────┘

Optional Dependencies:
┏━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Tool  ┃ Status ┃ Version       ┃ Description               ┃
┡━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ gh    │ ✓      │ gh 2.40.1     │ GitHub CLI                │
│ glab  │ ✓      │ glab 1.35.0   │ GitLab CLI                │
│ pytest│ ✓      │ pytest 7.4.3  │ Python testing framework  │
└───────┴────────┴───────────────┴───────────────────────────┘

✓ All required dependencies available
```

**If any required tools are missing:**
- See [Prerequisites](#prerequisites) for installation instructions
- See [Troubleshooting Guide](11-troubleshooting.md#dependency-issues) for help

### Verify Basic Functionality

Run these commands to verify everything is set up:

```bash
# 1. Check daf is installed
daf --version

# 2. Check daf can find config
daf list  # Should show empty list or existing sessions

# 3. Test JIRA integration (if configured)
daf sync --dry-run  # Preview what would be synced
```

## Troubleshooting Installation

### Python Version Issues

**Error:** `python: command not found`

**Solution:**
```bash
# Try python3
python3 --version

# If that works, create an alias
alias python=python3
```

### Permission Denied

**Error:** `Permission denied when installing`

**Solution:**
```bash
# Use --user flag
pip install --user .
```

### JIRA Authentication Fails

**Error:** `Authentication failed` or `401 Unauthorized` or `JIRA_API_TOKEN not set`

**Solutions:**
1. Verify token is set: `echo $JIRA_API_TOKEN`
2. Check token hasn't expired
3. For Enterprise JIRA, ensure you're using Personal Access Token (not API token)
4. Reload your shell: `source ~/.zshrc`
5. Test with: `daf sync --dry-run`

### Config File Not Found

**Error:** `Config file not found`

**Solution:**
```bash
# Create it
daf init

# Verify location
ls $DEVAIFLOW_HOME/config.json
```

## Upgrading

```bash
cd ~/development/workspace/devaiflow
git pull  # Get latest code
pip install --upgrade .
```

## Uninstalling

```bash
pip uninstall devaiflow
```

### Remove Data (Optional)

```bash
# Backup first!
cp -r $DEVAIFLOW_HOME $DEVAIFLOW_HOME.backup

# Remove all data
rm -rf $DEVAIFLOW_HOME
```

**Note:** This does NOT delete your Claude Code conversation files in `~/.claude/projects/`.

## Setting Up DAF_AGENTS.md (Required)

**IMPORTANT:** DAF_AGENTS.md is **required** for Claude Code sessions. When you run `daf open`, the tool validates that DAF_AGENTS.md exists before launching Claude.

### Where to Place DAF_AGENTS.md

DAF_AGENTS.md can be placed in one of two locations (checked in this order):

**Option 1: Repository Directory (Recommended for Customization)**

Place DAF_AGENTS.md in your project repository for project-specific customization:

```bash
# Copy to your project repository
cp /path/to/devaiflow/DAF_AGENTS.md ~/your-project/
cd ~/your-project
git add DAF_AGENTS.md
git commit -m "Add DAF_AGENTS.md"
```

**Benefits:**
- ✅ Customize JIRA templates for this specific project
- ✅ Version controlled with your project
- ✅ Different customizations per project

**Option 2: Workspace Directory (Shared Across All Projects)**

Place DAF_AGENTS.md in your workspace root to share it across all projects:

```bash
# Copy to workspace (e.g., ~/development/workspace/)
cp /path/to/devaiflow/DAF_AGENTS.md ~/development/workspace/
```

**Benefits:**
- ✅ One file shared across all projects in the workspace
- ✅ Easier maintenance (update once, affects all projects)
- ✅ Good for standardized workflows across many projects

### Lookup Order

When you run `daf open`, the tool searches for DAF_AGENTS.md in this order:

1. **Repository directory** (`~/your-project/DAF_AGENTS.md`) - Project-specific
2. **Workspace directory** (`~/your-workspace/DAF_AGENTS.md`) - Shared
3. **Error** - If not found in either location, Claude Code won't start

**Example error if not found:**
```
✗ DAF_AGENTS.md not found

Searched locations:
  1. Repository: /Users/you/my-project/DAF_AGENTS.md
  2. Workspace:  /Users/you/workspace/DAF_AGENTS.md
```

### Automatic Installation and Upgrades

**Auto-Installation on First Use**

If DAF_AGENTS.md is not found, `daf open` will offer to install the bundled version automatically:

```
⚠ DAF_AGENTS.md not found

DAF_AGENTS.md provides daf tool usage instructions to Claude.

Install DAF_AGENTS.md now?
This will copy the bundled DAF_AGENTS.md to: /Users/you/my-project/DAF_AGENTS.md
Install DAF_AGENTS.md to repository? [y/n] (y):
```

**Auto-Upgrade Detection**

When you upgrade the daf package (via `pip install --upgrade --force-reinstall .`), the bundled DAF_AGENTS.md may contain improvements:
- New command documentation
- Updated JIRA Wiki markup guidance
- Improved workflow instructions
- Template updates

When you run `daf open`, the tool automatically detects if your installed DAF_AGENTS.md is outdated by comparing content with the bundled version. If different, you'll see:

```
⚠ DAF_AGENTS.md has been updated
The bundled version contains newer documentation and command updates.

Upgrade DAF_AGENTS.md to the latest version?
This will replace: /Users/you/my-project/DAF_AGENTS.md
Upgrade to latest version? [y/n] (y):
```

**Upgrade Behavior:**
- **Accept (y)**: Replaces your installed file with the latest bundled version
- **Decline (n)**: Continues with your current version (session opens normally)
- **Mock mode**: Auto-upgrades without prompting (for automated testing)

**Note:** If you've customized DAF_AGENTS.md (e.g., modified JIRA templates), the upgrade will overwrite your changes. Before accepting, consider backing up your customizations.

### What DAF_AGENTS.md Provides

- Complete daf tool command reference
- JIRA integration workflows and templates
- Git and PR/MR creation guidelines
- Session management best practices
- Troubleshooting tips

**Note:** DAF_AGENTS.md is automatically read as a default context file (like AGENTS.md and CLAUDE.md) when you run `daf open`. You don't need to configure it manually.

### Customizing for Your Organization

**IMPORTANT**: DAF_AGENTS.md uses generic placeholders (PROJECT, YourWorkstream, gitlab.example.com) intentionally. Actual values are configured in `$DEVAIFLOW_HOME/config.json` via `daf config` commands, NOT by editing DAF_AGENTS.md.

#### Configuration: What Goes Where

**Configured in `$DEVAIFLOW_HOME/config.json` (via `daf config`):**
- ✅ JIRA URL, project key, workstream
- ✅ Affected version for bugs
- ✅ Field mappings (acceptance_criteria, epic_link, etc.)
- ✅ Workflow settings (auto-add summary, auto-create PR, etc.)
- ✅ Repository paths and detection settings
- ✅ Claude model and AI settings
- ✅ Git remote URLs (detected from `git remote -v`)

**Customized in DAF_AGENTS.md (manual editing):**
- ✅ JIRA issue templates (Epic, Story, Bug, Task format)
- ✅ Organization-specific workflows and best practices

That's it! Most configuration is automatic or done via `daf config`.

#### Configure Settings via `daf config`

```bash
# Interactive configuration (recommended)
daf config tui
```

**What's configurable** (via `daf config edit` TUI):
- **JIRA Tab:** URL, project, workstream, field mappings, visibility
- **Repository Tab:** Workspace path, detection method, branch naming
- **Claude Tab:** Model selection, temperature, Vertex AI settings
- **Session Workflow Tab:** Testing prompts, PR/MR auto-creation
- **Advanced Tab:** Context files, export settings

#### Customize DAF_AGENTS.md Templates

**The ONE thing to customize in DAF_AGENTS.md:**

**JIRA Issue Templates** ⭐

Location: Search for `#### JIRA Issue Templates` in DAF_AGENTS.md

These templates define the structure for issues created with `daf jira create`. Customize to match your organization's JIRA standards:

```bash
# 1. Copy DAF_AGENTS.md to your project
cp /path/to/devaiflow/DAF_AGENTS.md ~/my-project/

# 2. Edit JIRA templates
cd ~/my-project
vim DAF_AGENTS.md
# Find: #### JIRA Issue Templates
# Customize: Epic, Story, Bug, Task, Spike templates to match your org
```

**Why customize templates?**
Every organization has different JIRA standards:
- Required sections and field names
- Format requirements (Jira Wiki markup style)
- Company-specific information to include
- Validation and approval workflows

**Example - Your organization's Bug Template might require:**
```
h3. *Problem Statement*
<Brief description>

h3. *Environment*
- Version: <release>
- Platform: <OS/browser>

h3. *Business Impact*
- Severity: <Critical/High/Medium/Low>
- Users affected: <number/percentage>

h3. *Steps to Reproduce*
1. <step 1>
2. <step 2>
```

Instead of the generic template provided.

#### Complete Setup Example

```bash
# 1. Configure via daf config
daf config edit
# Set: JIRA URL, project, workstream, affected version, etc.

# 2. Copy DAF_AGENTS.md
cp /path/to/devaiflow/DAF_AGENTS.md ~/my-project/
cd ~/my-project

# 3. Customize JIRA templates
vim DAF_AGENTS.md
# Navigate to "#### JIRA Issue Templates"
# Edit Epic, Story, Bug, Task formats to match your org's standards

# 4. Commit to version control
git add DAF_AGENTS.md
git commit -m "Add customized DAF_AGENTS.md for our team"
```

### Key Takeaways

**DO NOT edit DAF_AGENTS.md to add:**
- Project keys, workstreams, JIRA URLs → Use `daf config`
- GitLab/GitHub hostnames → Auto-detected from `git remote -v`
- Repository paths → Use `daf config`

**DO edit DAF_AGENTS.md only to customize:**
- JIRA issue template formats (Epic, Story, Bug, Task, Spike)
- Organization-specific best practices (optional)

DAF_AGENTS.md is generic by design - it uses placeholders that are filled in at runtime from your `$DEVAIFLOW_HOME/config.json` and git configuration.

## Configuring Claude Code Permissions

**CRITICAL**: Claude Code must be configured to allow reading context files from `$DEVAIFLOW_HOME/` and `$DEVAIFLOW_HOME/`. Without this, the tool will fail when Claude tries to read organization context files.

### Why This Matters

DevAIFlow creates context files in `$DEVAIFLOW_HOME/` that Claude Code automatically reads when you run `daf open` or `daf jira new`:

- `$DEVAIFLOW_HOME/backends/JIRA.md` - JIRA integration rules
- `$DEVAIFLOW_HOME/ENTERPRISE.md` - Enterprise-wide policies and standards
- `$DEVAIFLOW_HOME/ORGANIZATION.md` - Organization-wide standards (JIRA templates, Wiki markup requirements)
- `$DEVAIFLOW_HOME/TEAM.md` - Team conventions
- `$DEVAIFLOW_HOME/USER.md` - Personal notes and preferences

By default, Claude Code may block access to these directories because they are dotfiles (start with `.`).

**CRITICAL:** These files must be readable from ALL working directories, including temporary directories created by `daf jira new`. This is why the allow list MUST be in the global `~/.claude/settings.json`, not in project-specific settings files.

### Required Configuration

Add file access permissions to your **global** Claude Code settings file:

**Location:** `~/.claude/settings.json`

**IMPORTANT:** Use the global settings file (`~/.claude/settings.json`), NOT the project-local file (`.claude/settings.local.json`). Project-local settings files are typically not committed to version control and won't be available when using `daf jira new` or when other team members clone the repository.

**Add this configuration:**

```json
{
  "permissions": {
    "allow": [
      "Read($DEVAIFLOW_HOME/ENTERPRISE.md)",
      "Read($DEVAIFLOW_HOME/ORGANIZATION.md)",
      "Read($DEVAIFLOW_HOME/TEAM.md)",
      "Read($DEVAIFLOW_HOME/USER.md)"
    ]
  }
}
```

**IMPORTANT:** Replace `$DEVAIFLOW_HOME` with your actual DevAIFlow home directory:
- **Default location**: `~/.daf-sessions` (if you haven't customized it)
- **Custom location**: Use the value of your `DEVAIFLOW_HOME` environment variable

**Example with default location:**
```json
{
  "permissions": {
    "allow": [
      "Read(~/.daf-sessions/ENTERPRISE.md)",
      "Read(~/.daf-sessions/ORGANIZATION.md)",
      "Read(~/.daf-sessions/TEAM.md)",
      "Read(~/.daf-sessions/USER.md)"
    ]
  }
}
```

### Step-by-Step Setup

1. **Create or edit the settings file:**
   ```bash
   # Check if file exists
   ls ~/.claude/settings.json

   # If not, create it (using default ~/.daf-sessions location)
   mkdir -p ~/.claude
   cat > ~/.claude/settings.json << 'EOF'
{
  "permissions": {
    "allow": [
      "Read(~/.daf-sessions/ENTERPRISE.md)",
      "Read(~/.daf-sessions/ORGANIZATION.md)",
      "Read(~/.daf-sessions/TEAM.md)",
      "Read(~/.daf-sessions/USER.md)"
    ]
  }
}
EOF
   ```

   **Note:** If you set a custom `DEVAIFLOW_HOME` environment variable, replace `~/.daf-sessions` with your custom path.

2. **Verify the file:**
   ```bash
   cat ~/.claude/settings.json
   ```

3. **Test with daf:**
   ```bash
   # Create a test context file
   echo "# Test Organization Context" > $DEVAIFLOW_HOME/ORGANIZATION.md

   # Open a session and verify Claude can read it
   daf new --name test-permissions --goal "Test Claude Code permissions"
   # In the Claude Code session, ask: "Can you read $DEVAIFLOW_HOME/ORGANIZATION.md?"
   ```

### Why Global Settings?

The allow list **must** be in the global `~/.claude/settings.json` file because:

1. **Project-local settings aren't portable:** Project `.claude/settings.local.json` files are typically git-ignored and not pushed to repositories
2. **daf jira new requires access:** When creating JIRA tickets with codebase analysis, Claude needs to read `$DEVAIFLOW_HOME/ORGANIZATION.md` for organization standards
3. **Team consistency:** All team members need the same access permissions, which global settings ensure

**Do NOT use `.claude/settings.local.json` in the project directory** for this configuration - it won't be available across different working directories or for team members.

### Common Issues

**Problem:** "Permission denied" when Claude tries to read context files

**Cause:** Claude Code settings don't allow reading from `$DEVAIFLOW_HOME/`

**Solution:** Add the paths to `file_access.read` array as shown above

**Problem:** Settings file doesn't seem to work

**Cause:** JSON syntax error

**Solution:** Validate your JSON:
```bash
python -m json.tool ~/.claude/settings.json
```

**Problem:** Changes not taking effect

**Cause:** Claude Code caches settings

**Solution:** Restart Claude Code completely (exit and reopen)

### Security Considerations

**What this allows:**
- Claude can read context files from `$DEVAIFLOW_HOME/` and `$DEVAIFLOW_HOME/`
- These directories only contain markdown documentation files
- No sensitive credentials or secrets stored in these locations

**What this does NOT allow:**
- Writing to these directories (read-only access)
- Accessing other dotfiles or system directories
- Reading files outside the specified paths

### Verifying Setup

After configuration, verify Claude Code can read context files:

```bash
# 1. Create test file
echo "# Test Content" > $DEVAIFLOW_HOME/ORGANIZATION.md

# 2. Open a session
daf open PROJ-12345

# 3. In Claude Code, it should automatically read the file
# Check the initial prompt - it should include instructions to read the file
```

For troubleshooting, see [Troubleshooting Guide - Claude Code Permission Issues](11-troubleshooting.md#claude-code-permission-issues).

## Next Steps

- [Quick Start Guide](03-quick-start.md) - Create your first session
- [Configuration Reference](06-configuration.md) - Customize the tool
- [Commands Reference](07-commands.md) - Learn available commands
