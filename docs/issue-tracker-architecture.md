# Issue Tracker Architecture

## Overview

DevAIFlow uses an interface-based architecture for issue tracking system integration. This allows the tool to support multiple backends (JIRA, GitHub Issues, GitLab Issues, etc.) through a common interface.

## Architecture Pattern

The issue tracker architecture follows the same pattern as the storage layer (`devflow/storage/`):

```
devflow/issue_tracker/
├── interface.py         # Abstract base class (IssueTrackerClient)
├── factory.py          # Factory for creating backend instances
├── mock_client.py      # Mock implementation for testing
└── __init__.py         # Public exports

devflow/jira/
├── client.py           # JIRA implementation (JiraClient)
├── exceptions.py       # JIRA-specific exceptions
├── field_mapper.py     # Field mapping helpers
└── ...                 # Other JIRA-specific modules
```

## Components

### 1. IssueTrackerClient Interface

**Location**: `devflow/issue_tracker/interface.py`

Abstract base class defining the contract that all issue tracker backends must implement.

**Key Methods**:
- Ticket operations: `get_ticket()`, `get_ticket_detailed()`, `list_tickets()`
- Ticket creation: `create_bug()`, `create_story()`, `create_task()`, `create_epic()`, `create_spike()`
- Ticket updates: `update_issue()`, `update_ticket_field()`, `transition_ticket()`
- Comments and attachments: `add_comment()`, `attach_file()`
- Links and relationships: `link_issues()`, `get_child_issues()`, `get_issue_link_types()`
- PR/MR tracking: `get_ticket_pr_links()`

All methods follow exception-based error handling using exceptions from `devflow.jira.exceptions`.

### 2. Factory Pattern

**Location**: `devflow/issue_tracker/factory.py`

Provides a factory function to create the appropriate backend based on configuration.

**Usage**:
```python
from devflow.issue_tracker.factory import create_issue_tracker_client

# Create default backend (JIRA)
client = create_issue_tracker_client()

# Create specific backend
client = create_issue_tracker_client("jira")
client = create_issue_tracker_client("mock")

# Future backends
client = create_issue_tracker_client("github")  # NotImplementedError
client = create_issue_tracker_client("gitlab")  # NotImplementedError
```

**Configuration**:
The factory reads the backend from `config.issue_tracker_backend` field. Defaults to "jira" for backward compatibility.

### 3. JIRA Implementation

**Location**: `devflow/jira/client.py`

The JIRA backend implements `IssueTrackerClient` interface and provides JIRA-specific functionality via the JIRA REST API.

**Key Features**:
- Exception-based error handling
- Field mapping and custom field discovery
- JIRA-specific transitions and workflows
- Comment visibility controls
- PR/MR link tracking

**Example**:
```python
from devflow.jira.client import JiraClient

# Direct instantiation (backward compatible)
client = JiraClient(timeout=30)

# Via factory (preferred for new code)
from devflow.issue_tracker.factory import create_issue_tracker_client
client = create_issue_tracker_client("jira")
```

### 4. Mock Implementation

**Location**: `devflow/issue_tracker/mock_client.py`

In-memory mock implementation for testing without external services.

**Features**:
- No external dependencies
- Sequential ticket numbering
- Basic filtering support
- Useful for unit tests

**Example**:
```python
from devflow.issue_tracker.factory import create_issue_tracker_client

# Create mock client
client = create_issue_tracker_client("mock")

# Use exactly like real client
key = client.create_bug(
    summary="Test bug",
    description="Description",
    project="TEST"
)
ticket = client.get_ticket(key)
```

## Configuration

**File**: `~/.daf-sessions/config.json`

```json
{
  "issue_tracker_backend": "jira"
}
```

**Default**: `"jira"` (for backward compatibility)

**Supported values**:
- `"jira"` - JIRA REST API backend
- `"mock"` - Mock in-memory backend (for testing)
- `"github"` - GitHub Issues (not yet implemented)
- `"gitlab"` - GitLab Issues (not yet implemented)

## Backward Compatibility

