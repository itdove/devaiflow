# Tutorial: Run Claude Code with Local Models Using llama.cpp

**Save 100% on AI costs and run completely offline**

This step-by-step tutorial shows you how to set up llama.cpp with DevAIFlow to run Claude Code using free local models on your machine. Perfect for:
- 💰 Developers wanting zero-cost AI assistance
- 🔒 Teams requiring complete data privacy
- ✈️ Working offline without internet access
- 🧪 Experimenting with different coding models

## What You'll Get

By the end of this tutorial, you'll have:
- ✅ llama.cpp server running locally
- ✅ Qwen3-Coder 25B model (or your choice)
- ✅ DevAIFlow configured to use local models
- ✅ Full Claude Code IDE integration working offline

**Time Required:** 15-20 minutes
**Cost:** FREE (forever)
**Difficulty:** Intermediate

## Prerequisites

### Hardware Requirements

**Minimum:**
- 16GB RAM (for 14B parameter models)
- 50GB free disk space
- macOS with Apple Silicon OR Linux with NVIDIA GPU

**Recommended:**
- 32GB+ RAM (for 25B+ parameter models)
- 100GB free disk space for multiple models
- Fast SSD for better performance

### Software Requirements

- **Git** - For cloning llama.cpp repository
- **CMake** - For building llama.cpp
- **DevAIFlow** - Already installed (`pip install devaiflow`)
- **Claude Code CLI** - Version 2.1.3 or higher

**Install dependencies:**

```bash
# macOS
brew install cmake git

# Ubuntu/Debian
sudo apt-get update && sudo apt-get install build-essential cmake git -y

# Fedora/RHEL
sudo dnf install gcc gcc-c++ cmake git -y
```

## Step 1: Build llama.cpp (One-Time Setup)

### For macOS (Apple Silicon)

```bash
# Clone the repository
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp

# Build with Metal support (GPU acceleration)
cmake -B build -DGGML_METAL=ON
cmake --build build --config Release -j

# Verify build succeeded
ls build/bin/llama-server  # Should exist
```

**Compilation time:** 3-5 minutes on modern Macs

### For Linux (NVIDIA GPU)

```bash
# Clone the repository
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp

# Build with CUDA support
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j

# Verify build succeeded
ls build/bin/llama-server  # Should exist
```

**Compilation time:** 5-10 minutes depending on hardware

### For Linux (CPU Only)

```bash
# Clone and build without GPU acceleration
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp

cmake -B build
cmake --build build --config Release -j

ls build/bin/llama-server  # Verify
```

**Note:** CPU-only mode is much slower but works without a GPU.

## Step 2: Choose and Test a Model

### Recommended Models for Coding

Choose based on your available RAM:

**For 32GB+ RAM (Best Quality):**
```bash
# Qwen3-Coder 25B (Excellent for coding, our recommendation)
MODEL="bartowski/cerebras_Qwen3-Coder-REAP-25B-A3B-GGUF:Q4_K_M"
ALIAS="Qwen3-Coder"
```

**For 16-32GB RAM (Good Balance):**
```bash
# DeepSeek-Coder V2 16B (Fast and capable)
MODEL="bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF:Q5_K_M"
ALIAS="DeepSeek-Coder"

# OR Qwen2.5-Coder 14B
MODEL="bartowski/Qwen2.5-Coder-14B-Instruct-GGUF:Q4_K_M"
ALIAS="Qwen2.5-Coder"
```

**For 16GB RAM (Minimum):**
```bash
# Qwen2.5-Coder 7B (Still quite capable)
MODEL="bartowski/Qwen2.5-Coder-7B-Instruct-GGUF:Q4_K_M"
ALIAS="Qwen2.5-7B"
```

### Understanding Model Naming

Example: `bartowski/Qwen2.5-Coder-14B-Instruct-GGUF:Q4_K_M`

- `bartowski` - HuggingFace user who quantized the model
- `Qwen2.5-Coder-14B-Instruct` - Base model name (14 billion parameters)
- `GGUF` - File format compatible with llama.cpp
- `Q4_K_M` - Quantization level (Q4 = 4-bit, medium quality)

**Quantization levels explained:**
- `Q4_K_M` - Best balance (recommended for most users)
- `Q5_K_M` - Higher quality, more RAM required
- `Q6_K` - Near-original quality, 50% more RAM
- `Q8_0` - Highest quality, double RAM

## Step 3: Start the llama.cpp Server

### Basic Server Command

```bash
cd llama.cpp

# Start server (replace MODEL and ALIAS with your choice from Step 2)
./build/bin/llama-server \
    -hf $MODEL \
    --alias "$ALIAS" \
    --port 8000 \
    --jinja \
    --ctx-size 64000
```

### Full Server Command (Optimized)

For better performance with Claude Code:

