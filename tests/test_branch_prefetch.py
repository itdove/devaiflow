"""Tests for async branch prefetch functionality (Issue #531)."""

from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from devflow.cli.commands.complete_command import (
    BranchPrefetch,
    BranchPrefetchResult,
    _select_target_branch,
    _start_branch_prefetch,
)
from devflow.config.models import PromptsConfig
from devflow.git.utils import GitUtils


def _create_minimal_config_mock(prompts_config=None):
    config = Mock()
    config.prompts = prompts_config or PromptsConfig()
    return config


# --- GitUtils.has_upstream_remote ---

class TestHasUpstreamRemote:
    def test_returns_true_when_upstream_exists(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            return result

        monkeypatch.setattr("devflow.git.utils.subprocess.run", mock_run)
        assert GitUtils.has_upstream_remote(Path("/repo")) is True

    def test_returns_false_when_no_upstream(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 128
            return result

        monkeypatch.setattr("devflow.git.utils.subprocess.run", mock_run)
        assert GitUtils.has_upstream_remote(Path("/repo")) is False

    def test_handles_timeout(self, monkeypatch):
        import subprocess
        def mock_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 2)

        monkeypatch.setattr("devflow.git.utils.subprocess.run", mock_run)
        assert GitUtils.has_upstream_remote(Path("/repo")) is False


# --- BranchPrefetchResult ---

class TestBranchPrefetchResult:
    def test_defaults(self):
        result = BranchPrefetchResult()
        assert result.remote_branches == {}
        assert result.upstream_info is None
        assert result.completed is False


# --- BranchPrefetch ---

class TestBranchPrefetch:
    def test_resolve_origin_only(self):
        executor = ThreadPoolExecutor(max_workers=1)
        origin_future = executor.submit(lambda: ["main", "develop"])
        prefetch = BranchPrefetch(origin_future, None, None, executor)

        result = prefetch.resolve(timeout=5.0)

        assert result.completed is True
        assert result.remote_branches == {"origin": ["main", "develop"]}
        assert result.upstream_info is None

    def test_resolve_origin_and_upstream(self):
        executor = ThreadPoolExecutor(max_workers=3)
        origin_future = executor.submit(lambda: ["main", "develop"])
        upstream_future = executor.submit(lambda: ["main", "release/3.0"])
        fork_info = {"upstream_url": "https://github.com/parent/repo.git"}
        fork_future = executor.submit(lambda: fork_info)

        prefetch = BranchPrefetch(origin_future, upstream_future, fork_future, executor)
        result = prefetch.resolve(timeout=5.0)

        assert result.completed is True
        assert result.remote_branches == {
            "origin": ["main", "develop"],
            "upstream": ["main", "release/3.0"],
        }
        assert result.upstream_info == fork_info

    def test_resolve_handles_origin_failure(self):
        executor = ThreadPoolExecutor(max_workers=1)
        origin_future = executor.submit(lambda: (_ for _ in ()).throw(RuntimeError("network error")))
        prefetch = BranchPrefetch(origin_future, None, None, executor)

        result = prefetch.resolve(timeout=5.0)

        assert result.completed is True
        assert result.remote_branches == {}

    def test_resolve_handles_upstream_failure(self):
        executor = ThreadPoolExecutor(max_workers=2)
        origin_future = executor.submit(lambda: ["main"])
        upstream_future = executor.submit(lambda: (_ for _ in ()).throw(RuntimeError("timeout")))
        prefetch = BranchPrefetch(origin_future, upstream_future, None, executor)

        result = prefetch.resolve(timeout=5.0)

        assert result.completed is True
        assert result.remote_branches == {"origin": ["main"]}

    def test_resolve_skips_empty_results(self):
        executor = ThreadPoolExecutor(max_workers=2)
        origin_future = executor.submit(lambda: [])
        upstream_future = executor.submit(lambda: [])
        prefetch = BranchPrefetch(origin_future, upstream_future, None, executor)

        result = prefetch.resolve(timeout=5.0)

        assert result.completed is True
        assert result.remote_branches == {}


# --- _start_branch_prefetch ---

class TestStartBranchPrefetch:
    def test_starts_origin_only_no_upstream(self, monkeypatch):
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.has_upstream_remote",
            lambda path: False,
        )
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.list_remote_branches",
            lambda path, remote: ["main", "develop"],
        )

        prefetch = _start_branch_prefetch(Path("/repo"))
        result = prefetch.resolve(timeout=5.0)

        assert result.remote_branches == {"origin": ["main", "develop"]}
        assert result.upstream_info is None

    def test_starts_both_remotes_when_upstream_exists(self, monkeypatch):
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.has_upstream_remote",
            lambda path: True,
        )

        def mock_list(path, remote):
            if remote == "origin":
                return ["feature-1"]
            elif remote == "upstream":
                return ["main", "release/3.0"]
            return []

        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.list_remote_branches",
            mock_list,
        )
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_fork_upstream_info",
            lambda path, prompt_for_remote: {"upstream_url": "https://github.com/parent/repo.git"},
        )

        prefetch = _start_branch_prefetch(Path("/repo"))
        result = prefetch.resolve(timeout=5.0)

        assert result.remote_branches == {
            "origin": ["feature-1"],
            "upstream": ["main", "release/3.0"],
        }
        assert result.upstream_info is not None


