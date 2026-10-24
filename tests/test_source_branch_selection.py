"""Tests for source branch selection and remote default discovery (#524, #638)."""

import io
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from devflow.cli.commands.new_command import (
    _get_default_source_branch,
    _get_source_remote,
    _handle_branch_creation,
    _prompt_for_source_branch,
    _prompt_for_source_branch_text,
)
from devflow.git.utils import GitUtils


class TestPromptForSourceBranch:
    """Tests for _prompt_for_source_branch numbered list."""

    @pytest.fixture(autouse=True)
    def origin_remote(self, monkeypatch):
        """Keep menu tests independent of the host repository's remotes."""
        monkeypatch.setattr(GitUtils, "get_remote_names", Mock(return_value=["origin"]))

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "list_remote_branches")
    def test_shows_numbered_list_and_selects_branch(self, mock_branches, mock_prompt):
        """User selects a branch by number from the list."""
        mock_branches.return_value = ["dev/1.14.0", "main", "release-1.13"]
        mock_prompt.return_value = "2"

        result = _prompt_for_source_branch(Path("/repo"), "main")

        assert result == "origin/main"
        mock_prompt.assert_called_once()
        call_kwargs = mock_prompt.call_args
        assert call_kwargs[1]["default"] == "2"  # main is index 2, should be default

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "list_remote_branches")
    def test_selects_non_default_branch(self, mock_branches, mock_prompt):
        """User selects a branch that is not the default."""
        mock_branches.return_value = ["dev/1.14.0", "main", "release-1.13"]
        mock_prompt.return_value = "1"

        result = _prompt_for_source_branch(Path("/repo"), "main")

        assert result == "origin/dev/1.14.0"

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "list_remote_branches")
    def test_cancel_returns_none(self, mock_branches, mock_prompt):
        """User selects cancel option."""
        mock_branches.return_value = ["main", "develop"]
        mock_prompt.return_value = "4"  # cancel = len(branches) + 2 = 4

        result = _prompt_for_source_branch(Path("/repo"), "main")

        assert result is None

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "list_remote_branches")
    @patch.object(GitUtils, "branch_exists", return_value=True)
    def test_custom_branch_falls_back_to_text(self, mock_exists, mock_branches, mock_prompt):
        """User selects custom branch option, then types branch name."""
        mock_branches.return_value = ["main", "develop"]
        # First call: select custom (option 3 = len + 1)
        # Second call: type branch name
        mock_prompt.side_effect = ["3", "feature/custom"]

        result = _prompt_for_source_branch(Path("/repo"), "main")

        assert result == "feature/custom"
        assert mock_prompt.call_count == 2

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "list_remote_branches")
    @patch.object(GitUtils, "branch_exists", return_value=True)
    def test_falls_back_to_text_when_no_remote_branches(
        self, mock_exists, mock_branches, mock_prompt
    ):
        """Falls back to text input when no remote branches found."""
        mock_branches.return_value = []
        mock_prompt.return_value = "main"

        result = _prompt_for_source_branch(Path("/repo"), "main")

        assert result == "main"
        mock_prompt.assert_called_once_with("Enter source branch", default="main")

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "list_remote_branches")
    @pytest.mark.parametrize("default_base", [None, "main", "origin/main"])
    def test_unavailable_default_selects_cancel(
        self, mock_branches, mock_prompt, default_base, capsys
    ):
        """An unavailable default never silently selects the first branch."""
        mock_branches.return_value = ["develop", "staging"]
        mock_prompt.side_effect = lambda *args, **kwargs: kwargs["default"]

        result = _prompt_for_source_branch(Path("/repo"), default_base)

        assert result is None
        assert mock_prompt.call_args.kwargs["default"] == "4"
        output = capsys.readouterr().out
        assert "4. Cancel (default)" in output
        assert "Enter cancels" in output

    @pytest.mark.parametrize("default_base", ["origin/main", "refs/remotes/origin/main"])
    def test_qualified_default_matches_unqualified_menu(self, default_base, capsys):
        """Qualified refs match only the selected remote's branch names."""
        with (
            patch.object(GitUtils, "list_remote_branches", return_value=["develop", "main"]),
            patch("sys.stdin", io.StringIO("\n")),
        ):
            result = _prompt_for_source_branch(Path("/repo"), default_base)

        assert result == "origin/main"
        assert "2. main (default)" in capsys.readouterr().out

    def test_explicit_number_still_works_without_default(self):
        """Users can explicitly select any branch even when Enter would cancel."""
        with (
            patch.object(GitUtils, "list_remote_branches", return_value=["develop", "staging"]),
            patch("devflow.cli.commands.new_command.Prompt.ask", return_value="1"),
        ):
            assert _prompt_for_source_branch(Path("/repo"), None) == "origin/develop"


