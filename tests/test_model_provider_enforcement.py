"""Tests for enterprise model provider enforcement.

Tests Story 4 (itdove/devaiflow#248): Enterprise Model Provider Enforcement
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import pytest

from devflow.config.loader import ConfigLoader
from devflow.config.models import (
    Config,
    EnterpriseConfig,
    TeamConfig,
    UserConfig,
    OrganizationConfig,
    JiraConfig,
    RepoConfig,
    ModelProviderConfig,
    ModelProviderProfile,
)


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory for testing."""
    config_dir = tmp_path / ".daf-sessions"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def enterprise_profile():
    """Enterprise-enforced Vertex AI profile with cost tracking."""
    return ModelProviderProfile(
        name="Vertex AI Production",
        use_vertex=True,
        vertex_project_id="enterprise-gcp-project",
        vertex_region="us-east5",
        cost_per_million_input_tokens=3.00,
        cost_per_million_output_tokens=15.00,
        monthly_budget_usd=5000.00,
        cost_center="ENG-PLATFORM",
    )


@pytest.fixture
def team_profile():
    """Team-level llama.cpp profile."""
    return ModelProviderProfile(
        name="Team llama.cpp Server",
        base_url="http://llama-cpp.internal:8000",
        auth_token="llama-cpp",
        api_key="",
        model_name="Qwen3-Coder",
        cost_per_million_input_tokens=0.0,
        cost_per_million_output_tokens=0.0,
        cost_center="ENG-BACKEND-TEAM",
    )


@pytest.fixture
def user_profile():
    """User's personal Anthropic API profile."""
    return ModelProviderProfile(
        name="My Anthropic API",
        api_key="sk-ant-test-key",
    )


@pytest.fixture
def organization_profile():
    """Organization-level Vertex AI profile for project-specific budget."""
    return ModelProviderProfile(
        name="AAP Project Vertex AI",
        use_vertex=True,
        vertex_project_id="aap-gcp-project",
        vertex_region="us-east5",
        cost_per_million_input_tokens=3.00,
        cost_per_million_output_tokens=15.00,
        monthly_budget_usd=2000.00,
        cost_center="ENG-AAP-PROJECT",
    )


