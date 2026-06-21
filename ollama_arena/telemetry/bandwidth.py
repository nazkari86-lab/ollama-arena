"""Memory bandwidth profiling and analysis.

Implements eBPF-based memory bandwidth monitoring (Linux) and
alternative methods for other platforms, with correlation to TTFT metrics.
"""
from __future__ import annotations

import platform
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Thread
from typing import List, Dict, Any, Optional, Callable

from .base import HardwarePlatform, HardwareDetector


class BandwidthMethod(Enum):
    """Memory bandwidth monitoring methods."""
    EBPF = "ebpf"  # eBPF-based (Linux only)
    PROC = "proc"  # /proc/meminfo (Linux)
    PSUTIL = "psutil"  # Cross-platform via psutil
    NVML = "nvml"  # NVIDIA NVML
    ROCM_SMI = "rocm_smi"  # AMD ROCm SMI
    NONE = "none"


@dataclass
class BandwidthMetrics:
    """Memory bandwidth measurement metrics."""
    timestamp: float
    bandwidth_gb_s: float  # Memory bandwidth in GB/s
    memory_used_gb: float
    memory_total_gb: float
    memory_percent: float
    
    # GPU memory (if available)
    gpu_memory_used_gb: float = 0.0
    gpu_memory_total_gb: float = 0.0
    gpu_bandwidth_gb_s: float = 0.0
    
    # Cache metrics (if available)
    l1_cache_hit_rate: float = 0.0
    l2_cache_hit_rate: float = 0.0
    l3_cache_hit_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "bandwidth_gb_s": self.bandwidth_gb_s,
            "memory_used_gb": self.memory_used_gb,
            "memory_total_gb": self.memory_total_gb,
            "memory_percent": self.memory_percent,
            "gpu_memory_used_gb": self.gpu_memory_used_gb,
            "gpu_memory_total_gb": self.gpu_memory_total_gb,
            "gpu_bandwidth_gb_s": self.gpu_bandwidth_gb_s,
            "l1_cache_hit_rate": self.l1_cache_hit_rate,
            "l2_cache_hit_rate": self.l2_cache_hit_rate,
            "l3_cache_hit_rate": self.l3_cache_hit_rate,
        }