class TestPromptForSourceBranchText:
    """Tests for _prompt_for_source_branch_text fallback."""

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "branch_exists", return_value=True)
    def test_accepts_valid_branch(self, mock_exists, mock_prompt):
        """Accepts a valid branch name."""
        mock_prompt.return_value = "develop"

        result = _prompt_for_source_branch_text(Path("/repo"), "main")

        assert result == "develop"

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    def test_cancel_returns_none(self, mock_prompt):
        """Returns None when user types cancel."""
        mock_prompt.return_value = "cancel"

        result = _prompt_for_source_branch_text(Path("/repo"), "main")

        assert result is None

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "branch_exists")
    def test_retries_on_invalid_then_accepts_valid(self, mock_exists, mock_prompt):
        """Retries when branch doesn't exist, accepts when valid."""
        mock_exists.side_effect = [False, True]
        mock_prompt.side_effect = ["nonexistent", "main"]

        with patch("devflow.cli.commands.new_command._show_branch_suggestions"):
            result = _prompt_for_source_branch_text(Path("/repo"), "main")

        assert result == "main"
        assert mock_prompt.call_count == 2

    def test_no_default_enter_cancels(self, monkeypatch):
        """Text fallback requires an explicit source when no default is known."""
        monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
        assert _prompt_for_source_branch_text(Path("/repo"), None) is None

    def test_custom_remote_branch_without_local_branch(self, monkeypatch):
        """Custom entry supports a remote-qualified branch without a local ref."""
        monkeypatch.setattr(GitUtils, "branch_exists", Mock(return_value=False))
        monkeypatch.setattr(GitUtils, "get_remote_names", Mock(return_value=["origin", "upstream"]))
        branches = Mock(return_value=["feature/custom"])
        monkeypatch.setattr(GitUtils, "list_remote_branches", branches)
        monkeypatch.setattr("sys.stdin", io.StringIO("upstream/feature/custom\n"))

        result = _prompt_for_source_branch_text(Path("/repo"), "origin/main")

        assert result == "upstream/feature/custom"
        branches.assert_called_once_with(Path("/repo"), "upstream")


@pytest.mark.parametrize(
    ("remotes", "branch", "expected"),
    [
        ([], None, None),
        (["origin"], None, "origin"),
        (["origin", "upstream"], None, "upstream"),
        (["secondary", "primary"], None, "primary"),
        (["origin", "upstream"], "origin/release/stable", "origin"),
        (["origin", "upstream"], "refs/remotes/upstream/main", "upstream"),
        (["origin"], "release/stable", "origin"),
        (["parent", "parent/team"], "parent/team/release/stable", "parent/team"),
    ],
)
def test_source_remote_identity(monkeypatch, remotes, branch, expected):
    """Only configured prefixes qualify a branch; the longest prefix wins."""
    monkeypatch.setattr(GitUtils, "get_remote_names", Mock(return_value=remotes))
    assert _get_source_remote(Path("/repo"), branch) == expected


