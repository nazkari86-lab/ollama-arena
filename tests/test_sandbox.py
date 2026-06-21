"""Tests for agentic/sandbox.py — SandboxManager."""
from __future__ import annotations

import unittest.mock as mock
import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Enums and dataclasses
# ──────────────────────────────────────────────────────────────────────────────

class TestSandboxEnums:
    def test_sandbox_backend_values(self):
        from ollama_arena.agentic.sandbox import SandboxBackend
        assert SandboxBackend.DOCKER == "docker"
        assert SandboxBackend.FIRECRACKER == "firecracker"
        assert SandboxBackend.KUBEVIRT == "kubevirt"
        assert SandboxBackend.MOCK == "mock"

    def test_sandbox_status_values(self):
        from ollama_arena.agentic.sandbox import SandboxStatus
        assert SandboxStatus.CREATING == "creating"
        assert SandboxStatus.RUNNING == "running"
        assert SandboxStatus.STOPPED == "stopped"
        assert SandboxStatus.FAILED == "failed"
        assert SandboxStatus.TERMINATED == "terminated"


class TestSandboxConfig:
    def test_defaults(self):
        from ollama_arena.agentic.sandbox import SandboxConfig, SandboxBackend
        cfg = SandboxConfig()
        assert cfg.backend == SandboxBackend.DOCKER
        assert cfg.cpu_limit == "2"
        assert cfg.memory_limit == "4g"
        assert cfg.timeout_seconds == 300
        assert cfg.network_isolated is True
        assert cfg.enable_seccomp is True
        assert cfg.image == "python:3.12-slim"


class TestSandboxResult:
    def test_defaults(self):
        from ollama_arena.agentic.sandbox import SandboxResult
        r = SandboxResult(success=True)
        assert r.output == ""
        assert r.error == ""
        assert r.exit_code == 0
        assert r.duration_s == 0.0
        assert r.timed_out is False

    def test_failure(self):
        from ollama_arena.agentic.sandbox import SandboxResult
        r = SandboxResult(success=False, error="failed", exit_code=1)
        assert not r.success
        assert r.exit_code == 1


class TestSandboxInstance:
    def test_defaults(self):
        from ollama_arena.agentic.sandbox import SandboxInstance, SandboxConfig, SandboxStatus
        import time
        before = time.time()
        inst = SandboxInstance(sandbox_id="s1", config=SandboxConfig())
        assert inst.status == SandboxStatus.CREATING
        assert inst.pid is None
        assert inst.container_id is None
        assert inst.created_at >= before


# ──────────────────────────────────────────────────────────────────────────────
# SandboxManager — MOCK backend (simplest path)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_manager():
    from ollama_arena.agentic.sandbox import SandboxManager, SandboxConfig, SandboxBackend
    cfg = SandboxConfig(backend=SandboxBackend.MOCK)
    return SandboxManager(config=cfg)


