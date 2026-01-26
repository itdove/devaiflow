# Issue Tracker Module

This module provides an interface abstraction layer for issue tracking systems, allowing DevAIFlow to support multiple backends (JIRA, GitHub Issues, GitLab Issues, etc.) through a common interface.

## Quick Start

### Using the Factory (Recommended)

```python
from devflow.issue_tracker.factory import create_issue_tracker_client

# Create default backend (JIRA)
client = create_issue_tracker_client()

# Create specific backend
client = create_issue_tracker_client("jira")
client = create_issue_tracker_client("mock")  # For testing
```

### Direct Instantiation (Backward Compatible)

```python
from devflow.jira.client import JiraClient

# Direct instantiation still works
client = JiraClient()
```

## Architecture

### Interface (`interface.py`)

Abstract base class defining the contract for all issue tracker backends.

**Key methods**:
- `get_ticket()`, `get_ticket_detailed()`, `list_tickets()`
- `create_bug()`, `create_story()`, `create_task()`, `create_epic()`, `create_spike()`
- `update_issue()`, `update_ticket_field()`, `transition_ticket()`
- `add_comment()`, `attach_file()`
- `link_issues()`, `get_child_issues()`, `get_issue_link_types()`
- `get_ticket_pr_links()`

### Factory (`factory.py`)

Creates appropriate backend instance based on configuration.

```python
def create_issue_tracker_client(
    backend: Optional[str] = None,
    timeout: int = 30
) -> IssueTrackerClient
```

### Mock Client (`mock_client.py`)

In-memory implementation for testing without external dependencies.

**Features**:
- No network calls
- Sequential ticket numbering
- Basic filtering
- Useful for unit tests

## Configuration

**File**: `$DEVAIFLOW_HOME/config.json`

```json
{
  "issue_tracker_backend": "jira"
}
```

**Supported backends**:
- `"jira"` - JIRA REST API (default)
- `"mock"` - In-memory mock (for testing)
- `"github"` - GitHub Issues (not yet implemented)
- `"gitlab"` - GitLab Issues (not yet implemented)

## Usage Examples

### Create and Get Ticket

```python
from devflow.issue_tracker.factory import create_issue_tracker_client

client = create_issue_tracker_client()

# Create a bug
key = client.create_bug(
    summary="Critical bug in API",
    description="API returns 500 for valid requests",
    project="PROJ",
    priority="Major",
    affected_version="1.0.0"
)

# Get ticket details
ticket = client.get_ticket(key)
print(f"Created: {ticket['key']} - {ticket['summary']}")
```

### List and Filter Tickets

```python
# List all tickets in project
tickets = client.list_tickets(project="PROJ")

# Filter by status
tickets = client.list_tickets(
    project="PROJ",
    status=["In Progress", "New"],
    assignee="currentUser()"
)

# Filter by type
tickets = client.list_tickets(
    project="PROJ",
    issue_type=["Bug", "Story"]
)
```

### Update Ticket

```python
# Update single field
client.update_ticket_field(key, "priority", "Critical")

# Transition status
client.transition_ticket(key, "In Progress")

# Add comment
client.add_comment(key, "Fixed in commit abc123")

# Attach file
client.attach_file(key, "/path/to/file.txt")
```

### Link Issues

```python
# Get available link types
link_types = client.get_issue_link_types()

# Link two issues
client.link_issues(
    issue_key="PROJ-123",
    link_type="blocks",
    linked_issue_key="PROJ-456",
    comment="Blocking deployment"
)
```

## Error Handling

All backends use exception-based error handling:

```python
from devflow.jira.exceptions import (
    JiraAuthError,
    JiraNotFoundError,
    JiraValidationError,
    JiraApiError,
    JiraConnectionError,
)

try:
    ticket = client.get_ticket("PROJ-12345")
except JiraNotFoundError as e:
    print(f"Ticket not found: {e.resource_id}")
except JiraAuthError as e:
    print(f"Authentication failed: {e}")
except JiraApiError as e:
    print(f"API error: {e.status_code} - {e.error_messages}")
```

## Testing with Mock Client

```python
from devflow.issue_tracker.factory import create_issue_tracker_client

# Create mock client
client = create_issue_tracker_client("mock")

# Use exactly like real client
key = client.create_bug(
    summary="Test bug",
    description="Test description",
    project="TEST"
)

# No external dependencies or network calls
ticket = client.get_ticket(key)
assert ticket["key"] == "TEST-1"
```

## Adding New Backends

To add support for a new issue tracking system:

### 1. Implement the Interface

```python
from devflow.issue_tracker.interface import IssueTrackerClient

class MyTrackerClient(IssueTrackerClient):
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        # Initialize your API client

    def get_ticket(self, issue_key: str, field_mappings=None):
        # Implement using your API
        pass

    # Implement all other abstract methods...
```

### 2. Register in Factory

Update `factory.py`:

```python
elif backend == "mytracker":
    from devflow.mytracker.client import MyTrackerClient
    return MyTrackerClient(timeout=timeout)
```

### 3. Add Tests

Create comprehensive tests similar to `tests/test_issue_tracker_interface.py`.

### 4. Update Configuration

Users can then select your backend:

```json
{
  "issue_tracker_backend": "mytracker"
}
```

## Files

- `interface.py` - Abstract base class (IssueTrackerClient)
- `factory.py` - Factory for creating backend instances
- `mock_client.py` - Mock implementation for testing
- `__init__.py` - Public exports

## Testing

**Run interface tests**:
```bash
pytest tests/test_issue_tracker_interface.py -v
```

**Run all JIRA tests**:
```bash
pytest tests/ -k "jira" -v
```

## Documentation

See [docs/issue-tracker-architecture.md](../../docs/issue-tracker-architecture.md) for detailed architecture documentation.

## JIRA Ticket

Implemented in: **PROJ-63197**