@pytest.mark.parametrize(
    ("remote_default", "local_branch"),
    [("release/stable", "main"), ("main", "feature/task")],
)
def test_default_discovery_through_selection(monkeypatch, capsys, remote_default, local_branch):
    """Remote HEAD beats local main and a current feature branch in both bug reproductions."""
    path = Path("/repo")
    monkeypatch.setattr(GitUtils, "get_remote_names", Mock(return_value=["origin"]))
    default = Mock(return_value=remote_default)
    monkeypatch.setattr(GitUtils, "get_default_branch", default)
    local_exists = Mock(side_effect=lambda path, branch: branch == local_branch)
    monkeypatch.setattr(GitUtils, "branch_exists", local_exists)
    monkeypatch.setattr(GitUtils, "get_current_branch", Mock(return_value=local_branch))
    branches = Mock(return_value=["develop", "main", "release/stable"])
    monkeypatch.setattr(GitUtils, "list_remote_branches", branches)
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))

    suggested = _get_default_source_branch(path)
    selected = _prompt_for_source_branch(path, suggested)

    assert suggested == selected == f"origin/{remote_default}"
    default.assert_called_once_with(path, remote="origin")
    branches.assert_called_once_with(path, "origin")
    local_exists.assert_not_called()
    assert f"{remote_default} (default)" in capsys.readouterr().out


@pytest.mark.parametrize("qualified_default", [None, "upstream/release/stable", "origin/main"])
def test_fork_defaults_and_menu_use_same_remote(monkeypatch, qualified_default, capsys):
    """Upstream discovery and explicit origin suggestions never match the other remote."""
    path = Path("/repo")
    monkeypatch.setattr(GitUtils, "get_remote_names", Mock(return_value=["origin", "upstream"]))
    defaults = {"upstream": "release/stable", "origin": "main"}
    default = Mock(side_effect=lambda path, remote: defaults[remote])
    monkeypatch.setattr(GitUtils, "get_default_branch", default)
    branches = Mock(side_effect=lambda path, remote: ["develop", defaults[remote]])
    monkeypatch.setattr(GitUtils, "list_remote_branches", branches)
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))

    suggested = qualified_default or _get_default_source_branch(path)
    selected = _prompt_for_source_branch(path, suggested)

    assert selected == suggested
    remote = suggested.split("/", 1)[0]
    branches.assert_called_once_with(path, remote)
    assert f"Available branches on {remote}" in capsys.readouterr().out
    if qualified_default is None:
        default.assert_called_once_with(path, remote="upstream")


def test_unresolved_remote_default_does_not_guess_local_main(monkeypatch):
    """A failed remote HEAD lookup must not turn a local guess into the remote default."""
    monkeypatch.setattr(GitUtils, "get_remote_names", Mock(return_value=["origin"]))
    monkeypatch.setattr(GitUtils, "get_default_branch", Mock(return_value=None))
    local_exists = Mock(return_value=True)
    monkeypatch.setattr(GitUtils, "branch_exists", local_exists)
    current = Mock(return_value="main")
    monkeypatch.setattr(GitUtils, "get_current_branch", current)

    assert _get_default_source_branch(Path("/repo")) is None
    local_exists.assert_not_called()
    current.assert_not_called()


@pytest.mark.parametrize(
    ("local_default", "current", "expected"),
    [
        ("main", "feature/task", "main"),
        (None, "feature/task", "feature/task"),
        (None, "HEAD", None),
    ],
)
def test_local_only_default_fallback(monkeypatch, local_default, current, expected):
    """Local-only repositories use a local base or attached HEAD, never detached HEAD."""
    monkeypatch.setattr(GitUtils, "get_remote_names", Mock(return_value=[]))
    monkeypatch.setattr(GitUtils, "get_default_branch", Mock(return_value=local_default))
    monkeypatch.setattr(GitUtils, "get_current_branch", Mock(return_value=current))
    assert _get_default_source_branch(Path("/repo")) == expected