class TestSandboxManagerMock:
    def test_init(self, mock_manager):
        assert mock_manager.sandboxes == {}
        assert mock_manager._backend_check is None

    def test_check_backend_mock_always_true(self, mock_manager):
        assert mock_manager._check_backend_available() is True
        # Second call uses cached value
        assert mock_manager._check_backend_available() is True

    def test_create_sandbox_mock(self, mock_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus
        inst = mock_manager.create_sandbox("test_sb")
        assert inst.sandbox_id == "test_sb"
        assert inst.status == SandboxStatus.RUNNING
        assert "test_sb" in mock_manager.sandboxes

    def test_create_sandbox_already_exists(self, mock_manager):
        mock_manager.create_sandbox("s1")
        inst1 = mock_manager.sandboxes["s1"]
        inst2 = mock_manager.create_sandbox("s1")
        assert inst1 is inst2

    def test_execute_task_not_found(self, mock_manager):
        result = mock_manager.execute_task("nonexistent", "ls")
        assert not result.success
        assert "not found" in result.error

    def test_execute_task_mock_success(self, mock_manager):
        mock_manager.create_sandbox("s1")
        with mock.patch("time.sleep"):
            result = mock_manager.execute_task("s1", "echo hello")
        assert result.success
        assert "Mock execution" in result.output
        assert result.sandbox_id == "s1"

    def test_execute_task_with_files(self, mock_manager):
        mock_manager.create_sandbox("s1")
        with mock.patch("time.sleep"):
            result = mock_manager.execute_task("s1", "cat test.txt", files={"test.txt": "content"})
        assert result.success

    def test_execute_task_timeout_zero_is_honored(self, mock_manager):
        """Regression: `timeout = timeout or instance.config.timeout_seconds`
        treated an explicit timeout=0 as falsy and silently substituted the
        much larger configured default (300s) instead of honoring 0."""
        mock_manager.create_sandbox("s1")
        with mock.patch("time.sleep") as sleep_mock:
            mock_manager.execute_task("s1", "echo hello", timeout=0)
        # _execute_mock sleeps min(1, timeout / 10) -- with timeout=0 that's 0.0,
        # not min(1, 300/10)=1 from the old default-substitution bug.
        sleep_mock.assert_called_once_with(0.0)

    def test_execute_task_not_running(self, mock_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus
        mock_manager.create_sandbox("s1")
        mock_manager.sandboxes["s1"].status = SandboxStatus.STOPPED
        result = mock_manager.execute_task("s1", "ls")
        assert not result.success
        assert "not running" in result.error

    def test_stop_sandbox_not_found(self, mock_manager):
        assert mock_manager.stop_sandbox("nonexistent") is False

    def test_stop_sandbox_mock(self, mock_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus
        mock_manager.create_sandbox("s1")
        result = mock_manager.stop_sandbox("s1")
        assert result is True
        assert mock_manager.sandboxes["s1"].status == SandboxStatus.STOPPED

    def test_cleanup_sandbox(self, mock_manager):
        mock_manager.create_sandbox("s1")
        result = mock_manager.cleanup_sandbox("s1")
        assert result is True
        assert "s1" not in mock_manager.sandboxes

    def test_cleanup_sandbox_not_found(self, mock_manager):
        result = mock_manager.cleanup_sandbox("nonexistent")
        assert result is False

    def test_cleanup_all(self, mock_manager):
        mock_manager.create_sandbox("s1")
        mock_manager.create_sandbox("s2")
        mock_manager.cleanup_all()
        assert mock_manager.sandboxes == {}

    def test_get_sandbox_status_existing(self, mock_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus
        mock_manager.create_sandbox("s1")
        status = mock_manager.get_sandbox_status("s1")
        assert status == SandboxStatus.RUNNING

    def test_get_sandbox_status_not_found(self, mock_manager):
        assert mock_manager.get_sandbox_status("nonexistent") is None

    def test_list_sandboxes_empty(self, mock_manager):
        assert mock_manager.list_sandboxes() == []

    def test_list_sandboxes_with_sandboxes(self, mock_manager):
        mock_manager.create_sandbox("s1")
        mock_manager.create_sandbox("s2")
        sandboxes = mock_manager.list_sandboxes()
        assert "s1" in sandboxes
        assert "s2" in sandboxes


# ──────────────────────────────────────────────────────────────────────────────
# SandboxManager — Docker backend (mocked)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def docker_manager():
    from ollama_arena.agentic.sandbox import SandboxManager, SandboxConfig, SandboxBackend
    cfg = SandboxConfig(backend=SandboxBackend.DOCKER)
    mgr = SandboxManager(config=cfg)
    return mgr


class TestSandboxManagerDocker:
    def test_check_backend_docker_found(self, docker_manager):
        with mock.patch("shutil.which", return_value="/usr/bin/docker"):
            result = docker_manager._check_backend_available()
        assert result is True

    def test_check_backend_docker_not_found_falls_back_to_mock(self, docker_manager):
        from ollama_arena.agentic.sandbox import SandboxBackend
        with mock.patch("shutil.which", return_value=None):
            result = docker_manager._check_backend_available()
        assert result is True
        assert docker_manager.config.backend == SandboxBackend.MOCK

    def test_create_docker_sandbox_success(self, docker_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus
        docker_manager._backend_check = True
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "abc123container"
        with mock.patch("subprocess.run", return_value=mock_result):
            inst = docker_manager.create_sandbox("docker_sb")
        assert inst.status == SandboxStatus.RUNNING
        assert inst.container_id == "abc123container"

    def test_create_docker_sandbox_failure(self, docker_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus
        docker_manager._backend_check = True
        mock_result = mock.MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "image not found"
        with mock.patch("subprocess.run", return_value=mock_result):
            inst = docker_manager.create_sandbox("failed_sb")
        assert inst.status == SandboxStatus.FAILED
        assert "image not found" in inst.metadata["error"]

    def test_create_docker_sandbox_timeout(self, docker_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus
        import subprocess
        docker_manager._backend_check = True
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            inst = docker_manager.create_sandbox("timeout_sb")
        assert inst.status == SandboxStatus.FAILED
        assert "Timeout" in inst.metadata["error"]

    def test_create_docker_sandbox_exception(self, docker_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus
        docker_manager._backend_check = True
        with mock.patch("subprocess.run", side_effect=Exception("docker daemon down")):
            inst = docker_manager.create_sandbox("error_sb")
        assert inst.status == SandboxStatus.FAILED

    def test_execute_docker_success(self, docker_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus, SandboxInstance, SandboxConfig
        docker_manager._backend_check = True
        cfg = SandboxConfig()
        inst = SandboxInstance(sandbox_id="d1", config=cfg, status=SandboxStatus.RUNNING)
        inst.container_id = "abc123"
        docker_manager.sandboxes["d1"] = inst
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hello\n"
        mock_result.stderr = ""
        with mock.patch("subprocess.run", return_value=mock_result):
            result = docker_manager.execute_task("d1", "echo hello")
        assert result.success
        assert "hello" in result.output

    def test_execute_docker_timeout(self, docker_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus, SandboxInstance, SandboxConfig
        import subprocess
        docker_manager._backend_check = True
        cfg = SandboxConfig()
        inst = SandboxInstance(sandbox_id="d1", config=cfg, status=SandboxStatus.RUNNING)
        inst.container_id = "abc123"
        docker_manager.sandboxes["d1"] = inst
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
            result = docker_manager.execute_task("d1", "sleep 1000")
        assert not result.success
        assert result.timed_out is True

    def test_execute_docker_exception(self, docker_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus, SandboxInstance, SandboxConfig
        docker_manager._backend_check = True
        cfg = SandboxConfig()
        inst = SandboxInstance(sandbox_id="d1", config=cfg, status=SandboxStatus.RUNNING)
        inst.container_id = "abc123"
        docker_manager.sandboxes["d1"] = inst
        with mock.patch("subprocess.run", side_effect=Exception("exec failed")):
            result = docker_manager.execute_task("d1", "bad_command")
        assert not result.success
        assert "exec failed" in result.error

    def test_stop_docker_sandbox(self, docker_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus, SandboxInstance, SandboxConfig
        docker_manager._backend_check = True
        cfg = SandboxConfig()
        inst = SandboxInstance(sandbox_id="d1", config=cfg, status=SandboxStatus.RUNNING)
        inst.container_id = "abc123"
        docker_manager.sandboxes["d1"] = inst
        with mock.patch("subprocess.run"):
            result = docker_manager.stop_sandbox("d1")
        assert result is True
        assert docker_manager.sandboxes["d1"].status == SandboxStatus.STOPPED

    def test_stop_docker_sandbox_exception(self, docker_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus, SandboxInstance, SandboxConfig
        docker_manager._backend_check = True
        cfg = SandboxConfig()
        inst = SandboxInstance(sandbox_id="d1", config=cfg, status=SandboxStatus.RUNNING)
        inst.container_id = "abc123"
        docker_manager.sandboxes["d1"] = inst
        with mock.patch("subprocess.run", side_effect=Exception("docker stopped")):
            result = docker_manager.stop_sandbox("d1")
        assert result is False

    def test_upload_files_docker(self, docker_manager):
        from ollama_arena.agentic.sandbox import SandboxInstance, SandboxConfig
        cfg = SandboxConfig()
        inst = SandboxInstance(sandbox_id="d1", config=cfg)
        inst.container_id = "abc123"
        with mock.patch("subprocess.run") as m:
            docker_manager._upload_files(inst, {"file.txt": "content"})
        m.assert_called()

    def test_upload_files_rejects_path_traversal(self, docker_manager):
        """Regression: an unsanitized filename key was interpolated both into
        a host tempfile suffix (`suffix=f"_{filename}"`) and the in-container
        `docker cp` destination path (`f"{working_dir}/{filename}"`), so a
        filename like "../../etc/passwd" could write outside the intended
        directory on both sides. Traversal-y / separator-containing filenames
        must now be rejected outright, not docker-cp'd."""
        from ollama_arena.agentic.sandbox import SandboxInstance, SandboxConfig
        cfg = SandboxConfig()
        inst = SandboxInstance(sandbox_id="d1", config=cfg)
        inst.container_id = "abc123"
        with mock.patch("subprocess.run") as m:
            docker_manager._upload_files(inst, {"../../etc/passwd": "pwned"})
        m.assert_not_called()

    def test_upload_files_allows_safe_filename_alongside_unsafe(self, docker_manager):
        from ollama_arena.agentic.sandbox import SandboxInstance, SandboxConfig
        cfg = SandboxConfig()
        inst = SandboxInstance(sandbox_id="d1", config=cfg)
        inst.container_id = "abc123"
        with mock.patch("subprocess.run") as m:
            docker_manager._upload_files(inst, {"../evil.txt": "bad", "good.txt": "ok"})
        # Only the safe filename should have triggered a docker cp call.
        assert m.call_count == 1
        cmd = m.call_args_list[0][0][0]
        assert any("good.txt" in part for part in cmd)
        assert not any("evil.txt" in part for part in cmd)

    def test_docker_sandbox_with_options(self, docker_manager):
        from ollama_arena.agentic.sandbox import SandboxStatus, SandboxConfig
        docker_manager._backend_check = True
        cfg = SandboxConfig(
            read_only_fs=True,
            network_isolated=True,
            environment={"KEY": "value"},
            volume_mounts={"/host": "/container"},
        )
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "cid"
        with mock.patch("subprocess.run", return_value=mock_result) as mock_run:
            inst = docker_manager.create_sandbox("opts_sb", config=cfg)
        # Check that subprocess.run was called with the right options
        call_args = mock_run.call_args_list[0][0][0]  # first positional arg = cmd list
        assert "--read-only" in call_args
        assert "--network=none" in call_args


# ──────────────────────────────────────────────────────────────────────────────
# SandboxManager — Firecracker and KubeVirt paths
# ──────────────────────────────────────────────────────────────────────────────

class TestSandboxManagerFirecracker:
    def test_check_backend_firecracker_found(self):
        from ollama_arena.agentic.sandbox import SandboxManager, SandboxConfig, SandboxBackend
        cfg = SandboxConfig(backend=SandboxBackend.FIRECRACKER)
        mgr = SandboxManager(config=cfg)
        with mock.patch("shutil.which", return_value="/usr/local/bin/firecracker"):
            assert mgr._check_backend_available() is True

    def test_check_backend_firecracker_not_found(self):
        from ollama_arena.agentic.sandbox import SandboxManager, SandboxConfig, SandboxBackend
        cfg = SandboxConfig(backend=SandboxBackend.FIRECRACKER)
        mgr = SandboxManager(config=cfg)
        with mock.patch("shutil.which", return_value=None):
            assert mgr._check_backend_available() is False

    def test_create_firecracker_sandbox_uses_mock(self):
        from ollama_arena.agentic.sandbox import SandboxManager, SandboxConfig, SandboxBackend, SandboxStatus
        cfg = SandboxConfig(backend=SandboxBackend.FIRECRACKER)
        mgr = SandboxManager(config=cfg)
        mgr._backend_check = True
        inst = mgr.create_sandbox("fc_sb")
        assert inst.status == SandboxStatus.RUNNING


class TestSandboxManagerKubevirt:
    def test_check_backend_kubevirt_kubectl_missing(self):
        from ollama_arena.agentic.sandbox import SandboxManager, SandboxConfig, SandboxBackend
        cfg = SandboxConfig(backend=SandboxBackend.KUBEVIRT)
        mgr = SandboxManager(config=cfg)
        with mock.patch("shutil.which", return_value=None):
            assert mgr._check_backend_available() is False

    def test_check_kubevirt_success(self):
        from ollama_arena.agentic.sandbox import SandboxManager, SandboxConfig, SandboxBackend
        cfg = SandboxConfig(backend=SandboxBackend.KUBEVIRT)
        mgr = SandboxManager(config=cfg)
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        with mock.patch("subprocess.run", return_value=mock_result):
            assert mgr._check_kubevirt() is True

    def test_check_kubevirt_failure(self):
        from ollama_arena.agentic.sandbox import SandboxManager, SandboxConfig, SandboxBackend
        cfg = SandboxConfig(backend=SandboxBackend.KUBEVIRT)
        mgr = SandboxManager(config=cfg)
        mock_result = mock.MagicMock()
        mock_result.returncode = 1
        with mock.patch("subprocess.run", return_value=mock_result):
            assert mgr._check_kubevirt() is False

    def test_check_kubevirt_exception(self):
        from ollama_arena.agentic.sandbox import SandboxManager, SandboxConfig, SandboxBackend
        cfg = SandboxConfig(backend=SandboxBackend.KUBEVIRT)
        mgr = SandboxManager(config=cfg)
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("kubectl")):
            assert mgr._check_kubevirt() is False

    def test_create_kubevirt_sandbox_uses_mock(self):
        from ollama_arena.agentic.sandbox import SandboxManager, SandboxConfig, SandboxBackend, SandboxStatus
        cfg = SandboxConfig(backend=SandboxBackend.KUBEVIRT)
        mgr = SandboxManager(config=cfg)
        mgr._backend_check = True
        inst = mgr.create_sandbox("kv_sb")
        assert inst.status == SandboxStatus.RUNNING
