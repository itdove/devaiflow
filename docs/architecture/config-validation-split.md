# Configuration Validation Split - Implementation Plan

## Overview

Split the monolithic configuration validation system into separate validators and schemas for each configuration file to support future central database storage and improve modularity.

## Current Architecture

### Files
- **Single Schema**: `config.schema.json` - Validates merged configuration
- **Single Validator**: `devflow/config/validator.py` - Validates after merging all 5 files
- **Validation Timing**: After merging (loses context of which file has issues)

### Configuration Files (Current)
```
~/.daf-sessions/
├── config.json              # User preferences
├── enterprise.json          # Enterprise settings (NEW)
├── organization.json        # Organization/project settings
├── team.json                # Team settings
└── backends/
    └── jira.json           # JIRA backend configuration
```

### Problems
1. **No per-file validation**: Can't validate a file before saving to central DB
2. **Unclear ownership**: Hard to know which file has the issue
3. **Monolithic**: Adding new backend types requires modifying central validator
4. **Testing**: Can't test validators independently
5. **Error messages**: Generic, not file-specific

## Proposed Architecture

### Directory Structure
```
devflow/config/
├── schemas/                        # JSON Schema files
│   ├── __init__.py
│   ├── enterprise.schema.json     # Enterprise config schema
│   ├── organization.schema.json   # Organization config schema
│   ├── team.schema.json           # Team config schema
│   ├── user.schema.json           # User config schema (config.json)
│   └── backends/
│       ├── jira.schema.json       # JIRA backend schema
│       ├── github.schema.json     # Future: GitHub backend
│       └── gitlab.schema.json     # Future: GitLab backend
│
├── validators/                     # Python validators
│   ├── __init__.py
│   ├── base.py                    # BaseConfigValidator (shared logic)
│   ├── enterprise.py              # EnterpriseConfigValidator
│   ├── organization.py            # OrganizationConfigValidator
│   ├── team.py                    # TeamConfigValidator
│   ├── user.py                    # UserConfigValidator
│   └── backends/
│       ├── __init__.py
│       ├── base.py                # BaseBackendValidator
│       ├── jira.py                # JiraBackendValidator
│       ├── github.py              # Future: GitHubBackendValidator
│       └── gitlab.py              # Future: GitLabBackendValidator
│
├── validator.py                    # UPDATED: Orchestrator using file-specific validators
├── loader.py                       # UPDATED: Use validators during load/save
└── models.py                       # Existing Pydantic models
```

### Benefits
1. ✅ **Central DB Ready**: Validate each file independently before storage
2. ✅ **Clear Ownership**: Each validator corresponds to one config file
3. ✅ **Better Error Messages**: File-specific validation with targeted suggestions
4. ✅ **Modular**: Easy to add new backend types (GitHub, GitLab, etc.)
5. ✅ **Testing**: Each validator can be tested independently
6. ✅ **Reusable**: Validators can be used in TUI, CLI, API, etc.

## Implementation Plan

### Phase 1: Create JSON Schemas

**Files to Create:**
1. `devflow/config/schemas/enterprise.schema.json`
2. `devflow/config/schemas/organization.schema.json`
3. `devflow/config/schemas/team.schema.json`
4. `devflow/config/schemas/user.schema.json`
5. `devflow/config/schemas/backends/jira.schema.json`

**Schema Content:** Extract from existing Pydantic models using:
- `EnterpriseConfig` → `enterprise.schema.json`
- `OrganizationConfig` → `organization.schema.json`
- `TeamConfig` → `team.schema.json`
- `UserConfig` → `user.schema.json`
- `JiraBackendConfig` → `backends/jira.schema.json`

**Schema Features:**
- JSON Schema Draft 7
- Include descriptions for each field
- Mark required fields
- Define enums for constrained values
- Add examples
- Include `$schema` and `$id` metadata