@pytest.mark.parametrize("remote_default", ["main", None])
@pytest.mark.parametrize("mode", ["auto", "non-interactive", "json"])
@pytest.mark.parametrize("remote", ["origin", "upstream"])
def test_non_interactive_default_resolution(monkeypatch, remote_default, mode, remote, capsys):
    """Automatic modes use the remote default or decline creation without prompting."""
    path = Path("/repo")
    values = {
        "is_git_repository": True,
        "has_uncommitted_changes": False,
        "get_remote_names": ["origin"] if remote == "origin" else ["origin", "upstream"],
        "get_default_branch": remote_default,
        "get_current_branch": "feature/task",
        "generate_branch_name": "test-task",
        "branch_exists": False,
        "fetch_origin": (True, None),
        "fetch_remote": (True, None),
        "checkout_branch": (True, None),
        "create_branch": (True, None),
    }
    mocks = {name: Mock(return_value=value) for name, value in values.items()}
    for name, mock in mocks.items():
        monkeypatch.setattr(GitUtils, name, mock)
    prompt = Mock(side_effect=AssertionError("Unexpected prompt"))
    monkeypatch.setattr("devflow.cli.commands.new_command.Prompt.ask", prompt)
    monkeypatch.setattr("devflow.cli.commands.new_command.Confirm.ask", prompt)
    monkeypatch.setattr("devflow.cli.commands.new_command.is_json_mode", lambda: mode == "json")
    monkeypatch.setattr("devflow.cli.utils.is_json_mode", lambda: mode == "json")

    result = _handle_branch_creation(
        str(path),
        "PROJ-638",
        "Test task",
        config=Mock(),
        auto_from_default=mode == "auto",
        non_interactive=mode == "non-interactive",
    )

    prompt.assert_not_called()
    mocks["get_default_branch"].assert_called_once_with(path, remote=remote)
    if remote_default:
        assert result == ("test-task", f"{remote}/main")
        mocks["checkout_branch"].assert_called_once_with(path, f"{remote}/main")
        if remote == "upstream":
            mocks["fetch_remote"].assert_called_once_with(path, "upstream")
            mocks["fetch_origin"].assert_not_called()
        else:
            mocks["fetch_origin"].assert_called_once_with(path)
    else:
        assert result is None
        mocks["fetch_origin"].assert_not_called()
        mocks["fetch_remote"].assert_not_called()
        mocks["checkout_branch"].assert_not_called()
        mocks["create_branch"].assert_not_called()
    if mode == "json":
        assert capsys.readouterr().out == ""


@pytest.mark.parametrize("source", ["feature/custom", "origin/release/stable", "upstream/develop"])
def test_explicit_source_bypasses_default_discovery(monkeypatch, source):
    """An explicit source remains usable even when default discovery would fail."""
    path = Path("/repo")
    for name, value in {
        "is_git_repository": True,
        "has_uncommitted_changes": False,
        "get_remote_names": ["origin", "upstream"],
        "get_current_branch": "feature/task",
        "branch_exists": False,
        "fetch_origin": (True, None),
        "fetch_remote": (True, None),
        "checkout_branch": (True, None),
        "create_branch": (True, None),
    }.items():
        monkeypatch.setattr(GitUtils, name, Mock(return_value=value))
    default = Mock(side_effect=AssertionError("Explicit sources must not resolve a default"))
    monkeypatch.setattr(GitUtils, "get_default_branch", default)
    prompt = Mock(side_effect=AssertionError("Unexpected prompt"))
    monkeypatch.setattr("devflow.cli.commands.new_command.Prompt.ask", prompt)
    monkeypatch.setattr("devflow.cli.commands.new_command.Confirm.ask", prompt)

    result = _handle_branch_creation(
        str(path),
        "PROJ-638",
        "Test task",
        config=Mock(),
        source_branch=source,
        branch_name="test-task",
        non_interactive=True,
    )

    assert result == ("test-task", source)
    default.assert_not_called()
    prompt.assert_not_called()
    if source.startswith("upstream/"):
        GitUtils.fetch_remote.assert_called_once_with(path, "upstream")
        GitUtils.fetch_origin.assert_not_called()
    else:
        GitUtils.fetch_origin.assert_called_once_with(path)
        GitUtils.fetch_remote.assert_not_called()


