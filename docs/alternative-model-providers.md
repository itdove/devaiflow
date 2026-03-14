# Alternative Model Providers

DevAIFlow supports running Claude Code with alternative AI model providers through environment variable configuration. This allows you to use local models (Ollama, llama.cpp, LM Studio) or cloud providers (OpenRouter, Minimax, etc.) instead of the default Anthropic API.

## Why Use Alternative Providers?

- **Cost savings**: Up to 98% cheaper than Claude Opus 4.5
- **Privacy**: Run models completely locally (no internet needed)
- **Flexibility**: Test different models for different use cases
- **No vendor lock-in**: Switch providers anytime

## Quick Start

### 1. Configure a Profile

Add to your `~/.daf-sessions/config.json`:

```json
{
  "model_provider": {
    "default_profile": "ollama-local",
    "profiles": {
      "ollama-local": {
        "name": "ollama-local",
        "base_url": "http://localhost:11434",
        "auth_token": "ollama",
        "api_key": "",
        "model_name": "devstral-small-2"
      }
    }
  }
}
```

### 2. Install and Start the Provider

```bash
# Example: Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull devstral-small-2
```

### 3. Use DevAIFlow

```bash
# Uses default profile (ollama-local)
daf open PROJ-123

# Override with different profile
MODEL_PROVIDER_PROFILE=anthropic daf open PROJ-123
```

## Configuration

### Profile Structure

Each profile contains:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `name` | string | Profile name | `"ollama-local"` |
| `base_url` | string (optional) | ANTHROPIC_BASE_URL override | `"http://localhost:11434"` |
| `auth_token` | string (optional) | ANTHROPIC_AUTH_TOKEN override | `"ollama"` |
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

**Priority**: User > Team > Organization > Enterprise

**Environment variable override**: `MODEL_PROVIDER_PROFILE=profile-name` (highest priority)

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
    "default_profile": "ollama-local",
    "profiles": {
      "ollama-local": {
        "name": "ollama-local",
        "base_url": "http://localhost:11434",
        "auth_token": "ollama",
        "api_key": "",
        "model_name": "devstral-small-2"
      }
    }
  }
}
```

## Provider Setup Guides

### Option 1: Ollama Local

**Time**: 5 minutes | **Cost**: Free | **Best for**: Privacy, offline use

#### Step 1: Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

#### Step 2: Pull a Model

```bash
# Recommended for 32GB RAM
ollama pull devstral-small-2

# Alternative: GLM-4.7-flash (30B - F16)
ollama pull glm-4.7-flash:bf16

# Alternative: Qwen3-Coder (30B)
ollama pull qwen3-coder:30b
```

**Model Recommendations by RAM**:
- **16GB**: devstral-small-2 (24B) - usable but slower
- **32GB**: devstral-small-2 (24B) or glm-4.7-flash:bf16 (30B) - good performance
- **64GB+**: qwen3-coder:30b or larger models

#### Step 3: Configure Profile

Add to `~/.daf-sessions/config.json`:

```json
{
  "model_provider": {
    "default_profile": "ollama-local",
    "profiles": {
      "ollama-local": {
        "name": "ollama-local",
        "base_url": "http://localhost:11434",
        "auth_token": "ollama",
        "api_key": "",
        "model_name": "devstral-small-2"
      }
    }
  }
}
```

#### Step 4: Use

```bash
daf open PROJ-123
```

### Option 2: Ollama Cloud Models

**Time**: 2 minutes | **Cost**: Pay-per-use | **Best for**: Cloud power with local workflow

Ollama provides `:cloud` variants that run on cloud infrastructure.

#### Step 1: Pull Cloud Model

```bash
ollama pull kimi-k2.5:cloud
ollama pull minimax-m2.1:cloud
```

#### Step 2: Configure Profile

```json
{
  "model_provider": {
    "profiles": {
      "ollama-cloud-kimi": {
        "name": "ollama-cloud-kimi",
        "base_url": "http://localhost:11434",
        "auth_token": "ollama",
        "api_key": "",
        "model_name": "kimi-k2.5:cloud"
      }
    }
  }
}
```

#### Step 3: Use

```bash
MODEL_PROVIDER_PROFILE=ollama-cloud-kimi daf open PROJ-123
```

### Option 3: OpenRouter

**Time**: 2 minutes | **Cost**: Pay-per-use | **Best for**: Access to many models with one API key

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

### Option 4: LM Studio

**Time**: 5 minutes | **Cost**: Free | **Best for**: GUI model management

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

### Option 5: llama.cpp + HuggingFace

**Time**: 15-20 minutes | **Cost**: Free | **Best for**: Any model from HuggingFace

#### Step 1: Build llama.cpp

**macOS (Apple Silicon)**:

```bash
brew install cmake
git clone https://github.com/ggml-org/llama.cpp
cmake llama.cpp -B llama.cpp/build -DGGML_METAL=ON
cmake --build llama.cpp/build --config Release -j
cp llama.cpp/build/bin/llama-* llama.cpp/
```

**Linux (NVIDIA GPU)**:

```bash
sudo apt-get update && sudo apt-get install build-essential cmake git -y
git clone https://github.com/ggml-org/llama.cpp
cmake llama.cpp -B llama.cpp/build -DGGML_CUDA=ON
cmake --build llama.cpp/build --config Release -j
cp llama.cpp/build/bin/llama-* llama.cpp/
```

#### Step 2: Start Server

```bash
cd llama.cpp
./llama-server -hf bartowski/cerebras_Qwen3-Coder-REAP-25B-A3B-GGUF:Q4_K_M \
    --alias "Qwen3-Coder-REAP-25B-A3B-GGUF" \
    --port 8000 \
    --jinja \
    --kv-unified \
    --cache-type-k q8_0 --cache-type-v q8_0 \
    --flash-attn on \
    --batch-size 4096 --ubatch-size 1024 \
    --ctx-size 64000
