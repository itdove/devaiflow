# AI Agent Support Matrix

DevAIFlow supports multiple AI coding assistants through a pluggable agent architecture. This document describes the capabilities and limitations of each supported agent.

## Supported AI Agents

| Agent | Backend Name | Status | CLI Command | Session Management |
|-------|--------------|--------|-------------|-------------------|
| **Claude Code** | `claude` | ✅ Fully Tested | `claude` | Full support |
| **GitHub Copilot** | `github-copilot`, `copilot` | ⚠️  Experimental | `code` (VS Code) | Limited |
| **Cursor** | `cursor` | ⚠️  Experimental | `cursor` | Limited |
| **Windsurf** | `windsurf` | ⚠️  Experimental | `windsurf` | Limited |

## Configuration

Set your preferred AI agent in the configuration:

```bash
# Using daf config (recommended)
daf config set agent_backend claude
daf config set agent_backend github-copilot
daf config set agent_backend cursor
daf config set agent_backend windsurf

# Or manually edit ~/.daf-sessions/config.json
{
  "agent_backend": "claude"  // or "github-copilot", "cursor", "windsurf"
}
```

## Feature Support Matrix

### Core Features

| Feature | Claude Code | GitHub Copilot | Cursor | Windsurf |
|---------|-------------|----------------|--------|----------|
| Launch session | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Resume session | ✅ Full | ⚠️  Workspace-based | ⚠️  Workspace-based | ⚠️  Workspace-based |
| Session ID capture | ✅ Automatic | ⚠️  Generated | ⚠️  Generated | ⚠️  Generated |
| Conversation files | ✅ .jsonl | ❌ Not accessible | ❌ Not accessible | ❌ Not accessible |
| Message counting | ✅ Accurate | ❌ Not supported | ❌ Not supported | ❌ Not supported |
| Session history | ✅ Full | ⚠️  Limited | ⚠️  Limited | ⚠️  Limited |
| Conversation export | ✅ Full | ❌ Not supported | ❌ Not supported | ❌ Not supported |
| Conversation repair | ✅ Full | ❌ Not applicable | ❌ Not applicable | ❌ Not applicable |

### Integration Features

| Feature | Claude Code | GitHub Copilot | Cursor | Windsurf |
|---------|-------------|----------------|--------|----------|
| JIRA integration | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Git workflows | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Time tracking | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Session notes | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Multi-conversation | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Session templates | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| AI-powered summaries | ✅ Full | ❌ Not supported | ❌ Not supported | ❌ Not supported |

## Agent-Specific Details

### Claude Code (Fully Tested)

**Backend:** `claude`

**Features:**
- ✅ Full session management with `.jsonl` conversation files
- ✅ Automatic session ID detection
- ✅ Precise message counting
- ✅ Conversation export/import
- ✅ Conversation file repair
- ✅ Resume exact conversation state

**CLI Commands:**
```bash
claude code              # Launch new session
claude --resume <uuid>  # Resume existing session
```

**Session Storage:**
- Location: `~/.claude/projects/<encoded-path>/<uuid>.jsonl`
- Format: JSONL (one JSON object per line)

**AI-Powered Summaries:**
- ✅ Full support via Anthropic API
- Requires `ANTHROPIC_API_KEY` environment variable
- Configure in TUI: AI tab → Session Summary → mode: "ai" or "both"
- Generates natural language summaries from conversation history

**Known Issues:** None

---

### GitHub Copilot (Experimental)

**Backend:** `github-copilot` or `copilot`

**Features:**
- ✅ Launch VS Code with GitHub Copilot
- ⚠️  Workspace-based resume (VS Code manages state internally)
- ⚠️  Generated session IDs (not native to Copilot)
- ❌ No conversation file access
- ❌ No message counting
- ❌ No conversation export

**CLI Commands:**
```bash
code <project-path>      # Launch/resume VS Code
```

**Session Storage:**
- Location: `~/.vscode/User/workspaceStorage/<workspace-id>/`
- Format: VS Code internal database (not accessible)

**AI-Powered Summaries:**
- ❌ Not supported (no conversation file access)
- Auto-downgrades to "local" mode (git-based summaries)
- Uses git diff and manual notes instead of AI analysis

**Known Limitations:**
- GitHub Copilot operates through IDE extensions, not standalone CLI
- Session management relies on VS Code workspace state
- Conversation history not accessible in parseable format
- Resume always opens workspace (no session-specific resume)
- Session IDs are generated timestamps, not native identifiers

**Recommended Use Cases:**
- Teams already using VS Code with Copilot
- Basic session tracking without conversation export needs
- JIRA integration and git workflows

---

### Cursor (Experimental)

**Backend:** `cursor`

**Features:**
- ✅ Launch Cursor editor
- ⚠️  Workspace-based resume (Cursor manages state)
- ⚠️  Generated session IDs
- ❌ No conversation file access
- ❌ No message counting
- ❌ Limited conversation export

**CLI Commands:**
```bash
cursor <project-path>    # Launch/resume Cursor
```

**Session Storage:**
- Location: `~/.cursor/User/workspaceStorage/<workspace-id>/`
- Format: Internal database (similar to VS Code)

