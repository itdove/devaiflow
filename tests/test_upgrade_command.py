"""Tests for daf upgrade command."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from devflow.cli.commands.upgrade_command import (
    upgrade_all,
    _print_upgrade_table,
)
from devflow.config.models import Config, RepoConfig, WorkspaceDefinition


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config object with workspace configured."""
    config = Mock(spec=Config)
    config.repos = Mock(spec=RepoConfig)
    config.repos.get_default_workspace_path.return_value = str(tmp_path)

    # Add workspaces attribute for upgrade_all tests
    workspace = WorkspaceDefinition(name="test-workspace", path=str(tmp_path))
    config.repos.workspaces = [workspace]

    return config


@pytest.fixture
def mock_config_loader(mock_config):
    """Create a mock config loader."""
    loader = Mock()
    loader.load_config.return_value = mock_config
    return loader


class TestUpgradeAll:
    """Tests for upgrade_all function."""

    def test_upgrade_all_no_config(self):
        """Test upgrade all when no config exists."""
        mock_loader = Mock()
        mock_loader.load_config.return_value = None

        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_loader):
            upgrade_all()

    def test_upgrade_all_no_workspaces(self):
        """Test upgrade all when no workspaces are configured."""
        mock_config = Mock(spec=Config)
        mock_config.repos = Mock(spec=RepoConfig)
        mock_config.repos.workspaces = []

        mock_loader = Mock()
        mock_loader.load_config.return_value = mock_config

        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_loader):
            upgrade_all()

    # Skipping outdated test - upgrade logic simplified
    #     def test_upgrade_all_commands_only(self, mock_config, mock_config_loader, tmp_path):
    #         """Test upgrading commands only."""
    #         # Create workspace directory
    #         (tmp_path / ".claude" / "commands").mkdir(parents=True)
    # 
    #         with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
    #             with patch('devflow.cli.commands.upgrade_command.get_all_command_statuses') as mock_cmd_statuses:
    #                 with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_commands') as mock_install_cmd:
    #                     with patch('devflow.cli.commands.upgrade_command._print_upgrade_table'):
    #                         mock_cmd_statuses.return_value = {"cmd1": "outdated"}
    #                         mock_install_cmd.return_value = (["cmd1"], [], [])
    # 
    #                         upgrade_all(upgrade_commands=True, upgrade_skills=False, quiet=False)
    # 
    #                         mock_install_cmd.assert_called_once()
    # 
    # Skipping outdated test - upgrade logic simplified
    #     def test_upgrade_all_skills_only(self, mock_config, mock_config_loader, tmp_path):
    #         """Test upgrading skills only."""
    #         # Create workspace directory
    #         (tmp_path / ".claude" / "skills").mkdir(parents=True)
    # 
    #         with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
    #             with patch('devflow.cli.commands.upgrade_command.get_all_skill_statuses') as mock_skill_statuses:
    #                 with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_skills') as mock_install_skill:
    #                     with patch('devflow.cli.commands.upgrade_command._print_upgrade_table'):
    #                         mock_skill_statuses.return_value = {"skill1": "not_installed"}
    #                         mock_install_skill.return_value = (["skill1"], [], [])
    # 
    #                         upgrade_all(upgrade_commands=False, upgrade_skills=True, quiet=False)
    # 
    #                         mock_install_skill.assert_called_once()
    # 
    # Skipping outdated test - upgrade logic simplified
    #     def test_upgrade_all_both(self, mock_config, mock_config_loader, tmp_path):
    #         """Test upgrading both commands and skills."""
    #         # Create workspace directories
    #         (tmp_path / ".claude" / "commands").mkdir(parents=True)
    #         (tmp_path / ".claude" / "skills").mkdir(parents=True)
    # 
    #         with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
    #             with patch('devflow.cli.commands.upgrade_command.get_all_command_statuses') as mock_cmd_statuses:
    #                 with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_commands') as mock_install_cmd:
    #                     with patch('devflow.cli.commands.upgrade_command.get_all_skill_statuses') as mock_skill_statuses:
    #                         with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_skills') as mock_install_skill:
    #                             with patch('devflow.cli.commands.upgrade_command._print_upgrade_table'):
    #                                 mock_cmd_statuses.return_value = {"cmd1": "outdated"}
    #                                 mock_install_cmd.return_value = (["cmd1"], [], [])
    #                                 mock_skill_statuses.return_value = {"skill1": "not_installed"}
    #                                 mock_install_skill.return_value = (["skill1"], [], [])
    # 
    #                                 upgrade_all(upgrade_commands=True, upgrade_skills=True, quiet=False)
    # 
    #                                 mock_install_cmd.assert_called_once()
    #                                 mock_install_skill.assert_called_once()
    # 
    # Skipping outdated test - upgrade logic simplified
    #     def test_upgrade_all_dry_run(self, mock_config, mock_config_loader, tmp_path):
    #         """Test upgrade all in dry run mode."""
    #         # Create workspace directories
    #         (tmp_path / ".claude" / "commands").mkdir(parents=True)
    #         (tmp_path / ".claude" / "skills").mkdir(parents=True)
    # 
    #         with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
    #             with patch('devflow.cli.commands.upgrade_command.get_all_command_statuses'):
    #                 with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_commands') as mock_install_cmd:
    #                     with patch('devflow.cli.commands.upgrade_command.get_all_skill_statuses'):
    #                         with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_skills') as mock_install_skill:
    #                             with patch('devflow.cli.commands.upgrade_command._print_upgrade_table'):
    #                                 mock_install_cmd.return_value = (["cmd1"], [], [])
    #                                 mock_install_skill.return_value = (["skill1"], [], [])
    # 
    #                                 upgrade_all(dry_run=True, quiet=False)
    # 
    #                                 # Verify dry_run flag was passed
    #                                 assert mock_install_cmd.call_args[1]['dry_run'] is True
    #                                 assert mock_install_skill.call_args[1]['dry_run'] is True
    # 
    # Skipping outdated test - upgrade logic simplified
    #     def test_upgrade_all_with_failures(self, mock_config, mock_config_loader, tmp_path):
    #         """Test upgrade all when some items fail."""
    #         # Create workspace directories
    #         (tmp_path / ".claude" / "commands").mkdir(parents=True)
    #         (tmp_path / ".claude" / "skills").mkdir(parents=True)
    # 
    #         with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
    #             with patch('devflow.cli.commands.upgrade_command.get_all_command_statuses'):
    #                 with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_commands') as mock_install_cmd:
    #                     with patch('devflow.cli.commands.upgrade_command.get_all_skill_statuses'):
    #                         with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_skills') as mock_install_skill:
    #                             with patch('devflow.cli.commands.upgrade_command._print_upgrade_table'):
    #                                 # Commands: 1 changed, 1 up-to-date, 1 failed
    #                                 mock_install_cmd.return_value = (["cmd1"], ["cmd2"], ["cmd3"])
    #                                 # Skills: 1 changed, 0 up-to-date, 1 failed
    #                                 mock_install_skill.return_value = (["skill1"], [], ["skill2"])
    # 
    #                                 upgrade_all(upgrade_commands=True, upgrade_skills=True, quiet=False)
    # 
    # Skipping outdated test - upgrade logic simplified
    #     def test_upgrade_all_commands_file_not_found(self, mock_config, mock_config_loader, tmp_path):
    #         """Test upgrade all when commands FileNotFoundError occurs."""
    #         # Create workspace directory
    #         (tmp_path / ".claude" / "commands").mkdir(parents=True)
    # 
    #         with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
    #             with patch('devflow.cli.commands.upgrade_command.get_all_command_statuses'):
    #                 with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_commands') as mock_install_cmd:
    #                     mock_install_cmd.side_effect = FileNotFoundError("Commands not found")
    # 
    #                     # Should handle gracefully
    #                     upgrade_all(upgrade_commands=True, upgrade_skills=False)
    # 
    # Skipping outdated test - upgrade logic simplified
    #     def test_upgrade_all_skills_file_not_found(self, mock_config, mock_config_loader, tmp_path):
    #         """Test upgrade all when skills FileNotFoundError occurs."""
    #         # Create workspace directory
    #         (tmp_path / ".claude" / "skills").mkdir(parents=True)
    # 
    #         with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
    #             with patch('devflow.cli.commands.upgrade_command.get_all_skill_statuses'):
    #                 with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_skills') as mock_install_skill:
    #                     mock_install_skill.side_effect = FileNotFoundError("Skills not found")
    # 
    #                     # Should handle gracefully
    #                     upgrade_all(upgrade_commands=False, upgrade_skills=True)
    # 
    # 
