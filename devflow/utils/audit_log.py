"""Audit logging for DevAIFlow operations.

This module provides centralized audit logging for security-sensitive operations
including model provider usage tracking for enterprise compliance.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

from devflow.utils.paths import get_cs_home

# Configure audit logger with separate handler
audit_logger = logging.getLogger("devaiflow.audit")
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False  # Don't propagate to root logger


def _get_audit_log_path() -> Path:
    """Get the path to the audit log file.

    Returns:
        Path to audit.log in DEVAIFLOW_HOME
    """
    cs_home = get_cs_home()
    return cs_home / "audit.log"


def _ensure_audit_log_handler():
    """Ensure audit logger has a file handler configured."""
    if not audit_logger.handlers:
        log_path = _get_audit_log_path()

        # Create parent directory if needed
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Add rotating file handler (max 10MB, keep 5 backups)
        from logging.handlers import RotatingFileHandler
        handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )

        # JSON format for structured logging
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        audit_logger.addHandler(handler)


def log_model_provider_usage(
    event_type: str,
    session_name: str,
    profile_name: Optional[str] = None,
    enforcement_source: Optional[str] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    use_vertex: bool = False,
    vertex_region: Optional[str] = None,
    cost_per_million_input_tokens: Optional[float] = None,
    cost_per_million_output_tokens: Optional[float] = None,
    cost_center: Optional[str] = None,
    additional_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Log model provider usage for audit trail.

    Args:
        event_type: Type of event (e.g., "session_created", "session_launched")
        session_name: Name of the session
        profile_name: Name of the model provider profile being used
        enforcement_source: Source of enforcement ("enterprise", "team", or None)
        model_name: Model name being used
        base_url: API base URL being used
        use_vertex: Whether Vertex AI is being used
        vertex_region: Vertex AI region (if applicable)
        cost_per_million_input_tokens: Cost per million input tokens in USD
        cost_per_million_output_tokens: Cost per million output tokens in USD
        cost_center: Cost center or department code
        additional_data: Additional data to include in log entry
    """
    _ensure_audit_log_handler()

    # Build structured log entry
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "category": "model_provider",
        "session_name": session_name,
        "profile_name": profile_name,
        "enforcement_source": enforcement_source,
        "model_name": model_name,
        "base_url": base_url,
        "use_vertex": use_vertex,
    }

    if vertex_region:
        log_entry["vertex_region"] = vertex_region

    # Cost tracking fields (for enterprise budget management)
    if cost_per_million_input_tokens is not None:
        log_entry["cost_per_million_input_tokens"] = cost_per_million_input_tokens
    if cost_per_million_output_tokens is not None:
        log_entry["cost_per_million_output_tokens"] = cost_per_million_output_tokens
    if cost_center:
        log_entry["cost_center"] = cost_center

    if additional_data:
        log_entry["additional_data"] = additional_data

    # Write as JSON (one entry per line for easy parsing)
    audit_logger.info(json.dumps(log_entry))


def log_config_change(
    event_type: str,
    config_file: str,
    field_path: str,
    old_value: Optional[Any] = None,
    new_value: Optional[Any] = None,
    additional_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Log configuration changes for audit trail.

    Args:
        event_type: Type of event (e.g., "config_updated", "profile_added")
        config_file: Configuration file that was changed
        field_path: Dot-separated path to field (e.g., "model_provider.default_profile")
        old_value: Previous value (optional)
        new_value: New value (optional)
        additional_data: Additional data to include in log entry
    """
    _ensure_audit_log_handler()

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "category": "config_change",
        "config_file": config_file,
        "field_path": field_path,
        "old_value": old_value,
        "new_value": new_value,
    }

    if additional_data:
        log_entry["additional_data"] = additional_data

    audit_logger.info(json.dumps(log_entry))
