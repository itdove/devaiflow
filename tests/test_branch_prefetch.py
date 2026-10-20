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
    @pytest.mark.parametrize("base_branch", [None, "release/old", "feature/current"])
    def test_unavailable_base_recommends_repository_default(
        self, monkeypatch, tmp_path, capsys, base_branch
    ):
        """Prefetch must propose main even when an unrelated branch sorts first."""
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.is_non_interactive", lambda: False
        )
        fetch = Mock()
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.list_remote_branches", fetch
        )
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_default_branch",
            lambda path, remote=None: "main",
        )
        prompt = Mock(side_effect=lambda *args, **kwargs: kwargs["default"])
        monkeypatch.setattr("rich.prompt.Prompt.ask", prompt)
        config = _create_minimal_config_mock(PromptsConfig(auto_select_target_branch=None))

        result = _select_target_branch(
            tmp_path,
            config,
            current_branch="feature/current",
            base_branch=base_branch,
            prefetched_branches={"origin": ["bugfix/other", "feature/current", "main"]},
        )

        assert result == "main"
        assert prompt.call_args.kwargs["default"] == "2"
        assert "2. main (default)" in capsys.readouterr().out
        fetch.assert_not_called()

    @pytest.mark.parametrize("upstream_remote", ["upstream", "parent"])
    @pytest.mark.parametrize("base_branch", ["release/old", "release/current"])
    def test_fork_recommendation_ignores_prefetch_remote_order(
        self, monkeypatch, tmp_path, capsys, upstream_remote, base_branch
    ):
        """Origin-first prefetched data must still recommend the PR destination."""
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.is_non_interactive", lambda: False
        )
        fetch = Mock()
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.list_remote_branches", fetch
        )
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_remote_name_for_url",
            lambda path, url: upstream_remote,
        )
        detect_default = Mock(return_value="trunk")
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_default_branch", detect_default
        )
        prompt = Mock(side_effect=lambda *args, **kwargs: kwargs["default"])
        monkeypatch.setattr("rich.prompt.Prompt.ask", prompt)
        config = _create_minimal_config_mock(PromptsConfig(auto_select_target_branch=None))
        prefetched = {
            "origin": ["bugfix/other", "feature/current", "release/current", "trunk"],
            upstream_remote: ["bugfix/other", "release/current", "trunk"],
        }
        expected_branch = "release/current" if base_branch == "release/current" else "trunk"

        result = _select_target_branch(
            tmp_path,
            config,
            upstream_info={"upstream_url": "https://github.com/parent/repo.git"},
            current_branch="feature/current",
            base_branch=base_branch,
            prefetched_branches=prefetched,
        )

        assert result == f"{upstream_remote}/{expected_branch}"
        detect_default.assert_called_once_with(tmp_path, remote=upstream_remote)
        recommended = [line for line in capsys.readouterr().out.splitlines() if "(default)" in line]
        assert len(recommended) == 1
        assert f"{upstream_remote}/{expected_branch}" in recommended[0]
        assert prefetched["origin"][1] == "feature/current"
        fetch.assert_not_called()

    @pytest.mark.parametrize("use_prefetch", [False, True])
    def test_fork_without_named_remote_resolves_parent_url(
        self, monkeypatch, tmp_path, use_prefetch
    ):
        """A detected parent without a local remote must not use the fork's default."""
        upstream_url = "https://example.com/parent/repo.git"
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.is_non_interactive", lambda: False
        )
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_remote_name_for_url",
            lambda path, url: None,
        )
        fetch = Mock(side_effect=lambda path, remote: ["bugfix/other", "trunk"])
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.list_remote_branches", fetch
        )
        detect_default = Mock(return_value="trunk")
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_default_branch", detect_default
        )
        monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *args, **kwargs: kwargs["default"])
        config = _create_minimal_config_mock(PromptsConfig(auto_select_target_branch=None))

        result = _select_target_branch(
            tmp_path,
            config,
            upstream_info={"upstream_url": upstream_url},
            base_branch="release/old",
            prefetched_branches={"origin": ["bugfix/other", "main"]} if use_prefetch else None,
        )

        assert result == "upstream/trunk"
        detect_default.assert_called_once_with(tmp_path, remote=upstream_url)
        assert fetch.call_args_list[0].args == (tmp_path, upstream_url)
        assert fetch.call_count == (1 if use_prefetch else 2)

    def test_missing_upstream_targets_does_not_recommend_fork_base(
        self, monkeypatch, tmp_path, capsys
    ):
        """A base available only on origin is not a recommendation for an upstream PR."""
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.is_non_interactive", lambda: False
        )
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_remote_name_for_url",
            lambda path, url: "upstream",
        )
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_default_branch",
            lambda path, remote=None: "trunk",
        )
        prompt = Mock(side_effect=lambda *args, **kwargs: kwargs["default"])
        monkeypatch.setattr("rich.prompt.Prompt.ask", prompt)
        config = _create_minimal_config_mock(PromptsConfig(auto_select_target_branch=None))

        result = _select_target_branch(
            tmp_path,
            config,
            upstream_info={"upstream_url": "https://example.com/parent/repo.git"},
            base_branch="release/current",
            prefetched_branches={
                "origin": ["bugfix/other", "main", "release/current"],
                "upstream": [],
            },
        )

        assert result is None
        assert prompt.call_args.kwargs["default"] == "4"
        assert "(default)" not in capsys.readouterr().out

    def test_prefetch_hit_skips_sync_fetch(self, monkeypatch):
        """When prefetched_branches provided, list_remote_branches should NOT be called."""
        call_count = {"n": 0}

        def mock_list(path, remote):
            call_count["n"] += 1
            return ["should-not-be-called"]

        monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.list_remote_branches", mock_list)
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_default_branch",
            lambda p, remote=None: "main",
        )

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
        monkeypatch.setattr("devflow.cli.commands.complete_command.is_non_interactive", lambda **kw: False)

        call_count = {"n": 0}

        def mock_list(path, remote):
            call_count["n"] += 1
            return ["main", "develop"]

        monkeypatch.setattr("devflow.cli.commands.complete_command.GitUtils.list_remote_branches", mock_list)
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_default_branch",
            lambda p, remote=None: "main",
        )

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
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_default_branch",
            lambda p, remote=None: "main",
        )

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
        monkeypatch.setattr(
            "devflow.cli.commands.complete_command.GitUtils.get_default_branch",
            lambda p, remote=None: "main",
        )

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
