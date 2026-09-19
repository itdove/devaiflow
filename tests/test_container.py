"""Tests for the DevAIFlow OpenShell-compatible container contract."""

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTAINER_DIR = REPO_ROOT / "container"
DOCKERFILE = CONTAINER_DIR / "Dockerfile.openshell"
RUNNER = CONTAINER_DIR / "run.sh"
SMOKE_TEST = CONTAINER_DIR / "smoke-test.sh"
GITHUB_POLICY = CONTAINER_DIR / "openshell-github-readwrite-policy.yaml"


def _capture_engine(path: Path) -> Path:
    """Create a fake container engine that records its arguments."""
    path.write_text(
        '#!/usr/bin/env bash\n'
        'printf \'%s\\n\' "$@" > "$CAPTURE"\n'
        'if [[ -n "${CAPTURE_ENV:-}" ]]; then\n'
        '    {\n'
        '        printf "HOME=%s\\n" "${HOME-<unset>}"\n'
        '        printf "XDG_DATA_HOME=%s\\n" "${XDG_DATA_HOME-<unset>}"\n'
        '        printf "XDG_CONFIG_HOME=%s\\n" "${XDG_CONFIG_HOME-<unset>}"\n'
        '        printf "XDG_STATE_HOME=%s\\n" "${XDG_STATE_HOME-<unset>}"\n'
        '        printf "XDG_CACHE_HOME=%s\\n" "${XDG_CACHE_HOME-<unset>}"\n'
        '    } > "$CAPTURE_ENV"\n'
        'fi\n',
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _clean_launcher_env(tmp_path: Path, engine: Path, capture: Path) -> dict[str, str]:
    """Return an isolated environment for launcher argument tests."""
    env = os.environ.copy()
    for name in (
        "DEVAIFLOW_HOME",
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_STATE_HOME",
        "XDG_CACHE_HOME",
        "DEVAIFLOW_IMAGE",
        "DEVAIFLOW_VOLUME_SUFFIX",
        "AI_GUARDIAN_AGENT",
        "AI_GUARDIAN_IDE",
        "AI_GUARDIAN_REST_PORT",
        "AI_GUARDIAN_PROFILE",
        "AI_GUARDIAN_SETUP_SCOPE",
        "CONTAINER_ENGINE_HOME",
        "CONTAINER_ENGINE_XDG_DATA_HOME",
        "CONTAINER_ENGINE_XDG_CONFIG_HOME",
        "CONTAINER_ENGINE_XDG_STATE_HOME",
        "CONTAINER_ENGINE_XDG_CACHE_HOME",
        "CAPTURE_ENV",
    ):
        env.pop(name, None)
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "CONTAINER_ENGINE": str(engine),
            "CAPTURE": str(capture),
        }
    )
    Path(env["HOME"]).mkdir()
    return env


def _flag_values(args: list[str], flag: str) -> list[str]:
    """Return values following a repeated command-line flag."""
    return [
        args[index + 1]
        for index, value in enumerate(args[:-1])
        if value == flag
    ]


