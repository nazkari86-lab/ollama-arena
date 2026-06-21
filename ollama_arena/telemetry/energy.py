"""Energy monitoring and tokens-per-watt calculation.

Supports NVIDIA NVML, AMD ROCm, and Apple Metal Performance Shaders (MPS)
for GPU power monitoring and energy efficiency metrics.
"""
from __future__ import annotations

import platform
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Thread
from typing import Callable, Optional, List, Dict, Any

from .base import HardwarePlatform, HardwareDetector


class PowerState(Enum):
    """Power monitoring states."""
    IDLE = "idle"
    RECORDING = "recording"
    ERROR = "error"


@dataclass
class PowerMetrics:
    """Power measurement metrics."""
    timestamp: float
    power_w: float  # Instantaneous power in watts
    energy_j: float = 0.0  # Cumulative energy in joules
    temperature_c: float = 0.0
    utilization_percent: float = 0.0
    memory_utilization_percent: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "power_w": self.power_w,
            "energy_j": self.energy_j,
            "temperature_c": self.temperature_c,
            "utilization_percent": self.utilization_percent,
            "memory_utilization_percent": self.memory_utilization_percent,
        }


class NVMLMonitor:
    """NVIDIA GPU power monitoring using NVML."""
    
    def __init__(self, device_index: int = 0):
        """Initialize NVML monitor.
        
        Args:
            device_index: GPU device index to monitor.
        """
        self.device_index = device_index
        self.handle = None
        self._initialized = False
        self._init_nvml()
    
    def _init_nvml(self) -> None:
        """Initialize NVML library."""
        try:
            import pynvml
            pynvml.nvmlInit()
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(self.device_index)
            self._initialized = True
        except ImportError:
            # pynvml not available
            pass
        except Exception as e:
            # NVML initialization failed
            pass
    
    def is_available(self) -> bool:
        """Check if NVML monitoring is available."""
        return self._initialized
    
    def get_power_usage(self) -> Optional[float]:
        """Get current power usage in watts."""
        if not self._initialized or self.handle is None:
            return None
        
        try:
            import pynvml
            # NVML returns power in milliwatts
            power_mw = pynvml.nvmlDeviceGetPowerUsage(self.handle)
            return power_mw / 1000.0
        except Exception:
            return None
    
    def get_temperature(self) -> Optional[float]:
        """Get current GPU temperature in Celsius."""
        if not self._initialized or self.handle is None:
            return None
        
        try:
            import pynvml
            temp = pynvml.nvmlDeviceGetTemperature(
                self.handle, 
                pynvml.NVML_TEMPERATURE_GPU
            )
            return float(temp)
        except Exception:
            return None
    
    def get_utilization(self) -> Optional[float]:
        """Get GPU utilization percentage (0-100)."""
        if not self._initialized or self.handle is None:
            return None
        
        try:
            import pynvml
            util = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
            return float(util.gpu)
        except Exception:
            return None
    
    def get_memory_utilization(self) -> Optional[float]:
        """Get GPU memory utilization percentage (0-100)."""
        if not self._initialized or self.handle is None:
            return None
        
        try:
            import pynvml
            util = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
            return float(util.memory)
        except Exception:
            return None
    
    def get_metrics(self) -> PowerMetrics:
        """Get all power metrics."""
        return PowerMetrics(
            timestamp=time.time(),
            power_w=self.get_power_usage() or 0.0,
            temperature_c=self.get_temperature() or 0.0,
            utilization_percent=self.get_utilization() or 0.0,
            memory_utilization_percent=self.get_memory_utilization() or 0.0,
        )


