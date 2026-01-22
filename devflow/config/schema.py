"""JSON Schema generation and validation for configuration."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import ValidationError

from .models import Config


def generate_json_schema() -> Dict[str, Any]:
    """Generate JSON Schema from Pydantic Config model.

    Returns:
        JSON Schema dictionary
    """
    # Pydantic v2 provides model_json_schema() method
    schema = Config.model_json_schema()

    # Add metadata
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    schema["$id"] = "https://github.com/itdove/devaiflow/blob/main/config.schema.json"
    schema["title"] = "DevAIFlow Configuration"
    schema["description"] = "Configuration schema for DevAIFlow (daf tool), auto-generated from Pydantic models"

    return schema


def save_schema(output_path: Optional[Path] = None) -> Path:
    """Generate and save JSON Schema to file.

    Args:
        output_path: Path to save schema file. Defaults to config.schema.json in project root.

    Returns:
        Path where schema was saved
    """
    if output_path is None:
        # Default to project root
        output_path = Path(__file__).parent.parent.parent / "config.schema.json"

    schema = generate_json_schema()

    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2)

    return output_path


def validate_config_dict(config_dict: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate a configuration dictionary against the schema.

    Args:
        config_dict: Configuration dictionary to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if validation passed
        - error_message: None if valid, error message string if invalid
    """
    try:
        # Pydantic validation happens automatically when constructing the model
        Config(**config_dict)
        return (True, None)
    except ValidationError as e:
        # Format validation errors nicely
        error_lines = []
        for error in e.errors():
            loc = " -> ".join(str(l) for l in error["loc"])
            msg = error["msg"]
            error_lines.append(f"  {loc}: {msg}")

        error_message = "Configuration validation failed:\n" + "\n".join(error_lines)
        return (False, error_message)
    except Exception as e:
        return (False, f"Unexpected validation error: {str(e)}")


def validate_config_file(config_path: Path) -> tuple[bool, Optional[str]]:
    """Validate a configuration file against the schema.

    Args:
        config_path: Path to config.json file

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if validation passed
        - error_message: None if valid, error message string if invalid
    """
    if not config_path.exists():
        return (False, f"Config file not found: {config_path}")

    try:
        with open(config_path, "r") as f:
            config_dict = json.load(f)
    except json.JSONDecodeError as e:
        return (False, f"Invalid JSON in config file: {e}")
    except Exception as e:
        return (False, f"Error reading config file: {e}")

    return validate_config_dict(config_dict)
