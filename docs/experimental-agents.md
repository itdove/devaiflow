# Experimental AI Agents

This document provides comprehensive information about experimental AI agent support in DevAIFlow, including GitHub Copilot, Cursor, and Windsurf.

## Overview

DevAIFlow supports multiple AI coding assistants through a unified agent interface. While Claude Code is fully tested and production-ready, GitHub Copilot, Cursor, and Windsurf are currently experimental with known limitations.

## Support Status

| Agent | Status | Test Coverage | Session Capture | Session Resume | Initial Prompt |
|-------|--------|---------------|-----------------|----------------|----------------|
| **Claude Code** | ✅ Fully Supported | 100% | ✅ Full Support | ✅ Full Support | ✅ Supported |
| **Ollama** | ✅ Supported | 100% | ✅ Full Support | ✅ Full Support | ✅ Supported |
| **GitHub Copilot** | ⚠️ Experimental | 100% | ⚠️ Limited | ⚠️ Limited | ❌ Not Supported |
| **Cursor** | ⚠️ Experimental | 100% | ⚠️ Limited | ⚠️ Limited | ❌ Not Supported |
| **Windsurf** | ⚠️ Experimental | 100% | ⚠️ Limited | ⚠️ Limited | ❌ Not Supported |

## Feature Comparison Matrix

### Session Management

| Feature | Claude Code | GitHub Copilot | Cursor | Windsurf |
|---------|-------------|----------------|--------|----------|
| **Session File Format** | JSONL | VS Code workspace | Cursor workspace | Windsurf workspace |
| **Session ID** | UUID-based | Workspace-based timestamp | Workspace-based timestamp | Workspace-based timestamp |
| **Session Discovery** | File monitoring | N/A | N/A | N/A |
| **Session Resume** | UUID resume | Workspace reopen | Workspace reopen | Workspace reopen |
| **Multi-Session Support** | ✅ Yes | ❌ No | ❌ No | ❌ No |

### Conversation Management

| Feature | Claude Code | GitHub Copilot | Cursor | Windsurf |
|---------|-------------|----------------|--------|----------|
| **Message Counting** | ✅ Accurate | ❌ Not Available | ❌ Not Available | ❌ Not Available |
| **Conversation Export** | ✅ Supported | ❌ Not Available | ❌ Not Available | ❌ Not Available |
| **Conversation Import** | ✅ Supported | ❌ Not Available | ❌ Not Available | ❌ Not Available |
| **Initial Prompt** | ✅ CLI Support | ❌ Manual Only | ❌ Manual Only | ❌ Manual Only |

### Integration Features

| Feature | Claude Code | GitHub Copilot | Cursor | Windsurf |
|---------|-------------|----------------|--------|----------|
| **CLI Launch** | ✅ `claude` | ✅ `code` | ✅ `cursor` | ✅ `windsurf` |
| **Time Tracking** | ✅ Accurate | ⚠️ Approximate | ⚠️ Approximate | ⚠️ Approximate |
| **Session Notes** | ✅ Supported | ✅ Supported | ✅ Supported | ✅ Supported |
| **JIRA Integration** | ✅ Full Support | ✅ Full Support | ✅ Full Support | ✅ Full Support |

## Known Limitations

### GitHub Copilot

**Architecture:** VS Code extension-based, not a standalone CLI agent

**Limitations:**
1. **No Session ID Detection**
   - GitHub Copilot doesn't create discrete session files
   - DevAIFlow generates workspace-based IDs using timestamps
   - Cannot differentiate between multiple sessions in the same workspace

2. **No Initial Prompt Support**
   - `daf open` launches VS Code but cannot send initial prompts via CLI
   - Users must manually paste prompts into Copilot Chat interface
   - Breaks the automated "initial context" workflow

3. **No Session Resume**
   - `daf open` with existing session just reopens VS Code
   - VS Code restores previous workspace state but doesn't resume specific conversation
   - No way to programmatically resume a specific Copilot chat thread

4. **No Message Counting**
   - Copilot conversation history stored in VS Code's internal database
   - No public API to count messages or export conversations
   - `get_session_message_count()` always returns 0

