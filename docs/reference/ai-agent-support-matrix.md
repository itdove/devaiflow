# AI Agent Support Matrix

DevAIFlow supports multiple AI coding assistants through a pluggable agent architecture. This document describes the capabilities and limitations of each supported agent.

## Concepts & Terminology

Before diving into the agent matrix, it's important to understand the three distinct concepts in the AI coding assistant ecosystem:

### 1. Agent (Agent Backend)

**What it is:** The coding assistant tool or interface you interact with.

**Think of it as:** "What tool am I typing into?" or "What application launches when I run `daf open`?"

**Examples:**
- Claude Code (standalone CLI)
- GitHub Copilot (VS Code extension)
- Cursor (IDE)
- Windsurf (IDE)
- Ollama (CLI that launches Claude Code)
- Aider (TUI)
- Crush (TUI)

**Configuration:**
```json
{
  "agent_backend": "claude"  // or "ollama", "cursor", "github-copilot", etc.
}
```

**Key Point:** DevAIFlow needs to know which agent you're using so it can launch sessions correctly, find conversation files, and extract statistics.

---

### 2. Model Provider

**What it is:** The AI service or API backend that hosts and serves the AI models.

**Think of it as:** "Who/what is processing my requests?" or "Where do my prompts get sent?"

**Examples:**
- Anthropic API (official Claude API)
- Vertex AI (Google Cloud's Claude API)
- OpenRouter (multi-model proxy)
- llama.cpp (local inference server)
- Ollama (local model server)
- OpenAI API
- AWS Bedrock

**Configuration (Claude Code only):**
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
        "model_name": "Qwen3-Coder"
      },
      "vertex": {
        "name": "vertex",
        "use_vertex": true,
        "vertex_project_id": "my-gcp-project"
      }
    }
  }
}
```

**Key Point:** Model providers are **only relevant for Claude Code agent**. Other agents (Cursor, Copilot, etc.) manage their own backend connections internally.

---

### 3. Model

**What it is:** The specific AI model (neural network) doing the thinking.

**Think of it as:** "Which AI brain is answering my questions?"

**Examples:**
- Claude Sonnet 4 (Anthropic's mid-tier model)
- Claude Opus 4 (Anthropic's most capable model)
- Claude Haiku 4 (Anthropic's fastest model)
- Qwen3-Coder (local coding model)
- DeepSeek Coder (local coding model)
- GPT-4 (OpenAI's model)

**Configuration:**
```json
{
  // For Claude Code with custom provider
  "model_provider": {
    "profiles": {
      "llama-cpp": {
        "model_name": "Qwen3-Coder"
      }
    }
  },

  // For Ollama agent
  "ollama": {
    "default_model": "qwen3-coder"
  }
}
```

**Key Point:** The model determines the quality, speed, and capabilities of responses. Different models excel at different tasks.

---

### How They Work Together

The relationship forms a hierarchy:

```
┌─────────────────────────────────────────────┐
│ Agent: Claude Code                          │
│ (What tool launches)                        │
│                                             │
│  ├─> Model Provider: Anthropic API          │
│  │   (Where prompts are sent)              │
│  │   └─> Model: Claude Sonnet 4            │
│  │       (Which AI brain responds)         │
│  │                                          │
│  ├─> Model Provider: llama.cpp              │
│  │   (Alternative backend)                 │
│  │   └─> Model: Qwen3-Coder                │
│  │       (Local model)                     │
│  │                                          │
│  └─> Model Provider: Vertex AI              │
│      (Google Cloud)                        │
│      └─> Model: Claude Opus 4              │
│          (Premium model)                   │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Agent: Ollama                               │
│ (Launches Claude Code with Ollama)         │
│                                             │
│  └─> Model Provider: Ollama Service         │
│      (Built-in local server)               │
│      └─> Model: qwen3-coder                 │
│          (Local model)                     │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Agent: Cursor                               │
│ (IDE)                                       │
│                                             │
│  └─> Model Provider: Cursor's Backend       │
│      (Managed internally)                  │
│      └─> Model: Various                     │
│          (Cursor manages this)             │
└─────────────────────────────────────────────┘
```

### Token Usage Tracking Context

Now that you understand these concepts, here's how they relate to **token usage tracking**:

- **Agent determines IF tracking is possible**: Only Claude Code can parse `.jsonl` conversation files
- **Model Provider determines token metadata format**: Each provider may report tokens differently
- **Model determines token counts**: Different models tokenize text differently

**Current Support:**
- ✅ **Claude Code + Anthropic API**: Full token tracking (input, output, cache creation, cache reads)
- ✅ **Claude Code + Alternative Providers**: Full tracking IF the provider exposes usage data
- ❌ **Ollama Agent**: No tracking (conversation files don't include token usage)
- ❌ **Other Agents**: No tracking (conversation files not accessible)

This is why token tracking is currently **Claude Code only** - it's the only agent that:
1. Exposes conversation files in a parseable format (`.jsonl`)
2. Includes token usage metadata in those files
3. Provides consistent access to this data

---

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
| **Crush** | `crush`, `opencode` | ⚠️  Experimental | `crush` | Limited | ✅ Experimental |

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
daf config set agent_backend crush

# Or manually edit $DEVAIFLOW_HOME/config.json
{
  "agent_backend": "claude",  // or "ollama", "github-copilot", "cursor", "windsurf", "aider", "continue", "crush"
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
daf skills --all-agents

# Install to a specific agent
daf skills --agent cursor
daf skills --agent windsurf

# Install to project directory (instead of global)
daf skills --level project --project-path .

# Install to both global and project
daf skills --level both --project-path .
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
| **Crush** | `~/.local/share/crush/skills/` | `<project>/.crush/skills/` | `$XDG_DATA_HOME` |

**Note:** Claude Code, GitHub Copilot, and Crush support environment variables to override the default config/data directory.

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
daf skills --all-agents
```

