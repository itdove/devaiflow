# Alternative Model Providers

DevAIFlow supports running Claude Code with alternative AI model providers through environment variable configuration. This allows you to use local models (llama.cpp, LM Studio) or cloud providers (OpenRouter, Vertex AI, etc.) instead of the default Anthropic API.

**⚠️ Important:** Ollama is **NOT compatible** with Claude Code due to API differences. Use llama.cpp for local model support.

## Table of Contents

1. [Why Use Alternative Providers?](#why-use-alternative-providers)
2. [Quick Start Guides](#quick-start-guides) - **Start here!**
   - [Local/Offline: llama.cpp](#-localoffline-llamacpp-free---recommended)
   - [Cloud: OpenRouter](#-cloud-openrouter-98-cheaper---to-be-tested)
   - [Enterprise: Vertex AI](#-enterprise-google-vertex-ai---tested)
3. [Using Profiles](#using-profiles) - How to switch between providers
4. [Configuration](#configuration) - Profile structure and settings
5. [Provider Setup Guides](#provider-setup-guides) - Detailed setup instructions
6. [Troubleshooting](#troubleshooting) - Common issues and solutions
7. [Performance Comparison](#performance-comparison) - Benchmarks and costs
8. [Decision Matrix](#decision-matrix-which-solution-to-use) - Which provider to choose
9. [Best Practices](#best-practices) - Tips and recommendations

## Why Use Alternative Providers?

- **Cost savings**: Up to 98% cheaper than Claude Opus 4.6 ($15/M tokens → $0.28/M tokens)
- **Privacy**: Run models completely locally (no internet needed)
- **Flexibility**: Test different models for different use cases
- **No vendor lock-in**: Switch providers anytime

## Quick Start Guides

Choose your path based on your needs:

### 🏠 Local/Offline: llama.cpp (FREE) - ✅ Recommended

**Best for:** Privacy, offline work, zero cost, full IDE integration

**Time:** 15-20 minutes | **Cost:** FREE | **Status:** ✅ Tested & Working

```bash
# 1. Build llama.cpp (one-time)
git clone https://github.com/ggml-org/llama.cpp
cmake llama.cpp -B llama.cpp/build -DGGML_METAL=ON  # macOS
# OR: cmake llama.cpp -B llama.cpp/build -DGGML_CUDA=ON  # Linux with GPU
cmake --build llama.cpp/build --config Release -j

# 2. Start server with a coding model
cd llama.cpp
./llama-server -hf bartowski/cerebras_Qwen3-Coder-REAP-25B-A3B-GGUF:Q4_K_M \
    --alias "Qwen3-Coder" --port 8000 --jinja --ctx-size 64000

# 3. Configure daf (choose one method)
# Method A: Interactive TUI (recommended)
daf config edit  # Navigate to "Model Providers" → Add Custom Provider

# Method B: Manual config
# Add to ~/.daf-sessions/config.json:
# {
#   "model_provider": {
#     "default_profile": "llama-cpp",
#     "profiles": {
#       "llama-cpp": {
#         "name": "llama-cpp",
#         "base_url": "http://localhost:8000",
#         "auth_token": "llama-cpp",
#         "api_key": "",
#         "model_name": "Qwen3-Coder"
#       }
#     }
#   }
# }

# 4. Use with daf
daf open PROJ-123
# Claude Code will now use your local Qwen3-Coder model!
```

**First Response Time:** 30-60 seconds (normal - processing 35k tokens of tool definitions)

**See detailed guide below** for hardware requirements, model recommendations, and troubleshooting.

---

### ☁️ Cloud: OpenRouter (98% cheaper) - ⚠️ To Be Tested

**Best for:** Cloud convenience, 100+ model options, very low cost

**Time:** 2 minutes | **Cost:** $0.28-3/M tokens (98% cheaper than Claude Opus) | **Status:** ⚠️ Not yet tested with DevAIFlow

```bash
# 1. Get API key
# Visit https://openrouter.ai
# Sign up and generate API key
# Add credits to account

# 2. Configure daf
daf config edit  # Navigate to "Model Providers" → Add Custom Provider
# Or manually edit ~/.daf-sessions/config.json:
# {
#   "model_provider": {
#     "default_profile": "openrouter-deepseek",
#     "profiles": {
#       "openrouter-deepseek": {
#         "name": "openrouter-deepseek",
#         "base_url": "https://openrouter.ai/api",
#         "auth_token": "YOUR_OPENROUTER_KEY",
#         "api_key": "",
#         "model_name": "deepseek/deepseek-v3"
#       }
#     }
#   }
# }

# 3. Use with daf
daf open PROJ-123 --model-profile openrouter-deepseek
```

**Popular OpenRouter Models:**
- `deepseek/deepseek-v3` - $0.28/M tokens (best value)
- `openai/gpt-oss-120b:free` - FREE tier
- `anthropic/claude-3.5-sonnet` - $3/M tokens (80% cheaper than direct Anthropic)

**See detailed guide below** for more model options and configuration.

---

### 🏢 Enterprise: Google Vertex AI - ✅ Tested

**Best for:** Enterprise GCP users, compliance requirements

**Time:** 5 minutes | **Cost:** ~$3/M tokens | **Status:** ✅ Tested & Working

```bash
# 1. Set up GCP authentication
gcloud auth application-default login

# 2. Configure daf
daf config edit  # Navigate to "Model Providers" → Add Vertex AI
# Or manually edit ~/.daf-sessions/config.json:
# {
#   "model_provider": {
#     "default_profile": "vertex",
#     "profiles": {
#       "vertex": {
#         "name": "vertex",
#         "use_vertex": true,
#         "vertex_project_id": "your-gcp-project-id",
#         "vertex_region": "us-east5",
#         "model_name": "claude-3-5-sonnet-v2@20250929"
#       }
#     }
#   }
# }

# 3. Use with daf
daf open PROJ-123
```

**See detailed guide below** for Vertex AI setup and configuration.

---

### ❌ What About Ollama?

**Ollama does NOT work with Claude Code.** This is due to fundamental API incompatibility:
- Ollama uses OpenAI-compatible API format
- Claude Code requires Anthropic Messages API format
- These formats are incompatible (like USB-A vs USB-C)

**Use llama.cpp instead** - it provides the same local model experience with full Claude Code compatibility.

## Using Profiles

DevAIFlow provides multiple ways to select which model provider profile to use:

### Method 1: CLI Flag (Recommended for Testing)

Use `--model-profile` flag to specify a profile for a single command:

```bash
# Create session with specific profile
daf new --name feature-123 --goal "Add feature" --model-profile vertex

# Open session with specific profile (overrides session default)
daf open feature-123 --model-profile llama-cpp

# Investigate with local model
daf investigate --goal "Research options" --model-profile llama-cpp

# Session remembers last used profile
daf open feature-123  # Uses llama-cpp from previous command
```

**Session Persistence**: When you use `--model-profile`, the profile is stored in the session. Future `daf open` commands for that session will use the stored profile unless overridden.

### Method 2: Environment Variable (Temporary Override)

Use `MODEL_PROVIDER_PROFILE` environment variable:

```bash
# One-time override
MODEL_PROVIDER_PROFILE=anthropic daf open PROJ-123

# Set for entire terminal session
export MODEL_PROVIDER_PROFILE=vertex
daf new --name task-456 --goal "Debug issue"
daf open task-456
```

### Method 3: Config Default (Persistent)

Set `default_profile` in your config:

```json
{
  "model_provider": {
    "default_profile": "llama-cpp",
    "profiles": { ... }
  }
}
```

All commands use this profile unless overridden.

### Priority Resolution

Profile selection follows this priority (highest to lowest):

1. **`--model-profile` flag** (per-command override)
2. **`session.model_profile`** (stored in session from previous `--model-profile`)
3. **`MODEL_PROVIDER_PROFILE` env var** (terminal session override)
4. **`config.model_provider.default_profile`** (persistent default)
5. **Anthropic API** (fallback)

**Example Workflow**:

```bash
# Set work profile as default in config
# default_profile: "vertex"

# Create session - uses Vertex AI (config default)
daf new --name PROJ-123 --goal "Fix bug"

# Test with local model - overrides config default
daf open PROJ-123 --model-profile llama-cpp

# Next open uses last profile (llama-cpp stored in session)
daf open PROJ-123

# Force back to Vertex for deployment testing
daf open PROJ-123 --model-profile vertex
```

## Configuration

### Profile Structure

Each profile contains:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `name` | string | Profile name | `"llama-cpp"` |
| `base_url` | string (optional) | ANTHROPIC_BASE_URL override | `"http://localhost:8000"` |
| `auth_token` | string (optional) | ANTHROPIC_AUTH_TOKEN override | `"llama-cpp"` |
| `api_key` | string (optional) | ANTHROPIC_API_KEY override | `""` (empty string to disable) |
| `model_name` | string (optional) | Model for `--model` flag | `"devstral-small-2"` |
| `use_vertex` | boolean | Use Google Vertex AI | `true` |
| `vertex_project_id` | string (optional) | GCP project ID | `"my-project-123"` |
| `vertex_region` | string (optional) | GCP region | `"us-east5"` |
| `env_vars` | object (optional) | Additional env vars | `{"CUSTOM_VAR": "value"}` |

### Configuration Hierarchy

Profiles can be defined at multiple levels:

1. **Enterprise** (`enterprise.json`) - Company-wide enforcement
2. **Organization** (`organization.json`) - Project-specific
3. **Team** (`team.json`) - Team defaults
4. **User** (`config.json`) - Personal profiles

**Config Merge Priority**: User > Team > Organization > Enterprise

**Runtime Profile Selection Priority** (highest to lowest):
1. `--model-profile` CLI flag
2. `session.model_profile` (stored from previous `--model-profile`)
3. `MODEL_PROVIDER_PROFILE` environment variable
4. `config.model_provider.default_profile`
5. Anthropic API (fallback)

### Managing Profiles

**Interactive TUI (Recommended)**:
```bash
daf config edit
# Navigate to "Model Providers" tab
# Add/Edit/Delete profiles with visual interface
# Press Ctrl+S to save
```

The TUI provides:
- Visual profile editor with form validation
- Add new profiles (Anthropic, Vertex AI, or Custom providers)
- Edit existing profiles (change settings, update credentials)
- Set default profile (marked with ⭐)
- Delete profiles (except base `anthropic` profile)
- Preview profile settings before saving

**Manual JSON Editing**:

Add to `~/.daf-sessions/config.json`:
```json
{
  "model_provider": {
    "default_profile": "llama-cpp",
    "profiles": {
      "llama-cpp": {
        "name": "llama-cpp",
        "base_url": "http://localhost:8000",
        "auth_token": "llama-cpp",
        "api_key": "",
        "model_name": "Qwen3-Coder"
      }
    }
  }
}
```

## Provider Setup Guides

### ⚠️ Important: Ollama Does NOT Work with Claude Code

**Critical:** Ollama **cannot** be used with Claude Code due to API incompatibility.

**Think of it like this:** Claude Code speaks "Anthropic language" while Ollama only speaks "OpenAI language" - they can't communicate! 🗣️

**The technical breakdown:**
- ❌ Ollama provides OpenAI-compatible API
- ❌ Claude Code requires Anthropic Messages API format
- ❌ These APIs are fundamentally different and incompatible
- ❌ Like trying to plug USB-A into USB-C - won't work!

**Test results confirm incompatibility:**
```bash
# Ollama + Claude Code (❌ FAILS)
claude --model kimi-k2.5:cloud
# Result: 500 {"type":"error","error":{"type":"api_error",...}}

claude --model devstral-small-2
# Result: Hangs forever with "Deliberating..."
```

**✅ Use llama.cpp instead** (see Option 1 below) for local models with full Claude Code IDE integration.

**Why articles claim Ollama works:**
- Articles actually use llama.cpp (not Ollama) but title says "Ollama"
- Articles use API translation layers (litellm, OpenRouter) that convert between formats
- Information is outdated from older Claude Code versions

**For terminal-based Ollama chat without Claude Code IDE:** Ollama works fine for basic CLI chat, but it does NOT integrate with Claude Code's file editing, tool calling, and IDE features.

---

### Option 1: llama.cpp Server (Recommended for Local Models)

**Status:** ✅ **Tested and confirmed working**
**Time**: 15-20 minutes | **Cost**: Free | **Best for**: Local/offline usage with full Claude Code IDE integration

llama.cpp is the **ONLY local solution** that provides full Claude Code compatibility with file editing, multi-file changes, and tool calling.

#### Why llama.cpp Works (But Ollama Doesn't)

**The Core Issue: API Incompatibility**

- **Ollama** → Provides **OpenAI-compatible API**
- **Claude Code** → Requires **Anthropic Messages API**
- **Result** → ❌ **Incompatible** (like trying to plug USB-A into USB-C)

**Simple Analogy:**
- **Claude Code** speaks "Anthropic language" 🇫🇷
- **Ollama** only speaks "OpenAI language" 🇩🇪
- **llama.cpp** is bilingual and can speak "Anthropic language" 🇫🇷 (with `--jinja` flag)

You can't have a conversation if you don't speak the same language!

**Technical Differences:**

| Feature | llama.cpp | Ollama | Impact |
|---------|-----------|--------|--------|
| `--jinja` flag | ✅ Available | ❌ Not available | **Required** for tool calling |
| API customization | ✅ Flexible | ❌ Fixed OpenAI format | Allows Anthropic compatibility |
| Response format | ✅ Configurable | ❌ Standard only | Matches Claude expectations |

**The Critical `--jinja` Flag:**

This is the most important difference:

```bash
# llama.cpp (WORKS) ✅
./llama-server -hf model --port 8000 --jinja  # ← This flag is CRITICAL

# Ollama (FAILS) ❌
ollama serve  # ← No --jinja flag available
```

**What `--jinja` does:**
- Enables proper tool calling / function calling support
- Formats responses in a way Claude Code can understand
- **Without it:** Claude Code hangs forever with "Deliberating..." or gets 500 errors

**What Actually Happens:**

```bash
# With Ollama ❌
claude --model kimi-k2.5:cloud
# Result: 500 {"type":"error","error":{"type":"api_error",...}}

claude --model devstral-small-2
# Result: Hangs forever with "Deliberating..."

# With llama.cpp ✅
claude --model Qwen3-Coder
# Result: SUCCESS - Full working response!
```

**Why Articles Claim "Ollama Works":**

This confuses users because:
1. **Misleading titles**: Articles say "Run Claude Code with Ollama" but actually use llama.cpp
2. **API translation layers**: Some use litellm or OpenRouter to translate between APIs
3. **Outdated info**: Older Claude Code versions had different requirements

**What Each Tool is Designed For:**

**Ollama** is designed for:
- ✅ OpenAI API compatibility
- ✅ Easy local chat in terminal
- ✅ Simple model management with `ollama pull`

But **NOT for**:
- ❌ Claude Code's Anthropic API format
- ❌ Claude Code's tool calling requirements
- ❌ IDE integration with file editing

**llama.cpp** is designed for:
- ✅ Maximum flexibility and customization
- ✅ Custom API formats (can mimic Anthropic)
- ✅ Advanced features like `--jinja` for tool calling
- ✅ Works with Claude Code's requirements

#### Prerequisites

- macOS with Apple Silicon OR Linux with NVIDIA GPU
- 16GB+ RAM (32GB+ recommended for larger models)
- Git, CMake installed

#### Step 1: Build llama.cpp

**macOS (Apple Silicon):**
```bash
# Install dependencies
brew install cmake

# Clone and build
git clone https://github.com/ggml-org/llama.cpp
cmake llama.cpp -B llama.cpp/build -DGGML_METAL=ON
cmake --build llama.cpp/build --config Release -j
```

**Linux (NVIDIA GPU):**
```bash
# Install dependencies
sudo apt-get update && sudo apt-get install build-essential cmake git -y

# Clone and build
git clone https://github.com/ggml-org/llama.cpp
cmake llama.cpp -B llama.cpp/build -DGGML_CUDA=ON
cmake --build llama.cpp/build --config Release -j
```

#### Step 2: Start llama.cpp Server

```bash
cd llama.cpp

# Start server with CRITICAL FLAGS
./llama-server -hf bartowski/cerebras_Qwen3-Coder-REAP-25B-A3B-GGUF:Q4_K_M \
    --alias "Qwen3-Coder" \
    --port 8000 \
    --jinja \              # ← CRITICAL: Required for tool calling
    --kv-unified \
    --cache-type-k q8_0 --cache-type-v q8_0 \
    --flash-attn on \
    --batch-size 4096 --ubatch-size 1024 \
    --ctx-size 64000
```

**Important flags explained:**
- `--jinja` - **REQUIRED** for Claude Code tool calling to work
- `--hf` - Download model directly from HuggingFace
- `--alias` - Model name to use in Claude Code
- `--ctx-size 64000` - Large context for Claude Code's tool definitions (~35k tokens)

**Keep this terminal running** - the server must stay active.

#### Step 3: Configure daf Model Provider Profile

**Method 1: Interactive TUI (Recommended)**

```bash
# Open configuration TUI
daf config edit

# Navigate to "Model Providers" tab
# Click "Add Profile" → "Custom Provider"
# Fill in:
#   Name: llama-cpp
#   Base URL: http://localhost:8000
#   Auth Token: llama-cpp
#   API Key: (leave empty)
#   Model Name: Qwen3-Coder
#
# Click "Set as Default" (optional)
# Press Ctrl+S to save
```

**Method 2: Manual JSON Edit**

Edit `~/.daf-sessions/config.json`:

```json
{
  "model_provider": {
    "default_profile": "llama-cpp",
    "profiles": {
      "llama-cpp": {
        "name": "llama-cpp",
        "base_url": "http://localhost:8000",
        "auth_token": "llama-cpp",
        "api_key": "",
        "model_name": "Qwen3-Coder"
      }
    }
  }
}
```

**Method 3: Environment Variables (Temporary)**

```bash
export ANTHROPIC_BASE_URL="http://localhost:8000"
export ANTHROPIC_AUTH_TOKEN="llama-cpp"
export ANTHROPIC_API_KEY=""
```

#### Step 4: Use with daf

```bash
# Uses default profile (llama-cpp)
daf open PROJ-123

# Or override per session
daf open PROJ-123 --model-profile llama-cpp

# Or use environment variable
MODEL_PROVIDER_PROFILE=llama-cpp daf open PROJ-456
```

**Session starts with Claude Code using your local llama.cpp model!**

#### Step 5: Test It Works

In Claude Code, type: `hi`

**Expected:**
- First prompt takes 30-60 seconds (processing 35k tokens of tool definitions)
- You get a response from the model
- Subsequent prompts are much faster

**If it hangs forever:**
- Check llama.cpp server logs
- Verify `--jinja` flag was included
- Verify model supports tool calling

#### Performance Notes

**Initial Prompt:**
- Claude Code sends ~35,140 tokens on first prompt (tool definitions, context)
- llama.cpp processes at ~2048 tokens/batch
- Expect 30-60 seconds for first response
- **This is normal!**

**Subsequent Prompts:**
- Much faster (context already loaded)
- Response time depends on hardware and model size

**Hardware Recommendations:**
- **16GB RAM:** Use Q4_K_M quantized models (24B parameters max)
- **32GB RAM:** Use Q4_K_M or Q5_K_M quantized models (30B parameters comfortable)
- **64GB+ RAM:** Larger models and higher quantization

#### Recommended Models for Coding

**For 32GB RAM:**
```bash
# Qwen3-Coder (25B) - Excellent for coding
./llama-server -hf bartowski/cerebras_Qwen3-Coder-REAP-25B-A3B-GGUF:Q4_K_M \
    --alias "Qwen3-Coder" --port 8000 --jinja \
    --ctx-size 64000 --batch-size 4096 --ubatch-size 1024

# DeepSeek-Coder V2 (16B) - Fast and capable
./llama-server -hf bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF:Q5_K_M \
    --alias "DeepSeek-Coder" --port 8000 --jinja \
    --ctx-size 64000 --batch-size 4096 --ubatch-size 1024
```

**For 16GB RAM:**
```bash
# Qwen2.5-Coder (14B) - Good balance
./llama-server -hf bartowski/Qwen2.5-Coder-14B-Instruct-GGUF:Q4_K_M \
    --alias "Qwen2.5-Coder" --port 8000 --jinja \
    --ctx-size 64000 --batch-size 4096 --ubatch-size 1024
```

#### Multiple Models Setup

You can configure multiple llama.cpp profiles for different models:

```json
{
  "model_provider": {
    "default_profile": "llama-coding",
    "profiles": {
      "llama-coding": {
        "name": "llama-coding",
        "base_url": "http://localhost:8000",
        "auth_token": "llama-cpp",
        "api_key": "",
        "model_name": "Qwen3-Coder"
      },
      "llama-fast": {
        "name": "llama-fast",
        "base_url": "http://localhost:8001",
        "auth_token": "llama-cpp",
        "api_key": "",
        "model_name": "Qwen2.5-7B"
      }
    }
  }
}
```

Start multiple servers on different ports:
```bash
# Terminal 1: Larger model for complex tasks
./llama-server -hf bartowski/cerebras_Qwen3-Coder-REAP-25B-A3B-GGUF:Q4_K_M \
    --port 8000 --alias "Qwen3-Coder" --jinja --ctx-size 64000

# Terminal 2: Smaller model for quick tasks
./llama-server -hf bartowski/Qwen2.5-Coder-7B-Instruct-GGUF:Q4_K_M \
    --port 8001 --alias "Qwen2.5-7B" --jinja --ctx-size 64000
```

Switch between them:
```bash
daf open PROJ-123 --model-profile llama-coding  # Use 25B model
daf open PROJ-456 --model-profile llama-fast    # Use 7B model
```

#### Pros and Cons

**Pros:**
- ✅ Full Claude Code IDE integration (file editing, multi-file changes)
- ✅ Works with any GGUF model from HuggingFace
- ✅ Completely offline
- ✅ Zero cost
- ✅ Tested and confirmed working
- ✅ Control over model size, quantization, hardware usage

**Cons:**
- ⚠️ Complex initial setup (build from source)
- ⚠️ Slow first prompt (30-60 seconds)
- ⚠️ Requires manual server management
- ⚠️ Need to keep terminal running

---

### Option 2: OpenRouter (⚠️ To Be Tested)

**Time**: 2 minutes | **Cost**: Pay-per-use | **Best for**: Access to many models with one API key | **Status**: ⚠️ Not yet tested with DevAIFlow

OpenRouter provides a universal adapter for AI APIs.

#### Step 1: Get API Key

1. Go to [openrouter.ai](https://openrouter.ai)
2. Create account and generate API key
3. Add credits to account

#### Step 2: Configure Profile

```json
{
  "model_provider": {
    "profiles": {
      "openrouter-free": {
        "name": "openrouter-free",
        "base_url": "https://openrouter.ai/api",
        "auth_token": "YOUR_OPENROUTER_KEY",
        "api_key": "",
        "model_name": "openai/gpt-oss-120b:free"
      },
      "openrouter-deepseek": {
        "name": "openrouter-deepseek",
        "base_url": "https://openrouter.ai/api",
        "auth_token": "YOUR_OPENROUTER_KEY",
        "api_key": "",
        "model_name": "deepseek/deepseek-v3.2"
      }
    }
  }
}
```

**Popular Models**:
- `openai/gpt-oss-120b:free` - Free tier
- `deepseek/deepseek-v3.2` - Cheapest ($0.28/M tokens)
- `anthropic/claude-3.5-sonnet` - High quality

#### Step 3: Use

```bash
MODEL_PROVIDER_PROFILE=openrouter-deepseek daf open PROJ-123
```

### Option 3: LM Studio (⚠️ To Be Tested)

**Time**: 5 minutes | **Cost**: Free | **Best for**: GUI model management | **Status**: ⚠️ Not yet tested with DevAIFlow

#### Step 1: Install LM Studio

Download from [lmstudio.ai/download](https://lmstudio.ai/download)

Or for servers:

```bash
curl -fsSL https://lmstudio.ai/install.sh | bash
```

#### Step 2: Download Model

Using GUI: Browse and download models directly
Using CLI:

```bash
lms chat
# Then use /download command to search and download models
```

#### Step 3: Start Server

```bash
lms server start --port 1234
```

#### Step 4: Configure Profile

```json
{
  "model_provider": {
    "profiles": {
      "lmstudio": {
        "name": "lmstudio",
        "base_url": "http://localhost:1234",
        "auth_token": "lmstudio",
        "api_key": "",
        "model_name": "qwen/qwen3-coder-30b"
      }
    }
  }
}
```

### Option 4: Google Vertex AI (✅ Tested)

**Time**: 5 minutes | **Cost**: Pay-per-use | **Best for**: Enterprise GCP users | **Status**: ✅ Tested and working

#### Step 1: Set Up GCP Project

1. Enable Vertex AI API in your GCP project
2. Set up authentication (Application Default Credentials)

```bash
gcloud auth application-default login
```

#### Step 2: Configure Profile

```json
{
  "model_provider": {
    "default_profile": "vertex",
    "profiles": {
      "vertex": {
        "name": "vertex",
        "use_vertex": true,
        "vertex_project_id": "your-gcp-project-id",
        "vertex_region": "us-east5",
        "model_name": "claude-3-5-sonnet-v2@20250929"
      }
    }
  }
}
```

## Switching Between Providers

### Permanent Switch

Edit `~/.daf-sessions/config.json`:

```json
{
  "model_provider": {
    "default_profile": "llama-cpp"  // Changed from "anthropic"
  }
}
```

### Temporary Override

Use environment variable:

```bash
# Use llama.cpp for this session
MODEL_PROVIDER_PROFILE=llama-cpp daf open PROJ-123

# Use Vertex AI for this session
MODEL_PROVIDER_PROFILE=vertex daf open PROJ-456

# Use Anthropic API (override llama.cpp default)
MODEL_PROVIDER_PROFILE=anthropic daf open PROJ-789
```

### Multiple Profiles Workflow

```json
{
  "model_provider": {
    "default_profile": "vertex",
    "profiles": {
      "vertex": {
        "name": "vertex",
        "use_vertex": true,
        "vertex_project_id": "work-project",
        "vertex_region": "us-east5"
      },
      "llama-cpp": {
        "name": "llama-cpp",
        "base_url": "http://localhost:8000",
        "auth_token": "llama-cpp",
        "api_key": "",
        "model_name": "Qwen3-Coder"
      },
      "anthropic": {
        "name": "anthropic"
      }
    }
  }
}
```

**Usage**:
- Work: Uses Vertex AI (default)
- Testing locally: `MODEL_PROVIDER_PROFILE=llama-cpp daf open`
- Emergency (llama.cpp server down): `MODEL_PROVIDER_PROFILE=anthropic daf open`

## Enterprise Configuration

Enterprises can enforce model provider usage across all users.

### Enforce Vertex AI Company-Wide

`~/.daf-sessions/enterprise.json`:

```json
{
  "model_provider": {
    "default_profile": "vertex",
    "profiles": {
      "vertex": {
        "name": "vertex",
        "use_vertex": true,
        "vertex_project_id": "company-gcp-project",
        "vertex_region": "us-east5"
      }
    }
  }
}
```

Users cannot override enterprise settings (only use allowed profiles).

### Provide Shared llama.cpp Server

`~/.daf-sessions/organization.json`:

```json
{
  "model_provider": {
    "profiles": {
      "llama-cpp-shared": {
        "name": "llama-cpp-shared",
        "base_url": "http://llama-cpp.internal.company.com:8000",
        "auth_token": "llama-cpp",
        "api_key": "",
        "model_name": "Qwen3-Coder"
      }
    }
  }
}
```

Teams can use the shared server without individual setup.

## Troubleshooting

### Common Issues by Category

#### 🚫 Ollama Compatibility Issues

**Problem:** "I followed Ollama setup but it doesn't work"

**Symptoms:**
- 500 errors: `{"type":"error","error":{"type":"api_error",...}}`
- Infinite hangs: `✽ Deliberating…` never completes
- Tool calling fails or file editing doesn't work

**Root Cause:** Ollama uses OpenAI-compatible API, but Claude Code requires Anthropic's API format. These are fundamentally incompatible (like trying to plug USB-A into USB-C).

**Solution:** ✅ Use llama.cpp instead:
1. Follow [llama.cpp setup guide](#option-1-llamacpp-server-recommended-for-local-models) above
2. Key difference: llama.cpp has `--jinja` flag for tool calling compatibility
3. llama.cpp server can be configured to match Anthropic API expectations

**Why articles claim Ollama works:**
- They actually use llama.cpp (not Ollama) but title says "Ollama"
- They use API translation layers (litellm, OpenRouter)
- Information is outdated from older Claude Code versions

---

#### 🐌 Performance Issues

**Problem:** llama.cpp hangs forever / very slow first response

**Expected Behavior:**
- First prompt: 30-60 seconds (processing ~35k tokens of tool definitions)
- Subsequent prompts: Much faster (context already loaded)

**If stuck after 2+ minutes:**

1. **Check Hardware Requirements:**
   - Model too large for available RAM?
   - Try smaller quantization (Q4_K_M instead of Q6_K)
   - Try smaller model (14B instead of 25B)

2. **Reduce Resource Usage:**
   ```bash
   # Reduce context size
   --ctx-size 32000  # instead of 64000

   # Reduce batch size (slower but less memory)
   --batch-size 2048 --ubatch-size 512
   ```

3. **Check Server Logs:**
   - Look for out-of-memory errors
   - Look for model loading failures
   - Verify model supports instruct format

**Performance Tuning:**
- **16GB RAM**: Use Q4_K_M quantized models, 14B-16B parameters max
- **32GB RAM**: Use Q4_K_M or Q5_K_M, 25B-30B parameters comfortable
- **64GB+ RAM**: Larger models and higher quantization

---

#### 🔧 Configuration Issues

**Problem:** Profile not found

**Error Message:**
```
Warning: MODEL_PROVIDER_PROFILE=llama-cpp not found in configuration
```

**Solutions:**
1. Check profile name in `~/.daf-sessions/config.json`
2. Profile names are **case-sensitive** (`llama-cpp` ≠ `Llama-Cpp`)
3. Verify JSON syntax is valid (use `daf config validate`)
4. Try using TUI: `daf config edit` to visually verify profiles

---

**Problem:** Missing `--jinja` flag

**Symptoms:**
- Server starts fine
- Claude Code connects
- Hangs on first prompt or tool use fails
- File editing doesn't work

**Solution:**
```bash
# ❌ WRONG (missing --jinja)
./llama-server -hf model --port 8000

# ✅ CORRECT (includes --jinja)
./llama-server -hf model --port 8000 --jinja
```

**The `--jinja` flag is REQUIRED for Claude Code tool calling to work!**

---

#### 🌐 Connection Issues

**Problem:** Connection refused

**Error Message:**
```
Error: Failed to connect to http://localhost:8000
```

**Debugging Steps:**

1. **Verify server is running:**
   ```bash
   curl http://localhost:8000/health
   # OR
   curl http://localhost:8000/v1/models
   ```

2. **Check port number:**
   - Does `base_url` in profile match server port?
   - Is another process using the port? `lsof -i :8000`

3. **For llama.cpp:**
   - Check terminal where `llama-server` is running
   - Look for startup errors or crashes

4. **Firewall/Network:**
   - Verify no firewall blocking localhost connections
   - Try `127.0.0.1` instead of `localhost`

---

**Problem:** Model not found

**Error Message:**
```
Error: model 'Qwen3-Coder' not found
```

**Solutions:**

1. **Verify alias matches:**
   - Server `--alias` flag must match profile `model_name`
   - Example: `--alias "Qwen3-Coder"` → `"model_name": "Qwen3-Coder"`

2. **Check server logs:**
   - Look for model loading errors
   - Verify model downloaded successfully from HuggingFace

3. **Try different model:**
   - Test with known-working model first
   - Example: `bartowski/Qwen2.5-Coder-7B-Instruct-GGUF:Q4_K_M`

---

#### ☁️ Cloud Provider Issues

**Problem:** Vertex AI authentication failed

**Solutions:**

1. **Re-authenticate:**
   ```bash
   gcloud auth application-default login
   ```

2. **Verify project ID:**
   - Check `vertex_project_id` is correct
   - Run `gcloud projects list` to see available projects

3. **Enable API:**
   - Vertex AI API must be enabled: `gcloud services enable aiplatform.googleapis.com`

4. **Check region:**
   - Verify `vertex_region` is valid (e.g., `us-east5`, `us-central1`)
   - Not all regions support all models

---

**Problem:** OpenRouter API errors

**Common Issues:**

1. **Invalid API key:**
   - Verify key is correct in profile `auth_token`
   - Check key hasn't been revoked at openrouter.ai

2. **Insufficient credits:**
   - Add credits to your OpenRouter account

3. **Model not available:**
   - Check model name is exact (case-sensitive)
   - Verify model is available at openrouter.ai/models

---

#### 📋 General Debugging Tips

**Enable verbose logging:**
```bash
# For llama.cpp
./llama-server --log-enable --log-file server.log ...

# For daf commands
daf open PROJ-123 --verbose
```

**Test with curl:**
```bash
# Test if server responds
curl http://localhost:8000/v1/models

# Test basic completion (OpenAI format)
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen3-Coder","messages":[{"role":"user","content":"Hi"}]}'
```

**Check daf configuration:**
```bash
# Validate config syntax
daf config validate

# Show active configuration
daf config show

# Show all profiles
daf config show-profiles
```

**Test step-by-step:**
1. ✅ Server running? (`curl http://localhost:8000/health`)
2. ✅ Profile configured? (`daf config show-profiles`)
3. ✅ Profile selected? (`daf open --model-profile llama-cpp`)
4. ✅ Claude Code launches? (check for errors)
5. ✅ First response? (wait 30-60 seconds)

## Performance Comparison

**Based on testing with MacBook Pro M1 (32GB) and Nvidia DGX Spark (120GB, GB10)**:

| Provider | Model | Hardware | Speed | Quality | Cost | Status |
|----------|-------|----------|-------|---------|------|--------|
| Anthropic | Claude Opus 4.6 | Cloud | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $$$$ | ✅ **Tested** |
| Vertex AI | Claude 3.5 Sonnet v2 | Cloud | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $$$ | ✅ **Tested** |
| llama.cpp | Qwen3-Coder (25B Q4) | Mac M1 32GB | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Free | ✅ **Tested** |
| llama.cpp | DeepSeek-Coder (16B Q5) | DGX Spark | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Free | ✅ **Tested** |
| OpenRouter | deepseek-v3.2 | Cloud | ? | ? | $ (98% cheaper) | ⚠️ **To be tested** |
| LM Studio | Various models | Local | ? | ? | Free | ⚠️ **To be tested** |
| ~~Ollama~~ | ~~Any model~~ | ~~Any~~ | ❌ | ❌ | ❌ | ❌ **Incompatible** |

**Note:** Only Anthropic API, Vertex AI, and llama.cpp have been tested and confirmed working. OpenRouter and LM Studio are theoretically compatible but need testing. Ollama does NOT work with Claude Code due to API incompatibility.

## Decision Matrix: Which Solution to Use?

### Quick Comparison

| Solution | Setup | Cost | Offline | IDE Integration | Model Choice | Status |
|----------|-------|------|---------|----------------|--------------|--------|
| **Anthropic API** | ⭐⭐⭐⭐⭐ Instant | $$$$ High | ❌ No | ✅ Full | Claude only | ✅ **Tested** |
| **Vertex AI** | ⭐⭐⭐⭐ Easy | $$$ Medium | ❌ No | ✅ Full | Claude only | ✅ **Tested** |
| **llama.cpp** | ⭐⭐ Complex | Free | ✅ Yes | ✅ Full | Any GGUF | ✅ **Tested** |
| **OpenRouter** | ⭐⭐⭐⭐⭐ Instant | $ Very low | ❌ No | ? | 100+ models | ⚠️ **To be tested** |
| **LM Studio** | ⭐⭐⭐⭐ Easy | Free | ✅ Yes | ? | Any GGUF | ⚠️ **To be tested** |
| **~~Ollama~~** | ❌ Not compatible | - | - | ❌ No | - | ❌ **Incompatible** |

### Use Case Recommendations

**Use Anthropic API when:**
- ✅ Want best quality (Claude Opus 4.6)
- ✅ Don't mind cost
- ✅ Need instant setup
- ✅ Have internet connection
- ✅ Need production reliability

**Use Vertex AI when:**
- ✅ Enterprise GCP user
- ✅ Need Claude models
- ✅ Want enterprise billing/security
- ✅ Already using GCP infrastructure
- ✅ Need compliance/audit trails

**Use OpenRouter when:**
- ✅ Want cloud convenience
- ✅ Want very low cost ($0.28/M tokens)
- ✅ Want access to many models
- ✅ Need instant setup
- ✅ Willing to pay (but cheaply)
- ✅ Want to test different models easily

**Use llama.cpp when:**
- ✅ Want completely offline/local
- ✅ Want zero cost
- ✅ Want full IDE integration
- ✅ Want control over model selection
- ✅ Don't mind complex setup
- ✅ Don't mind slow initial prompt (30-60s)
- ✅ Have sufficient hardware (16GB+ RAM)

**Use LM Studio when:**
- ✅ Want local models with GUI
- ✅ Prefer visual model management
- ✅ Want zero cost
- ✅ Don't mind slower performance vs llama.cpp
- ✅ Want easier setup than llama.cpp

**Do NOT use Ollama:**
- ❌ API incompatibility with Claude Code
- ❌ All models fail (500 errors or hangs)
- ❌ Use llama.cpp or LM Studio instead for local models

## Other LLM Servers - Compatibility Guide

**Want to try a different LLM server?** Here's what you need to know before testing:

### Compatibility Requirements

For an LLM server to work with Claude Code, it MUST support:

1. ✅ **Anthropic Messages API format** (not just OpenAI-compatible)
2. ✅ **Tool calling / function calling** in Anthropic format
3. ✅ **Response streaming** in the format Claude Code expects

**Most LLM servers WON'T work** because they're designed for OpenAI API compatibility, which is incompatible with Claude Code.

### Known Status

| Server | Status | Reason |
|--------|--------|--------|
| **llama.cpp** | ✅ **Works** | Flexible API, `--jinja` flag for tool calling |
| **LM Studio** | ✅ **Works** | GUI wrapper around llama.cpp |
| **OpenRouter** | ✅ **Works** | Cloud service with multi-API support |
| **Vertex AI** | ✅ **Works** | Native Claude models from Google Cloud |
| **Ollama** | ❌ **Incompatible** | OpenAI-only format, no `--jinja` equivalent |
| **vLLM** | ⚠️ **Likely fails** | OpenAI-compatible only (untested) |
| **Text Gen Inference** | ⚠️ **Likely fails** | OpenAI-compatible only (untested) |
| **LocalAI** | ⚠️ **Likely fails** | Explicitly OpenAI-compatible (untested) |
| **FastChat** | ⚠️ **Likely fails** | OpenAI-compatible API (untested) |
| **Koboldcpp** | ⚠️ **Unknown** | llama.cpp fork, might work (untested) |
| **Jan** | ⚠️ **Unknown** | Unclear API format (untested) |

### Testing a New Server

**Before adding a new server to the documentation**, please test:

1. **Basic connectivity:** Can you start a session?
2. **Simple prompts:** Does it respond to "hi" or simple questions?
3. **Tool calling:** Can it edit files when you ask? This is the critical test!
4. **Multi-turn conversation:** Does context work across multiple prompts?

**If it fails at tool calling** (step 3), it's incompatible - don't waste more time.

### How to Test Tool Calling

```bash
# 1. Start your LLM server
# 2. Configure daf profile pointing to it
# 3. Open a test session
daf new --name test-server --goal "Test compatibility"

# 4. In Claude Code, try a file operation:
# Type: "Create a file called test.txt with the word 'hello' in it"

# Expected: ✅ File is created
# Failure: ❌ Hangs, errors, or just responds without creating file
```

**If tool calling works, congrats! 🎉** Please report your success:
- Open an issue at: https://github.com/itdove/devaiflow/issues
- Title: "Confirmed working: [Server Name] with Claude Code"
- Include: Server version, configuration, test results

### Why We Don't List Untested Servers

We learned from the Ollama situation:
- ❌ Misleading documentation wastes users' time
- ❌ Untested claims damage credibility
- ✅ Only tested, verified configurations should be documented

**Help us expand this list!** Test servers and report your results. Community-verified configurations will be added to the official documentation.

## Best Practices

1. **Test locally first**: Use llama.cpp or LM Studio to test workflow before committing to paid API
2. **Have a fallback**: Configure multiple profiles (local + cloud)
3. **Match model to task**: Use smaller models for simple tasks, larger for complex
4. **Monitor costs**: Track API usage for cloud providers
5. **Keep profiles updated**: Document which models work well for your use cases
6. **Avoid Ollama**: Don't waste time trying to make Ollama work - it's incompatible with Claude Code

## See Also

- [AI Agent Support Matrix](ai-agent-support-matrix.md) - Compare different AI agents
- [Configuration Guide](configuration.md) - Full configuration reference
- [Article: Run Claude Code on Local/Cloud Models](https://medium.com/@luongnv89/run-claude-code-on-local-cloud-models-in-5-minutes-ollama-openrouter-llama-cpp-6dfeaee03cda)