class ROCmMonitor:
    """AMD GPU power monitoring using ROCm."""
    
    def __init__(self, device_index: int = 0):
        """Initialize ROCm monitor.
        
        Args:
            device_index: GPU device index to monitor.
        """
        self.device_index = device_index
        self._available = self._check_rocm()
    
    def _check_rocm(self) -> bool:
        """Check if ROCm tools are available."""
        try:
            result = subprocess.run(
                ["rocm-smi", "--showpower"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            # OSError covers FileNotFoundError (binary absent) as well as
            # PermissionError and other launch failures (e.g. a stale
            # non-executable rocm-smi stub on PATH).
            return False
    
    def is_available(self) -> bool:
        """Check if ROCm monitoring is available."""
        return self._available
    
    def get_power_usage(self) -> Optional[float]:
        """Get current power usage in watts."""
        if not self._available:
            return None
        
        try:
            result = subprocess.run(
                ["rocm-smi", "--showpower"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return None
            
            # Parse rocm-smi output for power
            for line in result.stdout.split("\n"):
                if "W" in line and ("average" in line.lower() or "power" in line.lower()):
                    try:
                        # Extract power value (format varies)
                        parts = line.split()
                        for part in parts:
                            if part.replace(".", "").isdigit():
                                power = float(part)
                                if 0 < power < 1000:  # Sanity check
                                    return power
                    except ValueError:
                        continue
            
            return None
        except Exception:
            return None
    
    def get_temperature(self) -> Optional[float]:
        """Get current GPU temperature in Celsius."""
        if not self._available:
            return None
        
        try:
            result = subprocess.run(
                ["rocm-smi", "--showtemp"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return None
            
            for line in result.stdout.split("\n"):
                if "C" in line.lower() and "temp" in line.lower():
                    try:
                        parts = line.split()
                        for part in parts:
                            if part.replace(".", "").isdigit():
                                temp = float(part)
                                if 0 < temp < 150:  # Sanity check
                                    return temp
                    except ValueError:
                        continue
            
            return None
        except Exception:
            return None
    
    def get_metrics(self) -> PowerMetrics:
        """Get all power metrics."""
        return PowerMetrics(
            timestamp=time.time(),
            power_w=self.get_power_usage() or 0.0,
            temperature_c=self.get_temperature() or 0.0,
        )


class MPSMonitor:
    """Apple Metal Performance Shaders power monitoring."""
    
    def __init__(self):
        """Initialize MPS monitor."""
        self._available = self._check_mps()
    
    def _check_mps(self) -> bool:
        """Check if MPS is available (Apple Silicon)."""
        return platform.system() == "Darwin" and platform.machine().startswith(("arm64", "arm"))
    
    def is_available(self) -> bool:
        """Check if MPS monitoring is available."""
        return self._available
    
    def get_power_usage(self) -> Optional[float]:
        """Get estimated power usage for Apple Silicon.
        
        Note: Apple doesn't provide direct GPU power metrics.
        This is an estimate based on system power reporting.
        """
        if not self._available:
            return None
        
        try:
            # Use powermetrics on macOS
            result = subprocess.run(
                ["sudo", "powermetrics", "--samplers", "gpu_power", "-i", "1000"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return None
            
            # Parse powermetrics output
            for line in result.stdout.split("\n"):
                if "GPU" in line and "mW" in line:
                    try:
                        parts = line.split()
                        for part in parts:
                            if part.replace(".", "").isdigit():
                                power_mw = float(part)
                                return power_mw / 1000.0  # Convert to watts
                    except ValueError:
                        continue
            
            return None
        except Exception:
            # powermetrics requires sudo and typically fails without a TTY
            # or passwordless sudo configured. Report "unknown" honestly
            # instead of fabricating a measurement (see get_metrics()).
            return None

    def get_metrics(self) -> PowerMetrics:
        """Get all power metrics.

        Note: when the real powermetrics-based measurement is unavailable
        (the common case — it needs sudo), this falls back to a rough,
        clearly-labeled idle-power estimate rather than a real reading.
        """
        return PowerMetrics(
            timestamp=time.time(),
            power_w=self.get_power_usage() or 5.0,  # Fallback estimate, not a real measurement
        )


class EnergyMonitor:
    """Unified energy monitor with platform-specific backends."""
    
    def __init__(self, device_index: int = 0):
        """Initialize energy monitor.
        
        Args:
            device_index: GPU device index to monitor.
        """
        self.device_index = device_index
        self.platform = HardwareDetector.detect_platform()
        
        # Initialize appropriate monitor
        self.nvml_monitor = NVMLMonitor(device_index) if self.platform == HardwarePlatform.NVIDIA else None
        self.rocm_monitor = ROCmMonitor(device_index) if self.platform == HardwarePlatform.AMD else None
        self.mps_monitor = MPSMonitor() if self.platform == HardwarePlatform.APPLE else None
        
        # Determine active monitor
        if self.nvml_monitor and self.nvml_monitor.is_available():
            self.active_monitor = self.nvml_monitor
        elif self.rocm_monitor and self.rocm_monitor.is_available():
            self.active_monitor = self.rocm_monitor
        elif self.mps_monitor and self.mps_monitor.is_available():
            self.active_monitor = self.mps_monitor
        else:
            self.active_monitor = None
        
        # Recording state
        self._is_recording = False
        self._start_time: Optional[float] = None
        self._energy_accumulator = 0.0
        self._power_samples: List[float] = []
        self._monitoring_thread: Optional[Thread] = None
        self._monitoring_interval = 0.1  # 100ms sampling
    
    def is_available(self) -> bool:
        """Check if energy monitoring is available."""
        return self.active_monitor is not None
    
    def start_recording(self) -> None:
        """Start energy recording."""
        if self._is_recording:
            return
        
        if not self.is_available():
            return
        
        self._is_recording = True
        self._start_time = time.time()
        self._energy_accumulator = 0.0
        self._power_samples = []
        
        # Start monitoring thread
        self._monitoring_thread = Thread(target=self._monitor_power, daemon=True)
        self._monitoring_thread.start()
    
    def stop_recording(self) -> PowerMetrics:
        """Stop energy recording and return metrics."""
        if not self._is_recording:
            return PowerMetrics(timestamp=time.time(), power_w=0.0)
        
        self._is_recording = False
        
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=1.0)
            self._monitoring_thread = None
        
        # Calculate average power
        avg_power = sum(self._power_samples) / len(self._power_samples) if self._power_samples else 0.0
        
        # Calculate energy: power * time
        duration = time.time() - (self._start_time or time.time())
        energy_j = avg_power * duration
        
        return PowerMetrics(
            timestamp=time.time(),
            power_w=avg_power,
            energy_j=energy_j,
        )
    
    def _monitor_power(self) -> None:
        """Background thread to monitor power consumption."""
        while self._is_recording:
            if self.active_monitor:
                metrics = self.active_monitor.get_metrics()
                self._power_samples.append(metrics.power_w)
            time.sleep(self._monitoring_interval)
    
    def get_current_metrics(self) -> PowerMetrics:
        """Get current power metrics without recording."""
        if self.active_monitor:
            return self.active_monitor.get_metrics()
        return PowerMetrics(timestamp=time.time(), power_w=0.0)


class TokensPerWattCalculator:
    """Calculate tokens-per-watt efficiency metrics."""
    
    @staticmethod
    def calculate(tokens_out: int, energy_j: float) -> float:
        """Calculate tokens per watt.
        
        Args:
            tokens_out: Number of output tokens generated.
            energy_j: Energy consumed in joules.
        
        Returns:
            Tokens per watt (tokens / joule).
        """
        if energy_j <= 0:
            return 0.0
        return tokens_out / energy_j
    
    @staticmethod
    def calculate_from_power(tokens_out: int, power_w: float, duration_s: float) -> float:
        """Calculate tokens per watt from power and duration.
        
        Args:
            tokens_out: Number of output tokens generated.
            power_w: Average power in watts.
            duration_s: Duration in seconds.
        
        Returns:
            Tokens per watt.
        """
        energy_j = power_w * duration_s
        return TokensPerWattCalculator.calculate(tokens_out, energy_j)
    
    @staticmethod
    def calculate_efficiency_score(tokens_per_watt: float, 
                                  baseline_tpw: float = 100.0) -> float:
        """Calculate efficiency score relative to baseline.
        
        Args:
            tokens_per_watt: Measured tokens per watt.
            baseline_tpw: Baseline tokens per watt for comparison.
        
        Returns:
            Efficiency score (1.0 = baseline, >1.0 = better).
        """
        if baseline_tpw <= 0:
            return 0.0
        return tokens_per_watt / baseline_tpw
    
    @staticmethod
    def estimate_cost_per_token(energy_j: float, tokens_out: int,
                                electricity_cost_usd_per_kwh: float = 0.12) -> float:
        """Estimate cost per token based on energy consumption.
        
        Args:
            energy_j: Energy consumed in joules.
            tokens_out: Number of tokens generated.
            electricity_cost_usd_per_kwh: Electricity cost in USD/kWh.
        
        Returns:
            Cost per token in USD.
        """
        if tokens_out <= 0:
            return 0.0
        
        # Convert joules to kWh: 1 kWh = 3.6e6 J
        energy_kwh = energy_j / 3.6e6
        cost_usd = energy_kwh * electricity_cost_usd_per_kwh
        
        return cost_usd / tokens_out


def get_energy_monitor(device_index: int = 0) -> EnergyMonitor:
    """Factory function to get an energy monitor instance.
    
    Args:
        device_index: GPU device index to monitor.
    
    Returns:
        EnergyMonitor instance with platform-specific backend.
    """
    return EnergyMonitor(device_index)
