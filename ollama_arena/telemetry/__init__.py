"""Hardware and Energy Telemetry System for ollama-arena.

This module provides comprehensive hardware monitoring, energy efficiency tracking,
and performance profiling capabilities for local LLM evaluation.
"""
from __future__ import annotations

from .base import (
    TelemetryCollector,
    HardwareInfo,
    TelemetryRecord,
    TelemetryStorage,
    get_telemetry_collector,
)
from .energy import (
    EnergyMonitor,
    PowerMetrics,
    TokensPerWattCalculator,
    get_energy_monitor,
)
from .quantization import (
    QuantizationTester,
    QuantizationResult,
    ParetoFrontier,
    get_quantization_tester,
)
from .bandwidth import (
    BandwidthProfiler,
    BandwidthMetrics,
    get_bandwidth_profiler,
)
from .dashboard import (
    TelemetryDashboard,
    DashboardMetrics,
    get_telemetry_dashboard,
)

__all__ = [
    # Base telemetry
    "TelemetryCollector",
    "HardwareInfo",
    "TelemetryRecord",
    "TelemetryStorage",
    "get_telemetry_collector",
    # Energy monitoring
    "EnergyMonitor",
    "PowerMetrics",
    "TokensPerWattCalculator",
    "get_energy_monitor",
    # Quantization testing
    "QuantizationTester",
    "QuantizationResult",
    "ParetoFrontier",
    "get_quantization_tester",
    # Bandwidth profiling
    "BandwidthProfiler",
    "BandwidthMetrics",
    "get_bandwidth_profiler",
    # Dashboard
    "TelemetryDashboard",
    "DashboardMetrics",
    "get_telemetry_dashboard",
]
