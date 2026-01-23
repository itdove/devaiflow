"""Template manager for DevAIFlow."""

import json
from pathlib import Path
from typing import Optional

from devflow.config.loader import ConfigLoader
from devflow.templates.models import NameExtractionConfig, SessionTemplate, TemplateConfig, TemplateIndex
from devflow.utils.paths import get_cs_home


class TemplateManager:
    """Manager for session templates."""

    def __init__(self, cs_home: Optional[Path] = None):
        """Initialize template manager.

        Args:
            cs_home: Path to DevAIFlow home directory (defaults to DEVAIFLOW_HOME or ~/.daf-sessions)
        """
        self.cs_home = cs_home or get_cs_home()
        self.templates_dir = self.cs_home / "templates"
        self.templates_file = self.cs_home / "templates.json"

        # Load config for template settings
        self.config_loader = ConfigLoader(config_dir=self.cs_home)
        self.config = self.config_loader.load_config()

        # Ensure templates directory exists
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Load templates
        self.index = self._load_templates()

    def _load_templates(self) -> TemplateIndex:
        """Load templates from templates.json file."""
        if not self.templates_file.exists():
            return TemplateIndex()

        try:
            with open(self.templates_file, "r") as f:
                data = json.load(f)
                return TemplateIndex(**data)
        except Exception as e:
            print(f"Warning: Failed to load templates: {e}")
            return TemplateIndex()

    def _save_templates(self) -> None:
        """Save templates to templates.json file."""
        with open(self.templates_file, "w") as f:
            json.dump(self.index.model_dump(mode="json"), f, indent=2)

    def get_template(self, name: str) -> Optional[SessionTemplate]:
        """Get template by name.

        Args:
            name: Template name

        Returns:
            Template or None if not found
        """
        return self.index.get_template(name)

    def list_templates(self) -> list[SessionTemplate]:
        """List all templates sorted by usage.

        Returns:
            List of templates sorted by usage count (descending)
        """
        return self.index.list_templates()

    def save_template(self, template: SessionTemplate) -> None:
        """Save or update a template.

        If template already exists, it will be updated.
        If template doesn't exist, it will be created.

        Args:
            template: Template to save
        """
        # Check if template exists and use appropriate method
        if self.get_template(template.name) is not None:
            self.index.update_template(template)
        else:
            self.index.add_template(template)
        self._save_templates()

    def delete_template(self, name: str) -> bool:
        """Delete a template.

        Args:
            name: Template name

        Returns:
            True if template was deleted, False if it didn't exist
        """
        result = self.index.remove_template(name)
        if result:
            self._save_templates()
        return result

    def find_matching_template(self, current_dir: Path) -> Optional[SessionTemplate]:
        """Find template that matches current directory.

        Args:
            current_dir: Current working directory

        Returns:
            Matching template or None
        """
        return self.index.find_matching_template(current_dir)

    def auto_create_template(
        self,
        project_path: Path,
        description: Optional[str] = None,
        default_jira_project: Optional[str] = None,
    ) -> SessionTemplate:
        """Auto-create template from project path.

        Args:
            project_path: Path to project directory
            description: Optional template description
            default_jira_project: Optional default JIRA project

        Returns:
            Created template
        """
        # Use simple name extraction - just use directory name
        template_name = project_path.name

        # Create template with sensible defaults
        template = SessionTemplate(
            name=template_name,
            description=description or f"Template for {template_name}",
            working_directory=project_path.name,
            branch=None,
            tags=[],
            issue_key=default_jira_project,
        )

        # Save template
        self.save_template(template)

        return template

    def update_usage(self, template_name: str) -> None:
        """Update template usage statistics.

        Args:
            template_name: Name of template that was used
        """
        template = self.get_template(template_name)
        if template:
            template.mark_used()
            self._save_templates()