@pytest.mark.parametrize("command", ["new", "open"])
@pytest.mark.parametrize("interactive", [True, False])
def test_multi_project_missing_default_cancels_before_creating_any_branch(
    monkeypatch, capsys, command, interactive
):
    """A missing base in any project cannot cause partial or arbitrary branch creation."""
    from devflow.cli.commands.new_command_multiproject import (
        create_multi_project_session,
    )
    from devflow.cli.commands.open_command import (
        _create_multi_project_conversation_for_open,
    )

    monkeypatch.setattr(
        "devflow.cli.commands.new_command._get_default_source_branch",
        Mock(side_effect=["origin/main", None]),
    )
    selection = Mock(side_effect=lambda path, default: default)
    monkeypatch.setattr("devflow.cli.commands.new_command._prompt_for_source_branch", selection)
    monkeypatch.setattr(
        "devflow.cli.commands.new_command.Prompt.ask", Mock(return_value="test-task")
    )
    create = Mock(side_effect=AssertionError("Must collect valid bases before creating branches"))
    monkeypatch.setattr("devflow.cli.commands.new_command._handle_branch_creation", create)
    config = SimpleNamespace(prompts=SimpleNamespace(use_issue_key_as_branch=True))
    manager = Mock()
    kwargs = {
        "project_names": ["project-a", "project-b"],
        "workspace_path": "/workspace",
        "config": config,
        "config_loader": Mock(),
        "session_manager": manager,
    }
    if command == "new":
        with pytest.raises(SystemExit) as exc:
            create_multi_project_session(
                **kwargs,
                name="test-session",
                goal="Test task",
                issue_key=None,
                issue_metadata_dict=None,
                issue_title=None,
                selected_workspace_name="workspace-1",
                force_new_session=False,
                model_profile=None,
                output_json=not interactive,
                non_interactive=not interactive,
            )
        assert exc.value.code == 1
        output = capsys.readouterr().out
        if not interactive:
            assert json.loads(output)["error"]["code"] == "NO_SOURCE_BRANCH"
    else:
        session = SimpleNamespace(name="test-session", issue_key=None, goal="Test task")
        assert (
            _create_multi_project_conversation_for_open(
                **kwargs,
                session=session,
                create_branch=True if not interactive else None,
            )
            is False
        )
    create.assert_not_called()
    manager.create_session.assert_not_called()
    assert selection.call_count == (2 if interactive else 0)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
@pytest.mark.parametrize(
    ("remote_default", "local_branch"),
    [("release/stable", "main"), ("main", "feature/task")],
)
@pytest.mark.parametrize("source_remote", ["origin", "upstream"])
def test_open_style_branch_creation_accepts_real_remote_default(
    tmp_path, monkeypatch, capsys, remote_default, local_branch, source_remote
):
    """Exercise actual Git HEAD discovery, Enter prompts, and branch creation together."""
    remote = tmp_path / "remote.git"
    path = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "--bare", "-b", remote_default, str(remote)],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "init", "-b", local_branch, str(path)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "Initial"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=path, check=True)
    if source_remote == "upstream":
        subprocess.run(["git", "remote", "add", "upstream", str(remote)], cwd=path, check=True)
    for branch in ["develop", "main", "release/stable"]:
        subprocess.run(
            ["git", "push", source_remote, f"HEAD:refs/heads/{branch}"],
            cwd=path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "update-ref", "-d", f"refs/remotes/{source_remote}/{branch}"],
            cwd=path,
            check=True,
        )
    assert not GitUtils.branch_exists(path, remote_default)
    monkeypatch.setattr("sys.stdin", io.StringIO("\n\n\n"))
    config = SimpleNamespace(prompts=SimpleNamespace(use_issue_key_as_branch=True))
    monkeypatch.setattr(
        "devflow.cli.commands.new_command.detect_backend_from_key", lambda *args: "jira"
    )

    result = _handle_branch_creation(str(path), "PROJ-638", "Test task", config=config)

    assert result == ("proj-638", f"{source_remote}/{remote_default}")
    assert GitUtils.get_current_branch(path) == "proj-638"
    assert (
        GitUtils.get_current_commit_sha(path)
        == subprocess.run(
            ["git", "rev-parse", f"refs/remotes/{source_remote}/{remote_default}"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    assert f"{remote_default} (default)" in capsys.readouterr().out