class TestPrintUpgradeTable:
    """Tests for _print_upgrade_table helper function."""

    def test_print_upgrade_table_quiet_mode(self):
        """Test that quiet mode suppresses output."""
        # Should not print anything in quiet mode
        _print_upgrade_table(
            changed=["item1"],
            up_to_date=["item2"],
            failed=["item3"],
            statuses_before={"item1": "outdated", "item2": "up_to_date", "item3": "not_installed"},
            item_type="command",
            dry_run=False,
            quiet=True
        )

    def test_print_upgrade_table_changed_items(self):
        """Test printing table with changed items."""
        _print_upgrade_table(
            changed=["item1", "item2"],
            up_to_date=[],
            failed=[],
            statuses_before={"item1": "outdated", "item2": "not_installed"},
            item_type="command",
            dry_run=False,
            quiet=False
        )

    def test_print_upgrade_table_up_to_date_items(self):
        """Test printing table with up-to-date items."""
        _print_upgrade_table(
            changed=[],
            up_to_date=["item1", "item2"],
            failed=[],
            statuses_before={"item1": "up_to_date", "item2": "up_to_date"},
            item_type="skill",
            dry_run=False,
            quiet=False
        )

    def test_print_upgrade_table_failed_items(self):
        """Test printing table with failed items."""
        _print_upgrade_table(
            changed=[],
            up_to_date=[],
            failed=["item1", "item2"],
            statuses_before={"item1": "outdated", "item2": "not_installed"},
            item_type="command",
            dry_run=False,
            quiet=False
        )

    def test_print_upgrade_table_mixed_items(self):
        """Test printing table with mixed status items."""
        _print_upgrade_table(
            changed=["item1"],
            up_to_date=["item2"],
            failed=["item3"],
            statuses_before={"item1": "outdated", "item2": "up_to_date", "item3": "not_installed"},
            item_type="command",
            dry_run=False,
            quiet=False
        )

    def test_print_upgrade_table_dry_run(self):
        """Test printing table in dry run mode."""
        _print_upgrade_table(
            changed=["item1", "item2"],
            up_to_date=["item3"],
            failed=[],
            statuses_before={"item1": "outdated", "item2": "not_installed", "item3": "up_to_date"},
            item_type="command",
            dry_run=True,
            quiet=False
        )

    def test_print_upgrade_table_missing_status_before(self):
        """Test printing table when status_before is missing for an item."""
        _print_upgrade_table(
            changed=["item1"],
            up_to_date=[],
            failed=["item2"],
            statuses_before={},  # Empty statuses
            item_type="skill",
            dry_run=False,
            quiet=False
        )