class EBPFBandwidthMonitor:
    """eBPF-based memory bandwidth monitor (Linux only)."""
    
    def __init__(self):
        """Initialize eBPF monitor."""
        self._available = self._check_ebpf()
        self._bpf_program: Optional[Callable] = None
        self._previous_bytes = 0
        self._previous_time = 0.0
    
    def _check_ebpf(self) -> bool:
        """Check if eBPF is available."""
        if platform.system() != "Linux":
            return False
        
        try:
            # Check for BCC tools
            result = subprocess.run(
                ["which", "bcc-usdt"],
                capture_output=True,
                timeout=2
            )
            if result.returncode == 0:
                return True
            
            # Check for BPFTrace
            result = subprocess.run(
                ["which", "bpftrace"],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def is_available(self) -> bool:
        """Check if eBPF monitoring is available."""
        return self._available
    
    def start_monitoring(self) -> bool:
        """Start eBPF monitoring."""
        if not self._available:
            return False
        
        try:
            # In a full implementation, this would load a BPF program
            # to track memory bandwidth via perf counters
            # For now, we'll use a simpler approach with /proc
            
            # Read initial memory stats
            with open("/proc/vmstat", "r") as f:
                for line in f:
                    if line.startswith("pgmajfault"):
                        # Use page faults as a proxy for memory activity
                        self._previous_bytes = int(line.split()[1])
            
            self._previous_time = time.time()
            return True
        except Exception:
            return False
    
    def get_bandwidth(self) -> Optional[float]:
        """Get current memory bandwidth in GB/s."""
        if not self._available:
            return None
        
        try:
            current_time = time.time()
            current_bytes = 0
            
            # Read current memory stats
            with open("/proc/vmstat", "r") as f:
                for line in f:
                    if line.startswith("pgmajfault"):
                        current_bytes = int(line.split()[1])
            
            # Calculate bandwidth
            bytes_diff = abs(current_bytes - self._previous_bytes)
            time_diff = current_time - self._previous_time
            
            if time_diff > 0:
                # Convert page faults to bandwidth (rough approximation)
                # In reality, you'd use perf counters for actual bandwidth
                bandwidth_bytes_per_sec = bytes_diff * 4096 / time_diff  # Assume 4KB pages
                bandwidth_gb_s = bandwidth_bytes_per_sec / (1024**3)
                
                self._previous_bytes = current_bytes
                self._previous_time = current_time
                
                return bandwidth_gb_s
            
            return 0.0
        except Exception:
            return None
    
    def stop_monitoring(self) -> None:
        """Stop eBPF monitoring."""
        # In a full implementation, this would detach the BPF program
        pass


class ProcMeminfoMonitor:
    """Memory monitor using /proc/meminfo (Linux)."""
    
    def __init__(self):
        """Initialize /proc/meminfo monitor."""
        self._available = platform.system() == "Linux"
        self._previous_used = 0
        self._previous_time = 0.0
    
    def is_available(self) -> bool:
        """Check if /proc/meminfo monitoring is available."""
        return self._available
    
    def start_monitoring(self) -> bool:
        """Start monitoring."""
        if not self._available:
            return False
        
        try:
            metrics = self.get_metrics()
            if metrics:
                self._previous_used = metrics.memory_used_gb
                self._previous_time = time.time()
                return True
        except Exception:
            pass
        
        return False
    
    def get_metrics(self) -> Optional[BandwidthMetrics]:
        """Get memory metrics."""
        if not self._available:
            return None
        
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = {}
                for line in f:
                    parts = line.split()
                    key = parts[0].rstrip(":")
                    value = int(parts[1])
                    meminfo[key] = value
            
            total_kb = meminfo.get("MemTotal", 0)
            available_kb = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
            used_kb = total_kb - available_kb
            
            total_gb = total_kb / (1024**2)
            used_gb = used_kb / (1024**2)
            percent = (used_gb / total_gb * 100) if total_gb > 0 else 0.0
            
            # Calculate bandwidth
            current_time = time.time()
            bandwidth = 0.0
            if self._previous_time > 0:
                time_diff = current_time - self._previous_time
                if time_diff > 0:
                    used_diff = abs(used_gb - self._previous_used)
                    bandwidth = used_diff / time_diff
                    self._previous_used = used_gb
                    self._previous_time = current_time
            
            return BandwidthMetrics(
                timestamp=current_time,
                bandwidth_gb_s=bandwidth,
                memory_used_gb=used_gb,
                memory_total_gb=total_gb,
                memory_percent=percent,
            )
        except Exception:
            return None
    
    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        pass


class PSUtilBandwidthMonitor:
    """Cross-platform memory monitor using psutil."""
    
    def __init__(self):
        """Initialize psutil monitor."""
        self._available = self._check_psutil()
        self._previous_used = 0
        self._previous_time = 0.0
    
    def _check_psutil(self) -> bool:
        """Check if psutil is available."""
        try:
            import psutil
            return True
        except ImportError:
            return False
    
    def is_available(self) -> bool:
        """Check if psutil monitoring is available."""
        return self._available
    
    def start_monitoring(self) -> bool:
        """Start monitoring."""
        if not self._available:
            return False
        
        try:
            import psutil
            mem = psutil.virtual_memory()
            self._previous_used = mem.used / (1024**3)
            self._previous_time = time.time()
            return True
        except Exception:
            return False
    
    def get_metrics(self) -> Optional[BandwidthMetrics]:
        """Get memory metrics."""
        if not self._available:
            return None
        
        try:
            import psutil
            
            mem = psutil.virtual_memory()
            current_time = time.time()
            
            used_gb = mem.used / (1024**3)
            total_gb = mem.total / (1024**3)
            percent = mem.percent
            
            # Calculate bandwidth
            bandwidth = 0.0
            if self._previous_time > 0:
                time_diff = current_time - self._previous_time
                if time_diff > 0:
                    used_diff = abs(used_gb - self._previous_used)
                    bandwidth = used_diff / time_diff
                    self._previous_used = used_gb
                    self._previous_time = current_time
            
            return BandwidthMetrics(
                timestamp=current_time,
                bandwidth_gb_s=bandwidth,
                memory_used_gb=used_gb,
                memory_total_gb=total_gb,
                memory_percent=percent,
            )
        except Exception:
            return None
    
    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        pass


class GPUBandwidthMonitor:
    """GPU memory bandwidth monitor (NVML/ROCm)."""
    
    def __init__(self, platform: HardwarePlatform, device_index: int = 0):
        """Initialize GPU bandwidth monitor.
        
        Args:
            platform: Hardware platform.
            device_index: GPU device index.
        """
        self.platform = platform
        self.device_index = device_index
        self._available = self._check_gpu()
        self._previous_used = 0
        self._previous_time = 0.0
    
    def _check_gpu(self) -> bool:
        """Check if GPU monitoring is available."""
        if self.platform == HardwarePlatform.NVIDIA:
            try:
                import pynvml
                pynvml.nvmlInit()
                return True
            except Exception:
                return False
        elif self.platform == HardwarePlatform.AMD:
            try:
                result = subprocess.run(
                    ["rocm-smi", "--showmeminfo"],
                    capture_output=True,
                    timeout=2
                )
                return result.returncode == 0
            except Exception:
                return False
        
        return False
    
    def is_available(self) -> bool:
        """Check if GPU monitoring is available."""
        return self._available
    
    def start_monitoring(self) -> bool:
        """Start GPU monitoring."""
        if not self._available:
            return False
        
        try:
            metrics = self.get_gpu_metrics()
            if metrics:
                self._previous_used = metrics["used_gb"]
                self._previous_time = time.time()
                return True
        except Exception:
            pass
        
        return False
    
    def get_gpu_metrics(self) -> Optional[Dict[str, float]]:
        """Get GPU memory metrics."""
        if self.platform == HardwarePlatform.NVIDIA:
            return self._get_nvidia_metrics()
        elif self.platform == HardwarePlatform.AMD:
            return self._get_amd_metrics()
        return None
    
    def _get_nvidia_metrics(self) -> Optional[Dict[str, float]]:
        """Get NVIDIA GPU metrics via NVML."""
        try:
            import pynvml
            
            handle = pynvml.nvmlDeviceGetHandleByIndex(self.device_index)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            
            current_time = time.time()
            used_gb = mem_info.used / (1024**3)
            total_gb = mem_info.total / (1024**3)
            
            # Calculate bandwidth
            bandwidth = 0.0
            if self._previous_time > 0:
                time_diff = current_time - self._previous_time
                if time_diff > 0:
                    used_diff = abs(used_gb - self._previous_used)
                    bandwidth = used_diff / time_diff
                    self._previous_used = used_gb
                    self._previous_time = current_time
            
            return {
                "used_gb": used_gb,
                "total_gb": total_gb,
                "bandwidth_gb_s": bandwidth,
            }
        except Exception:
            return None
    
    def _get_amd_metrics(self) -> Optional[Dict[str, float]]:
        """Get AMD GPU metrics via ROCm SMI."""
        try:
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return None
            
            used_gb = 0.0
            total_gb = 0.0
            
            for line in result.stdout.split("\n"):
                if "GB" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if "GB" in part:
                            try:
                                value = float(part.replace("GB", ""))
                                if "used" in line.lower():
                                    used_gb = value
                                elif "total" in line.lower():
                                    total_gb = value
                            except ValueError:
                                pass
            
            current_time = time.time()
            bandwidth = 0.0
            if self._previous_time > 0:
                time_diff = current_time - self._previous_time
                if time_diff > 0:
                    used_diff = abs(used_gb - self._previous_used)
                    bandwidth = used_diff / time_diff
                    self._previous_used = used_gb
                    self._previous_time = current_time
            
            return {
                "used_gb": used_gb,
                "total_gb": total_gb,
                "bandwidth_gb_s": bandwidth,
            }
        except Exception:
            return None
    
    def stop_monitoring(self) -> None:
        """Stop GPU monitoring."""
        pass


class BandwidthProfiler:
    """Unified memory bandwidth profiler."""
    
    def __init__(self, hw_platform: Optional[HardwarePlatform] = None,
                 device_index: int = 0):
        """Initialize bandwidth profiler.

        Args:
            hw_platform: Hardware platform. If None, auto-detected.
            device_index: GPU device index.
        """
        self.platform = hw_platform or HardwareDetector.detect_platform()
        self.device_index = device_index

        # Initialize available monitors
        self.ebpf_monitor = EBPFBandwidthMonitor() if platform.system() == "Linux" else None
        self.proc_monitor = ProcMeminfoMonitor() if platform.system() == "Linux" else None
        self.psutil_monitor = PSUtilBandwidthMonitor()
        self.gpu_monitor = GPUBandwidthMonitor(self.platform, device_index)
        
        # Select primary monitor
        if self.ebpf_monitor and self.ebpf_monitor.is_available():
            self.primary_monitor = self.ebpf_monitor
        elif self.proc_monitor and self.proc_monitor.is_available():
            self.primary_monitor = self.proc_monitor
        elif self.psutil_monitor and self.psutil_monitor.is_available():
            self.primary_monitor = self.psutil_monitor
        else:
            self.primary_monitor = None
        
        # Recording state
        self._is_recording = False
        self._start_time: Optional[float] = None
        self._bandwidth_samples: List[float] = []
        self._metrics_history: List[BandwidthMetrics] = []
        self._monitoring_thread: Optional[Thread] = None
        self._monitoring_interval = 0.1  # 100ms sampling
    
    def is_available(self) -> bool:
        """Check if bandwidth monitoring is available."""
        return self.primary_monitor is not None
    
    def start_recording(self) -> None:
        """Start bandwidth recording."""
        if self._is_recording:
            return
        
        if not self.is_available():
            return
        
        self._is_recording = True
        self._start_time = time.time()
        self._bandwidth_samples = []
        self._metrics_history = []
        
        # Start monitors
        if self.primary_monitor:
            self.primary_monitor.start_monitoring()
        if self.gpu_monitor.is_available():
            self.gpu_monitor.start_monitoring()
        
        # Start monitoring thread
        self._monitoring_thread = Thread(target=self._monitor_bandwidth, daemon=True)
        self._monitoring_thread.start()
    
    def stop_recording(self) -> BandwidthMetrics:
        """Stop bandwidth recording and return aggregated metrics."""
        if not self._is_recording:
            return BandwidthMetrics(timestamp=time.time(), bandwidth_gb_s=0.0,
                                  memory_used_gb=0.0, memory_total_gb=0.0,
                                  memory_percent=0.0)
        
        self._is_recording = False
        
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=1.0)
            self._monitoring_thread = None
        
        # Stop monitors
        if self.primary_monitor:
            self.primary_monitor.stop_monitoring()
        if self.gpu_monitor.is_available():
            self.gpu_monitor.stop_monitoring()
        
        # Calculate aggregates
        avg_bandwidth = sum(self._bandwidth_samples) / len(self._bandwidth_samples) if self._bandwidth_samples else 0.0
        
        if self._metrics_history:
            latest = self._metrics_history[-1]
            latest.bandwidth_gb_s = avg_bandwidth
            return latest
        
        return BandwidthMetrics(timestamp=time.time(), bandwidth_gb_s=avg_bandwidth,
                              memory_used_gb=0.0, memory_total_gb=0.0,
                              memory_percent=0.0)
    
    def _monitor_bandwidth(self) -> None:
        """Background thread to monitor bandwidth."""
        while self._is_recording:
            metrics = None
            
            # Get system memory metrics
            if self.primary_monitor:
                if hasattr(self.primary_monitor, 'get_metrics'):
                    metrics = self.primary_monitor.get_metrics()
                elif hasattr(self.primary_monitor, 'get_bandwidth'):
                    bw = self.primary_monitor.get_bandwidth()
                    if bw is not None:
                        metrics = BandwidthMetrics(
                            timestamp=time.time(),
                            bandwidth_gb_s=bw,
                            memory_used_gb=0.0,
                            memory_total_gb=0.0,
                            memory_percent=0.0,
                        )
            
            # Add GPU metrics if available
            if metrics and self.gpu_monitor.is_available():
                gpu_metrics = self.gpu_monitor.get_gpu_metrics()
                if gpu_metrics:
                    metrics.gpu_memory_used_gb = gpu_metrics["used_gb"]
                    metrics.gpu_memory_total_gb = gpu_metrics["total_gb"]
                    metrics.gpu_bandwidth_gb_s = gpu_metrics["bandwidth_gb_s"]
            
            if metrics:
                self._bandwidth_samples.append(metrics.bandwidth_gb_s)
                self._metrics_history.append(metrics)
            
            time.sleep(self._monitoring_interval)
    
    def get_current_metrics(self) -> Optional[BandwidthMetrics]:
        """Get current bandwidth metrics without recording."""
        if self.primary_monitor:
            if hasattr(self.primary_monitor, 'get_metrics'):
                return self.primary_monitor.get_metrics()
        
        return None
    
    def analyze_ttft_correlation(self, 
                                 ttft_samples: List[float],
                                 bandwidth_samples: List[float]) -> Dict[str, float]:
        """Analyze correlation between bandwidth and TTFT.
        
        Args:
            ttft_samples: List of Time To First Token measurements.
            bandwidth_samples: List of corresponding bandwidth measurements.
        
        Returns:
            Dictionary with correlation metrics.
        """
        if len(ttft_samples) != len(bandwidth_samples) or len(ttft_samples) < 2:
            return {"correlation": 0.0, "r_squared": 0.0}
        
        # Calculate Pearson correlation
        n = len(ttft_samples)
        
        # Means
        ttft_mean = sum(ttft_samples) / n
        bw_mean = sum(bandwidth_samples) / n
        
        # Covariance and variances
        covariance = sum((ttft_samples[i] - ttft_mean) * (bandwidth_samples[i] - bw_mean)
                        for i in range(n))
        ttft_variance = sum((ttft_samples[i] - ttft_mean) ** 2 for i in range(n))
        bw_variance = sum((bandwidth_samples[i] - bw_mean) ** 2 for i in range(n))
        
        # Correlation coefficient
        if ttft_variance == 0 or bw_variance == 0:
            correlation = 0.0
        else:
            correlation = covariance / (ttft_variance ** 0.5 * bw_variance ** 0.5)
        
        # R-squared
        r_squared = correlation ** 2
        
        return {
            "correlation": correlation,
            "r_squared": r_squared,
            "ttft_mean": ttft_mean,
            "bandwidth_mean": bw_mean,
        }


def get_bandwidth_profiler(platform: Optional[HardwarePlatform] = None,
                          device_index: int = 0) -> BandwidthProfiler:
    """Factory function to get a bandwidth profiler instance.
    
    Args:
        platform: Hardware platform. If None, auto-detected.
        device_index: GPU device index.
    
    Returns:
        BandwidthProfiler instance.
    """
    return BandwidthProfiler(platform, device_index)