# --- _select_target_branch with prefetched_branches ---

class TestSelectTargetBranchPrefetch:
    def test_prefetch_hit_skips_sync_fetch(self, monkeypatch):
        """When prefetched_branches provided, list_remote_branches should NOT be called."""
        call_count = {"n": 0}

        def mock_list(path, remote):
            call_count["n"] += 1
            return ["should-not-be-called"]

        monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.list_remote_branches", mock_list)
        monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", lambda p: "main")

        def mock_prompt(prompt_text, choices, default):
            return "1"

        monkeypatch.setattr("rich.prompt.Prompt.ask", mock_prompt)

        config = _create_minimal_config_mock(prompts_config=PromptsConfig(auto_select_target_branch=None))

        result = _select_target_branch(
            Path("/repo"), config,
            prefetched_branches={"origin": ["main", "develop"]},
        )

        assert call_count["n"] == 0
        assert result == "main"

    def test_prefetch_miss_falls_back_to_sync(self, monkeypatch):
        """When prefetched_branches is None, list_remote_branches should be called."""
        call_count = {"n": 0}

        def mock_list(path, remote):
            call_count["n"] += 1
            return ["main", "develop"]

        monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.list_remote_branches", mock_list)
        monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", lambda p: "main")

        def mock_prompt(prompt_text, choices, default):
            return "1"

        monkeypatch.setattr("rich.prompt.Prompt.ask", mock_prompt)

        config = _create_minimal_config_mock(prompts_config=PromptsConfig(auto_select_target_branch=None))

        result = _select_target_branch(Path("/repo"), config, prefetched_branches=None)

        assert call_count["n"] == 1
        assert result == "main"

    def test_prefetch_empty_returns_none(self, monkeypatch):
        """When prefetched_branches is empty dict, should handle gracefully."""
        config = _create_minimal_config_mock(prompts_config=PromptsConfig(auto_select_target_branch=None))

        result = _select_target_branch(Path("/repo"), config, prefetched_branches={})

        assert result is None

    def test_prefetch_fork_with_nonstandard_remote_name(self, monkeypatch):
        """When fork's upstream remote has a non-standard name, falls back to sync for that remote."""
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_remote_name_for_url",
            lambda path, url: "parent",
        )
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.list_remote_branches",
            lambda path, remote: ["main", "release/3.0"] if remote == "parent" else [],
        )
        monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", lambda p: "main")

        def mock_prompt(prompt_text, choices, default):
            return "1"

        monkeypatch.setattr("rich.prompt.Prompt.ask", mock_prompt)

        config = _create_minimal_config_mock(prompts_config=PromptsConfig(auto_select_target_branch=None))

        upstream_info = {"upstream_url": "https://github.com/parent/repo.git"}
        result = _select_target_branch(
            Path("/repo"), config,
            upstream_info=upstream_info,
            prefetched_branches={"origin": ["feature-1"]},
        )

        assert result is not None

    def test_prefetch_fork_standard_name_no_extra_fetch(self, monkeypatch):
        """When fork upstream is named 'upstream' and already in prefetch, no extra sync fetch."""
        call_count = {"n": 0}

        def mock_list(path, remote):
            call_count["n"] += 1
            return []

        monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.list_remote_branches", mock_list)
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_remote_name_for_url",
            lambda path, url: "upstream",
        )
        monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.get_default_branch", lambda p: "main")

        def mock_prompt(prompt_text, choices, default):
            return "1"

        monkeypatch.setattr("rich.prompt.Prompt.ask", mock_prompt)

        config = _create_minimal_config_mock(prompts_config=PromptsConfig(auto_select_target_branch=None))

        upstream_info = {"upstream_url": "https://github.com/parent/repo.git"}
        result = _select_target_branch(
            Path("/repo"), config,
            upstream_info=upstream_info,
            prefetched_branches={"origin": ["feature-1"], "upstream": ["main", "develop"]},
        )

        assert call_count["n"] == 0