class TestConfigurationHierarchy:
    """Test model_provider configuration hierarchy (Enterprise > Organization > Team > User)."""

    def test_enterprise_overrides_team_and_user(self, temp_config_dir, enterprise_profile, team_profile, user_profile):
        """Test that enterprise config takes precedence over team and user configs."""
        # Create enterprise config
        enterprise_config = EnterpriseConfig(
            model_provider=ModelProviderConfig(
                default_profile="vertex-prod",
                profiles={"vertex-prod": enterprise_profile}
            )
        )
        with open(temp_config_dir / "enterprise.json", "w") as f:
            json.dump(enterprise_config.model_dump(), f)

        # Create team config (should be ignored)
        team_config = TeamConfig(
            model_provider=ModelProviderConfig(
                default_profile="llama-cpp",
                profiles={"llama-cpp": team_profile}
            )
        )
        with open(temp_config_dir / "team.json", "w") as f:
            json.dump(team_config.model_dump(), f)

        # Create user config (should be ignored)
        user_config = UserConfig(
            repos=RepoConfig(),
            model_provider=ModelProviderConfig(
                default_profile="anthropic",
                profiles={"anthropic": user_profile}
            )
        )
        with open(temp_config_dir / "config.json", "w") as f:
            json.dump(user_config.model_dump(), f)

        # Create minimal backend config
        backends_dir = temp_config_dir / "backends"
        backends_dir.mkdir()
        with open(backends_dir / "jira.json", "w") as f:
            json.dump({"url": "https://jira.example.com"}, f)

        # Load merged config
        loader = ConfigLoader(config_dir=temp_config_dir)
        config = loader.load_config()

        # Enterprise config should win
        assert config.model_provider.default_profile == "vertex-prod"
        assert "vertex-prod" in config.model_provider.profiles
        assert config.model_provider.profiles["vertex-prod"].name == "Vertex AI Production"

    def test_organization_overrides_team_and_user_when_no_enterprise(self, temp_config_dir, organization_profile, team_profile, user_profile):
        """Test that organization config takes precedence over team and user when enterprise doesn't enforce."""
        # Create organization config
        organization_config = OrganizationConfig(
            jira_project="AAP",
            model_provider=ModelProviderConfig(
                default_profile="aap-vertex",
                profiles={"aap-vertex": organization_profile}
            )
        )
        with open(temp_config_dir / "organization.json", "w") as f:
            json.dump(organization_config.model_dump(), f)

        # Create team config (should be ignored)
        team_config = TeamConfig(
            model_provider=ModelProviderConfig(
                default_profile="llama-cpp",
                profiles={"llama-cpp": team_profile}
            )
        )
        with open(temp_config_dir / "team.json", "w") as f:
            json.dump(team_config.model_dump(), f)

        # Create user config (should be ignored)
        user_config = UserConfig(
            repos=RepoConfig(),
            model_provider=ModelProviderConfig(
                default_profile="anthropic",
                profiles={"anthropic": user_profile}
            )
        )
        with open(temp_config_dir / "config.json", "w") as f:
            json.dump(user_config.model_dump(), f)

        # Create minimal backend config
        backends_dir = temp_config_dir / "backends"
        backends_dir.mkdir()
        with open(backends_dir / "jira.json", "w") as f:
            json.dump({"url": "https://jira.example.com"}, f)

        # Load merged config
        loader = ConfigLoader(config_dir=temp_config_dir)
        config = loader.load_config()

        # Organization config should win
        assert config.model_provider.default_profile == "aap-vertex"
        assert "aap-vertex" in config.model_provider.profiles
        assert config.model_provider.profiles["aap-vertex"].name == "AAP Project Vertex AI"

    def test_team_overrides_user_when_no_enterprise(self, temp_config_dir, team_profile, user_profile):
        """Test that team config takes precedence over user when enterprise doesn't enforce."""
        # Create team config
        team_config = TeamConfig(
            model_provider=ModelProviderConfig(
                default_profile="llama-cpp",
                profiles={"llama-cpp": team_profile}
            )
        )
        with open(temp_config_dir / "team.json", "w") as f:
            json.dump(team_config.model_dump(), f)

        # Create user config (should be ignored)
        user_config = UserConfig(
            repos=RepoConfig(),
            model_provider=ModelProviderConfig(
                default_profile="anthropic",
                profiles={"anthropic": user_profile}
            )
        )
        with open(temp_config_dir / "config.json", "w") as f:
            json.dump(user_config.model_dump(), f)

        # Create minimal backend config
        backends_dir = temp_config_dir / "backends"
        backends_dir.mkdir()
        with open(backends_dir / "jira.json", "w") as f:
            json.dump({"url": "https://jira.example.com"}, f)

        # Load merged config
        loader = ConfigLoader(config_dir=temp_config_dir)
        config = loader.load_config()

        # Team config should win
        assert config.model_provider.default_profile == "llama-cpp"
        assert "llama-cpp" in config.model_provider.profiles

    def test_user_profile_when_no_enforcement(self, temp_config_dir, user_profile):
        """Test that user config is used when no enforcement exists."""
        # Create only user config
        user_config = UserConfig(
            repos=RepoConfig(),
            model_provider=ModelProviderConfig(
                default_profile="anthropic",
                profiles={"anthropic": user_profile}
            )
        )
        with open(temp_config_dir / "config.json", "w") as f:
            json.dump(user_config.model_dump(), f)

        # Create minimal backend config
        backends_dir = temp_config_dir / "backends"
        backends_dir.mkdir()
        with open(backends_dir / "jira.json", "w") as f:
            json.dump({"url": "https://jira.example.com"}, f)

        # Load merged config
        loader = ConfigLoader(config_dir=temp_config_dir)
        config = loader.load_config()

        # User config should be used
        assert config.model_provider.default_profile == "anthropic"
        assert "anthropic" in config.model_provider.profiles