```

**Important**: The `--jinja` flag is required for tool calling to work.

#### Step 3: Configure Profile

```json
{
  "model_provider": {
    "profiles": {
      "llama-cpp": {
        "name": "llama-cpp",
        "base_url": "http://localhost:8000",
        "api_key": "",
        "model_name": "Qwen3-Coder-REAP-25B-A3B-GGUF"
      }
    }
  }
}
```

### Option 6: Google Vertex AI

**Time**: 5 minutes | **Cost**: Pay-per-use | **Best for**: Enterprise GCP users

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
    "default_profile": "ollama-local"  // Changed from "anthropic"
  }
}
```

### Temporary Override

Use environment variable:

```bash
# Use Ollama for this session
MODEL_PROVIDER_PROFILE=ollama-local daf open PROJ-123

# Use Vertex AI for this session
MODEL_PROVIDER_PROFILE=vertex daf open PROJ-456

# Use Anthropic API (override Ollama default)
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
      "ollama-local": {
        "name": "ollama-local",
        "base_url": "http://localhost:11434",
        "auth_token": "ollama",
        "api_key": "",
        "model_name": "devstral-small-2"
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
- Testing locally: `MODEL_PROVIDER_PROFILE=ollama-local daf open`
- Emergency (Ollama down): `MODEL_PROVIDER_PROFILE=anthropic daf open`

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

### Provide Shared Ollama Server

`~/.daf-sessions/organization.json`:

```json
{
  "model_provider": {
    "profiles": {
      "ollama-shared": {
        "name": "ollama-shared",
        "base_url": "http://ollama.internal.company.com:11434",
        "auth_token": "ollama",
        "api_key": "",
        "model_name": "devstral-small-2"
      }
    }
  }
}
```

Teams can use the shared server without individual setup.

## Troubleshooting

### Profile Not Found

```
Warning: MODEL_PROVIDER_PROFILE=ollama-local not found in configuration
```

**Solution**: Check profile name in `~/.daf-sessions/config.json`. Profile names are case-sensitive.

### Connection Refused

```
Error: Failed to connect to http://localhost:11434
```

**Solutions**:
1. Check if server is running: `curl http://localhost:11434/api/tags`
2. Verify port number matches profile `base_url`
3. For Ollama: Run `ollama serve` or `ollama list` to start server

### Model Not Found

```
Error: model 'devstral-small-2' not found
```

**Solutions**:
1. Pull model: `ollama pull devstral-small-2`
2. List available models: `ollama list`
3. Verify `model_name` matches exact model name

### Tool Calling Doesn't Work

**For llama.cpp**: Must use `--jinja` flag when starting server:

```bash
./llama-server -hf ... --jinja ...
```

**For other providers**: Check model supports function calling/tool use.

### Vertex AI Authentication Failed

**Solutions**:
1. Run: `gcloud auth application-default login`
2. Verify `vertex_project_id` is correct
3. Check Vertex AI API is enabled in GCP project
4. Verify `vertex_region` matches your project configuration

## Performance Comparison

**Based on testing with MacBook Pro M1 (32GB) and Nvidia DGX Spark (120GB, GB10)**:

| Provider | Model | Hardware | Speed | Quality | Cost |
|----------|-------|----------|-------|---------|------|
| Anthropic | Claude Opus 4.5 | Cloud | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $$$$ |
| Vertex AI | Claude 3.5 Sonnet | Cloud | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $$$ |
| Ollama | devstral-small-2 (24B) | Mac M1 32GB | ⭐⭐⭐ | ⭐⭐⭐⭐ | Free |
| Ollama | glm-4.7-flash:bf16 (30B) | DGX Spark | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Free |
| Ollama Cloud | kimi-k2.5:cloud | Cloud | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | $ |
| OpenRouter | deepseek-v3.2 | Cloud | ⭐⭐⭐⭐ | ⭐⭐⭐ | $ (98% cheaper) |

## Best Practices

1. **Test locally first**: Use Ollama to test workflow before committing to paid API
2. **Have a fallback**: Configure multiple profiles (local + cloud)
3. **Match model to task**: Use smaller models for simple tasks, larger for complex
4. **Monitor costs**: Track API usage for cloud providers
5. **Keep profiles updated**: Document which models work well for your use cases

## See Also

- [AI Agent Support Matrix](ai-agent-support-matrix.md) - Compare different AI agents
- [Configuration Guide](06-configuration.md) - Full configuration reference
- [Article: Run Claude Code on Local/Cloud Models](https://medium.com/@luongnv89/run-claude-code-on-local-cloud-models-in-5-minutes-ollama-openrouter-llama-cpp-6dfeaee03cda)