**Team Collaboration:**
```bash
# Install to project and commit to git
cd /path/to/project
daf skills --level project --project-path .
git add .claude/skills .cursor/skills
git commit -m "Add DevAIFlow skills for team"
```

**Switching Between Agents:**
```bash
# You have skills already installed for Claude
# Now add them for Cursor too
daf skills --agents cursor
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
| Token usage tracking | ✅ Full | ❌ Not supported | ❌ Not supported | ❌ Not supported | ❌ Not supported |
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
- ✅ Token usage tracking with cost estimation
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

**Token Usage Tracking:**
- ✅ Extract token statistics from conversation files
- Shows input tokens, output tokens, cache creation, cache reads
- Calculates cache efficiency percentage (cache reads / total cacheable)
- Estimates session cost based on model pricing
- Displays in `daf info`, `daf active`, `daf list` commands
- Includes in markdown exports via `daf export`
- Supports prompt caching metrics (90% cost savings on cache reads)
- Tracks: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`

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

**Token Usage Tracking:**
- ❌ Not yet supported (Ollama doesn't expose token usage in conversation files)
- TODO: Implement if Ollama adds token usage data to Claude Code sessions
- For now, token statistics are not available when using Ollama backend

**Known Issues:**
- ⚠️  `--resume` flag not yet supported by Ollama CLI (falls back to regular Claude resume)
- ⚠️  `--session-id` and `--add-dir` flags not yet supported (TODO in Ollama)
- ⚠️  Token usage tracking not available (Ollama doesn't provide usage data)

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

### Crush (Experimental)

**Backend:** `crush` or `opencode`

**Features:**
- ✅ Launch Crush TUI-based agent
- ⚠️  SQLite-based session storage
- ⚠️  UUID session IDs (stored in database)
- ⚠️  Multi-model support (OpenAI, Anthropic, Gemini, Groq, AWS Bedrock, Azure)
- ⚠️  LSP integration for code-aware context
- ⚠️  MCP plugin extensibility
- ❌ No CLI-based prompt passing
- ❌ Limited conversation export (database format)

**CLI Commands:**
```bash
crush                    # Launch new session
crush --session <uuid>   # Resume specific session
crush --continue         # Resume last session
crush session list       # List all sessions
```

**Session Storage:**
- Location: `~/.local/share/crush/crush.db` (SQLite database)
- Format: SQLite database with sessions, messages, and metadata tables
- Can be overridden with `--data-dir` flag

**Environment Variables:**
- `XDG_DATA_HOME` - Override data directory location (Linux/Unix)
- `CRUSH_DISABLE_METRICS` or `DO_NOT_TRACK` - Disable metrics collection
- `CRUSH_PROFILE` - Enable pprof profiling server
- `CRUSH_` prefix - General environment variable convention

**Configuration:**
- Global: `~/.config/crush/crush.json`
- Project: `.crush.json` in project root
- Data directory contains: `crush.db`, `.gitignore`, `crush.json`

**AI-Powered Summaries:**
- ❌ Not supported (SQLite database format, not JSONL)
- Auto-downgrades to "local" mode (git-based summaries)
- Uses git diff and manual notes instead of AI analysis

**Known Limitations:**
- Crush stores all data in SQLite database, not individual conversation files
- Session ID detection requires database polling (slower than file-based)
- No native support for passing initial prompts via CLI (must enter interactively in TUI)
- Conversation export would require custom SQLite query logic
- Message counting requires database queries
- Resume always opens TUI (no headless mode)

**Advantages:**
- ✅ Beautiful terminal UI built with Bubble Tea
- ✅ Multi-model support (switch between providers)
- ✅ LSP integration for code-aware AI assistance
- ✅ MCP plugin system for extensibility
- ✅ Session management with branching/merging support
- ✅ Cross-platform (macOS, Linux, Windows, FreeBSD)

**Installation:**
```bash
# Homebrew (macOS/Linux)
brew install crush

# NPM
npm install -g @charmbracelet/crush

# Arch Linux
yay -S crush

# Winget (Windows)
winget install Charm.Crush

# Or download from: https://github.com/charmbracelet/crush
```

**Recommended Use Cases:**
- Teams wanting a beautiful TUI coding assistant
- Multi-model workflows (switching between OpenAI/Anthropic/Gemini)
- Developers who prefer terminal-based tools
- Projects benefiting from LSP integration
- Teams extending functionality with MCP plugins

**Not Recommended For:**
- Conversation history export requirements
- AI-powered session summaries
- Automated session ID capture workflows
- Headless/scriptable AI workflows

**History:**
Crush (formerly OpenCode) was created by Kujtim and later acquired by Charmbracelet. It continues to be actively developed and maintained by the Charm team.

**External Resources:**
- [GitHub](https://github.com/charmbracelet/crush)
- [Charm Blog Announcement](https://charm.land/blog/crush-comes-home/)
- [The New Stack Review](https://thenewstack.io/terminal-user-interfaces-review-of-crush-ex-opencode-al/)

---

## Testing Status

⚠️  **IMPORTANT**: Only Claude Code has been fully tested with comprehensive integration tests and real-world usage. Other agents are experimental implementations based on their documented CLI interfaces.

**Testing Coverage:**
- **Claude Code**: ✅ Unit tests, integration tests, production usage
- **Ollama**: ✅ Unit tests, integration tests, production usage
- **GitHub Copilot**: ⚠️  Unit tests only, no real-world testing
- **Cursor**: ⚠️  Unit tests only, no real-world testing
- **Windsurf**: ⚠️  Unit tests only, no real-world testing
- **Aider**: ⚠️  Unit tests only, no real-world testing
- **Continue**: ⚠️  Unit tests only, no real-world testing
- **Crush**: ⚠️  Unit tests only, no real-world testing

**Test Results:**
- All 2039 unit tests pass (3 skipped)
- 48 tests specifically for agent interface and implementations
- Integration tests run only with Claude Code

## Recommendations

### When to Use Each Agent

**Use Claude Code when:**
- You need full conversation history and export
- Message counting is important
- Token usage tracking and cost estimation are needed
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

**Use Crush when:**
- You want a beautiful TUI-based AI assistant
- Multi-model flexibility is important (easy switching between providers)
- You prefer terminal-based tools over IDE extensions
- LSP integration and code-aware context are priorities
- You want MCP plugin extensibility
- Session tracking is more important than conversation export

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