class TestSaveValidation:
    """Test that user overrides are not saved when enforcement is active."""

    def test_save_does_not_persist_user_model_provider_when_enforced(self, temp_config_dir, enterprise_profile):
        """Test that save_config doesn't persist user model_provider when enterprise enforces."""
        # Create enterprise config
        enterprise_config = EnterpriseConfig(
            model_provider=ModelProviderConfig(
                default_profile="vertex-prod",
                profiles={"vertex-prod": enterprise_profile}
            )
        )
        with open(temp_config_dir / "enterprise.json", "w") as f:
            json.dump(enterprise_config.model_dump(), f)

        # Create minimal backend and org configs
        backends_dir = temp_config_dir / "backends"
        backends_dir.mkdir()
        with open(backends_dir / "jira.json", "w") as f:
            json.dump({"url": "https://jira.example.com"}, f)
        with open(temp_config_dir / "organization.json", "w") as f:
            json.dump({"transitions": {}}, f)
        with open(temp_config_dir / "team.json", "w") as f:
            json.dump({}, f)
        with open(temp_config_dir / "config.json", "w") as f:
            json.dump({"repos": {"workspace": str(Path.home() / "development")}}, f)

        # Load config (gets enterprise-enforced profile)
        loader = ConfigLoader(config_dir=temp_config_dir)
        config = loader.load_config()

        # User attempts to add their own profile
        user_profile = ModelProviderProfile(name="My Local Profile", base_url="http://localhost:8000")
        config.model_provider.profiles["my-local"] = user_profile
        config.model_provider.default_profile = "my-local"

        # Save config
        loader.save_config(config)

        # Reload and verify user profile was NOT saved
        saved_user_config_path = temp_config_dir / "config.json"
        with open(saved_user_config_path) as f:
            saved_user_config = json.load(f)

        # model_provider should not be in user config when enforced
        assert saved_user_config.get("model_provider") is None

    def test_save_does_not_persist_user_model_provider_when_organization_enforces(self, temp_config_dir, organization_profile):
        """Test that save_config doesn't persist user model_provider when organization enforces."""
        # Create organization config
        organization_config = OrganizationConfig(
            jira_project="AAP",
            model_provider=ModelProviderConfig(
                default_profile="aap-vertex",
                profiles={"aap-vertex": organization_profile}
            )
        )
        with open(temp_config_dir / "organization.json", "w") as f:
            json.dump(organization_config.model_dump(), f)

        # Create minimal backend configs
        backends_dir = temp_config_dir / "backends"
        backends_dir.mkdir()
        with open(backends_dir / "jira.json", "w") as f:
            json.dump({"url": "https://jira.example.com"}, f)
        with open(temp_config_dir / "team.json", "w") as f:
            json.dump({}, f)
        with open(temp_config_dir / "config.json", "w") as f:
            json.dump({"repos": {"workspace": str(Path.home() / "development")}}, f)

        # Load config (gets organization-enforced profile)
        loader = ConfigLoader(config_dir=temp_config_dir)
        config = loader.load_config()

        # User attempts to add their own profile
        user_profile = ModelProviderProfile(name="My Local Profile", base_url="http://localhost:8000")
        config.model_provider.profiles["my-local"] = user_profile
        config.model_provider.default_profile = "my-local"

        # Save config
        loader.save_config(config)

        # Reload and verify user profile was NOT saved
        saved_user_config_path = temp_config_dir / "config.json"
        with open(saved_user_config_path) as f:
            saved_user_config = json.load(f)

        # model_provider should not be in user config when organization enforces
        assert saved_user_config.get("model_provider") is None

    def test_save_persists_user_model_provider_when_not_enforced(self, temp_config_dir, user_profile):
        """Test that save_config DOES persist user model_provider when no enforcement."""
        # No enterprise or team config - only user config
        backends_dir = temp_config_dir / "backends"
        backends_dir.mkdir()
        with open(backends_dir / "jira.json", "w") as f:
            json.dump({"url": "https://jira.example.com"}, f)
        with open(temp_config_dir / "organization.json", "w") as f:
            json.dump({"transitions": {}}, f)
        with open(temp_config_dir / "team.json", "w") as f:
            json.dump({}, f)

        # Create user config with model provider
        user_config = UserConfig(
            repos=RepoConfig(),
            model_provider=ModelProviderConfig(
                default_profile="my-local",
                profiles={"my-local": user_profile}
            )
        )
        with open(temp_config_dir / "config.json", "w") as f:
            json.dump(user_config.model_dump(), f)

        # Load and save config
        loader = ConfigLoader(config_dir=temp_config_dir)
        config = loader.load_config()
        loader.save_config(config)

        # Reload and verify user profile WAS saved
        with open(temp_config_dir / "config.json") as f:
            saved_user_config = json.load(f)

        # model_provider should be in user config when not enforced
        assert saved_user_config.get("model_provider") is not None
        assert saved_user_config["model_provider"]["default_profile"] == "my-local"