5. **No Conversation Export/Import**
   - Cannot export Copilot chat history for team handoff
   - Session sharing requires sharing entire VS Code workspace

**When to Use GitHub Copilot:**
- ✅ When you already use VS Code as your primary editor
- ✅ For code completion and inline suggestions
- ✅ When GitHub Copilot subscription is already available
- ❌ For automated session workflows requiring initial prompts
- ❌ For precise session tracking and time accounting
- ❌ For team collaboration requiring session export/import

### Cursor

**Architecture:** AI-first editor built on VS Code with integrated chat and code generation

**Limitations:**
1. **Workspace-Based Sessions Only**
   - Cursor manages sessions via workspace storage directories
   - Cannot create multiple discrete sessions for the same workspace
   - Session ID is timestamp-based, not UUID-based

2. **No Initial Prompt Support**
   - `daf open` launches Cursor but cannot send initial prompts
   - Users must manually use Cursor's AI Chat or Cascade
   - Automated context loading not supported

3. **Limited Session Detection**
   - Session files stored in `~/.cursor/User/workspaceStorage/`
   - Structure is not publicly documented
   - DevAIFlow scans for `workspace.json` and `state.vscdb` files

4. **No Message Counting**
   - AI chat history in workspace state database (SQLite)
   - Internal schema not documented
   - `get_session_message_count()` always returns 0

5. **No Direct Session Resume**
   - `daf open` reopens workspace, but specific chat thread not addressable
   - Cursor auto-restores AI chat history
   - Cannot programmatically resume specific conversation

**When to Use Cursor:**
- ✅ When you prefer Cursor's AI-first editing experience
- ✅ For Cascade (multi-step agentic workflows)
- ✅ When Cursor subscription is available
- ✅ For individual developer workflows
- ❌ For automated session workflows
- ❌ For team collaboration requiring session export
- ❌ For precise time tracking per conversation

### Windsurf

**Architecture:** Codeium's AI editor with advanced agentic coding (Cascade)

**Limitations:**
1. **Workspace-Based Sessions Only**
   - Similar to Cursor, sessions tied to workspace storage
   - Cannot have multiple discrete sessions per workspace
   - Session IDs generated using timestamps

2. **No Initial Prompt Support**
   - `daf open` launches Windsurf but cannot send prompts
   - Users must manually interact with AI Chat or Cascade
   - Automated workflows require manual intervention

3. **Limited Session Detection**
   - Session files in `~/.windsurf/User/workspaceStorage/`
   - Internal format similar to VS Code but not documented
   - DevAIFlow uses heuristic scanning

4. **No Message Counting**
   - AI chat and Cascade history in workspace state
   - Internal database schema not public
   - `get_session_message_count()` always returns 0

5. **No Direct Session Resume**
   - Workspace reopen restores AI state but not specific conversation
   - Cannot programmatically target a specific chat thread
   - Users must manually navigate to conversation

**When to Use Windsurf:**
- ✅ When you want Codeium's agentic coding features
- ✅ For Cascade workflows (multi-step AI coding tasks)
- ✅ When Windsurf/Codeium subscription is available
- ✅ For individual developer workflows
- ❌ For automated initial prompt workflows
- ❌ For team session sharing
- ❌ For accurate conversation message tracking

## Configuration

### Setting the Agent Backend

Configure which AI agent to use in your DevAIFlow configuration:

```bash
# Via environment variable
export DAF_AGENT_BACKEND="github-copilot"  # or "cursor" or "windsurf"

# Via config file (~/.daf-sessions/config.json)
{
  "agent_backend": "github-copilot"
}
```

**Supported values:**
- `"claude"` - Claude Code (default, fully supported)
- `"ollama"` or `"ollama-claude"` - Ollama with Claude CLI (supported)
- `"github-copilot"` or `"copilot"` - GitHub Copilot (experimental)
- `"cursor"` - Cursor (experimental)
- `"windsurf"` - Windsurf (experimental)

### Enterprise Enforcement

For enterprise deployments, set `agent_backend` in `enterprise.json` to enforce company-wide AI agent:

```json
{
  "agent_backend": "claude",
  "_comment": "All employees must use Claude Code for AI assistance"
}
```

See [Enterprise Guidelines](../ENTERPRISE.md) for details.

## Troubleshooting

### GitHub Copilot

#### Installation

**macOS/Linux:**
```bash
# Install VS Code CLI
# macOS (if not already in PATH)
sudo ln -s "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" /usr/local/bin/code

# Verify installation
code --version
```

**Windows:**
```powershell
# Add VS Code to PATH during installation
# Or manually add: C:\Users\<username>\AppData\Local\Programs\Microsoft VS Code\bin

# Verify
code --version
```

#### Common Issues

**Error: "code: command not found"**

**Solution:**
- Install VS Code: https://code.visualstudio.com/
- Ensure VS Code CLI is in PATH
- On macOS: `Command+Shift+P` → "Shell Command: Install 'code' command in PATH"

**Error: "GitHub Copilot extension not installed"**

**Solution:**
- Open VS Code
- Install extension: https://marketplace.visualstudio.com/items?itemName=GitHub.copilot
- Sign in to GitHub
- Ensure Copilot subscription is active

**Issue: Session not detected**

**Explanation:**
- GitHub Copilot doesn't create discrete session files
- DevAIFlow generates workspace-based session IDs automatically
- This is expected behavior, not an error

**Issue: Initial prompt not sent**

**Explanation:**
- GitHub Copilot CLI doesn't support sending prompts programmatically
- After `daf open` launches VS Code, manually:
  1. Open Copilot Chat (Ctrl/Cmd + Shift + I)
  2. Paste the initial prompt
  3. Continue working

### Cursor

#### Installation

**macOS:**
```bash
# Install Cursor
brew install --cask cursor

# Or download from https://cursor.sh/

# Verify CLI
cursor --version
```

**Linux:**
```bash
# Download from https://cursor.sh/
# Extract and add to PATH

# Verify
cursor --version
```

**Windows:**
```powershell
# Download from https://cursor.sh/
# Install and add to PATH

# Verify
cursor --version
```

#### Common Issues

**Error: "cursor: command not found"**

**Solution:**
- Install Cursor: https://cursor.sh/
- Add cursor CLI to PATH
- On macOS: Cursor may install CLI automatically after first launch
- Verify with `which cursor`

**Error: "Cursor subscription required"**

**Explanation:**
- Cursor AI features require subscription
- Sign up at https://cursor.sh/pricing
- Free tier available for limited usage

**Issue: Session resume doesn't restore chat**

**Explanation:**
- Cursor restores workspace state but not specific chat threads
- This is a platform limitation, not a DevAIFlow bug
- Manually navigate to previous conversation in Cursor

**Issue: Cannot count messages**

**Explanation:**
- Cursor's internal database schema is not public
- DevAIFlow cannot parse conversation history
- Use Cursor's built-in history viewer instead

### Windsurf

#### Installation

**macOS:**
```bash
# Download from https://codeium.com/windsurf
# Install and drag to Applications

# Add CLI to PATH
sudo ln -s "/Applications/Windsurf.app/Contents/Resources/app/bin/windsurf" /usr/local/bin/windsurf

# Verify
windsurf --version
```

**Linux:**
```bash
# Download from https://codeium.com/windsurf
# Extract and add to PATH

# Verify
windsurf --version
```

**Windows:**
```powershell
# Download from https://codeium.com/windsurf
# Install and add to PATH: C:\Users\<username>\AppData\Local\Programs\Windsurf\bin

# Verify
windsurf --version
```

#### Common Issues

**Error: "windsurf: command not found"**

**Solution:**
- Install Windsurf: https://codeium.com/windsurf
- Add windsurf CLI to PATH
- On macOS: May need to manually symlink after installation

**Error: "Codeium account required"**

**Explanation:**
- Windsurf requires Codeium account
- Sign up at https://codeium.com/
- Free tier available

**Issue: Cascade workflows not saved**

**Explanation:**
- Cascade workflow history managed by Windsurf internally
- DevAIFlow tracks session but not internal Cascade state
- Use Windsurf's built-in Cascade history

**Issue: Cannot resume specific Cascade**

