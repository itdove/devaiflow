"""Tests for daf config show --paths flag (#512)."""

import json

from click.testing import CliRunner

from devflow.cli.main import cli


def test_paths_outputs_three_lines(temp_daf_home):
    runner = CliRunner()
    result = runner.invoke(cli, ["config", "show", "--paths"])
    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert len(lines) == 3
    assert lines[0].startswith("config_dir=")
    assert lines[1].startswith("data_dir=")
    assert lines[2].startswith("state_dir=")


def test_paths_values_match_path_functions(temp_daf_home):
    from devflow.utils.paths import get_cs_config_home, get_cs_home, get_cs_state_home

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "show", "--paths"])
    assert result.exit_code == 0

    paths = {}
    for line in result.output.strip().split("\n"):
        key, value = line.split("=", 1)
        paths[key] = value

    assert paths["config_dir"] == str(get_cs_config_home())
    assert paths["data_dir"] == str(get_cs_home())
    assert paths["state_dir"] == str(get_cs_state_home())


def test_paths_json_output(temp_daf_home):
    runner = CliRunner()
    result = runner.invoke(cli, ["config", "show", "--paths", "--json"])
    assert result.exit_code == 0

    data = json.loads(result.output)
    assert "config_dir" in data
    assert "data_dir" in data
    assert "state_dir" in data


def test_paths_skips_config_loading(temp_daf_home):
    """--paths should work without loading config (no config.json needed)."""
    import shutil
    config_file = temp_daf_home / "config.json"
    if config_file.exists():
        config_file.unlink()

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "show", "--paths"])
    assert result.exit_code == 0
    assert "config_dir=" in result.output
