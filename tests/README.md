# Testing DevAIFlow

This directory contains tests for the `daf` tool with JIRA mocking capabilities.

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_jira_mock.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=devflow --cov-report=html
```

## JIRA Mocking

Tests use the `mock_jira_cli` fixture to intercept JIRA CLI subprocess calls and return fake responses. This allows testing JIRA-dependent functionality without requiring:
- Actual JIRA CLI installation
- Network access
- Valid JIRA credentials
- Real JIRA tickets

### How It Works

The `mock_jira_cli` fixture (defined in `conftest.py`) monkey-patches `subprocess.run()` to intercept calls to the `jira` command:

```python
def test_example(mock_jira_cli):
    # Configure a mock JIRA ticket
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
        }
    })

    # Now any code that calls 'jira issue view PROJ-12345'
    # will get the mock data instead of hitting real JIRA
```

### Supported JIRA Commands

The mock supports these JIRA CLI commands:

- `jira issue view <KEY>` - View ticket details
- `jira issue comment <KEY> <TEXT>` - Add comment
- `jira issue attach <KEY> <FILE>` - Attach file
- `jira issue move <KEY> <STATUS>` - Transition status
- `jira issue list` - List tickets

### MockJiraCLI API

**`set_ticket(key, data)`** - Configure a mock ticket:
```python
mock_jira_cli.set_ticket("PROJ-12345", {
    "key": "PROJ-12345",
    "fields": {
        "summary": "Implement backup feature",
        "status": {"name": "New"},
        "issuetype": {"name": "Story"},
        "customfield_12310243": 5,  # Story points
    }
})
```

**`fail_next_command(pattern)`** - Make a command fail:
```python
mock_jira_cli.fail_next_command("issue view")
# Next 'jira issue view' call will return error
```

**Verification methods:**
- `mock_jira_cli.comments` - Dict of comments added per ticket
- `mock_jira_cli.attachments` - Dict of attachments per ticket
- `mock_jira_cli.transitions` - Dict of status transitions

### Isolated Test Environment

The `temp_cs_home` fixture creates a temporary `.daf-sessions` directory for each test, ensuring tests don't modify your actual session data:

```python
def test_example(temp_cs_home):
    # temp_cs_home is a Path to temporary directory
    # All daf commands will use this directory instead of ~/.daf-sessions
```

## Example Tests

See these files for examples:

- **`test_jira_mock.py`** - Basic JIRA mocking examples
- **`test_new_command_with_jira.py`** - Integration tests for `daf new` with JIRA validation

## Writing New Tests

### Testing JIRA Integration

```python
def test_your_feature(mock_jira_cli, temp_cs_home):
    # 1. Setup mock JIRA tickets
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Test"}
    })

    # 2. Run daf command
    from click.testing import CliRunner
    from devflow.cli.main import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["new", "--name", "test", "--jira", "PROJ-12345"])

    # 3. Verify results
    assert result.exit_code == 0
    assert "PROJ-12345" in result.output

    # 4. Verify JIRA interactions
    assert "PROJ-12345" in mock_jira_cli.comments
```

### Testing JIRA Failures

```python
def test_jira_failure(mock_jira_cli):
    # Make JIRA command fail
    mock_jira_cli.fail_next_command("issue view")

    # Your code should handle the failure gracefully
    result = subprocess.run(
        ["jira", "issue", "view", "PROJ-12345"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 1
```

### Testing Without JIRA

```python
def test_no_jira_needed(temp_cs_home):
    # Test features that don't require JIRA
    runner = CliRunner()
    result = runner.invoke(cli, ["new", "--name", "test", "--goal", "Testing"])

    assert result.exit_code == 0
```

## Dependencies

Required for testing:

```bash
pip install pytest pytest-cov
```

Optional for development:

```bash
pip install pytest-watch  # Auto-run tests on file changes
```

## Continuous Testing

Watch for changes and auto-run tests:

```bash
# Install pytest-watch
pip install pytest-watch

# Run in watch mode
ptw
```
