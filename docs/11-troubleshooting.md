# Troubleshooting Guide

Common issues and their solutions.

## Dependency Issues

### Missing Required Tool - git command not found

**Problem:** Error message: "git command not found. Required for: create branch"

**Cause:** Git is not installed or not in PATH.

**Solution:**
1. **Check if git is installed:**
   ```bash
   daf check
   ```

2. **Install git:**
   - macOS: `brew install git` or download from https://git-scm.com/downloads
   - Linux: `sudo apt install git` (Ubuntu/Debian) or `sudo yum install git` (RHEL/CentOS)
   - Windows: Download from https://git-scm.com/downloads

3. **Verify installation:**
   ```bash
   git --version
   daf check
   ```

### Missing Required Tool - claude command not found

**Problem:** Error message: "claude command not found. Required for: launch Claude Code session"

**Cause:** Claude Code CLI is not installed or not in PATH.

**Solution:**
1. **Install Claude Code CLI:**
   - Follow instructions at: https://docs.claude.com/en/docs/claude-code/installation

2. **Verify installation:**
   ```bash
   claude --version
   daf check
   ```

### Missing Optional Tool - gh/glab not found

**Problem:** When running `daf complete`, error: "gh command not found. Required for: create GitHub pull request"

**Cause:** GitHub CLI (gh) or GitLab CLI (glab) not installed.

**Solution:**

**For GitHub (gh):**
1. **Install gh CLI:**
   - macOS: `brew install gh`
   - Linux: Follow instructions at https://cli.github.com/
   - Windows: `winget install GitHub.cli`

2. **Authenticate:**
   ```bash
   gh auth login
   ```

3. **Verify:**
   ```bash
   gh --version
   daf check
   ```

**For GitLab (glab):**
1. **Install glab CLI:**
   - macOS: `brew install glab`
   - Other platforms: https://gitlab.com/gitlab-org/cli

2. **Authenticate:**
   ```bash
   glab auth login --hostname gitlab.example.com
   ```

3. **Verify:**
   ```bash
   glab --version
   daf check
   ```

**Note:** These are optional - you can manually create PRs/MRs if these tools aren't installed.

### Dependency Check Before Operations

**Best Practice:**

After installing the daf tool, run:
```bash
daf check
```

This verifies all dependencies are correctly installed and shows which optional features are available.

**In CI/CD pipelines:**
```bash
# Check dependencies and fail if required tools missing
daf check || exit 1

# Or check with JSON output for parsing
daf check --json | jq '.data.all_required_available'
```

## Claude Code Permission Issues

### Context Files Cannot Be Read - Permission Denied

**Problem:** When running `daf open`, Claude Code shows "Permission denied" errors when trying to read files from `~/.daf-sessions/` or `~/.daf-sessions/`

**Example Error:**
```
Error: Cannot read file: ~/.daf-sessions/ORGANIZATION.md
Permission denied
```

**Cause:** Claude Code settings don't allow reading from these directories. By default, Claude Code may block access to dotfiles (directories starting with `.`).

**Solution:**

1. **Add file access permissions to Claude Code settings:**

   Create or edit `~/.claude/settings.json`:
   ```bash
   mkdir -p ~/.claude
   cat > ~/.claude/settings.json << 'EOF'
{
  "file_access": {
    "read": [
      "~/.daf-sessions/**/*",
      "~/.daf-sessions/**/*"
    ]
  }
}
EOF
   ```

2. **Verify the configuration:**
   ```bash
   cat ~/.claude/settings.json
   ```

   Should show:
   ```json
   {
     "file_access": {
       "read": [
         "~/.daf-sessions/**/*",
         "~/.daf-sessions/**/*"
       ]
     }
   }
   ```

3. **Restart Claude Code completely:**
   - Exit Claude Code (not just close the window)
   - Reopen with `daf open`

4. **Test the fix:**
   ```bash
   # Create a test file
   echo "# Test Content" > ~/.daf-sessions/ORGANIZATION.md

   # Open a session
   daf open PROJ-12345

   # Verify Claude can read the file (check initial prompt)
   ```

**Why Global Settings File?**

The allow list **must** be in the global `~/.claude/settings.json` file, NOT in project-local `.claude/settings.local.json`:

- **Reason:** Project-local settings files are git-ignored and won't work for `daf jira new` sessions or when switching repositories
- **Solution:** Always configure file access in the global `~/.claude/settings.json` file

**Do NOT use** `.claude/settings.local.json` in project directories for this configuration.