class TestTUIEnforcement:
    """Test TUI enforcement detection and UI behavior."""

    @patch("devflow.ui.config_tui.ConfigLoader")
    def test_get_model_provider_enforcement_source_enterprise(self, mock_loader_class, enterprise_profile):
        """Test _get_model_provider_enforcement_source detects enterprise enforcement."""
        # Mock loader to return enterprise config
        mock_loader = Mock()
        mock_loader._load_enterprise_config.return_value = EnterpriseConfig(
            model_provider=ModelProviderConfig(
                default_profile="vertex-prod",
                profiles={"vertex-prod": enterprise_profile}
            )
        )
        mock_loader._load_organization_config.return_value = OrganizationConfig()
        mock_loader._load_team_config.return_value = TeamConfig()

        # Import and test (would normally be in TUI class)
        from devflow.ui.config_tui import ConfigTUI

        # Create minimal config for TUI
        config = Config(
            jira=JiraConfig(url="https://jira.example.com", transitions={}),
            repos=RepoConfig(),
        )

        # Create TUI instance with mocked loader
        with patch.object(ConfigTUI, "__init__", lambda self, *args, **kwargs: None):
            tui = ConfigTUI()
            tui.config_loader = mock_loader
            tui.config = config

            # Test enforcement detection
            source = tui._get_model_provider_enforcement_source()
            assert source == "enterprise"

    @patch("devflow.ui.config_tui.ConfigLoader")
    def test_get_model_provider_enforcement_source_organization(self, mock_loader_class, organization_profile):
        """Test _get_model_provider_enforcement_source detects organization enforcement."""
        mock_loader = Mock()
        mock_loader._load_enterprise_config.return_value = EnterpriseConfig()
        mock_loader._load_organization_config.return_value = OrganizationConfig(
            jira_project="AAP",
            model_provider=ModelProviderConfig(
                default_profile="aap-vertex",
                profiles={"aap-vertex": organization_profile}
            )
        )
        mock_loader._load_team_config.return_value = TeamConfig()

        from devflow.ui.config_tui import ConfigTUI

        config = Config(
            jira=JiraConfig(url="https://jira.example.com", transitions={}),
            repos=RepoConfig(),
        )

        with patch.object(ConfigTUI, "__init__", lambda self, *args, **kwargs: None):
            tui = ConfigTUI()
            tui.config_loader = mock_loader
            tui.config = config

            source = tui._get_model_provider_enforcement_source()
            assert source == "organization"

    @patch("devflow.ui.config_tui.ConfigLoader")
    def test_get_model_provider_enforcement_source_team(self, mock_loader_class, team_profile):
        """Test _get_model_provider_enforcement_source detects team enforcement."""
        mock_loader = Mock()
        mock_loader._load_enterprise_config.return_value = EnterpriseConfig()
        mock_loader._load_organization_config.return_value = OrganizationConfig()
        mock_loader._load_team_config.return_value = TeamConfig(
            model_provider=ModelProviderConfig(
                default_profile="llama-cpp",
                profiles={"llama-cpp": team_profile}
            )
        )

        from devflow.ui.config_tui import ConfigTUI

        config = Config(
            jira=JiraConfig(url="https://jira.example.com", transitions={}),
            repos=RepoConfig(),
        )

        with patch.object(ConfigTUI, "__init__", lambda self, *args, **kwargs: None):
            tui = ConfigTUI()
            tui.config_loader = mock_loader
            tui.config = config

            source = tui._get_model_provider_enforcement_source()
            assert source == "team"

    @patch("devflow.ui.config_tui.ConfigLoader")
    def test_get_model_provider_enforcement_source_none(self, mock_loader_class):
        """Test _get_model_provider_enforcement_source returns None when no enforcement."""
        mock_loader = Mock()
        mock_loader._load_enterprise_config.return_value = EnterpriseConfig()
        mock_loader._load_organization_config.return_value = OrganizationConfig()
        mock_loader._load_team_config.return_value = TeamConfig()

        from devflow.ui.config_tui import ConfigTUI

        config = Config(
            jira=JiraConfig(url="https://jira.example.com", transitions={}),
            repos=RepoConfig(),
        )

        with patch.object(ConfigTUI, "__init__", lambda self, *args, **kwargs: None):
            tui = ConfigTUI()
            tui.config_loader = mock_loader
            tui.config = config

            source = tui._get_model_provider_enforcement_source()
            assert source is None