class TestUpgradeAllComprehensive:
    """Comprehensive tests for upgrade_all function covering all upgrade paths."""

    def test_upgrade_all_with_slash_commands(self, mock_config, mock_config_loader):
        """Test upgrade with slash commands."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_slash_commands') as mock_slash:
                with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_reference_skills') as mock_ref:
                    with patch('devflow.cli.commands.upgrade_command.console'):
                        mock_slash.return_value = (["daf-list"], ["daf-active"], [])
                        mock_ref.return_value = ([], ["daf-cli"], [])

                        upgrade_all(upgrade_skills=True, upgrade_hierarchical_skills=False, quiet=False)

                        mock_slash.assert_called_once()
                        mock_ref.assert_called_once()

    def test_upgrade_all_with_reference_skills(self, mock_config, mock_config_loader):
        """Test upgrade with reference skills."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_slash_commands') as mock_slash:
                with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_reference_skills') as mock_ref:
                    with patch('devflow.cli.commands.upgrade_command.console'):
                        mock_slash.return_value = ([], [], [])
                        mock_ref.return_value = (["gh-cli", "git-cli"], [], [])

                        upgrade_all(upgrade_skills=True, upgrade_hierarchical_skills=False, quiet=False)

                        assert mock_ref.called

    def test_upgrade_all_dry_run_with_changes(self, mock_config, mock_config_loader):
        """Test dry run mode with potential changes."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_slash_commands') as mock_slash:
                with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_reference_skills') as mock_ref:
                    with patch('devflow.cli.commands.upgrade_command.console') as mock_console:
                        mock_slash.return_value = (["daf-list"], [], [])
                        mock_ref.return_value = (["gh-cli"], [], [])

                        upgrade_all(dry_run=True, upgrade_skills=True, upgrade_hierarchical_skills=False, quiet=False)

                        # Verify dry_run passed to install functions
                        assert mock_slash.call_args[1]['dry_run'] is True
                        assert mock_ref.call_args[1]['dry_run'] is True

    def test_upgrade_all_with_failures(self, mock_config, mock_config_loader):
        """Test upgrade when some items fail."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_slash_commands') as mock_slash:
                with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_reference_skills') as mock_ref:
                    with patch('devflow.cli.commands.upgrade_command.console') as mock_console:
                        mock_slash.return_value = (["daf-list"], [], ["daf-broken"])
                        mock_ref.return_value = ([], [], ["gh-cli-broken"])

                        upgrade_all(upgrade_skills=True, upgrade_hierarchical_skills=False, quiet=False)

                        # Should complete despite failures
                        assert mock_console.print.called

    def test_upgrade_all_slash_commands_exception(self, mock_config, mock_config_loader):
        """Test handling of exception during slash command installation."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_slash_commands') as mock_slash:
                with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_reference_skills') as mock_ref:
                    with patch('devflow.cli.commands.upgrade_command.console') as mock_console:
                        mock_slash.side_effect = Exception("Installation failed")
                        mock_ref.return_value = ([], [], [])

                        upgrade_all(upgrade_skills=True, upgrade_hierarchical_skills=False, quiet=False)

                        # Should continue despite exception
                        assert mock_ref.called

    def test_upgrade_all_reference_skills_exception(self, mock_config, mock_config_loader):
        """Test handling of exception during reference skill installation."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_slash_commands') as mock_slash:
                with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_reference_skills') as mock_ref:
                    with patch('devflow.cli.commands.upgrade_command.console') as mock_console:
                        mock_slash.return_value = ([], [], [])
                        mock_ref.side_effect = Exception("Reference skill failed")

                        upgrade_all(upgrade_skills=True, upgrade_hierarchical_skills=False, quiet=False)

                        # Should handle exception gracefully
                        assert mock_console.print.called

    def test_upgrade_all_hierarchical_skills(self, mock_config, mock_config_loader):
        """Test upgrade with hierarchical skills."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.utils.hierarchical_skills.install_hierarchical_skills') as mock_hierarchical:
                with patch('devflow.utils.hierarchical_skills.get_hierarchical_skill_statuses') as mock_statuses:
                    with patch('devflow.cli.commands.upgrade_command.console'):
                        mock_statuses.return_value = {"01-enterprise": "not_installed"}
                        mock_hierarchical.return_value = (["01-enterprise"], [], [])

                        upgrade_all(upgrade_skills=False, upgrade_hierarchical_skills=True, quiet=False)

                        mock_hierarchical.assert_called_once()

    def test_upgrade_all_hierarchical_skills_exception(self, mock_config, mock_config_loader):
        """Test handling of exception during hierarchical skill installation."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.utils.hierarchical_skills.install_hierarchical_skills') as mock_hierarchical:
                with patch('devflow.utils.hierarchical_skills.get_hierarchical_skill_statuses') as mock_statuses:
                    with patch('devflow.cli.commands.upgrade_command.console') as mock_console:
                        mock_statuses.return_value = {}
                        mock_hierarchical.side_effect = Exception("Hierarchical skill failed")

                        upgrade_all(upgrade_skills=False, upgrade_hierarchical_skills=True, quiet=False)

                        # Should continue despite exception
                        assert mock_console.print.called

    def test_upgrade_all_quiet_mode(self, mock_config, mock_config_loader):
        """Test quiet mode suppresses output."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_slash_commands') as mock_slash:
                with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_reference_skills') as mock_ref:
                    with patch('devflow.cli.commands.upgrade_command.console') as mock_console:
                        mock_slash.return_value = (["item1"], [], [])
                        mock_ref.return_value = ([], ["item2"], [])

                        upgrade_all(upgrade_skills=True, upgrade_hierarchical_skills=False, quiet=True)

                        # Verify quiet flag passed to install functions
                        assert mock_slash.call_args[1]['quiet'] is True
                        assert mock_ref.call_args[1]['quiet'] is True

    def test_upgrade_all_summary_with_changes(self, mock_config, mock_config_loader):
        """Test summary output when changes are made."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_slash_commands') as mock_slash:
                with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_reference_skills') as mock_ref:
                    with patch('devflow.cli.commands.upgrade_command.console') as mock_console:
                        mock_slash.return_value = (["daf-list", "daf-active"], [], [])
                        mock_ref.return_value = (["gh-cli"], [], [])

                        upgrade_all(upgrade_skills=True, upgrade_hierarchical_skills=False, quiet=False)

                        # Summary should be printed
                        assert mock_console.print.called

    def test_upgrade_all_summary_all_up_to_date(self, mock_config, mock_config_loader):
        """Test summary output when all items are up-to-date."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_slash_commands') as mock_slash:
                with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_reference_skills') as mock_ref:
                    with patch('devflow.cli.commands.upgrade_command.console') as mock_console:
                        mock_slash.return_value = ([], ["daf-list"], [])
                        mock_ref.return_value = ([], ["gh-cli"], [])

                        upgrade_all(upgrade_skills=True, upgrade_hierarchical_skills=False, quiet=False)

                        # Summary should show all up-to-date
                        assert mock_console.print.called

    def test_upgrade_all_summary_with_failures(self, mock_config, mock_config_loader):
        """Test summary output when failures occur."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_slash_commands') as mock_slash:
                with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_reference_skills') as mock_ref:
                    with patch('devflow.cli.commands.upgrade_command.console') as mock_console:
                        mock_slash.return_value = (["daf-list"], [], ["daf-broken"])
                        mock_ref.return_value = ([], [], ["gh-cli-broken"])

                        upgrade_all(upgrade_skills=True, upgrade_hierarchical_skills=False, quiet=False)

                        # Summary should show failures
                        assert mock_console.print.called

    def test_upgrade_all_dry_run_summary(self, mock_config, mock_config_loader):
        """Test dry run summary output."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_slash_commands') as mock_slash:
                with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_reference_skills') as mock_ref:
                    with patch('devflow.cli.commands.upgrade_command.console') as mock_console:
                        mock_slash.return_value = (["daf-list"], [], [])
                        mock_ref.return_value = ([], [], [])

                        upgrade_all(dry_run=True, upgrade_skills=True, upgrade_hierarchical_skills=False, quiet=False)

                        # Dry run message should be shown
                        assert mock_console.print.called

    def test_upgrade_all_locations_displayed(self, mock_config, mock_config_loader):
        """Test that skill locations are displayed in output."""
        with patch('devflow.cli.commands.upgrade_command.ConfigLoader', return_value=mock_config_loader):
            with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_slash_commands') as mock_slash:
                with patch('devflow.cli.commands.upgrade_command.install_or_upgrade_reference_skills') as mock_ref:
                    with patch('devflow.utils.hierarchical_skills.install_hierarchical_skills') as mock_hierarchical:
                        with patch('devflow.utils.hierarchical_skills.get_hierarchical_skill_statuses') as mock_statuses:
                            with patch('devflow.utils.paths.get_cs_home') as mock_cs_home:
                                with patch('devflow.cli.commands.upgrade_command.console') as mock_console:
                                    mock_slash.return_value = ([], [], [])
                                    mock_ref.return_value = ([], [], [])
                                    mock_statuses.return_value = {}
                                    mock_hierarchical.return_value = ([], [], [])
                                    mock_cs_home.return_value = Path("/home/user/.daf-sessions")

                                    upgrade_all(upgrade_skills=True, upgrade_hierarchical_skills=True, quiet=False)

                                    # Both location messages should be printed
                                    assert mock_console.print.called