def _run_launcher(env: dict[str, str], *args: str) -> list[str]:
    """Run the launcher against a fake engine and return captured arguments."""
    result = subprocess.run(
        ["bash", str(RUNNER), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return Path(env["CAPTURE"]).read_text(encoding="utf-8").splitlines()


def test_openshell_dockerfile_uses_pinned_ai_guardian_and_daf_base():
    """The image derives from AI Guardian and pins its PyPI fallback."""
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert (
        "ARG BASE_IMAGE=quay.io/redhatproductsecurity/ai-guardian-openshell:latest"
        in dockerfile
    )
    assert "FROM ${BASE_IMAGE}" in dockerfile
    version_match = re.search(
        r"^ARG DEVAIFLOW_VERSION=(?P<version>[^\s]+)$",
        dockerfile,
        flags=re.MULTILINE,
    )
    assert version_match
    assert version_match.group("version") == "2.2.0"
    assert 'ARG DEVAIFLOW_WHEEL=""' in dockerfile
    assert '"devaiflow==${DEVAIFLOW_VERSION}"' in dockerfile
    assert 'uv pip install --python /sandbox/.venv/bin/python "${wheel}"' in dockerfile
    assert "ai-guardian.support-image=true" in dockerfile
    assert "COPY openshell-github-readwrite-policy.yaml" in dockerfile
    assert "/usr/share/devaiflow/openshell-github-readwrite-policy.yaml" in dockerfile


def test_github_readwrite_policy_is_narrow_and_credential_free():
    """The bundled overlay grants only GitHub API and smart-HTTP access."""
    policy = GITHUB_POLICY.read_text(encoding="utf-8")

    assert "host: api.github.com" in policy
    assert "access: read-write" in policy
    assert 'path: "/**/git-upload-pack"' in policy
    assert 'path: "/**/git-receive-pack"' in policy
    assert "GITHUB_TOKEN" not in policy
    assert "Authorization" not in policy


def test_openshell_dockerfile_creates_writable_xdg_layout():
    """The image creates and owns every container-side DAF XDG directory."""
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    expected_paths = (
        "/sandbox/.config/devaiflow",
        "/sandbox/.local/share/devaiflow",
        "/sandbox/.local/state/devaiflow",
        "/sandbox/.cache/devaiflow",
    )
    for path in expected_paths:
        assert path in dockerfile
    assert "chown -R sandbox:sandbox" in dockerfile
    assert "XDG_DATA_HOME=/sandbox/.local/share" in dockerfile
    assert "XDG_CONFIG_HOME=/sandbox/.config" in dockerfile
    assert "XDG_STATE_HOME=/sandbox/.local/state" in dockerfile
    assert "XDG_CACHE_HOME=/sandbox/.cache" in dockerfile
    assert "ln -s /sandbox/.local/share/devaiflow /sandbox/.daf-sessions" in dockerfile


@pytest.mark.skipif(os.name == "nt", reason="The launcher is a POSIX shell script")
def test_container_scripts_are_valid_and_executable():
    """The launcher and smoke test are executable and syntactically valid."""
    for script in (RUNNER, SMOKE_TEST):
        result = subprocess.run(
            ["bash", "-n", str(script)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert os.access(script, os.X_OK)


def test_launcher_mounts_only_final_xdg_directories(tmp_path):
    """Fresh hosts receive four narrow mounts and container-local XDG roots."""
    engine = _capture_engine(tmp_path / "fake-engine")
    capture = tmp_path / "args"
    env = _clean_launcher_env(tmp_path, engine, capture)
    host_root = tmp_path / "host-xdg"
    repo = tmp_path / "repo"
    repo.mkdir()
    env.update(
        {
            "XDG_DATA_HOME": str(host_root / "data"),
            "XDG_CONFIG_HOME": str(host_root / "config"),
            "XDG_STATE_HOME": str(host_root / "state"),
            "XDG_CACHE_HOME": str(host_root / "cache"),
        }
    )

    args = _run_launcher(
        env,
        "--image",
        "localhost/devaiflow:test",
        "--repo",
        str(repo),
        "--",
        "daf",
        "--version",
    )
    env_values = _flag_values(args, "--env")
    volumes = _flag_values(args, "--volume")

    assert "XDG_DATA_HOME=/sandbox/.local/share" in env_values
    assert "XDG_CONFIG_HOME=/sandbox/.config" in env_values
    assert "XDG_STATE_HOME=/sandbox/.local/state" in env_values
    assert "XDG_CACHE_HOME=/sandbox/.cache" in env_values
    assert "AI_GUARDIAN_HOST_CONFIG_MOUNTED=false" in env_values
    assert "AI_GUARDIAN_REST_PORT=63152" in env_values
    assert "AI_GUARDIAN_REST_HOST=0.0.0.0" in env_values
    assert not any(value.startswith(str(host_root / "config") + ":") for value in volumes)
    assert f"{host_root / 'data' / 'devaiflow'}:/sandbox/.local/share/devaiflow" in volumes
    assert f"{host_root / 'config' / 'devaiflow'}:/sandbox/.config/devaiflow" in volumes
    assert f"{host_root / 'state' / 'devaiflow'}:/sandbox/.local/state/devaiflow" in volumes
    assert f"{host_root / 'cache' / 'devaiflow'}:/sandbox/.cache/devaiflow" in volumes
    assert f"{repo.resolve()}:/sandbox/repo" in volumes
    assert "--pull=never" in args
    assert _flag_values(args, "--publish") == ["63152"]
    labels = _flag_values(args, "--label")
    assert "ai-guardian.managed=true" in labels
    assert "ai-guardian.daemon=true" in labels
    assert "ai-guardian.runtime=container" in labels
    assert "ai-guardian.rest-port=63152" in labels
    assert all(
        (host_root / root / "devaiflow").is_dir()
        for root in ("data", "config", "state", "cache")
    )


def test_launcher_allows_a_custom_daemon_rest_port(tmp_path):
    """A custom internal REST port is passed to both the daemon and engine."""
    engine = _capture_engine(tmp_path / "fake-engine")
    capture = tmp_path / "args"
    env = _clean_launcher_env(tmp_path, engine, capture)

    args = _run_launcher(env, "--port", "63200", "--", "daf", "--version")
    env_values = _flag_values(args, "--env")
    labels = _flag_values(args, "--label")

    assert "AI_GUARDIAN_REST_PORT=63200" in env_values
    assert _flag_values(args, "--publish") == ["63200"]
    assert "ai-guardian.rest-port=63200" in labels


def test_launcher_can_separate_engine_environment_from_daf_xdg_roots(tmp_path):
    """Temporary DAF XDG roots do not hide the engine's image storage."""
    engine = _capture_engine(tmp_path / "fake-engine")
    capture = tmp_path / "args"
    capture_env = tmp_path / "env"
    env = _clean_launcher_env(tmp_path, engine, capture)
    host_root = tmp_path / "host-xdg"
    env.update(
        {
            "XDG_DATA_HOME": str(host_root / "data"),
            "XDG_CONFIG_HOME": str(host_root / "config"),
            "XDG_STATE_HOME": str(host_root / "state"),
            "XDG_CACHE_HOME": str(host_root / "cache"),
            "CONTAINER_ENGINE_HOME": "/engine/home",
            "CONTAINER_ENGINE_XDG_DATA_HOME": "/engine/data",
            "CONTAINER_ENGINE_XDG_CONFIG_HOME": "/engine/config",
            "CONTAINER_ENGINE_XDG_STATE_HOME": "/engine/state",
            "CONTAINER_ENGINE_XDG_CACHE_HOME": "/engine/cache",
            "CAPTURE_ENV": str(capture_env),
        }
    )

    _run_launcher(env, "--image", "localhost/devaiflow:test", "--", "daf", "--version")

    engine_env = capture_env.read_text(encoding="utf-8").splitlines()
    assert "HOME=/engine/home" in engine_env
    assert "XDG_DATA_HOME=/engine/data" in engine_env
    assert "XDG_CONFIG_HOME=/engine/config" in engine_env
    assert "XDG_STATE_HOME=/engine/state" in engine_env
    assert "XDG_CACHE_HOME=/engine/cache" in engine_env


@pytest.mark.parametrize("use_explicit_home", [False, True])
def test_launcher_preserves_unified_installations(tmp_path, use_explicit_home):
    """Explicit and valid legacy unified homes are mounted without migration."""
    engine = _capture_engine(tmp_path / "fake-engine")
    capture = tmp_path / "args"
    env = _clean_launcher_env(tmp_path, engine, capture)

    if use_explicit_home:
        unified_home = tmp_path / "existing-unified"
        unified_home.mkdir()
        (unified_home / "sessions.json").write_text("{}", encoding="utf-8")
        env["DEVAIFLOW_HOME"] = str(unified_home)
    else:
        unified_home = Path(env["HOME"]) / ".daf-sessions"
        unified_home.mkdir()
        (unified_home / "config.json").write_text("{}", encoding="utf-8")

    args = _run_launcher(env, "--", "daf", "--version")
    env_values = _flag_values(args, "--env")
    volumes = _flag_values(args, "--volume")

    assert "DEVAIFLOW_HOME=/sandbox/.devaiflow" in env_values
    assert volumes == [f"{unified_home.resolve()}:/sandbox/.devaiflow"]
    assert not any("/sandbox/.local/share/devaiflow" in value for value in volumes)


def test_smoke_test_covers_paths_and_cross_container_persistence():
    """The smoke test exercises the user-visible image and mount contract."""
    smoke_test = SMOKE_TEST.read_text(encoding="utf-8")

    assert "run.sh" in smoke_test
    assert "command -v daf" in smoke_test
    assert "daf --version" in smoke_test
    assert 'test "$XDG_CONFIG_HOME" = "/sandbox/.config"' in smoke_test
    assert 'test "$XDG_DATA_HOME" = "/sandbox/.local/share"' in smoke_test
    assert 'test "$XDG_STATE_HOME" = "/sandbox/.local/state"' in smoke_test
    assert 'test "$XDG_CACHE_HOME" = "/sandbox/.cache"' in smoke_test
    assert "/sandbox/.local/share/devaiflow" in smoke_test
    assert "/sandbox/.config/devaiflow" in smoke_test
    assert "/sandbox/.local/state/devaiflow" in smoke_test
    assert "/sandbox/.cache/devaiflow" in smoke_test
    assert "/sandbox/.daf-sessions" in smoke_test
    assert "/usr/share/devaiflow/openshell-github-readwrite-policy.yaml" in smoke_test
    assert ".container-smoke-marker" in smoke_test
    assert "DEVAIFLOW_VOLUME_SUFFIX" in smoke_test


def test_openshell_docs_use_ai_guardian_lifecycle_command():
    """Gateway instructions use the merged AI Guardian sandbox workflow."""
    guide = (CONTAINER_DIR / "README.md").read_text(encoding="utf-8")

    assert "ai-guardian sandbox create" in guide
    assert "--runtime openshell" in guide
    assert "--cli codex" in guide
    assert "--policy ./container/openshell-github-readwrite-policy.yaml" in guide
    assert "container/openshell.sh" not in guide
