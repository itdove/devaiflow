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
OPEN_SHELL = CONTAINER_DIR / "openshell.sh"
STAGE_SCRIPT = CONTAINER_DIR / "stage-devaiflow.sh"
DAF_WRAPPER = CONTAINER_DIR / "daf-wrapper.sh"
CONFIG_SANITIZER = CONTAINER_DIR / "sanitize-config.py"
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
        "AI_GUARDIAN_REST_BIND_ADDRESS",
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
    assert "COPY stage-devaiflow.sh /usr/local/bin/devaiflow-stage" in dockerfile
    assert "COPY daf-wrapper.sh /usr/local/bin/daf" in dockerfile
    assert "devaiflow.config-staging=/usr/local/bin/devaiflow-stage" in dockerfile
    assert "ENV PATH=/usr/local/bin:/sandbox/.venv/bin" in dockerfile
    assert "mv /sandbox/.venv/bin/daf /sandbox/.venv/bin/daf-real" in dockerfile
    assert "exec /sandbox/.venv/bin/daf-real" in DAF_WRAPPER.read_text(encoding="utf-8")


def test_github_readwrite_policy_is_narrow_and_credential_free():
    """The bundled overlay grants only GitHub API and smart-HTTP access."""
    policy = GITHUB_POLICY.read_text(encoding="utf-8")

    assert "host: api.github.com" in policy
    assert "access: read-write" in policy
    assert 'path: "/**/git-upload-pack"' in policy
    assert 'path: "/**/git-receive-pack"' in policy
    assert "GITHUB_TOKEN" not in policy
    assert "Authorization" not in policy


