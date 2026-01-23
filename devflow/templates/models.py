"""Template data models for DevAIFlow."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class NameExtractionConfig(BaseModel):
    """Configuration for extracting template names from project paths."""

    remove_prefixes: List[str] = Field(
        default_factory=list,
        description="Prefixes to remove when extracting template name from path",
    )
    remove_suffixes: List[str] = Field(
        default_factory=list,
        description="Suffixes to remove when extracting template name from path",
    )


class SessionTemplate(BaseModel):
    """Session template for quick session creation."""

    name: str = Field(..., description="Template name (e.g., 'backend-api')")
    description: Optional[str] = Field(None, description="Human-readable description")

    # Session settings from source session
    working_directory: Optional[str] = Field(None, description="Working directory name")
    branch: Optional[str] = Field(None, description="Git branch pattern")
    tags: List[str] = Field(default_factory=list, description="Tags to apply to sessions")
    issue_key: Optional[str] = Field(None, description="issue tracker key (if any)")

    # Metadata
    created_at: Optional[datetime] = Field(None, description="Template creation timestamp")
    last_used: Optional[datetime] = Field(None, description="Last time template was used")
    usage_count: int = Field(0, description="Number of times template was used")

    def mark_used(self) -> None:
        """Mark template as used (updates last_used and increments usage_count)."""
        self.last_used = datetime.now()
        self.usage_count += 1


class TemplateConfig(BaseModel):
    """Configuration for template behavior."""

    auto_create: bool = Field(
        True, description="Automatically create templates when creating sessions in new directories"
    )
    auto_use: bool = Field(True, description="Automatically use matching templates when creating sessions")
    name_extraction: NameExtractionConfig = Field(
        default_factory=NameExtractionConfig, description="Configuration for template name extraction"
    )
    defaults: Dict[str, bool] = Field(
        default_factory=lambda: {
            "auto_create_branch": True,
            "branch_strategy": "from_default",
            "require_jira": False,
        },
        description="Default settings for new templates",
    )


class TemplateIndex(BaseModel):
    """Index of all session templates."""

    templates: Dict[str, SessionTemplate] = Field(
        default_factory=dict, description="Templates indexed by name"
    )

    def add_template(self, template: SessionTemplate) -> None:
        """Add a new template to the index.

        Raises:
            ValueError: If template with this name already exists
        """
        if template.name in self.templates:
            raise ValueError(f"Template '{template.name}' already exists")
        self.templates[template.name] = template

    def update_template(self, template: SessionTemplate) -> None:
        """Update an existing template in the index.

        Raises:
            ValueError: If template with this name doesn't exist
        """
        if template.name not in self.templates:
            raise ValueError(f"Template '{template.name}' not found")
        self.templates[template.name] = template

    def get_template(self, name: str) -> Optional[SessionTemplate]:
        """Get template by name."""
        return self.templates.get(name)

    def remove_template(self, name: str) -> bool:
        """Remove template by name. Returns True if template existed."""
        if name in self.templates:
            del self.templates[name]
            return True
        return False

    def list_templates(self) -> List[SessionTemplate]:
        """Get all templates sorted by usage count (descending) then by last used."""
        return sorted(
            self.templates.values(),
            key=lambda t: (t.usage_count, t.last_used or datetime.min),
            reverse=True,
        )

    def find_matching_template(self, current_dir: Path) -> Optional[SessionTemplate]:
        """Find template that matches current directory.

        Matching logic:
        1. Pattern match on working_directory (contains)
        2. Return most recently used if multiple matches

        Args:
            current_dir: Current working directory path

        Returns:
            Matching template or None
        """
        matches = []

        for template in self.templates.values():
            # Pattern match on directory name
            if template.working_directory and template.working_directory in current_dir.name:
                matches.append(template)

        if matches:
            # Return most recently used
            return max(matches, key=lambda t: t.last_used or datetime.min)

        return None

    def extract_template_name(self, project_path: Path, config: NameExtractionConfig) -> str:
        """Extract template name from project path.

        Examples:
            /Users/dvernier/development/workspace/backend-api
            → backend-api

            /Users/dvernier/development/workspace/frontend-app
            → frontend-app

            /Users/dvernier/projects/my-app
            → my-app

        Args:
            project_path: Path to project directory
            config: Name extraction configuration

        Returns:
            Extracted template name
        """
        base_name = project_path.name

        # Remove configured prefixes
        for prefix in config.remove_prefixes:
            if base_name.startswith(prefix):
                base_name = base_name[len(prefix) :]
                break

        # Remove configured suffixes
        for suffix in config.remove_suffixes:
            if base_name.endswith(suffix):
                base_name = base_name[: -len(suffix)]
                break

        return base_name
