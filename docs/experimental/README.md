# Experimental Features

This directory contains documentation for experimental DevAIFlow features that are under active development.

## What are Experimental Features?

Experimental features are:
- **Under Active Development**: May have incomplete functionality or rough edges
- **Subject to Change**: APIs, commands, and behavior may change in future releases
- **Opt-In Only**: Must be explicitly enabled to use
- **Not Production-Ready**: Use with caution in production environments

## Enabling Experimental Features

### Option 1: Command-Line Flag

Use the `-e` or `--experimental` flag **before** the command:

```bash
# Short form (recommended)
daf -e feature list
daf -e feature create my-feature --parent "PROJ-100"

# Long form
daf --experimental feature list
daf --experimental feature create my-feature --parent "PROJ-100"
```

**Important:** The flag must come **before** the command name:
```bash
# ✅ Correct
daf -e feature list

# ❌ Incorrect - will not work
daf feature list -e
daf feature -e list
```

### Option 2: Environment Variable

Set the environment variable for persistent access:

```bash
# Bash/Zsh
export DEVAIFLOW_EXPERIMENTAL=1

# Fish
set -x DEVAIFLOW_EXPERIMENTAL 1

# Add to your shell profile for permanent access
echo 'export DEVAIFLOW_EXPERIMENTAL=1' >> ~/.bashrc  # or ~/.zshrc
```

Then use commands normally (no flag needed):

```bash
daf feature list
daf feature create my-feature --sessions "s1,s2,s3"
```

## Current Experimental Features

### Feature Orchestration

Multi-session workflow orchestration with automated verification.

**Documentation**: [feature-orchestration.md](./feature-orchestration.md)

**Status**: Active development, breaking changes possible

**Commands**:
- `daf feature create` - Create feature orchestration
- `daf feature list` - List features
- `daf feature status` - Show feature details
- `daf feature sync` - Add new children from parent (for tickets updated after creation)
- `daf feature run` - Execute feature workflow
- `daf feature resume` - Resume paused feature
- `daf feature reorder` - Change session order
- `daf feature delete` - Delete feature

**Key Capabilities**:
- Auto-discover child tickets from parent (JIRA/GitHub/GitLab)
- Automated verification between sessions
- Dependency-based ordering
- Integrated PR creation for entire feature

## Graduation to Stable

Experimental features will graduate to stable status when they meet these criteria:

1. **Stability**: No critical bugs for 2+ releases
2. **Documentation**: Comprehensive docs and examples
3. **Testing**: Good test coverage (unit + integration)
4. **User Feedback**: Positive feedback from early adopters
5. **API Stability**: No breaking changes planned

Graduated features will:
- Appear in standard `daf --help` output
- No longer require `--experimental` flag
- Follow semantic versioning for compatibility

## Deprecation Policy

If an experimental feature is deprecated:
1. Warning added to documentation
2. Deprecation notice shown on use (1 release)
3. Feature removed (next major release)

## Reporting Issues

Found a bug or have feedback? Please report at:

**https://github.com/itdove/devaiflow/issues**

Include:
- `[experimental]` in the issue title
- Which experimental feature
- Steps to reproduce
- DevAIFlow version (`daf --version`)

## See Also

- [Contributing Guide](../../CONTRIBUTING.md)
- [Architecture Documentation](../developer/)
- [Command Reference](../reference/commands.md)
