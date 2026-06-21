"""Stateful VM Sandboxes for isolated task execution.

Integrates with KubeVirt/Firecracker for isolated virtual machines.
Provides sandbox manager for spinning up/tearing down VMs, task execution
within sandboxes, and lifecycle management with resource limits.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger("arena.agentic.sandbox")


class SandboxBackend(str, Enum):
    """Available sandbox backends."""
    DOCKER = "docker"
    FIRECRACKER = "firecracker"
    KUBEVIRT = "kubevirt"
    MOCK = "mock"  # For testing


class SandboxStatus(str, Enum):
    """Sandbox lifecycle status."""
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    TERMINATED = "terminated"


@dataclass
class SandboxConfig:
    """Configuration for sandbox instances."""
    backend: SandboxBackend = SandboxBackend.DOCKER
    cpu_limit: str = "2"
    memory_limit: str = "4g"
    timeout_seconds: int = 300
    network_isolated: bool = True
    read_only_fs: bool = False
    enable_seccomp: bool = True
    pids_limit: int = 128
    image: str = "python:3.12-slim"
    working_dir: str = "/workspace"
    environment: dict[str, str] = field(default_factory=dict)
    volume_mounts: dict[str, str] = field(default_factory=dict)  # host:container


@dataclass
class SandboxResult:
    """Result of sandbox execution."""
    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0
    duration_s: float = 0.0
    timed_out: bool = False
    resource_usage: dict[str, Any] = field(default_factory=dict)
    sandbox_id: str = ""


@dataclass
class SandboxInstance:
    """Represents a running sandbox instance."""
    sandbox_id: str
    config: SandboxConfig
    status: SandboxStatus = SandboxStatus.CREATING
    created_at: float = field(default_factory=time.time)
    pid: Optional[int] = None
    container_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SandboxManager:
    """Manager for stateful VM sandboxes.

    Handles lifecycle (create, start, stop, cleanup), resource enforcement,
    and task execution within isolated environments.
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self.sandboxes: dict[str, SandboxInstance] = {}
        self._backend_check: Optional[bool] = None

    def _check_backend_available(self) -> bool:
        """Check if the configured backend is available."""
        if self._backend_check is not None:
            return self._backend_check

        if self.config.backend == SandboxBackend.DOCKER:
            self._backend_check = shutil.which("docker") is not None
            if not self._backend_check:
                log.warning("Docker not found, falling back to MOCK backend")
                self.config.backend = SandboxBackend.MOCK
                self._backend_check = True
        elif self.config.backend == SandboxBackend.FIRECRACKER:
            self._backend_check = shutil.which("firecracker") is not None
        elif self.config.backend == SandboxBackend.KUBEVIRT:
            self._backend_check = shutil.which("kubectl") is not None and self._check_kubevirt()
        else:
            self._backend_check = True  # MOCK always available

        return self._backend_check

    def _check_kubevirt(self) -> bool:
        """Check if KubeVirt is installed in Kubernetes cluster."""
        try:
            result = subprocess.run(
                ["kubectl", "get", "crd", "virtualmachineinstances.kubevirt.io"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def create_sandbox(
        self,
        sandbox_id: str,
        config: Optional[SandboxConfig] = None,
    ) -> SandboxInstance:
        """Create a new sandbox instance.

        Args:
            sandbox_id: Unique identifier for the sandbox
            config: Optional override configuration

        Returns:
            SandboxInstance representing the created sandbox
        """
        if sandbox_id in self.sandboxes:
            log.warning(f"Sandbox {sandbox_id} already exists")
            return self.sandboxes[sandbox_id]

        if not self._check_backend_available():
            raise RuntimeError(f"Backend {self.config.backend} not available")

        cfg = config or self.config
        instance = SandboxInstance(sandbox_id=sandbox_id, config=cfg)

        if cfg.backend == SandboxBackend.DOCKER:
            instance = self._create_docker_sandbox(instance)
        elif cfg.backend == SandboxBackend.FIRECRACKER:
            instance = self._create_firecracker_sandbox(instance)
        elif cfg.backend == SandboxBackend.KUBEVIRT:
            instance = self._create_kubevirt_sandbox(instance)
        else:  # MOCK
            instance.status = SandboxStatus.RUNNING
            log.info(f"Created MOCK sandbox {sandbox_id}")

        self.sandboxes[sandbox_id] = instance
        return instance

    def _create_docker_sandbox(self, instance: SandboxInstance) -> SandboxInstance:
        """Create a Docker-based sandbox."""
        cfg = instance.config
        cmd = [
            "docker", "run", "-d",
            "--name", f"arena-{instance.sandbox_id}",
            "--cpus", cfg.cpu_limit,
            "--memory", cfg.memory_limit,
            "--pids-limit", str(cfg.pids_limit),
        ]

        if cfg.network_isolated:
            cmd.extend(["--network=none"])

        if cfg.read_only_fs:
            cmd.extend(["--read-only"])
            cmd.extend(["--tmpfs", "/tmp"])

        if cfg.enable_seccomp:
            seccomp_path = Path(__file__).parent.parent / "sandboxes" / "seccomp.json"
            if seccomp_path.exists():
                cmd.extend(["--security-opt", f"seccomp={seccomp_path}"])

        cmd.extend(["--security-opt=no-new-privileges", "--cap-drop=ALL"])

        # Add environment variables
        for key, value in cfg.environment.items():
            cmd.extend(["-e", f"{key}={value}"])

        # Add volume mounts
        for host_path, container_path in cfg.volume_mounts.items():
            cmd.extend(["-v", f"{host_path}:{container_path}"])

        cmd.extend([cfg.image, "tail", "-f", "/dev/null"])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                instance.status = SandboxStatus.FAILED
                instance.metadata["error"] = result.stderr
                log.error(f"Failed to create Docker sandbox: {result.stderr}")
                return instance

            instance.container_id = result.stdout.strip()
            instance.status = SandboxStatus.RUNNING
            log.info(f"Created Docker sandbox {instance.sandbox_id}: {instance.container_id}")
        except subprocess.TimeoutExpired:
            instance.status = SandboxStatus.FAILED
            instance.metadata["error"] = "Timeout creating container"
            log.error("Timeout creating Docker container")
        except Exception as e:
            instance.status = SandboxStatus.FAILED
            instance.metadata["error"] = str(e)
            log.error(f"Error creating Docker sandbox: {e}")

        return instance

    def _create_firecracker_sandbox(self, instance: SandboxInstance) -> SandboxInstance:
        """Create a Firecracker-based microVM sandbox.

        Note: This is a placeholder implementation. Full Firecracker integration
        requires kernel boot images, root filesystems, and more complex setup.
        """
        log.warning("Firecracker backend not fully implemented, using MOCK")
        instance.status = SandboxStatus.RUNNING
        return instance

    def _create_kubevirt_sandbox(self, instance: SandboxInstance) -> SandboxInstance:
        """Create a KubeVirt-based VirtualMachineInstance sandbox.

        Note: This is a placeholder implementation. Full KubeVirt integration
        requires Kubernetes cluster setup and YAML manifest generation.
        """
        log.warning("KubeVirt backend not fully implemented, using MOCK")
        instance.status = SandboxStatus.RUNNING
        return instance

    def execute_task(
        self,
        sandbox_id: str,
        task: str,
        files: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> SandboxResult:
        """Execute a task within a sandbox.

        Args:
            sandbox_id: ID of the sandbox to execute in
            task: Task description or command to execute
            files: Optional dict of filename -> content to upload to sandbox
            timeout: Optional override for task timeout

        Returns:
            SandboxResult with execution outcome
        """
        if sandbox_id not in self.sandboxes:
            return SandboxResult(
                success=False,
                error=f"Sandbox {sandbox_id} not found",
                sandbox_id=sandbox_id,
            )

        instance = self.sandboxes[sandbox_id]
        if instance.status != SandboxStatus.RUNNING:
            return SandboxResult(
                success=False,
                error=f"Sandbox {sandbox_id} not running (status: {instance.status})",
                sandbox_id=sandbox_id,
            )

        timeout = timeout if timeout is not None else instance.config.timeout_seconds
        t0 = time.time()

        # Upload files if provided
        if files:
            self._upload_files(instance, files)

        # Execute task
        if instance.config.backend == SandboxBackend.DOCKER:
            result = self._execute_docker(instance, task, timeout)
        else:
            result = self._execute_mock(instance, task, timeout)

        result.duration_s = round(time.time() - t0, 3)
        result.sandbox_id = sandbox_id
        return result

    def _upload_files(self, instance: SandboxInstance, files: dict[str, str]) -> None:
        """Upload files to the sandbox."""
        if instance.config.backend == SandboxBackend.DOCKER and instance.container_id:
            for filename, content in files.items():
                # Reject path separators / traversal in filenames: an unsanitized
                # filename ends up both in the host tempfile suffix (breaking out
                # of the intended tmp directory) and in the in-container `docker cp`
                # destination path (breaking out of working_dir).
                safe_name = os.path.basename(filename)
                if not safe_name or safe_name in (".", "..") or safe_name != filename:
                    log.error(f"Rejecting unsafe upload filename: {filename!r}")
                    continue

                # Use docker cp to upload files
                with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=f"_{safe_name}") as f:
                    f.write(content)
                    temp_path = f.name

                try:
                    container_path = f"{instance.config.working_dir}/{safe_name}"
                    subprocess.run(
                        ["docker", "cp", temp_path, f"{instance.container_id}:{container_path}"],
                        capture_output=True,
                        timeout=10,
                    )
                finally:
                    os.unlink(temp_path)

    def _execute_docker(
        self,
        instance: SandboxInstance,
        task: str,
        timeout: int,
    ) -> SandboxResult:
        """Execute task in Docker sandbox."""
        cmd = [
            "docker", "exec",
            f"arena-{instance.sandbox_id}",
            "bash", "-c",
            f"cd {instance.config.working_dir} && {task}",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return SandboxResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                error="Task execution timeout",
                timed_out=True,
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                error=f"Execution error: {e}",
            )

    def _execute_mock(
        self,
        instance: SandboxInstance,
        task: str,
        timeout: int,
    ) -> SandboxResult:
        """Mock execution for testing."""
        log.info(f"MOCK execution in {instance.sandbox_id}: {task[:100]}")
        time.sleep(min(1, timeout / 10))  # Simulate some work
        return SandboxResult(
            success=True,
            output=f"Mock execution completed for: {task[:100]}",
        )

    def stop_sandbox(self, sandbox_id: str) -> bool:
        """Stop a running sandbox."""
        if sandbox_id not in self.sandboxes:
            return False

        instance = self.sandboxes[sandbox_id]
        if instance.config.backend == SandboxBackend.DOCKER and instance.container_id:
            try:
                subprocess.run(
                    ["docker", "stop", f"arena-{sandbox_id}"],
                    capture_output=True,
                    timeout=10,
                )
                subprocess.run(
                    ["docker", "rm", f"arena-{sandbox_id}"],
                    capture_output=True,
                    timeout=10,
                )
                instance.status = SandboxStatus.STOPPED
                log.info(f"Stopped Docker sandbox {sandbox_id}")
                return True
            except Exception as e:
                log.error(f"Error stopping sandbox {sandbox_id}: {e}")
                return False

        instance.status = SandboxStatus.STOPPED
        return True

    def cleanup_sandbox(self, sandbox_id: str) -> bool:
        """Cleanup and remove a sandbox."""
        self.stop_sandbox(sandbox_id)
        if sandbox_id in self.sandboxes:
            del self.sandboxes[sandbox_id]
            log.info(f"Cleaned up sandbox {sandbox_id}")
            return True
        return False

    def cleanup_all(self) -> None:
        """Cleanup all sandboxes."""
        for sandbox_id in list(self.sandboxes.keys()):
            self.cleanup_sandbox(sandbox_id)

    def get_sandbox_status(self, sandbox_id: str) -> Optional[SandboxStatus]:
        """Get the status of a sandbox."""
        instance = self.sandboxes.get(sandbox_id)
        return instance.status if instance else None

    def list_sandboxes(self) -> list[str]:
        """List all sandbox IDs."""
        return list(self.sandboxes.keys())


# Import shutil at module level for availability
import shutil
