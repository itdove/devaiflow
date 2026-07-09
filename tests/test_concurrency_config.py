"""Tests for ConcurrencyConfig model."""

import pytest
from devflow.config.models import ConcurrencyConfig


class TestConcurrencyConfig:
    """Tests for ConcurrencyConfig Pydantic model."""

    def test_default_values(self):
        config = ConcurrencyConfig()
        assert config.mode == "strict"
        assert config.auto_clone_path is None
        assert config.cleanup_on_complete is True

    def test_valid_modes(self):
        for mode in ["strict", "analyze", "permissive"]:
            config = ConcurrencyConfig(mode=mode)
            assert config.mode == mode

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="concurrency.mode must be one of"):
            ConcurrencyConfig(mode="invalid")

    def test_auto_clone_path_override(self):
        config = ConcurrencyConfig(auto_clone_path="/custom/path")
        assert config.auto_clone_path == "/custom/path"

    def test_cleanup_on_complete_false(self):
        config = ConcurrencyConfig(cleanup_on_complete=False)
        assert config.cleanup_on_complete is False

    def test_serialization_roundtrip(self):
        config = ConcurrencyConfig(mode="analyze", auto_clone_path="/tmp/clones", cleanup_on_complete=False)
        data = config.model_dump()
        restored = ConcurrencyConfig(**data)
        assert restored.mode == "analyze"
        assert restored.auto_clone_path == "/tmp/clones"
        assert restored.cleanup_on_complete is False

    def test_json_roundtrip(self):
        config = ConcurrencyConfig(mode="permissive")
        json_str = config.model_dump_json()
        restored = ConcurrencyConfig.model_validate_json(json_str)
        assert restored.mode == "permissive"