```bash
./build/bin/llama-server \
    -hf $MODEL \
    --alias "$ALIAS" \
    --port 8000 \
    --jinja \
    --kv-unified \
    --cache-type-k q8_0 --cache-type-v q8_0 \
    --flash-attn on \
    --batch-size 4096 --ubatch-size 1024 \
    --ctx-size 64000 \
    --n-gpu-layers 99  # macOS/NVIDIA only, remove for CPU
```

**Important flags explained:**

| Flag | Purpose | Required? |
|------|---------|-----------|
| `--jinja` | Enables tool calling support | **YES - CRITICAL** |
| `-hf` | Download model from HuggingFace | Recommended |
| `--alias` | Model name for Claude Code | **YES** |
| `--ctx-size 64000` | Large context for Claude's tool definitions | **YES** |
| `--port 8000` | Port to listen on | Customizable |
| `--batch-size 4096` | Processing batch size | Performance tuning |
| `--flash-attn on` | Flash attention (faster) | macOS only |

### First Run: Model Download

**First time running with `-hf` flag:**
```
Loading model from HuggingFace...
Downloading bartowski/cerebras_Qwen3-Coder-REAP-25B-A3B-GGUF:Q4_K_M
Progress: [=====>    ] 45%
```

**Download time:** 5-15 minutes depending on model size and internet speed
- 7B model: ~4GB download
- 14B model: ~8GB download
- 25B model: ~15GB download

**Models are cached** in `~/.cache/huggingface/hub/` - subsequent starts are instant.

### Verify Server is Running

Once you see:
```
llama server listening at http://127.0.0.1:8000
```

Test it:
```bash
# In a new terminal
curl http://localhost:8000/v1/models
```

Expected output:
```json
{
  "data": [
    {
      "id": "Qwen3-Coder",
      "object": "model",
      ...
    }
  ]
}
```

**✅ Success!** Your llama.cpp server is running.

**Keep this terminal window open** - the server must stay running for Claude Code to use it.

## Step 4: Configure DevAIFlow

You have three options:

### Option A: Interactive TUI (Recommended for Beginners)

```bash
# Open configuration interface
daf config edit

# Navigate using Tab key:
# 1. Go to "Model Providers" tab
# 2. Click "Add Profile" button
# 3. Select "Custom Provider"
# 4. Fill in the form:
#    - Name: llama-cpp
#    - Base URL: http://localhost:8000
#    - Auth Token: llama-cpp
#    - API Key: (leave empty or enter empty string)
#    - Model Name: Qwen3-Coder  (match your --alias from Step 3)
# 5. Click "Set as Default" (optional)
# 6. Press Ctrl+S to save
```

### Option B: Manual JSON Editing

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

**Important:**
- `base_url` must match your server port
- `model_name` must match your `--alias` flag exactly (case-sensitive)
- `api_key` can be empty string or omitted

### Option C: Environment Variables (Temporary Testing)

```bash
# Set for current terminal session only
export ANTHROPIC_BASE_URL="http://localhost:8000"
export ANTHROPIC_AUTH_TOKEN="llama-cpp"
export ANTHROPIC_API_KEY=""

# Test it
daf open PROJ-123
```

This method doesn't persist across terminal sessions.

## Step 5: Test Your Setup

### Create a Test Session

```bash
# Create a test session
daf new --name llama-test --goal "Test local llama.cpp setup"

# Claude Code should launch automatically
# If it doesn't, the session was created - you can open it manually:
# daf open llama-test
```

### First Prompt Test

In Claude Code, type: `hi`

**Expected behavior:**
1. **First time:** 30-60 second wait (normal!)
   - Claude Code sends ~35,000 tokens of tool definitions
   - llama.cpp processes them in batches
   - Progress shows in terminal: `prompt eval time = 45678.89 ms`

2. **Response appears:** You should get a greeting message

3. **Subsequent prompts:** Much faster (context already loaded)

**If you see a response, congratulations! 🎉 It's working!**

### Test File Operations

Try asking Claude Code to create a file:
```
Create a file called test.txt with the word "Hello from llama.cpp!" in it
```

**Expected:**
- Claude Code uses the Edit or Write tool
- File appears in your directory
- You see confirmation message

**If file operations work, you have full IDE integration! ✅**

## Step 6: Use with Real Projects

Now use it for actual work:

```bash
# Create session for real ticket
daf new PROJ-12345 --goal "Implement user authentication"

# Or sync existing tickets
daf sync

# Open any session - uses llama.cpp by default
daf open PROJ-12345

# Work normally in Claude Code
# All file operations, multi-file changes, tool calling work!

# Complete when done
daf complete PROJ-12345
```

## Advanced: Multiple Models

Want different models for different tasks?

### Set Up Multiple Servers

```bash
# Terminal 1: Large model for complex tasks (port 8000)
./build/bin/llama-server \
    -hf bartowski/cerebras_Qwen3-Coder-REAP-25B-A3B-GGUF:Q4_K_M \
    --alias "Qwen3-Coder" --port 8000 --jinja --ctx-size 64000

# Terminal 2: Small model for quick tasks (port 8001)
./build/bin/llama-server \
    -hf bartowski/Qwen2.5-Coder-7B-Instruct-GGUF:Q4_K_M \
    --alias "Qwen2.5-7B" --port 8001 --jinja --ctx-size 64000
```