The interface layer is fully backward compatible:

1. **Direct JiraClient import still works**:
   ```python
   from devflow.jira.client import JiraClient
   client = JiraClient()
   ```

2. **All existing code continues to function** without changes

3. **Configuration defaults to JIRA** if not specified

4. **No breaking changes** to existing CLI commands or workflows

## Adding New Backends

To add support for a new issue tracking system (e.g., GitHub Issues):

### 1. Create Implementation

Create `devflow/github/issues_client.py`:

```python
from devflow.issue_tracker.interface import IssueTrackerClient
from devflow.jira.exceptions import (
    JiraApiError,
    JiraAuthError,
    JiraNotFoundError,
)

class GitHubIssuesClient(IssueTrackerClient):
    """GitHub Issues implementation of IssueTrackerClient."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        # Initialize GitHub API client

    def get_ticket(self, issue_key: str, field_mappings=None) -> Dict:
        # Implement using GitHub API
        pass

    # Implement all other abstract methods...
```

### 2. Register in Factory

Update `devflow/issue_tracker/factory.py`:

```python
def create_issue_tracker_client(backend: Optional[str] = None, timeout: int = 30):
    # ... existing code ...

    elif backend == "github":
        from devflow.github.issues_client import GitHubIssuesClient
        return GitHubIssuesClient(timeout=timeout)
```

### 3. Update Configuration

Users can then select the backend:

```json
{
  "issue_tracker_backend": "github"
}
```

### 4. Implementation Guidelines

- **Follow the interface contract**: Implement all abstract methods
- **Use standard exceptions**: Raise `JiraAuthError`, `JiraApiError`, `JiraNotFoundError`, etc.
- **Match return formats**: Return data in the standardized format defined in interface docstrings
- **Handle errors properly**: Don't swallow exceptions, let them propagate
- **Add tests**: Create comprehensive tests similar to `tests/test_issue_tracker_interface.py`

## Exception Handling

All backends must use the exception hierarchy from `devflow.jira.exceptions`:

- `JiraError` - Base exception for all errors
- `JiraAuthError` - Authentication failures (401/403)
- `JiraApiError` - General API errors
- `JiraNotFoundError` - Resource not found (404)
- `JiraValidationError` - Validation errors (400 with field errors)
- `JiraConnectionError` - Network/connection failures

**Note**: Despite the name "Jira", these exceptions are used for all issue tracker backends for consistency.

## Testing

### Unit Tests

Test file: `tests/test_issue_tracker_interface.py`

**Coverage**:
- Factory creation for all backends
- Mock client functionality
- Interface compliance verification
- Error handling

**Run tests**:
```bash
pytest tests/test_issue_tracker_interface.py -v
```

### Integration Tests

All existing JIRA integration tests continue to work:

```bash
pytest tests/ -k "jira" -v
```

## Benefits

1. **Extensibility**: Easy to add new backends (GitHub, GitLab, Linear, etc.)
2. **Team flexibility**: Different teams can use different issue trackers
3. **Testability**: Mock implementation for fast, isolated tests
4. **Decoupling**: Commands depend on interface, not concrete implementation
5. **Future-proof**: Architecture ready for additional backends
6. **Backward compatible**: Existing code continues to work

## Future Enhancements

Potential future backends:

- **GitHub Issues**: Use GitHub GraphQL API
- **GitLab Issues**: Use GitLab REST API
- **Linear**: Use Linear GraphQL API
- **Asana**: Use Asana REST API
- **Azure DevOps**: Use Azure DevOps REST API
- **Custom/Self-hosted**: Plugin system for custom backends

## Related Documentation

- Interface definition: `devflow/issue_tracker/interface.py`
- Factory implementation: `devflow/issue_tracker/factory.py`
- JIRA client: `devflow/jira/client.py`
- Exception hierarchy: `devflow/jira/exceptions.py`
- Configuration: `docs/06-configuration.md`
- Storage backend pattern: `devflow/storage/base.py` (similar architecture)

## JIRA Ticket

This architecture was implemented in: **PROJ-63197**