class TestAuditLogging:
    """Test audit logging for model provider usage."""

    def test_log_model_provider_usage_with_cost_tracking(self, tmp_path):
        """Test that audit log captures cost tracking metadata."""
        from devflow.utils.audit_log import log_model_provider_usage, audit_logger

        # Clear any existing handlers to ensure clean state
        audit_logger.handlers.clear()

        # Set up audit log in temp directory
        with patch("devflow.utils.audit_log.get_cs_home", return_value=tmp_path):
            log_model_provider_usage(
                event_type="session_created",
                session_name="TEST-123",
                profile_name="vertex-prod",
                enforcement_source="enterprise",
                model_name=None,
                base_url=None,
                use_vertex=True,
                vertex_region="us-east5",
                cost_per_million_input_tokens=3.00,
                cost_per_million_output_tokens=15.00,
                cost_center="ENG-PLATFORM",
            )

            # Flush handlers to ensure log is written
            for handler in audit_logger.handlers:
                handler.flush()

            # Verify audit log was created and contains expected fields
            audit_log_path = tmp_path / "audit.log"
            assert audit_log_path.exists()

            with open(audit_log_path) as f:
                log_entry = json.loads(f.read())

            assert log_entry["event_type"] == "session_created"
            assert log_entry["session_name"] == "TEST-123"
            assert log_entry["profile_name"] == "vertex-prod"
            assert log_entry["enforcement_source"] == "enterprise"
            assert log_entry["use_vertex"] is True
            assert log_entry["vertex_region"] == "us-east5"
            assert log_entry["cost_per_million_input_tokens"] == 3.00
            assert log_entry["cost_per_million_output_tokens"] == 15.00
            assert log_entry["cost_center"] == "ENG-PLATFORM"

    def test_log_includes_enforcement_metadata(self, tmp_path):
        """Test that audit log includes enforcement source metadata."""
        from devflow.utils.audit_log import log_model_provider_usage, audit_logger

        # Clear any existing handlers to avoid caching issues
        audit_logger.handlers.clear()

        # Test with enterprise enforcement
        with patch("devflow.utils.audit_log.get_cs_home", return_value=tmp_path):
            log_model_provider_usage(
                event_type="session_created",
                session_name="TEST-456",
                profile_name="vertex-prod",
                enforcement_source="enterprise",
                model_name=None,
                base_url=None,
                use_vertex=True,
                vertex_region="us-east5",
            )

            # Flush and close handlers to ensure log is written
            for handler in audit_logger.handlers:
                handler.flush()
                handler.close()

            audit_log_path = tmp_path / "audit.log"
            with open(audit_log_path) as f:
                log_entry = json.loads(f.read())

            assert log_entry["enforcement_source"] == "enterprise"
            assert log_entry["profile_name"] == "vertex-prod"


class TestCostTracking:
    """Test cost tracking fields in profiles."""

    def test_model_provider_profile_with_cost_tracking(self):
        """Test that ModelProviderProfile accepts cost tracking fields."""
        profile = ModelProviderProfile(
            name="Vertex AI Production",
            use_vertex=True,
            vertex_project_id="test-project",
            vertex_region="us-east5",
            cost_per_million_input_tokens=3.00,
            cost_per_million_output_tokens=15.00,
            monthly_budget_usd=5000.00,
            cost_center="ENG-PLATFORM",
        )

        assert profile.cost_per_million_input_tokens == 3.00
        assert profile.cost_per_million_output_tokens == 15.00
        assert profile.monthly_budget_usd == 5000.00
        assert profile.cost_center == "ENG-PLATFORM"

    def test_model_provider_profile_serialization_with_cost_tracking(self):
        """Test that cost tracking fields are serialized correctly."""
        profile = ModelProviderProfile(
            name="Vertex AI Production",
            use_vertex=True,
            vertex_project_id="test-project",
            vertex_region="us-east5",
            cost_per_million_input_tokens=3.00,
            cost_per_million_output_tokens=15.00,
            monthly_budget_usd=5000.00,
            cost_center="ENG-PLATFORM",
        )

        profile_dict = profile.model_dump()

        assert profile_dict["cost_per_million_input_tokens"] == 3.00
        assert profile_dict["cost_per_million_output_tokens"] == 15.00
        assert profile_dict["monthly_budget_usd"] == 5000.00
        assert profile_dict["cost_center"] == "ENG-PLATFORM"

    def test_model_provider_profile_deserialization_with_cost_tracking(self):
        """Test that cost tracking fields are deserialized correctly."""
        profile_dict = {
            "name": "Vertex AI Production",
            "use_vertex": True,
            "vertex_project_id": "test-project",
            "vertex_region": "us-east5",
            "cost_per_million_input_tokens": 3.00,
            "cost_per_million_output_tokens": 15.00,
            "monthly_budget_usd": 5000.00,
            "cost_center": "ENG-PLATFORM",
        }

        profile = ModelProviderProfile(**profile_dict)

        assert profile.cost_per_million_input_tokens == 3.00
        assert profile.cost_per_million_output_tokens == 15.00
        assert profile.monthly_budget_usd == 5000.00
        assert profile.cost_center == "ENG-PLATFORM"