**Explanation:**
- Windsurf doesn't expose programmatic Cascade resume API
- Reopen workspace to see all previous Cascades
- Manually select which one to continue

## Migration Path

### Moving from Experimental to Production

When an experimental agent becomes stable:

1. **Validation Requirements:**
   - ✅ 90%+ unit test pass rate
   - ✅ Integration tests passing
   - ✅ 5+ community validations
   - ✅ Known limitations documented
   - ✅ Troubleshooting guide complete

2. **Promotion Process:**
   - Remove "⚠️ EXPERIMENTAL" warnings from code
   - Update README.md support status
   - Update this document's status table
   - Announce in release notes

### Current Status

**As of v0.2.0:**
- ✅ Unit tests: 100% coverage (all 3 agents)
- ⏳ Integration tests: In progress
- ⏳ Community validations: 0/5 per agent
- ✅ Limitations documented
- ✅ Troubleshooting guides complete

**Estimated timeline to stable:** 2-4 weeks pending community feedback

## Community Validation

Help us stabilize experimental agents by testing and reporting feedback!

### How to Validate

1. **Install the agent** (GitHub Copilot, Cursor, or Windsurf)
2. **Configure DevAIFlow:**
   ```bash
   daf config set-agent-backend github-copilot  # or cursor/windsurf
   ```
3. **Test basic workflow:**
   ```bash
   daf new test-session
   # Verify agent launches
   # Verify session tracking works
   # Test session resume
   ```
4. **Report results** using our validation template

### Validation Template

Please report your experience using this template in a GitHub issue:

**Title:** `[Agent Validation] <GitHub Copilot|Cursor|Windsurf> - <Your OS>`

**Body:**
```markdown
## Environment
- OS: (macOS / Linux / Windows)
- Agent: (GitHub Copilot / Cursor / Windsurf)
- Agent Version:
- DevAIFlow Version:
- Python Version:

## Test Results

### Session Creation
- [ ] Agent launches successfully
- [ ] Session ID captured
- Notes:

### Session Resume
- [ ] Can resume session via `daf open`
- [ ] Workspace state restored
- Notes:

### Basic Workflow
- [ ] Can create JIRA ticket from session
- [ ] Time tracking works
- [ ] Session notes work
- Notes:

### Issues Encountered
(Describe any problems, errors, or unexpected behavior)

### Overall Assessment
- [ ] Ready for daily use
- [ ] Needs improvements (specify)
- [ ] Not recommended yet

### Additional Comments
(Any other feedback)
```

## Best Practices

### For All Experimental Agents

1. **Be Aware of Limitations:**
   - Read the limitations section for your agent
   - Understand what features are not supported
   - Plan workflows accordingly

2. **Manual Initial Prompts:**
   - `daf open` launches the editor
   - Manually paste initial context
   - Bookmark JIRA ticket URL for reference

3. **Session Tracking:**
   - DevAIFlow tracks session at workspace level
   - Use `daf note` to document progress
   - Time tracking is approximate

4. **Team Collaboration:**
   - Session export/import not supported
   - Share code via git commits instead
   - Document work in JIRA comments

### Recommended: Use Claude Code for Production

For production workflows requiring:
- Automated initial prompts
- Accurate session tracking
- Session export/import
- Team collaboration
- Precise time accounting

**→ Use Claude Code instead of experimental agents.**

Experimental agents are best for individual developers who already use and prefer those specific editors.

## Feedback and Contributions

Help improve experimental agent support:

**Report Issues:**
- GitHub Issues: https://github.com/itdove/devaiflow/issues
- Label: `experimental-agents`

**Contributing:**
- Agent implementation: `devflow/agent/<agent>_agent.py`
- Tests: `tests/test_agent_interface.py`
- Documentation: This file

**Discussion:**
- For questions and discussions, open a GitHub Discussion
- Share your validation results and use cases

## See Also

- [Agent Interface Architecture](agent-interface-architecture.md)
- [Enterprise Configuration](ENTERPRISE.md)
- [Configuration Guide](06-configuration.md)
- [Troubleshooting Guide](11-troubleshooting.md)
