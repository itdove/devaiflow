# AI Agent Support Matrix

DevAIFlow supports multiple AI coding assistants through a pluggable agent architecture. This document describes the capabilities and limitations of each supported agent.

## Supported AI Agents

| Agent | Backend Name | Status | CLI Command | Session Management | Skill Installation |
|-------|--------------|--------|-------------|-------------------|-------------------|
| **Claude Code** | `claude` | ✅ Fully Tested | `claude` | Full support | ✅ Full support |
| **Ollama** | `ollama`, `ollama-claude` | ✅ Fully Integrated | `ollama launch claude` | Full support (via Claude Code) | ✅ Full support |
| **GitHub Copilot** | `github-copilot`, `copilot` | ⚠️  Experimental | `code` (VS Code) | Limited | ✅ Experimental |
| **Cursor** | `cursor` | ⚠️  Experimental | `cursor` | Limited | ✅ Experimental |
| **Windsurf** | `windsurf` | ⚠️  Experimental | `windsurf` | Limited | ✅ Experimental |
| **Aider** | `aider` | ⚠️  Experimental | `aider` | Limited | ✅ Experimental |
| **Continue** | `continue` | ⚠️  Experimental | `continue` (VS Code ext) | Limited | ✅ Experimental |

## Configuration

Set your preferred AI agent in the configuration:

```bash
# Using daf config (recommended)
daf config set agent_backend claude
daf config set agent_backend ollama
daf config set agent_backend github-copilot
daf config set agent_backend cursor
daf config set agent_backend windsurf
daf config set agent_backend aider
daf config set agent_backend continue

# Or manually edit $DEVAIFLOW_HOME/config.json
{
  "agent_backend": "claude",  // or "ollama", "github-copilot", "cursor", "windsurf", "aider", "continue"
  "ollama": {
    "default_model": "qwen3-coder"  // optional, only for ollama backend
  }
}
```

## Multi-Agent Skill Installation

**NEW:** DevAIFlow can install skills to multiple AI agents simultaneously, making it easier to maintain consistent tooling across different coding assistants.

### Quick Start

```bash
# Install skills to all supported agents
daf upgrade --all-agents

# Install to a specific agent
daf upgrade --agent cursor
daf upgrade --agent windsurf

# Install to project directory (instead of global)
daf upgrade --level project --project-path .

# Install to both global and project
daf upgrade --level both --project-path .
```

### Skill Directory Locations

Each agent has its own skills directory where DevAIFlow installs bundled skills:

| Agent | Global Skills Directory | Project Skills Directory | Environment Variable |
|-------|------------------------|-------------------------|---------------------|
| **Claude Code** | `~/.claude/skills/` | `<project>/.claude/skills/` | `$CLAUDE_CONFIG_DIR` |
| **GitHub Copilot** | `~/.copilot/skills/` | `<project>/.github-copilot/skills/` | `$COPILOT_HOME` |
| **Cursor** | `~/.cursor/skills/` | `<project>/.cursor/skills/` | _(none)_ |
| **Windsurf** | `~/.codeium/windsurf/skills/` | `<project>/.windsurf/skills/` | _(none)_ |
| **Aider** | `~/.aider/skills/` | `<project>/.aider/skills/` | _(none)_ |
| **Continue** | `~/.continue/skills/` | `<project>/.continue/skills/` | _(none)_ |

**Note:** Claude Code and GitHub Copilot support environment variables to override the default config directory.

### Installation Levels

**Global Installation (default):**
- Installs to `~/.agent/skills/`
- Available in all projects
- Recommended for personal use

**Project Installation:**
- Installs to `<project>/.agent/skills/`
- Only available in that specific project
- Recommended for team sharing (commit to git)

**Both:**
- Installs to both global and project directories
- Useful for ensuring skills are always available

### Use Cases

**Personal Development:**
```bash
# Install to all your agents globally
daf upgrade --all-agents
```

**Team Collaboration:**
```bash
# Install to project and commit to git
cd /path/to/project
daf upgrade --level project --project-path .
git add .claude/skills .cursor/skills
git commit -m "Add DevAIFlow skills for team"
```

**Switching Between Agents:**
```bash
# You have skills already installed for Claude
# Now add them for Cursor too
daf upgrade --agents cursor
```

### Compatibility

**Fully Tested:**
- ✅ Claude Code - Skills work natively with skill system
- ✅ Ollama - Uses Claude Code's skill system

**Experimental:**
- ⚠️  GitHub Copilot - Skills may work as context files
- ⚠️  Cursor - Skills may work as context files
- ⚠️  Windsurf - Skills may work as context files
- ⚠️  Aider - Skills may work with `--read` flag
- ⚠️  Continue - Skills may work as context files

**Note:** Only Claude Code and Ollama have native skill support. Other agents may be able to use the skill files as context/documentation, but functionality is not guaranteed.

## Feature Support Matrix

### Core Features

| Feature | Claude Code | Ollama | GitHub Copilot | Cursor | Windsurf |
|---------|-------------|--------|----------------|--------|----------|
| Launch session | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Resume session | ✅ Full | ✅ Full | ⚠️  Workspace-based | ⚠️  Workspace-based | ⚠️  Workspace-based |
| Session ID capture | ✅ Automatic | ✅ Automatic | ⚠️  Generated | ⚠️  Generated | ⚠️  Generated |
| Conversation files | ✅ .jsonl | ✅ .jsonl | ❌ Not accessible | ❌ Not accessible | ❌ Not accessible |
| Message counting | ✅ Accurate | ✅ Accurate | ❌ Not supported | ❌ Not supported | ❌ Not supported |
| Session history | ✅ Full | ✅ Full | ⚠️  Limited | ⚠️  Limited | ⚠️  Limited |
| Conversation export | ✅ Full | ✅ Full | ❌ Not supported | ❌ Not supported | ❌ Not supported |
| Conversation repair | ✅ Full | ✅ Full | ❌ Not applicable | ❌ Not applicable | ❌ Not applicable |

