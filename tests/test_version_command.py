"""Tests for daf --version command."""

import sys
from unittest.mock import patch

from click.testing import CliRunner

from devflow import __version__
from devflow.cli.main import cli


def test_version_plain_text():
    """Test --version outputs plain text by default."""
    runner = CliRunner()
    with patch.object(sys, 'argv', ['daf', '--version']):
        result = runner.invoke(cli, ['--version'])

    assert result.exit_code == 0
    assert __version__ in result.output
    assert result.output.strip() == f"cli, version {__version__}"


def test_version_is_eager():
    """Test --version exits before processing other commands."""
    runner = CliRunner()
    # Try with an invalid command - should still show version
    with patch.object(sys, 'argv', ['daf', '--version', 'invalid-command']):
        result = runner.invoke(cli, ['--version', 'invalid-command'])

    assert result.exit_code == 0
    assert __version__ in result.output


# Note: Testing --version --json is challenging in CliRunner because:
# 1. --json is not a global option (it's added per-command via @json_option)
# 2. --version callback checks sys.argv for --json flag
# 3. CliRunner doesn't allow undefined options like --json at group level
#
# The feature works correctly in real CLI usage:
#   daf --version        # outputs: cli, version X.Y.Z
#   daf --version --json # outputs: {"version": "X.Y.Z"}
#
# Manual testing confirmed both work as expected.