**For detailed configuration instructions**, see [Installation Guide - Configuring Claude Code Permissions](02-installation.md#configuring-claude-code-permissions).

### Settings File Invalid JSON

**Problem:** Claude Code doesn't recognize the settings file or shows JSON errors

**Cause:** Syntax error in the JSON file (missing comma, trailing comma, unquoted keys, etc.)

**Solution:**

1. **Validate the JSON:**
   ```bash
   python -m json.tool ~/.claude/settings.json
   ```

2. **Common mistakes:**
   - Missing comma between array items
   - Trailing comma after last item (not allowed in JSON)
   - Single quotes instead of double quotes
   - Unquoted keys

3. **Fix or recreate the file:**
   ```bash
   # Backup existing file
   mv ~/.claude/settings.json ~/.claude/settings.json.backup

   # Create new file with correct syntax
   cat > ~/.claude/settings.json << 'EOF'
{
  "file_access": {
    "read": [
      "~/.daf-sessions/**/*",
      "~/.daf-sessions/**/*"
    ]
  }
}
EOF
   ```

### Settings Changes Not Taking Effect

**Problem:** Added paths to `settings.json` but Claude Code still can't read context files

**Cause:** Claude Code caches settings and needs to be restarted

**Solution:**

1. **Fully exit Claude Code:**
   - Don't just close the window
   - Ensure the process is completely terminated

2. **Reopen the session:**
   ```bash
   daf open PROJ-12345
   ```

3. **Verify in Claude Code:**
   - Ask Claude to read a file: "Can you read ~/.daf-sessions/ORGANIZATION.md?"
   - If it can read it, the settings are working

**Still not working?**

1. **Check file exists:**
   ```bash
   ls -la ~/.daf-sessions/ORGANIZATION.md
   ```

2. **Check file permissions:**
   ```bash
   chmod 644 ~/.daf-sessions/ORGANIZATION.md
   ```

3. **Verify settings file syntax:**
   ```bash
   python -m json.tool ~/.claude/settings.json
   ```

## Session Issues

### Session Won't Open - "No conversation found"

**Problem:** Running `daf open` shows "No conversation found with session ID: ..."

**Cause:** Session has a `ai_agent_session_id` but the conversation file doesn't exist (orphaned session).

**Solutions:**

1. **Automatic fix (recommended):**
   ```bash
   daf open PROJ-12345
   ```
   The tool will detect the missing file and generate a new UUID automatically.

2. **Manual cleanup:**
   ```bash
   # Preview orphaned sessions
   daf cleanup-sessions --dry-run

   # Clean them
   daf cleanup-sessions

   # Then open
   daf open PROJ-12345
   ```

### Session Already Has a Working Directory

**Problem:** `daf open` prompts for working directory even though session already has one.

**Cause:** Session created via `daf sync` without project path.

**Solution:**
Just select the appropriate working directory when prompted. It will be saved for future use.

### Multiple Sessions When Opening

**Problem:** `daf open PROJ-12345` shows multiple sessions to choose from.

**Cause:** You created multiple sessions in the same session group (e.g., working across multiple repos).

**Solution:**
This is expected behavior. Select the session number you want to work on.

### Session Not Found

**Problem:** `daf open my-session` says "Session 'my-session' not found"

**Solutions:**

1. **List all sessions:**
   ```bash
   daf list --all
   ```

2. **Search for it:**
   ```bash
   daf search "session"
   ```

3. **Check if it's under a JIRA key:**
   ```bash
   daf list | grep -i PROJ
   ```

## JIRA Integration Issues

### JIRA CLI Not Found

**Problem:** `jira: command not found`

**Solutions:**

1. **Install JIRA CLI:**
   ```bash
   # macOS
   brew install ankitpokhrel/jira-cli/jira-cli

   # Linux
   wget https://github.com/ankitpokhrel/jira-cli/releases/latest/download/jira_linux_amd64.tar.gz
   tar -xzf jira_linux_amd64.tar.gz
   sudo mv jira /usr/local/bin/
   ```

2. **Verify installation:**
   ```bash
   which jira
   jira --version
   ```

### JIRA Authentication Failed

**Problem:** `401 Unauthorized` or `Authentication failed`

**Solutions:**

1. **Check token is set:**
   ```bash
   echo $JIRA_API_TOKEN
   ```

2. **Re-initialize JIRA CLI:**
   ```bash
   jira init
   ```

3. **For self-hosted JIRA, use Personal Access Token (not API token)**

4. **Regenerate token:**
   - Go to JIRA → Profile → Security/API Tokens
   - Create new token
   - Update environment variable
   - Reload shell: `source ~/.zshrc`

### JIRA Personal Access Token Expired

**Problem:** JIRA commands suddenly fail with `Authentication failed for issue tracker ticket` even though they were working before

**Example Error:**
```
✗ Authentication failed for issue tracker ticket AAP-12345
```

**Cause:** JIRA Personal Access Tokens (PAT) have an expiration date. Once expired, all JIRA API calls will fail with 401 errors.

**How to Diagnose:**

1. **Check if token recently stopped working:**
   - Was working yesterday/last week
   - Suddenly all JIRA commands fail
   - Error message is "Authentication failed"

2. **Check token expiration in JIRA:**
   - Go to JIRA → Profile (top right) → Personal Access Tokens
   - Look for your token in the list
   - Check "Expiry date" and "Last authenticated" columns
   - If status shows "Expired", this is the issue

**Solutions:**

1. **Create a new Personal Access Token:**
   ```
   1. Go to JIRA → Profile → Personal Access Tokens
   2. Click "Create token"
   3. Set a name (e.g., "Laptop - 2026")
   4. Choose expiration date (default is 90 days)
   5. Click "Create"
   6. Copy the token immediately (won't be shown again)
   ```

2. **Update your environment variable:**
   ```bash
   # Update the token in your shell
   export JIRA_API_TOKEN="your_new_token_here"

   # Add to your shell profile to persist across sessions
   echo 'export JIRA_API_TOKEN="your_new_token_here"' >> ~/.zshrc

   # Reload your shell
   source ~/.zshrc
   ```

3. **Verify the fix:**
   ```bash
   # Test JIRA authentication
   daf jira view AAP-12345

   # Should now work successfully
   ```

**Prevention:**

- **Set calendar reminders** before token expiration
- **Use longer expiration periods** (90 days, 180 days, or 1 year depending on your organization's policy)
- **Keep track of expiration dates** in a password manager

**Note:** After updating `JIRA_API_TOKEN`, you may need to restart any open terminals or IDE sessions to pick up the new environment variable.

### JIRA Ticket Not Found

**Problem:** `JIRA ticket PROJ-12345 not found`

**Solutions:**

1. **Verify ticket exists:**
   ```bash
   jira issue view PROJ-12345
   ```

2. **Check you have access to the ticket**

3. **Verify JIRA URL in config:**
   ```bash
   cat ~/.daf-sessions/config.json | grep url
   ```

### JIRA Status Transition Failed

**Problem:** Status doesn't change when opening/completing sessions

**Solutions:**

1. **Check transition configuration:**
   ```bash
   cat ~/.daf-sessions/config.json
   ```

2. **Verify transition is valid for your workflow:**
   ```bash
   jira issue view PROJ-12345
   ```
   Check current status and available transitions.

3. **Check `on_fail` setting:**
   - `warn` - Shows warning but continues
   - `block` - Stops if transition fails

### JIRA Transition Failed Due to Missing Required Field

**Problem:** `daf open PROJ-12345` fails with error about missing required field (commonly `acceptance_criteria`)

**Example Error:**
```
Error: Failed to transition PROJ-12345 to 'In Progress'
Field 'acceptance_criteria' is required
```

**Cause:**
- JIRA ticket was created without a required field (often due to JIRA configuration issues)
- When `daf open` tries to transition from "New" to "In Progress", JIRA validates required fields
- This is a JIRA configuration bug where tickets can be created without required fields, but cannot be transitioned without them

**Solutions:**

1. **Add the missing field to JIRA ticket first (recommended):**
   ```bash
   # Update the JIRA ticket with the missing field
   daf jira update PROJ-12345 --acceptance-criteria "- Add acceptance criteria here\n- Another criterion"

   # Then open the session
   daf open PROJ-12345
   ```

2. **Alternative: Delete session and re-open after fixing JIRA:**
   ```bash
   # Delete the local session (keeps JIRA ticket intact)
   daf delete PROJ-12345

   # Fix the JIRA ticket manually or via daf jira update
   daf jira update PROJ-12345 --acceptance-criteria "- Criterion 1\n- Criterion 2"

   # Re-open session (will now transition successfully)
   daf open PROJ-12345
   ```

3. **For multiple tickets with missing acceptance criteria:**
   ```bash
   # View the ticket to see what's missing
   daf jira view PROJ-12345

   # Add acceptance criteria
   daf jira update PROJ-12345 --acceptance-criteria "- User can complete action\n- System validates input"

   # Now open will work
   daf open PROJ-12345
   ```

**Prevention:**
- When creating JIRA tickets with `daf jira create story`, always include `--acceptance-criteria`:
  ```bash
  daf jira create story \
    --summary "Feature description" \
    --parent PROJ-1234 \
    --acceptance-criteria "- Criterion 1\n- Criterion 2\n- Criterion 3"
  ```

**Note:** This is a known JIRA configuration issue where tickets can be created without required fields but cannot be transitioned without them. There is no fix on the daf tool side - the field must be added to the JIRA ticket before transition.

### JIRA Custom Field Errors

**Problem:** JIRA commands fail with "Unknown field" or "Field not found" errors

**Causes:**
- JIRA custom field IDs changed (rare but possible after instance upgrade)
- Field mappings not cached yet
- Cached field mappings are outdated

**Solutions:**

1. **Refresh field mappings:**
   ```bash
   daf init --refresh
   ```
   This refreshes JIRA custom field mappings without changing any of your configuration.

2. **Or use the specific refresh command:**
   ```bash
   daf config refresh-jira-fields
   ```

3. **Verify JIRA_API_TOKEN is set:**
   ```bash
   echo $JIRA_API_TOKEN
   ```

4. **Check field mappings in config:**
   ```bash
   cat ~/.daf-sessions/config.json | grep -A 10 field_mappings
   ```

**What gets refreshed:**
- JIRA custom field mappings (field IDs and allowed values)
- Field cache timestamp

**What is preserved:**
- All user configuration (JIRA URL, workstream, workspace path, etc.)
- All session data (sessions, notes, templates)

## Conversation Issues

### Corrupted Conversation File

**Problem:** Claude Code session crashes, freezes, or shows errors about corrupted conversation files

**Symptoms:**
- Session won't resume
- JSON decode errors when opening session
- Claude Code crashes when loading conversation
- Error messages about invalid UTF-8 or surrogates
- Tool results too large causing issues

**Solutions:**

1. **Automatic repair (recommended):**
   ```bash
   # Repair by JIRA key or session name
   daf repair-conversation PROJ-12345

   # Preview what needs repair first
   daf repair-conversation PROJ-12345 --dry-run
   ```

2. **Scan all sessions for corruption:**
   ```bash
   # Check all sessions (doesn't modify anything)
   daf repair-conversation --check-all

   # Repair all corrupted sessions automatically
   daf repair-conversation --all
   ```

3. **Repair specific conversation in multi-conversation session:**
   ```bash
   daf repair-conversation PROJ-12345 --conversation-id 1
   ```

4. **Custom truncation size for very large tool outputs:**
   ```bash
   # Increase truncation limit if needed
   daf repair-conversation PROJ-12345 --max-size 15000
   ```

5. **Direct UUID repair (when session metadata is corrupted):**
   ```bash
   daf repair-conversation f545206f-480f-4c2d-8823-c6643f0e693d
   ```

**What the repair tool fixes:**
- Invalid JSON lines (syntax errors)
- Invalid Unicode surrogate pairs
- Oversized tool results/outputs
- Validates all repairs produce valid JSON

**Safety:**
- Automatic backup created before repair (`.jsonl.backup-TIMESTAMP`)
- Can restore from backup if needed
- Dry-run mode available to preview changes

**After repair:**
Must restart Claude Code for changes to take effect:
```bash
# Exit Claude Code completely
# Then reopen
daf open PROJ-12345
```

**Prevention:**
- Keep tool outputs reasonable (<10KB per message)
- Clean up long sessions periodically with `daf cleanup-conversation`
- Monitor for very large file operations in tools

---

## Conversation Cleanup Issues

### Can't Run Cleanup - Claude Code Active

**Problem:** `Error: Cannot run cleanup while Claude Code is active`

**Solution:**
1. Exit Claude Code completely (close the session)
2. Run cleanup command
3. Reopen with `daf open`

This is intentional - Claude Code caches the conversation and will overwrite cleanup on exit.

### Cleanup Removed Too Many Messages

**Problem:** Cleaned up more than intended

**Solution:**
```bash
# List available backups
daf cleanup-conversation PROJ-12345 --list-backups

# Restore from backup
daf cleanup-conversation PROJ-12345 --restore-backup 20251120-163147
```

Backups are automatic and kept for all cleanups.

### 413 Error Still Occurs After Cleanup

**Problem:** Still getting "413 Prompt is too long" after cleanup

**Solutions:**

1. **Exit and reopen Claude Code** (it caches the conversation)

2. **Clean more aggressively:**
   ```bash
   daf cleanup-conversation PROJ-12345 --keep-last 50
   ```

3. **Check conversation file size:**
   ```bash
   ls -lh ~/.claude/projects/*/PROJ-12345*.jsonl
   ```

## Installation Issues

### Python Version Too Old

**Problem:** `Python 3.10 or higher required`

**Solutions:**

1. **Check version:**
   ```bash
   python --version
   python3 --version
   ```

   **Note:** DevAIFlow officially supports Python 3.10, 3.11, and 3.12. Python 3.9 may work but is not tested.

2. **Install newer Python:**
   ```bash
   # macOS
   brew install python@3.11

   # Linux
   sudo apt-get install python3.11
   ```

3. **Use pyenv:**
   ```bash
   pyenv install 3.11.0
   pyenv global 3.11.0
   ```

### Permission Denied

**Problem:** Permission errors during installation

**Solutions:**

1. **Use user installation:**
   ```bash
   pip install --user .
   ```


3. **Fix permissions:**
   ```bash
   sudo chown -R $(whoami) ~/.local
   ```

### Command Not Found After Installation

**Problem:** `daf: command not found`

**Solutions:**

1. **Check PATH:**
   ```bash
   echo $PATH
   ```

2. **Find where daf was installed:**
   ```bash
   pip show devaiflow
   ```

3. **Add to PATH in ~/.zshrc or ~/.bashrc:**
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

4. **Reload shell:**
   ```bash
   source ~/.zshrc
   ```

## Configuration Issues

### Config File Not Found

**Problem:** `Config file not found`

**Solution:**
```bash
daf init
```

This creates the default config file at `~/.daf-sessions/config.json`.

### Invalid JSON in Config

**Problem:** `JSONDecodeError` when running commands

**Solutions:**

1. **Validate JSON:**
   ```bash
   python -m json.tool ~/.daf-sessions/config.json
   ```

2. **Restore default config:**
   ```bash
   mv ~/.daf-sessions/config.json ~/.daf-sessions/config.json.backup
   daf init
   ```

3. **Common JSON mistakes:**
   - Missing commas between fields
   - Trailing commas (not allowed in JSON)
   - Unquoted keys or values
   - Single quotes instead of double quotes

### Configuration Warnings on Load

**Problem:** Seeing warnings about placeholder values or missing required fields:

```
⚠ Configuration Warning: Found 2 configuration issue(s)
  • backends/jira.json: url contains placeholder value: 'TODO: https://your-jira-instance.com'
  • organization.json: jira_project is null (required for ticket creation)
Run 'daf config show --validate' for details and suggestions
```

**Cause:** Config files contain template placeholder values that need to be customized.

**Solutions:**

1. **Get detailed validation report:**
   ```bash
   daf config show --validate
   ```

2. **Fix placeholder values:**
   - Edit `backends/jira.json` and set `url` to your actual JIRA instance
   - Edit `organization.json` and set `jira_project` to your project key
   - Replace any "TODO:" values with actual values

3. **Use interactive TUI editor:**
   ```bash
   daf config tui
   ```
   The TUI provides input validation and helps you set required values correctly.

**Example fixes:**

```bash
# Before (placeholder):
{
  "url": "TODO: https://your-jira-instance.com",
  "jira_project": "TODO: YOUR_PROJECT_KEY"
}

# After (actual values):
{
  "url": "https://jira.company.com",
  "jira_project": "PROJ"
}
```

**Note:** These warnings are non-fatal - commands will still run, but JIRA features may not work properly until you fix the placeholders.

### Repository Not Found/Not Listed

**Problem:** `daf new` or `daf open` doesn't find all your repositories

**Cause:** Workspace path points to wrong directory

**Solutions:**

1. **Check current workspace:**
   ```bash
   daf config show | grep workspace
   ```

2. **Update workspace path:**
   ```bash
   # Update to directory containing your repositories
   daf config tui /Users/username/development/workspace
   ```

3. **Verify repositories found:**
   - Command shows count of directories found
   - Should match expected number of repositories

**Example:**
```bash
# Before: workspace was /Users/username/development (15 repos)
# After: workspace is /Users/username/development/workspace (52 repos)
daf config tui ~/development/workspace
# ✓ Workspace set to: /Users/username/development/workspace
# Found 52 directories in workspace
```

### Repository Not Suggested

**Problem:** Tool doesn't suggest the right repository

**Solutions:**

1. **Check keywords in config:**
   ```bash
   cat ~/.daf-sessions/config.json
   ```

2. **Update keywords:**
   ```json
   {
     "repos": {
       "keywords": {
         "my-backend-api": ["api", "backend", "server"],
         "my-frontend-app": ["ui", "frontend", "react"]
       }
     }
   }
   ```

3. **Use full path:**
   ```bash
   daf new --name "test" --goal "..." --path /full/path/to/project
   ```

## PR/MR Template Issues

### Could Not Fetch Template from GitHub

**Problem:** `daf complete` shows "Could not fetch template from GitHub"

**Causes and Solutions:**

**For Public Repositories:**

The tool automatically falls back to unauthenticated GitHub API when `gh` CLI is unavailable.

1. **Check the template URL is correct:**
   ```bash
   daf config show | grep pr_template_url
   ```

2. **Verify the file exists:**
   - Open the URL in your browser
   - Make sure the file exists at that path
   - Check the branch name matches (main vs master)

3. **Try raw URL format:**
   ```bash
   daf config set-pr-template-url https://raw.githubusercontent.com/owner/repo/main/PULL_REQUEST_TEMPLATE.md
   ```

**For Private Repositories:**

Private repositories require `gh` CLI installed and authenticated:

1. **Install GitHub CLI:**
   ```bash
   # macOS
   brew install gh

   # Linux
   curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
   sudo apt update
   sudo apt install gh
   ```

2. **Authenticate:**
   ```bash
   gh auth login
   ```

3. **Verify authentication:**
   ```bash
   gh auth status
   ```

### GitHub API Rate Limit Exceeded

**Problem:** Message shows "GitHub API rate limit exceeded" or 403 errors

**Cause:** Unauthenticated GitHub API requests are limited to 60 per hour.

**Solutions:**

1. **Install and authenticate gh CLI for higher limits:**
   ```bash
   # Install (see above)
   gh auth login

   # Authenticated users get 5000 requests/hour
   ```

2. **Wait for rate limit reset:**
   - Rate limits reset every hour
   - Check rate limit status: `curl https://api.github.com/rate_limit`

3. **Use raw URL as workaround:**
   ```bash
   daf config set-pr-template-url https://raw.githubusercontent.com/owner/repo/main/PULL_REQUEST_TEMPLATE.md
   ```

### Template File Not Found (404)

**Problem:** "File not found" or 404 error when fetching template

**Solutions:**

1. **Verify file path in repository:**
   ```bash
   # Check your template URL
   daf config show | grep pr_template_url

   # Common locations:
   # - .github/PULL_REQUEST_TEMPLATE.md
   # - docs/PULL_REQUEST_TEMPLATE.md
   # - PULL_REQUEST_TEMPLATE.md (root)
   ```

2. **Check branch name:**
   ```bash
   # Use 'main' not 'master' (or vice versa)
   daf config set-pr-template-url https://github.com/org/repo/blob/main/PULL_REQUEST_TEMPLATE.md
   ```

3. **Verify repository and file existence:**
   - Open the URL in a browser
   - Make sure you can see the file
   - Copy the exact URL from the browser address bar

## Performance Issues

### Slow Session Listing

**Problem:** `daf list` is slow

**Causes:**
- Many sessions (100+)
- Large conversation files

**Solutions:**

1. **Filter results:**
   ```bash
   daf list --active
   daf list --since "last week"
   ```

2. **Delete old sessions:**
   ```bash
   daf list --status complete
   daf delete old-session
   ```

3. **Export and archive:**
   ```bash
   daf export --all --output archive.tar.gz
   daf delete --all --force
   daf import archive.tar.gz
   ```

### Claude Code Launch Slow

**Problem:** `daf open` takes long to launch Claude Code

**Cause:** Large conversation file

**Solution:**
```bash
daf cleanup-conversation PROJ-12345 --older-than 1d
```

## Data Issues

### Lost Session Data

**Problem:** Sessions disappeared

**Solutions:**

1. **Check if file exists:**
   ```bash
   ls ~/.daf-sessions/sessions.json
   ```

2. **Restore from backup:**
   ```bash
   # If you have a backup
   cp ~/.daf-sessions/sessions.json.backup ~/.daf-sessions/sessions.json
   ```

3. **Import from export:**
   ```bash
   daf import ~/backup.tar.gz
   ```

### Duplicate Sessions

**Problem:** Same session appears multiple times

**Cause:** Usually from manual edits to sessions.json

**Solution:**
1. **Backup first:**
   ```bash
   cp ~/.daf-sessions/sessions.json ~/.daf-sessions/sessions.json.backup
   ```

2. **Manually edit sessions.json to remove duplicates**

3. **Or delete and recreate:**
   ```bash
   daf delete duplicate-session
   daf new --name "..." --goal "..."
   ```

## Getting More Help

### Enable Debug Logging

Add to your command:
```bash
daf --debug list
```

### Check Logs

```bash
# System logs (macOS)
log show --predicate 'process == "daf"' --last 1h

# Check Python errors
python -c "import daf; print(daf.__file__)"
```

### Report an Issue

If you can't resolve the issue:

1. **Gather information:**
   ```bash
   daf --version
   python --version
   claude --version
   jira --version  # if using JIRA
   ```

2. **Check existing issues:**
   https://github.com/itdove/devaiflow/issues

3. **Create a new issue** with:
   - Error message (full output)
   - Steps to reproduce
   - Version information
   - Config (remove sensitive data!)

## Common Error Messages

### "AI_AGENT_SESSION_ID environment variable set"

**Meaning:** You're trying to run `daf new` or `daf open` from inside Claude Code

**Solution:** Exit Claude Code and run the command from a regular terminal

### "Session group already exists"

**Meaning:** Session name already used

**Solutions:**
- Use a different name
- Add to existing group: answer "y" when prompted
- Resume existing: `daf open <name>`

### "Git repository not found"

**Meaning:** Not in a git repository when trying to create branch

**Solutions:**
- Init git: `git init`
- Skip branch creation when prompted
- Use `--branch` flag to skip prompt

### "Cannot complete session on wrong branch with uncommitted changes"

**Meaning:** You're trying to `daf complete` but you're on a different branch than the session was created on, and you have uncommitted changes.

**Why this happens:**
- You manually switched branches (e.g., `git checkout other-branch`) after starting the session
- Session was created on `feature-branch` but you're now on `main` or another branch
- The tool prevents committing session changes to the wrong branch

**Solutions:**

1. **Commit or stash your changes first:**
   ```bash
   # Option 1: Commit changes to current branch
   git add .
   git commit -m "WIP: changes on wrong branch"

   # Option 2: Stash changes
   git stash

   # Then checkout the session branch
   git checkout <session-branch>

   # Run daf complete again
   daf complete <identifier>
   ```

2. **If changes belong to the current branch:**
   ```bash
   # Commit them here first
   git add .
   git commit -m "Your commit message"

   # Switch to session branch
   git checkout <session-branch>

   # Complete the session
   daf complete <identifier>
   ```

**Note:** If you're on the wrong branch but have NO uncommitted changes, the tool will automatically checkout the session branch for you.

## Development and Testing

### Mock Services for Integration Testing

The tool includes comprehensive mock services for testing without affecting production data.

**Enable Mock Mode:**
```bash
export DAF_MOCK_MODE=1
```

**What happens in mock mode:**
- All session data is isolated to `~/.daf-sessions/mocks/`
- `daf list` shows only mock sessions (separate from real sessions)
- Visual warning banner appears on every command: "⚠️ MOCK MODE ENABLED ⚠️"
- **Claude Code is NOT launched** - `daf open` skips the subprocess
- Mock data includes: sessions, JIRA tickets, GitHub PRs, GitLab MRs

**Common Commands:**
```bash
# Enable mock mode
export DAF_MOCK_MODE=1

# Create mock sessions
daf new test-session --goal "Testing feature"
daf list  # Shows only mock sessions

# Clear all mock data
daf purge-mock-data

# Disable mock mode
unset DAF_MOCK_MODE
daf list  # Shows real sessions again
```

**Use Cases:**
- Testing new features without affecting production data
- Integration tests in CI/CD
- Developing without JIRA API access
- Training and demos with sample data

**Mock Data Location:**
```
~/.daf-sessions/mocks/
├── sessions.json       # Mock session index
├── jira.json          # Mock JIRA tickets, comments, transitions
├── github.json        # Mock GitHub PRs
├── gitlab.json        # Mock GitLab MRs
└── claude.json        # Mock Claude Code sessions
```

**Running Tests with Mock Mode:**
```bash
# Run pytest with mock services
DAF_MOCK_MODE=1 pytest

# Run specific test
DAF_MOCK_MODE=1 pytest tests/test_mock_persistence.py
```

**Important Notes:**
- Mock and real data are completely isolated
- Mock mode is controlled entirely by the environment variable
- No configuration files required
- Mock data persists across commands until purged

### Testing Without Mock Mode

For more realistic end-to-end testing, you can also test **WITHOUT** mock mode:

**When to test without mock mode:**
- Validating real Claude Code conversation export/import
- Testing real JIRA API integration
- End-to-end testing with actual Claude Code sessions
- Verifying collaboration workflows with conversation files

**Setup:**
```bash
# Ensure DAF_MOCK_MODE is NOT set
unset DAF_MOCK_MODE

# Set JIRA credentials
export JIRA_API_TOKEN="your-token"
export JIRA_AUTH_TYPE="Bearer"

# Use DEVAIFLOW_HOME for isolation
export DEVAIFLOW_HOME="$HOME/.daf-sessions-test"
```

**Testing collaboration on single laptop:**
```bash
# Developer A
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-a"
daf init
daf config tui PROJ
daf config tui ~/development/workspace
daf jira new story --parent PROJ-XXXXX --goal "Test feature"
# Work in Claude Code, then export:
daf sync PROJ-12345
daf export PROJ-12345 --output /tmp/session-export.tar.gz

# Developer B
export DEVAIFLOW_HOME="$HOME/.daf-sessions-dev-b"
daf init
daf config tui PROJ
daf config tui ~/development/workspace
daf import /tmp/session-export.tar.gz
daf open PROJ-12345  # Continue with full conversation history
```

See `integration-tests/TEST_COLLABORATION_SCENARIO.md` for complete step-by-step guide.

**Common Issues When Testing Without Mock Mode:**

#### Claude Code Doesn't Launch

**Problem:** `daf open` doesn't launch Claude Code

**Cause:** Headless/CI environment without display

**Solution:** This is expected. The test still validates session export/import, git operations, and JIRA integration. Conversation files won't be created without a display, but that's normal.

#### JIRA Tickets Need Cleanup

**Problem:** Real JIRA tickets created during testing

**Solution:**
```bash
# Close the ticket
daf jira update PROJ-XXXXX --status 'Closed'

# Or delete in JIRA web interface
```

This is expected when testing without mock mode - you're creating real tickets.

#### DAF_MOCK_MODE is Set Error

**Problem:** Test script detects `DAF_MOCK_MODE` environment variable

**Solution:**
```bash
unset DAF_MOCK_MODE
./test_collaboration_workflow_no_mock.sh
```

#### Multiple Conversation Files in ~/.claude/projects/

**Problem:** Testing creates many conversation files

**Solution:** This is normal - each test creates unique conversation files. They won't conflict with your work. You can delete test files after testing if desired.

#### "JIRA_API_TOKEN not set" Error

**Problem:** Missing JIRA credentials for no-mock testing

**Solution:**
```bash
export JIRA_API_TOKEN="your-personal-access-token"
export JIRA_AUTH_TYPE="Bearer"
```

## Windows-Specific Issues

### Command Not Found in PowerShell

**Problem:** `daf: command not found` or `daf: The term 'daf' is not recognized`

**Cause:** Python Scripts directory not in PATH

**Solutions:**

1. **Check if daf is installed:**
   ```powershell
   python -m pip show devaiflow
   # Note the "Location" path
   ```

2. **Find daf.exe location:**
   ```powershell
   # Typical locations:
   # C:\Users\YourName\AppData\Local\Programs\Python\Python312\Scripts\daf.exe
   # C:\Users\YourName\AppData\Roaming\Python\Python312\Scripts\daf.exe

   # Search for it:
   Get-ChildItem -Path $env:LOCALAPPDATA -Recurse -Filter "daf.exe" -ErrorAction SilentlyContinue
   ```

3. **Add to PATH temporarily:**
   ```powershell
   $env:PATH += ";C:\Users\YourName\AppData\Local\Programs\Python\Python312\Scripts"
   ```

4. **Add to PATH permanently:**
   - Press `Win + X` → System
   - Advanced system settings → Environment Variables
   - Edit "Path" variable
   - Add: `C:\Users\YourName\AppData\Local\Programs\Python\Python312\Scripts`
   - Click OK, restart PowerShell

### Python Module Not Found

**Problem:** `ModuleNotFoundError: No module named 'devflow'`

**Cause:** Package not installed or Python can't find it

**Solutions:**

1. **Verify installation:**
   ```powershell
   pip show devaiflow
   ```

2. **Check Python version:**
   ```powershell
   python --version
   # Must be 3.9 or higher
   ```

3. **Reinstall:**
   ```powershell
   pip uninstall devaiflow
   pip install .
   ```

4. **Check if multiple Python versions installed:**
   ```powershell
   # Use py launcher to select version
   py -3.12 -m pip install .
   ```

### Git Commands Fail

**Problem:** Git commands fail with "command not found" or path errors

**Cause:** Git not in PATH or not installed

**Solutions:**

1. **Verify Git installation:**
   ```powershell
   git --version

   # If not found, install:
   winget install Git.Git
   ```

2. **Add Git to PATH:**
   ```powershell
   # Typical location:
   $env:PATH += ";C:\Program Files\Git\cmd"

   # Restart PowerShell
   ```

3. **Use Git Bash instead:**
   - Right-click in project folder → "Git Bash Here"
   - Run daf commands in Git Bash terminal

### Permission Denied Errors

**Problem:** `PermissionError: [WinError 5] Access is denied`

**Cause:** Insufficient permissions to write to installation directory

**Solutions:**

1. **Install for current user only:**
   ```powershell
   pip install --user .
   ```

2. **Run PowerShell as Administrator:**
   - Right-click PowerShell → "Run as administrator"
   - Then install: `pip install .`

3. **Check antivirus:**
   - Some antivirus software blocks pip installations
   - Temporarily disable or add exception for Python

### Path with Spaces Issues

**Problem:** Commands fail when paths contain spaces (e.g., "My Documents")

**Cause:** Path not quoted correctly

**Solutions:**

1. **Use quotes in commands:**
   ```powershell
   daf new --name "test" --goal "Test" --path "C:\Users\My Name\Projects\repo"
   ```

2. **Use short paths without spaces:**
   ```powershell
   # Instead of: C:\Users\My Name\Documents\Development
   # Use: C:\Development
   ```

3. **Avoid spaces in workspace path:**
   ```powershell
   daf config tui
   # Set workspace to: C:\development\workspace
   # Not: C:\Users\My Name\Documents\Development
   ```

### Claude Code Won't Launch

**Problem:** `daf open` doesn't launch Claude Code

**Cause:** Claude CLI not installed or not in PATH

**Solutions:**

1. **Verify Claude is installed:**
   ```powershell
   claude --version

   # If not found:
   winget install Anthropic.Claude
   ```

2. **Find Claude installation:**
   ```powershell
   Get-Command claude -ErrorAction SilentlyContinue

   # If not found, search:
   Get-ChildItem -Path $env:LOCALAPPDATA -Recurse -Filter "claude.exe" -ErrorAction SilentlyContinue
   ```

3. **Add to PATH:**
   ```powershell
   # Typical location:
   $env:PATH += ";C:\Users\YourName\AppData\Local\Programs\Claude"
   ```

4. **Restart PowerShell completely:**
   - Close all PowerShell windows
   - Open new PowerShell
   - Try again

### Line Ending Issues (CRLF vs LF)

**Problem:** Git shows all files as modified, or shell scripts fail

**Cause:** Windows uses CRLF (`\r\n`), Unix/Linux uses LF (`\n`)

**Solutions:**

1. **Configure Git to handle line endings:**
   ```powershell
   git config --global core.autocrlf true
   ```

2. **For this repository only:**
   ```powershell
   cd C:\path\to\devaiflow
   git config core.autocrlf true
   ```

3. **Fix existing files:**
   ```powershell
   # Re-checkout files with correct line endings
   git rm --cached -r .
   git reset --hard
   ```

### Integration Tests Won't Run

**Problem:** Can't run `test_collaboration_workflow.sh` or `test_jira_green_path.sh`

**Cause:** Bash scripts require Unix shell

**Solutions:**

1. **Use WSL (Recommended):**
   ```powershell
   # Install WSL
   wsl --install

   # Restart computer

   # Open WSL terminal
   wsl
   cd /mnt/c/Users/YourName/development/devaiflow
   ./integration-tests/test_collaboration_workflow.sh
   ```

2. **Use Git Bash:**
   - Right-click project folder → "Git Bash Here"
   - Run: `./integration-tests/test_collaboration_workflow.sh`

3. **Skip integration tests:**
   - Unit tests work natively: `pytest`
   - Integration tests are optional for development
   - CI/CD handles integration testing

### PowerShell Execution Policy

**Problem:** "Running scripts is disabled on this system"

**Cause:** PowerShell execution policy blocks scripts

**Solutions:**

1. **Check current policy:**
   ```powershell
   Get-ExecutionPolicy
   ```

2. **Set to RemoteSigned (recommended):**
   ```powershell
   # Run as Administrator:
   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

3. **Bypass for single session:**
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process
   ```

### File Locking Issues

**Problem:** Can't update sessions.json or config files

**Cause:** File is locked by another process

**Solutions:**

1. **Close all daf commands:**
   - Ensure no `daf` commands are running
   - Check Task Manager for Python processes

2. **Close Claude Code:**
   - Exit Claude Code completely
   - Check system tray for Claude icon
   - End process in Task Manager if necessary

3. **Check file permissions:**
   ```powershell
   # View file permissions
   Get-Acl C:\Users\YourName\.claude-sessions\sessions.json

   # Reset permissions if needed (as Administrator):
   icacls "C:\Users\YourName\.claude-sessions" /reset /T
   ```

### Unicode/Encoding Errors

**Problem:** `UnicodeDecodeError` or characters display as ?

**Cause:** Terminal encoding mismatch

**Solutions:**

1. **Set PowerShell to UTF-8:**
   ```powershell
   # Add to PowerShell profile ($PROFILE):
   [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
   $env:PYTHONIOENCODING = "utf-8"
   ```

2. **Use Windows Terminal (recommended):**
   - Install from Microsoft Store
   - Better Unicode support than cmd.exe or old PowerShell

3. **Set console code page:**
   ```cmd
   # In Command Prompt:
   chcp 65001
   ```

### Antivirus False Positives

**Problem:** Antivirus blocks or quarantines daf.exe

**Cause:** Some antivirus software flags Python executables

**Solutions:**

1. **Add exception for Python Scripts:**
   - Open your antivirus settings
   - Add exception for: `C:\Users\YourName\AppData\Local\Programs\Python`

2. **Add exception for daf.exe:**
   - Add specific exception for daf.exe location

3. **Verify it's not actual malware:**
   ```powershell
   # Check file hash
   Get-FileHash C:\path\to\daf.exe -Algorithm SHA256
   ```

### Windows Defender SmartScreen

**Problem:** "Windows protected your PC" warning

**Cause:** SmartScreen doesn't recognize the publisher

**Solutions:**

1. **Click "More info" → "Run anyway"**
   - Only do this if you trust the source

2. **Disable SmartScreen for this app:**
   - Right-click daf.exe → Properties → Unblock

3. **Build from source:**
   - Clone repository
   - Install with: `pip install -e .`

## Still Having Issues?

1. **Try reinstalling:**
   ```bash
   pip uninstall devaiflow
   pip install .
   ```

2. **Check the FAQ:** [FAQ.md](12-faq.md)

3. **Ask for help:** Create an issue with full details