### Integration Features

| Feature | Claude Code | Ollama | GitHub Copilot | Cursor | Windsurf |
|---------|-------------|--------|----------------|--------|----------|
| JIRA integration | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Git workflows | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Time tracking | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Session notes | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Multi-conversation | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Session templates | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| AI-powered summaries | ✅ Full | ✅ Full | ❌ Not supported | ❌ Not supported | ❌ Not supported |

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

**Using Alternative Models:**

DevAIFlow supports running Claude Code with alternative AI model providers through configuration profiles. This allows you to use:

- **Local models**: llama.cpp, LM Studio (free, private, offline)
- **Cloud providers**: OpenRouter, Vertex AI (cost savings up to 98%)

**Quick Start:**

Configure profiles in `~/.daf-sessions/config.json`:

```json
{
  "model_provider": {
    "default_profile": "anthropic",
    "profiles": {
      "anthropic": {
        "name": "anthropic"
      },
      "llama-cpp": {
        "name": "llama-cpp",
        "base_url": "http://localhost:8000",
        "auth_token": "llama-cpp",
        "api_key": "",
        "model_name": "Qwen3-Coder"
      },
      "vertex": {
        "name": "vertex",
        "use_vertex": true,
        "vertex_project_id": "your-gcp-project",
        "vertex_region": "us-east5"
      }
    }
  }
}
```

**Switch providers:**

```bash
# Use default profile (Anthropic)
daf open PROJ-123

# Use llama.cpp for testing
MODEL_PROVIDER_PROFILE=llama-cpp daf open PROJ-123

# Use Vertex AI for work
MODEL_PROVIDER_PROFILE=vertex daf open PROJ-123
```

**Comprehensive Guide**: See [Alternative Model Providers](alternative-model-providers.md) for:
- Detailed setup instructions for each provider
- Model recommendations by hardware (16GB/32GB/64GB+ RAM)
- Configuration hierarchy (enterprise/org/team/user)
- Performance comparisons and cost analysis
- Troubleshooting common issues

**External Reference**: [Run Claude Code on Local/Cloud Models](https://medium.com/@luongnv89/run-claude-code-on-local-cloud-models-in-5-minutes-ollama-openrouter-llama-cpp-6dfeaee03cda)

---

### Ollama (Fully Integrated)

**Backend:** `ollama` or `ollama-claude`

**Features:**
- ✅ Full session management with `.jsonl` conversation files (same as Claude Code)
- ✅ Automatic session ID detection
- ✅ Precise message counting
- ✅ Conversation export/import
- ✅ Conversation file repair
- ✅ Resume exact conversation state
- ✅ Local model support (free, private, offline)
- ✅ Zero configuration required

**CLI Commands:**
```bash
ollama launch claude              # Launch new session
ollama launch claude --model <model>  # Launch with specific model
# Note: --resume support coming soon (currently uses Claude Code's resume)
```

**Session Storage:**
- Location: `~/.claude/projects/<encoded-path>/<uuid>.jsonl`
- Format: JSONL (same as Claude Code)
- **Note:** Sessions are stored in `~/.claude` regardless of launcher for compatibility

**Model Selection Priority:**
1. DAF config (`config.ollama.default_model` or model provider profile)
2. Environment variable (`OLLAMA_MODEL`)
3. Ollama's default from `~/.ollama/config.json`
4. Ollama's built-in default

**Configuration:**
```bash
# Method 1: daf config TUI
daf config edit
# Set "AI Agent Backend" to "Ollama (local models)"
# Optionally set "Default Model" under "Ollama Configuration"

# Method 2: Manual config in ~/.daf-sessions/config.json
{
  "agent_backend": "ollama",
  "ollama": {
    "default_model": "qwen3-coder"
  }
}
```

**Popular Models:**
- `qwen3-coder` - 25B parameters, excellent for coding (recommended)
- `llama3.3` - 70B parameters, powerful but slower
- `codellama` - Meta's coding-specific model
- `mistral` - Fast and capable

**Advantages:**
- ✅ Simplest local model setup (one install command)
- ✅ Automatic server management (no manual server start)
- ✅ Model management built-in (`ollama pull`, `ollama list`)
- ✅ Native integration with `ollama launch claude`
- ✅ Same session management as Claude Code
- ✅ Free and private (runs locally)

**AI-Powered Summaries:**
- ✅ Full support (same as Claude Code)
- Works with any Ollama model
- Uses local model for summary generation (free)
- Configure in TUI: AI tab → Session Summary → mode: "ai" or "both"

**Known Issues:**
- ⚠️  `--resume` flag not yet supported by Ollama CLI (falls back to regular Claude resume)
- ⚠️  `--session-id` and `--add-dir` flags not yet supported (TODO in Ollama)

**Installation:**
```bash
# macOS/Linux:
curl -fsSL https://ollama.com/install.sh | sh

# Or download from: https://ollama.com

# Pull a model:
ollama pull qwen3-coder
```

**See Also:** [Alternative Model Providers](alternative-model-providers.md) for detailed setup guide

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
- You want to use Anthropic's Claude API

**Use Ollama when:**
- You want local models (free, private, offline)
- You need the simplest local model setup
- You want to avoid API costs
- Privacy is important (data stays local)
- You want full Claude Code features with local models
- You're okay with slightly lower quality than Claude Opus/Sonnet

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