**Example Schema Structure:**
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://devaiflow.dev/schemas/enterprise.schema.json",
  "title": "Enterprise Configuration",
  "description": "Enterprise-wide configuration for DevAIFlow",
  "type": "object",
  "properties": {
    "agent_backend": {
      "type": ["string", "null"],
      "enum": ["claude", "github-copilot", null],
      "description": "AI agent backend enforced by enterprise"
    },
    "backend_overrides": {
      "type": ["object", "null"],
      "description": "Override backend configuration values"
    }
  },
  "additionalProperties": false
}
```

### Phase 2: Create Base Validator Classes

**File:** `devflow/config/validators/base.py`

**Classes:**
```python
class BaseConfigValidator:
    """Base class for all configuration validators.

    Provides common validation logic:
    - JSON Schema validation
    - Placeholder detection
    - Required field checking
    - Custom validation hooks
    """

    schema_path: Path  # Path to JSON schema file
    config_file: str   # Config file name (e.g., "enterprise.json")

    def validate_dict(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate a configuration dictionary."""
        pass

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a configuration file."""
        pass

    def _check_placeholders(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Check for placeholder values (TODO:, YOUR_, example.com)."""
        pass

    def _check_required_fields(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Check for null required fields."""
        pass

    def _validate_with_schema(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate against JSON Schema."""
        pass

    def custom_validations(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Override for file-specific custom validations."""
        return []
```

### Phase 3: Create File-Specific Validators

**Files to Create:**
1. `devflow/config/validators/enterprise.py`
2. `devflow/config/validators/organization.py`
3. `devflow/config/validators/team.py`
4. `devflow/config/validators/user.py`
5. `devflow/config/validators/backends/jira.py`

**Example:** `devflow/config/validators/enterprise.py`
```python
from pathlib import Path
from typing import Any, Dict, List

from .base import BaseConfigValidator, ValidationIssue


class EnterpriseConfigValidator(BaseConfigValidator):
    """Validator for enterprise.json configuration file."""

    schema_path = Path(__file__).parent.parent / "schemas" / "enterprise.schema.json"
    config_file = "enterprise.json"

    def custom_validations(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Enterprise-specific validations."""
        issues = []

        # Validate agent_backend is a known value
        agent_backend = data.get("agent_backend")
        if agent_backend and agent_backend not in ["claude", "github-copilot"]:
            issues.append(ValidationIssue(
                file=self.config_file,
                field="agent_backend",
                issue_type="invalid_value",
                message=f"Unknown agent_backend: '{agent_backend}'",
                suggestion="Use 'claude' or 'github-copilot'",
                severity="error"
            ))

        # Validate backend_overrides structure
        backend_overrides = data.get("backend_overrides")
        if backend_overrides:
            if not isinstance(backend_overrides, dict):
                issues.append(ValidationIssue(
                    file=self.config_file,
                    field="backend_overrides",
                    issue_type="invalid_type",
                    message="backend_overrides must be an object",
                    suggestion="Use a JSON object: {\"field_mappings\": {...}}",
                    severity="error"
                ))

        return issues
```

**Example:** `devflow/config/validators/backends/jira.py`
```python
class JiraBackendValidator(BaseBackendValidator):
    """Validator for backends/jira.json configuration file."""

    schema_path = Path(__file__).parent.parent.parent / "schemas" / "backends" / "jira.schema.json"
    config_file = "backends/jira.json"

    # JIRA-specific placeholder patterns
    PLACEHOLDER_PATTERNS = [
        r"jira\.example\.com",
        r"your-jira-instance",
        r"TODO:.*jira",
    ]

    def custom_validations(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """JIRA-specific validations."""
        issues = []

        # Validate JIRA URL format
        url = data.get("url")
        if url:
            if not url.startswith("https://"):
                issues.append(ValidationIssue(
                    file=self.config_file,
                    field="url",
                    issue_type="invalid_url",
                    message="JIRA URL must use HTTPS",
                    suggestion="Change to https://...",
                    severity="error"
                ))

            # Check for common JIRA URL patterns
            if ".atlassian.net" in url or "jira" in url.lower():
                # Valid JIRA URL patterns
                pass
            else:
                issues.append(ValidationIssue(
                    file=self.config_file,
                    field="url",
                    issue_type="suspicious_url",
                    message="URL doesn't look like a JIRA instance",
                    suggestion="Verify this is your JIRA URL",
                    severity="warning"
                ))

        # Validate transitions structure
        transitions = data.get("transitions", {})
        if transitions:
            for event, config in transitions.items():
                if "to" not in config:
                    issues.append(ValidationIssue(
                        file=self.config_file,
                        field=f"transitions.{event}",
                        issue_type="missing_field",
                        message=f"Transition '{event}' missing 'to' field",
                        suggestion="Add 'to' field with target status",
                        severity="error"
                    ))

        return issues
```

### Phase 4: Update ConfigValidator Orchestrator

**File:** `devflow/config/validator.py` (UPDATE existing)

**Changes:**
```python
from .validators.enterprise import EnterpriseConfigValidator
from .validators.organization import OrganizationConfigValidator
from .validators.team import TeamConfigValidator
from .validators.user import UserConfigValidator
from .validators.backends.jira import JiraBackendValidator


class ConfigValidator:
    """Orchestrates validation across all configuration files."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir

        # Initialize file-specific validators
        self.enterprise_validator = EnterpriseConfigValidator()
        self.organization_validator = OrganizationConfigValidator()
        self.team_validator = TeamConfigValidator()
        self.user_validator = UserConfigValidator()
        self.jira_backend_validator = JiraBackendValidator()

    def validate_split_config_files(self) -> ValidationResult:
        """Validate all configuration files individually.

        Returns:
            ValidationResult with issues from all files
        """
        all_issues = []

        # Validate enterprise.json
        enterprise_file = self.config_dir / "enterprise.json"
        if enterprise_file.exists():
            result = self.enterprise_validator.validate_file(enterprise_file)
            all_issues.extend(result.issues)

        # Validate organization.json
        org_file = self.config_dir / "organization.json"
        if org_file.exists():
            result = self.organization_validator.validate_file(org_file)
            all_issues.extend(result.issues)

        # Validate team.json
        team_file = self.config_dir / "team.json"
        if team_file.exists():
            result = self.team_validator.validate_file(team_file)
            all_issues.extend(result.issues)

        # Validate config.json (user)
        user_file = self.config_dir / "config.json"
        if user_file.exists():
            result = self.user_validator.validate_file(user_file)
            all_issues.extend(result.issues)

        # Validate backends/jira.json
        jira_file = self.config_dir / "backends" / "jira.json"
        if jira_file.exists():
            result = self.jira_backend_validator.validate_file(jira_file)
            all_issues.extend(result.issues)

        return ValidationResult(
            is_complete=len(all_issues) == 0,
            issues=all_issues
        )

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a single configuration file.

        Useful for central DB: validate before saving.
        """
        file_name = file_path.name

        if file_name == "enterprise.json":
            return self.enterprise_validator.validate_file(file_path)
        elif file_name == "organization.json":
            return self.organization_validator.validate_file(file_path)
        elif file_name == "team.json":
            return self.team_validator.validate_file(file_path)
        elif file_name == "config.json":
            return self.user_validator.validate_file(file_path)
        elif file_path.parent.name == "backends" and file_name == "jira.json":
            return self.jira_backend_validator.validate_file(file_path)
        else:
            raise ValueError(f"Unknown config file: {file_path}")
```

### Phase 5: Update ConfigLoader

**File:** `devflow/config/loader.py` (UPDATE existing)

**Changes:**
```python
def _load_enterprise_config(self) -> Optional["EnterpriseConfig"]:
    """Load enterprise configuration from enterprise.json."""
    from .models import EnterpriseConfig
    from .validator import ConfigValidator

    enterprise_file = self.config_dir / "enterprise.json"

    if not enterprise_file.exists():
        return EnterpriseConfig()

    try:
        with open(enterprise_file, "r") as f:
            data = json.load(f)

        # Validate file before loading
        validator = ConfigValidator(self.config_dir)
        result = validator.enterprise_validator.validate_file(enterprise_file)

        if result.issues:
            # Show validation warnings (non-fatal)
            self._print_validation_warnings(result, "enterprise.json")

        return EnterpriseConfig(**data)
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Failed to load enterprise config: {e}")
        console.print("[dim]  Using default enterprise configuration[/dim]")
        return EnterpriseConfig()

def _save_enterprise_config(self, enterprise_config: "EnterpriseConfig") -> None:
    """Save enterprise configuration to enterprise.json."""
    from .validator import ConfigValidator

    enterprise_file = self.config_dir / "enterprise.json"

    # Convert to dict
    data = enterprise_config.model_dump(by_alias=True, exclude_none=False)

    # Validate before saving
    validator = ConfigValidator(self.config_dir)
    result = validator.enterprise_validator.validate_dict(data)

    if result.get_issues_by_severity("error"):
        # Fatal errors - don't save
        raise ValueError(f"Cannot save invalid enterprise.json:\n{result}")

    # Save to file
    with open(enterprise_file, "w") as f:
        json.dump(data, f, indent=2)

    # Show warnings (non-fatal)
    if result.get_issues_by_severity("warning"):
        self._print_validation_warnings(result, "enterprise.json")
```

### Phase 6: Testing

**Test Files to Create:**
```
tests/config/validators/
├── __init__.py
├── test_base_validator.py
├── test_enterprise_validator.py
├── test_organization_validator.py
├── test_team_validator.py
├── test_user_validator.py
└── backends/
    ├── __init__.py
    └── test_jira_validator.py
```

**Test Coverage:**
- JSON Schema validation
- Placeholder detection
- Required field validation
- Custom validation rules
- Error message quality
- File-specific validations
- Integration with ConfigLoader

**Example Test:**
```python
def test_enterprise_validator_agent_backend():
    """Test that invalid agent_backend is caught."""
    validator = EnterpriseConfigValidator()

    data = {
        "agent_backend": "invalid-backend",
        "backend_overrides": None
    }

    result = validator.validate_dict(data)

    assert not result.is_complete
    assert len(result.issues) == 1
    assert result.issues[0].field == "agent_backend"
    assert result.issues[0].issue_type == "invalid_value"
    assert "claude" in result.issues[0].suggestion
```

### Phase 7: Documentation Updates

**Files to Update:**
- `docs/06-configuration.md` - Document validation per file
- `docs/11-troubleshooting.md` - Update validation error examples
- `README.md` - Mention validation improvements
- `CHANGELOG.md` - Add entry for validation split

**New Documentation:**
- `docs/architecture/validation.md` - Validation architecture
- `docs/schemas/README.md` - Schema documentation

## Migration Strategy

### Backward Compatibility

**No breaking changes:**
1. Old `config.schema.json` remains for backward compatibility
2. Old `ConfigValidator.validate_merged_config()` still works
3. New methods added alongside old ones
4. Deprecation warnings for old methods

**Migration Path:**
```python
# OLD (still works, deprecated)
validator = ConfigValidator(config_dir)
result = validator.validate_merged_config(config)

# NEW (recommended)
validator = ConfigValidator(config_dir)
result = validator.validate_split_config_files()
```

### Deprecation Timeline

**Version 1.x** (Current):
- Add new validators alongside old
- Show deprecation warnings for old methods
- Update internal code to use new validators

**Version 2.0** (Future):
- Remove old `validate_merged_config()` method
- Remove old `config.schema.json`
- Only file-specific validation remains

## Central Database Integration

### Use Case: Save to Central DB

```python
def save_enterprise_config_to_db(enterprise_config: EnterpriseConfig):
    """Save enterprise config to central database."""
    from devflow.config.validators.enterprise import EnterpriseConfigValidator

    # Validate before saving
    validator = EnterpriseConfigValidator()
    data = enterprise_config.model_dump(by_alias=True, exclude_none=False)
    result = validator.validate_dict(data)

    if result.get_issues_by_severity("error"):
        raise ValueError(f"Invalid enterprise config: {result}")

    # Save to database
    db.enterprise_configs.insert(data)
```

### Use Case: Load from Central DB

```python
def load_enterprise_config_from_db() -> EnterpriseConfig:
    """Load enterprise config from central database."""
    from devflow.config.validators.enterprise import EnterpriseConfigValidator

    # Load from database
    data = db.enterprise_configs.find_one()

    # Validate after loading (in case DB data is corrupted)
    validator = EnterpriseConfigValidator()
    result = validator.validate_dict(data)

    if result.get_issues_by_severity("error"):
        # Log error, use defaults
        logger.error(f"Invalid enterprise config from DB: {result}")
        return EnterpriseConfig()

    return EnterpriseConfig(**data)
```

## Implementation Checklist

### Phase 1: Schemas
- [ ] Create `devflow/config/schemas/` directory
- [ ] Create `enterprise.schema.json`
- [ ] Create `organization.schema.json`
- [ ] Create `team.schema.json`
- [ ] Create `user.schema.json`
- [ ] Create `backends/jira.schema.json`

### Phase 2: Base Validators
- [ ] Create `devflow/config/validators/` directory
- [ ] Create `base.py` with `BaseConfigValidator`
- [ ] Create `backends/base.py` with `BaseBackendValidator`
- [ ] Add JSON Schema validation using `jsonschema` library
- [ ] Add placeholder detection logic
- [ ] Add required field checking

### Phase 3: File-Specific Validators
- [ ] Create `enterprise.py` with `EnterpriseConfigValidator`
- [ ] Create `organization.py` with `OrganizationConfigValidator`
- [ ] Create `team.py` with `TeamConfigValidator`
- [ ] Create `user.py` with `UserConfigValidator`
- [ ] Create `backends/jira.py` with `JiraBackendValidator`

### Phase 4: Update ConfigValidator
- [ ] Add file-specific validator instances
- [ ] Add `validate_split_config_files()` method
- [ ] Add `validate_file()` method for single file validation
- [ ] Keep old `validate_merged_config()` with deprecation warning

### Phase 5: Update ConfigLoader
- [ ] Update all `_load_*_config()` methods to validate
- [ ] Update all `_save_*_config()` methods to validate before save
- [ ] Add validation warning display

### Phase 6: Testing
- [ ] Create test directory structure
- [ ] Write tests for base validator
- [ ] Write tests for each file-specific validator
- [ ] Write integration tests with ConfigLoader
- [ ] Achieve 90%+ test coverage

### Phase 7: Documentation
- [ ] Update configuration documentation
- [ ] Update troubleshooting guide
- [ ] Create validation architecture doc
- [ ] Add schema documentation

### Phase 8: Migration
- [ ] Add deprecation warnings to old methods
- [ ] Update all internal code to use new validators
- [ ] Update CLI commands to show file-specific errors
- [ ] Test backward compatibility

## Success Criteria

- ✅ Each config file has its own JSON schema
- ✅ Each config file has its own validator class
- ✅ Validators can be used independently (for central DB)
- ✅ Error messages specify which file has the issue
- ✅ All tests pass with 90%+ coverage
- ✅ Documentation is complete
- ✅ Backward compatibility maintained
- ✅ No breaking changes for users

## Timeline Estimate

- **Phase 1 (Schemas)**: 2-3 days
- **Phase 2 (Base Validators)**: 2-3 days
- **Phase 3 (File Validators)**: 3-4 days
- **Phase 4 (ConfigValidator)**: 1-2 days
- **Phase 5 (ConfigLoader)**: 2-3 days
- **Phase 6 (Testing)**: 3-4 days
- **Phase 7 (Documentation)**: 2-3 days
- **Phase 8 (Migration)**: 1-2 days

**Total**: 16-24 days (3-4 weeks)

## Dependencies

- `jsonschema` library (add to requirements.txt)
- Python 3.8+ (for type hints)
- Existing Pydantic models
- Existing configuration structure

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing code | High | Maintain backward compatibility, deprecation warnings |
| Complex validation logic | Medium | Start simple, add complexity incrementally |
| Performance overhead | Low | Cache validators, optimize schema validation |
| Schema maintenance | Medium | Generate schemas from Pydantic models where possible |

## Future Enhancements

1. **Auto-generate schemas** from Pydantic models using `pydantic-to-json-schema`
2. **IDE integration** with JSON Schema for auto-complete in config files
3. **Web UI** for configuration with live validation
4. **Migration tool** to help users fix validation errors
5. **Backend plugins** for GitHub, GitLab, etc. with their own validators
