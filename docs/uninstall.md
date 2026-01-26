# Uninstall DevAIFlow

## Overview

This guide explains how to completely remove DevAIFlow from your system, including all configuration files, session data, and cached information.

## Before You Uninstall

### Backup Your Data

If you might want to restore your sessions or configuration later:

```bash
# Backup entire DevAIFlow directory
tar -czf devaiflow-backup-$(date +%Y%m%d).tar.gz $DEVAIFLOW_HOME/

# Or backup specific data
cp -r $DEVAIFLOW_HOME/ ~/devaiflow-backup/
```

### Export Active Sessions

If you have active sessions you want to keep:

```bash
# List all sessions
daf list

# Export specific session
daf export my-session-name

# Export all sessions in a workspace
cd ~/workspace/myproject
daf export --all
```

## Complete Uninstall

### Step 1: Uninstall Python Package

```bash
# Uninstall DevAIFlow
pip uninstall devaiflow

# Confirm removal
daf --version  # Should show "command not found"
```

### Step 2: Remove Configuration and Data

**⚠️ WARNING:** This deletes all your sessions, configuration, and history!

```bash
# Remove entire DevAIFlow directory
rm -rf $DEVAIFLOW_HOME/

# Remove workspace configurations (optional)
# Review each workspace first!
find ~/workspace -name "organization.json" -o -name "team.json" -o -name "backends" -type d
```

### Step 3: Remove Claude Code Integration (If Installed)

If you installed DevAIFlow commands in Claude Code:

```bash
# Remove from workspace .claude directory
rm -rf ~/workspace/*/.claude/commands/daf-*
rm -rf ~/workspace/*/.claude/commands/cs-*

# Remove from global Claude Code commands
rm -rf ~/.claude/commands/daf-*
rm -rf ~/.claude/commands/cs-*
```

### Step 4: Clean Up Environment Variables (If Set)

Check your shell configuration files and remove any DevAIFlow-related variables:

```bash
# Check for environment variables
grep -r "DAF_\|CLAUDE_SESSION" ~/.bashrc ~/.zshrc ~/.bash_profile ~/.zprofile 2>/dev/null

# Common variables to remove:
# - CLAUDE_API_KEY (if only used for DevAIFlow)
# - DAF_MOCK_MODE
# - Any workspace paths
```

### Step 5: Remove Git Configuration (If Set)

```bash
# Check for DevAIFlow git aliases
git config --global --list | grep daf

# Remove if found
git config --global --unset alias.daf-status
# (repeat for any other daf-related aliases)
```

## Partial Uninstall (Keep Data)

If you want to keep your session data but remove the application:

```bash
# Uninstall package only
pip uninstall devaiflow

# Keep $DEVAIFLOW_HOME/ for future reinstall
# Data remains intact for later use
```

## Selective Cleanup

### Remove Only Session Data

```bash
# Keep configuration, remove sessions
rm -rf $DEVAIFLOW_HOME/sessions/
rm -rf $DEVAIFLOW_HOME/conversations/
```

### Remove Only Configuration

```bash
# Keep sessions, remove config
rm $DEVAIFLOW_HOME/config.json
rm $DEVAIFLOW_HOME/organization.json
rm $DEVAIFLOW_HOME/team.json
rm -rf $DEVAIFLOW_HOME/backends/
```

## Verification

After uninstall, verify everything is removed:

```bash
# Check command is gone
which daf
which cs

# Check files are gone
ls $DEVAIFLOW_HOME/  # Should not exist or show "No such file or directory"

# Check pip
pip list | grep devaiflow  # Should return nothing
```

## What Gets Removed

### Files Deleted in Complete Uninstall

```
$DEVAIFLOW_HOME/
├── config.json                   # User preferences
├── organization.json             # Organization settings
├── team.json                     # Team settings
├── backends/
│   └── jira.json                # JIRA configuration
├── sessions/
│   └── *.json                   # All session metadata
├── conversations/
│   └── */*.md                   # All conversation history
└── diagnostics/
    └── *.log                    # Debug logs
```

### Workspace Files (Optional Removal)

```
~/workspace/*/
├── organization.json             # Shared team config
├── team.json                     # Shared team config
├── backends/jira.json           # Shared backend config
└── .claude/
    └── commands/daf-*.md        # DevAIFlow commands
```

## Reinstalling Later

If you want to reinstall DevAIFlow after uninstalling:

### With Backup

```bash
# Reinstall
pip install devaiflow

# Restore backup
tar -xzf devaiflow-backup-20260118.tar.gz -C ~/

# Or restore from directory
cp -r ~/devaiflow-backup/.claude-sessions/ ~/
```

### Fresh Install

```bash
# Install
pip install devaiflow

# Initialize with defaults
daf init

# Configure
daf config tui
```

## Troubleshooting

### Command Still Exists After Uninstall

**Cause:** Multiple Python environments or cached executables

**Solution:**
```bash
# Find all installations
which -a daf
pip list | grep devaiflow
pip3 list | grep devaiflow

# Uninstall from all environments
pip uninstall devaiflow
pip3 uninstall devaiflow

# Clear shell hash
hash -r
```

### Permission Denied When Removing Files

**Cause:** Files owned by different user or protected

**Solution:**
```bash
# Check ownership
ls -la $DEVAIFLOW_HOME/

# Remove with sudo if needed (be careful!)
sudo rm -rf $DEVAIFLOW_HOME/

# Or change ownership first
sudo chown -R $USER:$USER $DEVAIFLOW_HOME/
rm -rf $DEVAIFLOW_HOME/
```

### Can't Find All Workspace Configurations

**Cause:** Configs in unexpected locations

**Solution:**
```bash
# Search entire system
find ~ -name "organization.json" -o -name "backends" -type d 2>/dev/null

# Review each location
# Remove only DevAIFlow-related configs
```

## Alternative: Disable Instead of Uninstall

If you want to temporarily disable DevAIFlow:

```bash
# Rename the data directory
mv $DEVAIFLOW_HOME $DEVAIFLOW_HOME.disabled

# DevAIFlow will create fresh config on next run
# To re-enable, just rename back:
# mv $DEVAIFLOW_HOME.disabled $DEVAIFLOW_HOME
```

## Data Retention

### What Happens to Your Data

When you uninstall:

- **Local data:** Completely removed (unless backed up)
- **JIRA tickets:** Remain unchanged (DevAIFlow doesn't delete JIRA data)
- **Git commits:** Remain in your repositories
- **Claude Code history:** Remains in Claude's storage (separate from DevAIFlow)

### What DevAIFlow Never Stores

DevAIFlow never stores:
- Your JIRA password (only username, you authenticate via browser)
- Claude API keys in plain text (stored in system keychain when possible)
- Your code or files (only conversation history and metadata)

## Support

If you're uninstalling due to issues, we'd love to help:

- Report issues: https://github.com/itdove/devaiflow/issues
- Documentation: https://github.com/itdove/devaiflow/docs
- Ask the maintainer why you're leaving (feedback appreciated!)

## Feedback

Before you go, please let us know why you're uninstalling:

```bash
# Quick feedback (optional)
echo "Uninstall reason: [your reason]" > /tmp/daf-uninstall-feedback.txt
```

Common reasons and solutions:

- **Too complex:** Try `daf config tui` for easier setup
- **Not using Claude Code:** DevAIFlow works standalone with Claude API
- **JIRA integration issues:** Check `docs/troubleshooting.md`
- **Workspace conflicts:** Use per-workspace configs
- **Just testing:** Keep it installed and try `daf new --help`

Thank you for trying DevAIFlow!