def test_config_sanitizer_removes_credentials_without_losing_safe_settings(tmp_path):
    """Config snapshots omit credential values before OpenShell upload."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    (source / "config.json").write_text(
        '{"api_url":"https://example.invalid/api",'
        '"model_provider":{"profiles":{"local":{'
        '"api_key":"do-not-upload", "model_name":"model-a"}}}}\n',
        encoding="utf-8",
    )
    (source / "backends").mkdir()
    (source / "backends" / "service.json").write_text(
        '{"auth_token":"also-do-not-upload", "enabled":true}\n',
        encoding="utf-8",
    )
    (source / "auth.json").write_text('{"token":"do-not-upload"}\n', encoding="utf-8")
    outside = tmp_path / "outside"
    outside.write_text("outside\n", encoding="utf-8")
    (source / "linked").symlink_to(outside)

    result = subprocess.run(
        ["python3", str(CONFIG_SANITIZER), str(source), str(destination)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    sanitized = (destination / "config.json").read_text(encoding="utf-8")
    backend = (destination / "backends" / "service.json").read_text(encoding="utf-8")
    assert "do-not-upload" not in sanitized
    assert "do-not-upload" not in backend
    assert "api_url" in sanitized
    assert "model_name" in sanitized
    assert not (destination / "auth.json").exists()
    assert not (destination / "linked").exists()


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
    assert "test ! -L /sandbox/.daf-sessions" in dockerfile


@pytest.mark.skipif(os.name == "nt", reason="The launcher is a POSIX shell script")
def test_container_scripts_are_valid_and_executable():
    """The launcher and smoke test are executable and syntactically valid."""
    for script in (RUNNER, SMOKE_TEST, OPEN_SHELL, STAGE_SCRIPT, DAF_WRAPPER):
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
    assert "DEVAIFLOW_HOST_CONFIG_MOUNTED=true" in env_values
    assert "DEVAIFLOW_HOST_CONFIG_PATH=/sandbox/.config/devaiflow" in env_values
    assert "AI_GUARDIAN_REST_PORT=63152" in env_values
    assert "AI_GUARDIAN_REST_HOST=0.0.0.0" in env_values
    assert not any(value.startswith(str(host_root / "config") + ":") for value in volumes)
    assert f"{host_root / 'data' / 'devaiflow'}:/sandbox/.local/share/devaiflow" in volumes
    assert f"{host_root / 'config' / 'devaiflow'}:/sandbox/.config/devaiflow" in volumes
    assert f"{host_root / 'state' / 'devaiflow'}:/sandbox/.local/state/devaiflow" in volumes
    assert f"{host_root / 'cache' / 'devaiflow'}:/sandbox/.cache/devaiflow" in volumes
    assert f"{repo.resolve()}:/sandbox/repo" in volumes
    assert "--pull=never" in args
    assert _flag_values(args, "--publish") == ["127.0.0.1::63152"]
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
    assert _flag_values(args, "--publish") == ["127.0.0.1::63200"]
    assert "ai-guardian.rest-port=63200" in labels


def test_launcher_allows_an_explicit_rest_bind_address(tmp_path):
    """A caller can opt into a non-loopback daemon binding explicitly."""
    engine = _capture_engine(tmp_path / "fake-engine")
    capture = tmp_path / "args"
    env = _clean_launcher_env(tmp_path, engine, capture)

    args = _run_launcher(
        env,
        "--bind-address",
        "0.0.0.0",
        "--",
        "daf",
        "--version",
    )

    assert _flag_values(args, "--publish") == ["0.0.0.0::63152"]


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
    assert 'cmp "$(command -v daf)" /usr/local/bin/daf' in smoke_test
    assert "test ! -e /sandbox/.daf-sessions" in smoke_test
    assert "/usr/share/devaiflow/openshell-github-readwrite-policy.yaml" in smoke_test
    assert ".container-smoke-marker" in smoke_test
    assert "DEVAIFLOW_VOLUME_SUFFIX" in smoke_test


def test_devaiflow_stage_preserves_sandbox_local_config_precedence(tmp_path):
    """An uploaded host snapshot is copied once and never overwrites local config."""
    host_config = tmp_path / "host-config"
    active_config = tmp_path / "active-config"
    host_config.mkdir()
    (host_config / "config.json").write_text('{"source": "host"}\n', encoding="utf-8")
    (host_config / "backends").mkdir()
    (host_config / "backends" / "jira.json").write_text("{}\n", encoding="utf-8")

    env = os.environ.copy()
    (tmp_path / "home").mkdir()
    env.update(
        {
            "DEVAIFLOW_HOST_CONFIG_MOUNTED": "true",
            "DEVAIFLOW_HOST_CONFIG_PATH": str(host_config),
            "DEVAIFLOW_ACTIVE_CONFIG_DIR": str(active_config),
            "HOME": str(tmp_path / "home"),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        }
    )
    first = subprocess.run(
        ["bash", str(STAGE_SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr
    assert (active_config / "config.json").read_text(encoding="utf-8") == (
        '{"source": "host"}\n'
    )
    assert (active_config / "backends" / "jira.json").is_file()

    (active_config / "config.json").write_text('{"source": "local"}\n', encoding="utf-8")
    second = subprocess.run(
        ["bash", str(STAGE_SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert second.returncode == 0, second.stderr
    assert (active_config / "config.json").read_text(encoding="utf-8") == (
        '{"source": "local"}\n'
    )


def test_openshell_launcher_uploads_only_daf_config(tmp_path):
    """The gateway launcher uploads config and leaves XDG data/state/cache local."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    ai_guardian_log = tmp_path / "ai-guardian.log"
    openshell_log = tmp_path / "openshell.log"
    for name in ("ai-guardian", "openshell"):
        command = fake_bin / name
        command.write_text(
            "#!/usr/bin/env bash\n",
            encoding="utf-8",
        )
        command.chmod(command.stat().st_mode | stat.S_IXUSR)

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        '{"source": "host", "api_key": "do-not-upload"}\n', encoding="utf-8"
    )
    (config_dir / "sessions.json").write_text('{"must_not_upload": true}\n', encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()

    env = os.environ.copy()
    (tmp_path / "home").mkdir()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "PATH": f"{fake_bin}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            "COMMAND_LOG": str(ai_guardian_log),
        }
    )
    # Point each fake command at its own argument log.
    (fake_bin / "ai-guardian").write_text(
        "#!/usr/bin/env bash\n"
        'printf \'%s\\n\' "$@" >> "${AI_GUARDIAN_LOG}"\n',
        encoding="utf-8",
    )
    (fake_bin / "openshell").write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "${1:-}" == "sandbox" && "${2:-}" == "get" ]]; then exit 1; fi\n'
        'if [[ "${1:-}" == "sandbox" && "${2:-}" == "upload" ]]; then\n'
        '    test ! -e "${5}/sessions.json"\n'
        '    ! grep -F "do-not-upload" "${5}/config.json"\n'
        '    grep -F "source" "${5}/config.json" >/dev/null\n'
        'fi\n'
        'printf \'%s\\n\' "$@" >> "${OPENSHELL_LOG}"\n',
        encoding="utf-8",
    )
    (fake_bin / "ai-guardian").chmod((fake_bin / "ai-guardian").stat().st_mode | stat.S_IXUSR)
    (fake_bin / "openshell").chmod((fake_bin / "openshell").stat().st_mode | stat.S_IXUSR)
    env.update(
        {
            "AI_GUARDIAN_LOG": str(ai_guardian_log),
            "OPENSHELL_LOG": str(openshell_log),
        }
    )

    result = subprocess.run(
        [
            "bash",
            str(OPEN_SHELL),
            "--name",
            "devaiflow-test",
            "--image",
            "quay.io/example/devaiflow:test",
            "--config-dir",
            str(config_dir),
            "--repo",
            str(repo),
            "--no-connect",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    ai_args = ai_guardian_log.read_text(encoding="utf-8").splitlines()
    openshell_args = openshell_log.read_text(encoding="utf-8").splitlines()
    assert "--runtime" in ai_args
    assert "openshell" in ai_args
    assert "DEVAIFLOW_HOST_CONFIG_MOUNTED=true" in ai_args
    assert "DEVAIFLOW_HOST_CONFIG_PATH=/sandbox/.config/devaiflow.host" in ai_args
    assert "DEVAIFLOW_OPEN_SHELL_STAGING=true" in ai_args
    assert openshell_args[:3] == ["sandbox", "upload", "--no-git-ignore"]
    upload_index = openshell_args.index("upload")
    upload_args = openshell_args[upload_index:]
    assert "/sandbox/.config/devaiflow.host" in upload_args
    assert "/sandbox/.local/share/devaiflow" not in upload_args
    assert "/sandbox/.local/state/devaiflow" not in upload_args
    assert "/sandbox/.cache/devaiflow" not in upload_args
    assert "/usr/local/bin/devaiflow-stage" in openshell_args


def test_openshell_launcher_rejects_names_that_ai_guardian_would_shorten(tmp_path):
    """The wrapper fails before creation when the gateway name is too long."""
    result = subprocess.run(
        [
            "bash",
            str(OPEN_SHELL),
            "--name",
            "devaiflow-name-that-is-too-long",
            "--repo",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "at most 19 characters" in result.stderr


def test_openshell_docs_use_daf_config_upload_and_local_xdg_strategy():
    """Gateway instructions document the DAF upload and sandbox-local data rule."""
    guide = (CONTAINER_DIR / "README.md").read_text(encoding="utf-8")

    assert "container/openshell.sh" in guide
    assert "ai-guardian sandbox create" in guide
    assert "/sandbox/.config/devaiflow.host" in guide
    assert "sandbox-local" in guide
    assert "sessions and backups" in guide
    assert "state and audit files" in guide
    assert "clones in" in guide
    assert "19 characters" in guide
    assert "credential fields" in guide
    assert "loopback" in guide