**AI-Powered Summaries:**
- ❌ Not supported (conversation format not documented)
- Auto-downgrades to "local" mode (git-based summaries)
- Uses git diff and manual notes instead of AI analysis

**Known Limitations:**
- Cursor's AI chat history stored in internal workspace database
- Conversation format not publicly documented
- Session IDs are generated, not native to Cursor
- Resume relies on workspace state restoration
- Message counting not supported

**Recommended Use Cases:**
- Teams using Cursor as primary editor
- AI-first development workflows
- Session organization without conversation export requirements

---

### Windsurf (Experimental)

**Backend:** `windsurf`

**Features:**
- ✅ Launch Windsurf editor
- ⚠️  Workspace-based resume
- ⚠️  Generated session IDs
- ❌ No conversation file access
- ❌ No message counting
- ❌ No conversation export

**CLI Commands:**
```bash
windsurf <project-path>  # Launch/resume Windsurf
```

**Session Storage:**
- Location: `~/.windsurf/User/workspaceStorage/<workspace-id>/`
- Format: Internal database

**AI-Powered Summaries:**
- ❌ Not supported (workflow history not accessible)
- Auto-downgrades to "local" mode (git-based summaries)
- Uses git diff and manual notes instead of AI analysis

**Known Limitations:**
- Windsurf (Codeium) stores AI chat and Cascade workflows internally
- Session IDs generated (not native)
- Conversation history format not documented
- Resume depends on workspace state
- No access to Cascade workflow history

**Recommended Use Cases:**
- Teams using Windsurf/Codeium
- Agentic coding workflows (Cascade)
- Session tracking and JIRA integration

---

## Testing Status

⚠️  **IMPORTANT**: Only Claude Code has been fully tested with comprehensive integration tests and real-world usage. Other agents are experimental implementations based on their documented CLI interfaces.

**Testing Coverage:**
- **Claude Code**: ✅ Unit tests, integration tests, production usage
- **GitHub Copilot**: ⚠️  Unit tests only, no real-world testing
- **Cursor**: ⚠️  Unit tests only, no real-world testing
- **Windsurf**: ⚠️  Unit tests only, no real-world testing

**Test Results:**
- All 2039 unit tests pass (3 skipped)
- 48 tests specifically for agent interface and implementations
- Integration tests run only with Claude Code

## Recommendations

### When to Use Each Agent

**Use Claude Code when:**
- You need full conversation history and export
- Message counting is important
- You want conversation repair capabilities
- You need AI-powered session summaries
- You need proven, production-tested functionality

**Use GitHub Copilot when:**
- Your team already uses VS Code with Copilot
- You want session organization for JIRA workflows
- Conversation export is not critical
- You prefer IDE-integrated AI assistance

**Use Cursor when:**
- Your team uses Cursor as primary editor
- You want AI-first development experience
- Session tracking and git workflows are priorities
- Conversation export is not required

**Use Windsurf when:**
- Your team uses Windsurf/Codeium
- You leverage Cascade agentic workflows
- Session management for JIRA integration
- Conversation export not needed

## Migration Between Agents

You can switch agents at any time by changing the `agent_backend` configuration:

```bash
# Switch from Claude Code to Cursor
daf config set agent_backend cursor

# Switch back to Claude Code
daf config set agent_backend claude
```

**Important Notes:**
- Existing sessions remain tied to their original agent
- Conversation files are not portable between agents
- Session metadata (JIRA links, notes, time tracking) is preserved
- Only the agent-specific data (conversation files, session IDs) changes

## Contributing

We welcome community contributions to improve support for additional AI agents!

**To add support for a new agent:**

1. Implement `AgentInterface` in `devflow/agent/your_agent.py`
2. Add factory support in `devflow/agent/factory.py`
3. Add unit tests in `tests/test_agent_interface.py`
4. Update documentation (this file and `AGENTS.md`)
5. Submit a merge request

**To improve existing agent support:**

1. Test with real-world usage
2. Report issues with detailed reproduction steps
3. Submit fixes with tests
4. Update documentation with findings

See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines.

## Troubleshooting

### Agent Not Found

**Error:** `ToolNotFoundError: command not found`

**Solution:** Ensure the agent's CLI is installed and in PATH:

```bash
# Claude Code
which claude

# GitHub Copilot (VS Code)
which code

# Cursor
which cursor

# Windsurf
which windsurf
```

### Session ID Not Captured

**Problem:** Session starts but ID not detected

**For Claude Code:**
- Check `~/.claude/projects/` directory permissions
- Verify session file creation in project directory
- Increase capture timeout in configuration

**For Other Agents:**
- Session IDs are auto-generated (no capture needed)
- Workspace state managed by the editor

### Conversation Not Resuming

**For Claude Code:**
- Verify session UUID exists in `~/.claude/projects/<encoded-path>/`
- Check conversation file is valid JSONL
- Use `daf repair` to fix corrupted files

**For Other Agents:**
- Resume relies on workspace state restoration
- Verify workspace directory exists
- Relaunch opens the workspace (editor restores state)

## Feedback

We want to hear from you!

- **Feature requests**: Open an issue in GitLab
- **Bug reports**: Include agent backend and version
- **Success stories**: Share how you use multi-agent support
- **Documentation improvements**: Submit MRs

Your feedback helps improve support for all AI coding assistants.