### Configure Multiple Profiles

Edit `~/.daf-sessions/config.json`:

```json
{
  "model_provider": {
    "default_profile": "llama-large",
    "profiles": {
      "llama-large": {
        "name": "llama-large",
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

### Switch Between Models

```bash
# Use large model for complex refactoring
daf open PROJ-123 --model-profile llama-large

# Use fast model for simple bug fix
daf open PROJ-456 --model-profile llama-fast

# Sessions remember their profile choice
daf open PROJ-123  # Uses llama-large automatically
```

## Common Issues and Solutions

### Issue: "Deliberating..." Hangs Forever

**Solution 1:** Wait longer
- First prompt takes 30-60 seconds (normal!)
- Check terminal - are you seeing progress?
- `prompt eval time = 45678.89 ms` means it's working

**Solution 2:** Reduce resource usage
```bash
# Use smaller model
MODEL="bartowski/Qwen2.5-Coder-7B-Instruct-GGUF:Q4_K_M"

# OR reduce context size
--ctx-size 32000  # instead of 64000

# OR reduce batch size
--batch-size 2048 --ubatch-size 512
```

### Issue: Tool Calling Doesn't Work

**Symptoms:**
- Claude responds but doesn't create/edit files
- Gets stuck when trying to use tools

**Solution:** Add `--jinja` flag
```bash
# WRONG
./build/bin/llama-server -hf model --port 8000

# CORRECT
./build/bin/llama-server -hf model --port 8000 --jinja
```

**The `--jinja` flag is CRITICAL for Claude Code compatibility!**

### Issue: Out of Memory

**Symptoms:**
- Server crashes during model load
- System becomes unresponsive

**Solutions:**
1. Use smaller quantization:
   - Q4_K_M instead of Q5_K_M
   - Q4_K_M instead of Q6_K

2. Use smaller model:
   - 7B instead of 14B
   - 14B instead of 25B

3. Close other applications to free RAM

### Issue: Server Won't Start

**Check:**
```bash
# Port already in use?
lsof -i :8000
# If yes, either kill that process or use different port

# Model file corrupt?
rm -rf ~/.cache/huggingface/hub/models*Qwen*
# Then restart server to re-download
```

## Performance Tips

### Optimize for Your Hardware

**For Apple Silicon Macs:**
```bash
--flash-attn on \         # Use Flash Attention
--n-gpu-layers 99 \       # Offload everything to GPU
--kv-unified              # Unified KV cache
```

**For NVIDIA GPUs:**
```bash
--n-gpu-layers 99 \       # Offload all layers to GPU
--batch-size 4096 \       # Larger batches if you have VRAM
--ubatch-size 1024
```

**For CPU-Only:**
```bash
--threads 8 \             # Match your CPU core count
--batch-size 512 \        # Smaller batches
--ubatch-size 128
```

### Expected Performance

**MacBook Pro M1 Max (32GB):**
- Model: Qwen3-Coder 25B Q4_K_M
- First prompt: ~45 seconds
- Subsequent prompts: 5-10 seconds
- Quality: Excellent

**Desktop with RTX 4090 (24GB VRAM):**
- Model: DeepSeek-Coder V2 16B Q5_K_M
- First prompt: ~20 seconds
- Subsequent prompts: 2-5 seconds
- Quality: Excellent

## Cost Comparison

### Claude Opus 4.6 (Cloud)

- Cost: $15 per million tokens
- For 10M tokens/month: **$150/month**
- For 50M tokens/month: **$750/month**

### llama.cpp (Local)

- Cost: $0 (FREE)
- Initial hardware: You already have it
- Electricity: ~$0.50-2/month
- **Savings: 100%**

## Next Steps

Now that you have local models working:

1. **Experiment with models:** Try different coding models to find your favorite
2. **Create profiles:** Set up profiles for different use cases
3. **Share with team:** Document your setup for teammates
4. **Contribute back:** Report which models work best at https://github.com/itdove/devaiflow/issues

## Troubleshooting Resources

- **DevAIFlow Docs:** [Alternative Model Providers](../reference/alternative-model-providers.md)
- **llama.cpp GitHub:** https://github.com/ggml-org/llama.cpp
- **HuggingFace Models:** https://huggingface.co/models?other=gguf
- **Community Help:** https://github.com/itdove/devaiflow/issues

## Conclusion

You now have a completely free, offline AI coding assistant running on your local machine! This setup provides:

- ✅ Zero ongoing costs
- ✅ Complete data privacy
- ✅ Works offline
- ✅ Full Claude Code IDE integration
- ✅ Flexibility to try different models

Happy coding! 🎉

---

**Found this tutorial helpful?** Please star the [DevAIFlow repository](https://github.com/itdove/devaiflow) and share with others!

**Questions or issues?** Open an issue on GitHub: https://github.com/itdove/devaiflow/issues
